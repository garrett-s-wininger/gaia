"""Actual Clang VFS observations refreshed after every compile, including IR hits."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import random
import select
import subprocess
import time


def digest(body):return hashlib.sha256(body).hexdigest()


class Host:
    def __init__(self,executable,work):
        self.log=(work/'host.stderr').open('wb')
        self.process=subprocess.Popen([str(executable)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,text=True)
    def request(self,value):
        self.process.stdin.write(json.dumps(value)+'\n');self.process.stdin.flush()
        if not select.select([self.process.stdout],[],[],60)[0]:raise TimeoutError('host response')
        line=self.process.stdout.readline()
        if not line:raise RuntimeError('host exited '+str(self.process.poll()))
        return json.loads(line)
    def close(self):
        if self.process.poll() is None:self.process.stdin.close()
        try:self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:self.process.terminate();self.process.wait(timeout=10)
        self.process.stdout.close();self.log.close()
        if self.process.returncode:raise RuntimeError('host failed '+str(self.process.returncode))


def sources():
    optional='#if __has_include(<optional.h>)\n#include <optional.h>\n#else\n#define EXTRA 0\n#endif\n'
    return {'a.h':'#define VALUE 1\n','b.h':'#define VALUE 1\n','early/keep.h':'/* existing virtual directory */\n',
            'late/selected.h':'#define VALUE 2\n','unit0.c':'#include "a.h"\nint f0(void){return VALUE+FLAG;}\n',
            'unit1.c':'#include <selected.h>\n'+optional+'int f1(void){return VALUE+EXTRA+FLAG;}\n',
            'unit2.cc':'#include "a.h"\n'+optional+'template<int N> int helper(){return VALUE+EXTRA+FLAG+N;}\nextern "C" int f2(void){return helper<0>();}\n'}


def materialize(root,edits):
    for name,body in edits.items():
        path=root/name
        if body is None:path.unlink(missing_ok=True)
        else:path.parent.mkdir(parents=True,exist_ok=True);path.write_text(body)


def command(clang,root,output,index,flag,depfile):
    source=root/('unit2.cc' if index==2 else f'unit{index}.c')
    return [str(clang),'-O2','-Werror=date-time','-std=c++17' if index==2 else '-std=c11',
            '-I',str(root/'early'),'-I',str(root/'late'),'-DFLAG='+str(flag),'-MMD','-MF',str(depfile),'-MT',f'unit{index}.o','-c',str(source),'-o',str(output)]


def call(host,clang,root,output,index,flag,generation,mode):
    dep=output.with_suffix('.d');args=command(clang,root,output,index,flag,dep)
    return host.request(dict(args=args,cwd=str(root),output=str(output),mode=mode,context='fixed-toolchain-sdk-environment-v1',
                             analysis='off',store=True,logical=True,generation=generation))


def run_case(args,root,mode):
    files=sources();materialize(root,files);host=Host(args.host,root);flag=0;generation=0;rows=[]
    input_root={str(root/name):body for name,body in files.items()}
    begin=time.perf_counter_ns();admission=host.request(dict(edits=input_root,source_root=str(root),expected_generation=generation));assert admission['ok'];generation=admission['generation']
    prep=[]
    try:
        for index in range(3):
            output=root/f'unit{index}.o';row=call(host,args.clang,root,output,index,flag,generation,mode);assert row['ok'];prep.append(row)
        preparation_ns=time.perf_counter_ns()-begin
        edits=[('unchanged',{},None),('unrelated',{'unrelated/ignored.h':'ignored\n'},None),
               ('A-to-identical-B',{'unit0.c':files['unit0.c'].replace('"a.h"','"b.h"')},None),
               ('old-A-changed',{'a.h':'#define VALUE 4\n'},None),('current-B-changed',{'b.h':'#define VALUE 5\n'},None),
               ('earlier-shadow-appears',{'early/selected.h':'#define VALUE 7\n'},None),
               ('optional-appears',{'early/optional.h':'#define EXTRA 9\n'},None),
               ('optional-deleted',{'early/optional.h':None},None),('configuration',{},11),
               ('invalid-source',{'unit0.c':'int invalid( {\n'},None),
               ('recovery',{'unit0.c':files['unit0.c'].replace('"a.h"','"b.h"')},None)]
        for label,change,new_flag in edits:
            if new_flag is not None:flag=new_flag
            with args.lock.open('a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX);begin=time.perf_counter_ns();cpu=time.process_time_ns()
                ack=host.request(dict(edits={str(root/n):b for n,b in change.items()},source_root=str(root),expected_generation=generation));assert ack['ok'];generation=ack['generation']
                result=[call(host,args.clang,root,root/f'unit{i}.o',i,flag,generation,mode) for i in range(3)]
                elapsed=time.perf_counter_ns()-begin;controller_cpu=time.process_time_ns()-cpu
            materialize(root,change)
            identities={};deps={}
            for index,row in enumerate(result):
                output=root/f'unit{index}-oracle.o';dep=output.with_suffix('.d');oracle=subprocess.run(command(args.clang,root,output,index,flag,dep),capture_output=True)
                assert bool(row['ok'])==(oracle.returncode==0),(label,index,row,oracle.stderr)
                if row['ok']:
                    actual=(root/f'unit{index}.o').read_bytes();expected=output.read_bytes();assert actual==expected,(label,index)
                    actual_dep=(root/f'unit{index}.d').read_bytes();assert actual_dep==dep.read_bytes(),(label,index,'depfile')
                    identities[str(index)]=digest(actual);deps[str(index)]=digest(actual_dep)
            if mode=='observed':
                if label in ('unchanged','unrelated'):assert all(r['validation_hit'] for r in result)
                if label=='A-to-identical-B':
                    assert not result[0]['validation_hit'] and result[0]['hit']
                    observed=[o['path'] for o in result[0]['observations'] if o['kind']=='content']
                    assert str(root/'b.h') in observed and str(root/'a.h') not in observed
                    assert 'b.h' in (root/'unit0.d').read_text() and 'a.h' not in (root/'unit0.d').read_text()
                if label=='old-A-changed':assert result[0]['validation_hit'] and not result[2]['validation_hit']
                if label=='current-B-changed':assert not result[0]['validation_hit'] and result[2]['validation_hit']
                if label=='earlier-shadow-appears':assert not result[1]['validation_hit']
                if label in ('optional-appears','optional-deleted'):assert not result[1]['validation_hit'] and not result[2]['validation_hit']
                if label=='configuration':assert all(not r['validation_hit'] for r in result)
                if label=='invalid-source':assert not result[0]['ok']
                if label=='recovery':assert all(r['ok'] for r in result)
            rows.append(dict(scenario=label,wall_ns=elapsed,controller_cpu_ns=controller_cpu,generation=generation,responses=result,objects=identities,dependency_files=deps))
        stale=call(host,args.clang,root,root/'unit0.o',0,flag,generation-1,mode);assert not stale['ok']
        return dict(mode=mode,preparation_ns=preparation_ns,initial_admission=admission,seed_responses=prep,rows=rows,stale_request=stale)
    finally:host.close()


def main():
    p=argparse.ArgumentParser();p.add_argument('--host',type=Path,required=True);p.add_argument('--clang',type=Path,required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--lock',type=Path,required=True);p.add_argument('--trials',type=int,default=3);args=p.parse_args()
    args.work.mkdir(parents=True,exist_ok=False);args.output.mkdir(parents=True,exist_ok=True)
    source=Path(__file__);native=source.with_name('observed_host.cpp');pins={p.name:digest(p.read_bytes()) for p in (source,native)};tools={p.name:digest(p.read_bytes()) for p in (args.host,args.clang)}
    result=dict(schema='GAIA-CLANG-OBSERVATIONS-1',status='running',source_sha256=pins,tools=tools,cases=[],
        scope='Actual Clang threeTU C/C++ prototype, immutable regularUTF8 source namespace, sourceVFS presence/content/listing descriptors. SDK/tool/environment outside sourceRoot externallyfixed; no completehermetic capture. Clean-diagnostic-only observed skips, currentfrontendIRhits refreshdeps+observations, no arbitrarysideproducts/analysis cache. Unchanged outputrestore occursinsideclock; CLI object+depfile oracles outsideboth clocks.')
    try:
        for block in range(args.trials):
            order=['native','observed'];random.Random(191+block).shuffle(order)
            for mode in order:
                root=args.work/f'{block}-{mode}';root.mkdir();case=run_case(args,root,mode);case['block']=block;result['cases'].append(case)
                (args.output/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(block,mode,'complete',flush=True)
        assert pins=={p.name:digest(p.read_bytes()) for p in (source,native)};assert tools=={p.name:digest(p.read_bytes()) for p in (args.host,args.clang)};result['source_tools_verified_after']=True;result['status']='complete'
    except Exception as error:result['status']='failed';result['error']=dict(type=type(error).__name__,message=str(error));raise
    finally:(args.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
