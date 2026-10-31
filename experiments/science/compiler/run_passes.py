"""Real LLVM analysis/codegen overlap and speculative backend experiments."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'compiler/followthrough'))
sys.path.insert(0,str(HERE.parents[1]/'compiler/semantic_invalidation'))
from run_ir import Host
import context


def sha(body):return hashlib.sha256(body).hexdigest()
def file_pin(path):return sha(Path(path).read_bytes())
def cpu(pid):
    fields=Path(f'/proc/{pid}/stat').read_text().split(') ',1)[1].split()
    return (int(fields[11])+int(fields[12]))/os.sysconf('SC_CLK_TCK')
def save(path,data):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,indent=2)+'\n')


def run(a):
    for name in ('host','origin','work','output','lock'):setattr(a,name,getattr(a,name).resolve())
    a.work.mkdir(parents=True,exist_ok=False);origin=json.loads(a.origin.read_text());first=next(iter(origin['preparation'].values()))
    old=Path(next(v for v in first['command'] if v.endswith('.c'))).parent.parent
    project=a.work/'project';shutil.copytree(old,project)
    implementation=[HERE/'pass_host.cpp',HERE/'process_passes.inc',Path(__file__),HERE.parents[1]/'compiler/followthrough/run_ir.py',HERE.parents[1]/'compiler/semantic_invalidation/context.py']
    pins={p.name:file_pin(p) for p in implementation};binary_pin=file_pin(a.host)
    data={'schema_version':1,'status':'running','origin_sha256':file_pin(a.origin),'source_archive_sha256':origin.get('source_archive_sha256'),'implementation':pins,'host_sha256':binary_pin,'trials':a.trials,'preparation':{},'observations':[],
          'scope':'Current Clang22 pre-optimization IR; actual dominator/loop/postdominator analyses. Parallel children get private Linux COW snapshots; LLVM mutable context is not concurrently shared. Single-thread-at-fork checked at runtime. Speculative backend overlaps exact current-IR guard; private object/diagnostics discarded on hit. This is not arbitrary optimizer-pass parallelization. ParentCPU counters have clock-tick granularity; childCPU from wait4; Python/controllerCPU excluded. Input mutation, SDK validation and oracle hashes outside request clocks. Warm pages; per-request timing lock, other preparation/unrelated load possible.'}
    raw=a.output/'results.json';save(raw,data);host=Host(a.host,a.work)
    try:
        for name,item in origin['preparation'].items():
            command=[str(x).replace(str(old),str(project)) for x in item['command']]
            source=Path(next(x for x in command if x.endswith('.c')));body=source.read_bytes();work=a.work/name.replace('/','-');work.mkdir()
            output=work/'candidate.o';reference=work/'reference.o';fixed=context.snapshot(command,project,source,work)
            context.verify(fixed);key=sha(json.dumps(fixed,sort_keys=True).encode())
            variants={'unchanged':body,'unused_type':body+b'\ntypedef unsigned long GaiaSpecUnused;\n','semantic':body+b'\nstatic __attribute__((used)) unsigned gaia_spec_value=19;\n'}
            oracles={};facts={};prep_start=time.perf_counter_ns()
            for variant,value in variants.items():
                source.write_bytes(value);oracle=list(command);oracle[oracle.index('-o')+1]=str(reference)
                subprocess.run(oracle,cwd=project,capture_output=True,check=True)
                oracles[variant]=file_pin(reference)
                row=host.call(command,project,output,mode='native',key=key,pipeline='serial')
                assert row['ok'] and file_pin(output)==oracles[variant],(name,variant,row)
                facts[variant]=(row['dom_sha256'],row['postdom_sha256'],row['dom'],row['loops'],row['postdom'])
            source.write_bytes(body);seed=host.call(command,project,output,key=key,store=True)
            assert seed['ok'] and file_pin(output)==oracles['unchanged']
            data['preparation'][name]={'seconds':(time.perf_counter_ns()-prep_start)/1e9,'context':context.portable(fixed),'oracles':oracles,'analysis_facts':facts,'seed':seed}
            modes={
                'native_full':dict(mode='native',pipeline='off',speculate=False),
                'serial_guard':dict(mode='ir',pipeline='off',speculate=False),
                'speculative_guard':dict(mode='ir',pipeline='off',speculate=True),
                'analyses_serial':dict(mode='ir',pipeline='serial',speculate=False),
                'analyses_parallel':dict(mode='ir',pipeline='parallel',speculate=False),
                'analyses_and_speculation':dict(mode='ir',pipeline='parallel',speculate=True),
            }
            for block in range(a.trials):
                cases=[(mode,variant) for mode in modes for variant in variants];random.Random(619+block).shuffle(cases)
                for mode,variant in cases:
                    source.write_bytes(variants[variant])
                    with a.lock.open('a') as lock:
                        fcntl.flock(lock,fcntl.LOCK_EX);before=cpu(host.p.pid);begin=time.perf_counter_ns()
                        row=host.call(command,project,output,key=key,**modes[mode])
                        elapsed=time.perf_counter_ns()-begin;parent_cpu=cpu(host.p.pid)-before
                    assert row['ok'] and file_pin(output)==oracles[variant],(name,mode,variant,row)
                    if modes[mode]['pipeline']!='off':
                        actual=(row['dom_sha256'],row['postdom_sha256'],row['dom'],row['loops'],row['postdom'])
                        assert actual==facts[variant],(name,variant,mode,'analysis differs')
                    data['observations'].append({'source':name,'block':block,'mode':mode,'variant':variant,'operation_ns':elapsed,'parent_cpu_seconds':parent_cpu,'total_worker_cpu_estimate_seconds':parent_cpu+row['children_cpu_seconds'],'output_sha256':oracles[variant],'result':row})
                    save(raw,data);print(name,block,mode,variant,round(elapsed/1e6,3),flush=True)
            source.write_bytes(body);context.verify(fixed)
        assert pins=={p.name:file_pin(p) for p in implementation};assert binary_pin==file_pin(a.host)
        data['status']='complete';data['frozen_inputs_verified_after']=True;save(raw,data)
    except BaseException as error:
        data['status']='failed';data['error']={'type':type(error).__name__,'message':str(error)};save(raw,data);raise
    finally:host.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['host','origin','work','output','lock']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--trials',type=int,default=3);run(p.parse_args())
