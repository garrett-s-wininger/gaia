#!/usr/bin/env python3
"""Bounded diagnostic with named-thread CPU attribution; not a primary timing run."""
import argparse
import json
import os
import statistics
import subprocess
import time
from pathlib import Path
from run_variants import AFFINITY, RUN_ENV, write
from run_native import process_cpu


def threads(pid):
    result={}
    for task in Path('/proc/'+str(pid)+'/task').iterdir():
        try:
            name=(task/'comm').read_text().strip()
            fields=(task/'stat').read_text().rpartition(') ')[2].split()
            result[int(task.name)]=dict(name=name,cpu=(int(fields[11])+int(fields[12]))/os.sysconf('SC_CLK_TCK'))
        except (FileNotFoundError,ProcessLookupError):pass
    return result


def role(name):
    if name.startswith('C1 '):return 'jit_c1'
    if name.startswith('C2 '):return 'jit_c2'
    if 'JVMCI' in name:return 'jit_jvmci'
    if name.startswith(('GC Thread','G1 ','ZDriver','ZWorker','ZDirector','Shenandoah')):return 'gc_named_workers'
    return 'other'


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--data',type=Path,required=True);parser.add_argument('--count',type=int,default=32);args=parser.parse_args()
    if not 16<=args.count<=64:parser.error('16..64 requests required')
    w=args.data;p=json.loads((w/'prepared-instrumented/prepared.json').read_text());flags=json.loads((w/'flags-config.json').read_text());head=json.loads((w/'head-config.json').read_text());refs=json.loads((w/'endpoint-references.json').read_text())
    selected={name:flags[name] for name in ('g1','parallel')};selected.update({name:head[name] for name in ('ea-aot-code','native-o2-serial')})
    data=dict(count=args.count,observer='Sidecar /proc per-thread scans before/after each request; CPU ticks are coarse and dying-thread CPU may be absent. Independent diagnostic, not a repeat of primary latency measurements.',cpu_ticks_per_second=os.sysconf('SC_CLK_TCK'),cases={})
    for name,spec in selected.items():
        output=w/'convergence32'/name;output.mkdir(parents=True,exist_ok=True);command=[*spec['prefix'],p['source'],p['second_source'],p['jdk'],str(output),str(w/'platform-sdk')]
        proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=RUN_ENV,preexec_fn=lambda:os.sched_setaffinity(0,AFFINITY))
        if proc.stdout.readline()!='READY\n':raise RuntimeError(proc.stderr.read())
        rows=[]
        for index in range(args.count):
            process_before=process_cpu(proc.pid);before=threads(proc.pid);begin=time.perf_counter()
            proc.stdin.write(('first' if not index else 'warm')+'\n');proc.stdin.flush();line=proc.stdout.readline();end=time.perf_counter();after=threads(proc.pid);process_after=process_cpu(proc.pid)
            if not line:raise RuntimeError(proc.stderr.read())
            row=json.loads(line);reference=refs[spec['reference']]['0']
            if any(row.get(k)!=reference[k] for k in ('classes','bytes','sha256')):raise ValueError((name,row,reference))
            roles={key:0.0 for key in ('jit_c1','jit_c2','jit_jvmci','gc_named_workers','other')};details=[]
            for tid,item in after.items():
                delta=item['cpu']-before.get(tid,dict(cpu=0))['cpu'];category=role(item['name']);roles[category]+=delta
                details.append(dict(tid=tid,name=item['name'],role=category,cpu_seconds=delta))
            row.update(index=index+1,wall_seconds=end-begin,process_cpu_seconds=process_after-process_before,role_cpu_seconds=roles,thread_cpu_deltas=details,
                       unaccounted_process_cpu_seconds=process_after-process_before-sum(roles.values()))
            rows.append(row)
        proc.stdin.write('stop\n');proc.stdin.flush();_,stderr=proc.communicate(timeout=30)
        if proc.returncode:raise RuntimeError(stderr)
        last=rows[-8:];prior=rows[-16:-8]
        summary=dict(last8_compile_ms=statistics.median(r['compile_ns']/1e6 for r in last),prior8_compile_ms=statistics.median(r['compile_ns']/1e6 for r in prior),last8_compile_thread_cpu_ms=statistics.median(r['compile_thread_cpu_ns']/1e6 for r in last),last8_process_cpu_ms=statistics.median(r['process_cpu_seconds']*1000 for r in last),last8_jit_cpu_ms=statistics.median(sum(r['role_cpu_seconds'][k] for k in ('jit_c1','jit_c2','jit_jvmci'))*1000 for r in last),last8_named_gc_cpu_ms=statistics.median(r['role_cpu_seconds']['gc_named_workers']*1000 for r in last))
        data['cases'][name]=dict(command=command,exit_code=proc.returncode,requests=rows,summary=summary,stderr=stderr);write(w/'convergence32.json',data)
    print(json.dumps({k:v['summary'] for k,v in data['cases'].items()},indent=2))


if __name__=='__main__':main()
