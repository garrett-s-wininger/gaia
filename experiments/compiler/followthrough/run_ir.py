"""Matched single-frontend IR reuse, detached AST analysis and boundary probes."""
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
sys.path.insert(0,str(HERE.parent/'semantic_invalidation'))
from semantic_cache import Compiler
from ccache_control import Ccache
import context

def sha(body):return hashlib.sha256(body).hexdigest()
def save(path,data):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,indent=2)+'\n')

class Host:
    def __init__(self,binary,work):
        self.log=(work/'host-stderr').open('w+b')
        self.p=subprocess.Popen([str(binary)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,text=True)
    def request(self,request):
        at=self.log.tell();start=time.perf_counter()
        self.p.stdin.write(json.dumps(request)+'\n');self.p.stdin.flush()
        line=self.p.stdout.readline()
        if not line:raise RuntimeError('host exited: '+(self.log.seek(0) or self.log.read().decode(errors='replace')))
        result=json.loads(line);result['endpoint_seconds']=time.perf_counter()-start
        self.log.seek(at);result['stderr']=self.log.read().decode(errors='replace')
        return result
    def call(self,command,cwd,output,mode='ir',key='fixed',analysis='off',store=False,**options):
        args=list(command);args[args.index('-o')+1]=str(output)
        output.unlink(missing_ok=True)
        return self.request(dict(args=args,cwd=str(cwd),output=str(output),context=key,mode=mode,analysis=analysis,store=store,**options))
    def close(self):
        self.p.stdin.close();self.p.wait(timeout=30);self.p.stdout.close();self.log.close()
        if self.p.returncode:raise RuntimeError('host exit '+str(self.p.returncode))

def boundary_probes(host,work,clang):
    probes={
      'unused-type':('int f(void){return 1;}\n','int f(void){return 1;}\ntypedef long unused;\n',[]),
      'warning':('int f(void){return 1;}\n','int f(void){return 1;}\n#warning retained-warning\n',[]),
      'packing':('struct S{char a;int b;};int f(void){return sizeof(struct S);}\n','#pragma pack(1)\nstruct S{char a;int b;};int f(void){return sizeof(struct S);}\n',[]),
      'target-attribute':('int f(int x){return x+1;}\n','__attribute__((target("sse4.2"))) int f(int x){return x+1;}\n',[]),
      'inline-assembly':('int f(void){__asm__("nop");return 1;}\n','int f(void){__asm__("nop; nop");return 1;}\n',[]),
      'debug-lines':('int f(void){return 1;}\n','\n\nint f(void){return 1;}\n',['-g']),
      'syntax-error':('int f(void){return 1;}\n','int f(void){return nope;}\n',[]),
    }
    rows=[];source=work/'boundary.c';output=work/'boundary.o';reference=work/'reference.o'
    for name,(base,edit,extra) in probes.items():
        command=[clang,'-O2',*extra,'-c',str(source),'-o',str(output)];source.write_text(base)
        seed=host.call(command,work,output,key=name,store=True);assert seed['ok']
        source.write_text(edit);actual=host.call(command,work,output,key=name)
        args=command.copy();args[args.index('-o')+1]=str(reference);p=subprocess.run(args,cwd=work,capture_output=True,text=True)
        correct=(actual['ok']==(p.returncode==0))
        if actual['ok']:correct=correct and output.read_bytes()==reference.read_bytes()
        if name=='warning':correct=correct and 'retained-warning' in actual['stderr'] and actual['hit']
        if name in ('packing','target-attribute','inline-assembly','debug-lines'):correct=correct and not actual['hit']
        assert correct,(name,actual,p.stderr)
        rows.append(dict(name=name,result=actual,reference_stderr=p.stderr,correct=correct))
    return rows

def run(args):
    args.output.mkdir(parents=True,exist_ok=False);work=args.output/'work';work.mkdir()
    os.environ['LD_LIBRARY_PATH']=str(args.ccache.resolve().parent.parent/'lib')+':'+os.environ.get('LD_LIBRARY_PATH','')
    origin=json.loads(args.origin.read_text());preparation=origin['preparation'];first=next(iter(preparation.values()));old=Path(first['fixed_context']['project_root']);project=work/'project';shutil.copytree(old,project)
    implementation=[HERE/'ir_host.cpp',HERE/'run_ir.py',*[HERE.parent/'semantic_invalidation'/n for n in ('context.py','semantic_cache.py','ccache_control.py')]];hashes={str(p.relative_to(HERE.parent)):sha(p.read_bytes()) for p in implementation};frozen=work/'frozen';frozen.mkdir()
    for p in implementation:shutil.copyfile(p,frozen/p.name)
    host=Host(args.host,work);data=dict(status='running',trials=args.trials,cases=[],preparation={},scope='Private fixed-context Zstandard TUs; unchanged seeded candidate; all native calls parse once; cache output is object only.',source_archive_sha256=origin['source_archive_sha256'],implementation_sha256=hashes,host_sha256=sha(args.host.read_bytes()),compiler=first['command'][0],environment_sha256=sha(json.dumps(dict(os.environ),sort_keys=True).encode()))
    try:
      for name,item in preparation.items():
        command=[str(v).replace(str(old),str(project)) for v in item['command']];source=next(Path(v) for v in command if v.endswith('.c'));original=source.read_bytes();unit=work/name.replace('/','-');compiler=Compiler(command,project,unit)
        fixed=context.snapshot(command,project,source,unit);context.verify(fixed);identity=sha(json.dumps(fixed,sort_keys=True).encode());out=unit/'current.o'
        variants={'unchanged':original,'comment':original+b'\n/* shared pipeline comment */\n','unused-macro':original+b'\n#define GAIA_UNUSED 11\n','unused-type':original+b'\ntypedef unsigned long GaiaUnusedType;\n','semantic':original+b'\nstatic __attribute__((used)) const unsigned gaia_used=11;\n'}
        seed=host.call(command,project,out,key=identity,store=True);assert seed['ok'];baseline=out.read_bytes();compiler.full(unit/'oracle.o');assert baseline==(unit/'oracle.o').read_bytes(),name
        ccache=Ccache(args.ccache,compiler,baseline);references={};refstats={}
        for scenario,body in variants.items():source.write_bytes(body);refstats[scenario]=compiler.full(unit/'oracle.o');references[scenario]=sha((unit/'oracle.o').read_bytes())
        source.write_bytes(original)
        data['preparation'][name]=dict(seed=seed,context=context.portable(fixed),reference=refstats,ccache=ccache.preparation,command=command,baseline_object_sha256=sha(baseline))
        configurations=[(mode,scenario) for mode in ('native','ir','ccache') for scenario in variants];rng=random.Random(819)
        for block in range(args.trials):
          rng.shuffle(configurations)
          for mode,scenario in configurations:
            source.write_bytes(variants[scenario])
            if mode=='ccache':result=ccache.call(out);result['endpoint_seconds']=result['seconds']
            else:result=host.call(command,project,out,mode=mode,key=identity)
            result.update(source=name,scenario=scenario,mode=mode,block=block,object_sha256=sha(out.read_bytes()));result['correct']=result['object_sha256']==references[scenario];assert result['correct'],result
            data['cases'].append(result);print(name,block,mode,scenario,round(result['endpoint_seconds']*1000,2),flush=True);save(args.output/'results.json',data)
        source.write_bytes(original)
        # Same parsed AST feeds codegen and a detached declaration-name analysis.
        analysis=[]
        for block in range(args.trials):
          modes=['off','serial','parallel','independent'];rng.shuffle(modes)
          for mode in modes:
            start=time.perf_counter()
            if mode=='independent':
              first=host.call(command,project,unit/'analysis-unused.o',mode='analysis');row=host.call(command,project,out,mode='native');row['analysis_only']=first;row['analysis_count']=first['analysis_count'];row['endpoint_seconds']=time.perf_counter()-start
            else:row=host.call(command,project,out,mode='native',analysis=mode)
            row.update(mode=mode,block=block);assert sha(out.read_bytes())==sha(baseline);analysis.append(row)
        serial={r['analysis_count'] for r in analysis if r['mode']=='serial'};parallel={r['analysis_count'] for r in analysis if r['mode']=='parallel'};assert serial==parallel
        data['preparation'][name]['shared_analysis']=analysis;data['preparation'][name]['context_after']=context.verify(fixed)
      data['boundaries']=boundary_probes(host,work,data['compiler']);assert hashes=={str(p.relative_to(HERE.parent)):sha(p.read_bytes()) for p in implementation},'implementation changed during measurement';assert sha(args.host.read_bytes())==data['host_sha256'],'host changed during measurement';data['frozen_inputs_verified_after']=True;data['status']='complete';save(args.output/'results.json',data)
      save(args.output/'validation.json',dict(passed=True,objects_checked=len(data['cases']),boundary_probes=len(data['boundaries']),raw_sha256=sha((args.output/'results.json').read_bytes())))
    finally:host.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--host',type=Path,required=True);p.add_argument('--origin',type=Path,required=True);p.add_argument('--ccache',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--trials',type=int,default=3);p.add_argument('--measurement-lock',type=Path,required=True);a=p.parse_args()
    with a.measurement_lock.open('a') as lock:fcntl.flock(lock,fcntl.LOCK_EX);run(a)
