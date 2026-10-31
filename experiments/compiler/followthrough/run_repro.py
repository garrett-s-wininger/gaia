"""Deterministic perturbations that expose missing compiler/request identities."""
import argparse
import fcntl
import os
from pathlib import Path
import subprocess
import time
from run_ir import save,sha

def run(a):
 a.output.mkdir(parents=True,exist_ok=False);rows=[];clang=str(a.clang)
 def compile(root,body,flags=(),changes=None):
  root.mkdir(parents=True,exist_ok=True);source=root/'unit.c';source.write_text(body);output=root/'unit.o';env=dict(os.environ);env.update(changes or {});command=[clang,'-O2',*flags,'-c',str(source),'-o',str(output)];start=time.perf_counter();p=subprocess.run(command,env=env,capture_output=True,text=True,timeout=60);elapsed=time.perf_counter()-start
  assert p.returncode==0,p.stderr
  return dict(command=command,seconds=elapsed,object_sha256=sha(output.read_bytes()),stderr=p.stderr,environment_changes=changes or {})
 def pair(name,left,right,expect_equal):
  equal=left['object_sha256']==right['object_sha256'];assert equal==expect_equal,(name,left,right);rows.append(dict(name=name,left=left,right=right,equal=equal,expected_equal=expect_equal,correct=True))
 x=a.output/'A';y=a.output/'B';body='const char *file(void){return __FILE__;}\nint f(void){return 1;}\n'
 pair('absolute-path-and-debug',compile(x,body,['-g']),compile(y,body,['-g']),False)
 def maps(root):return ['-g','-ffile-prefix-map='+str(root)+'=/src','-fdebug-compilation-dir=/src']
 pair('declared-path-mapping',compile(x,body,maps(x)),compile(y,body,maps(y)),True)
 include_a=a.output/'include-a';include_b=a.output/'include-b';include_a.mkdir();include_b.mkdir();(include_a/'choice.h').write_text('#define VALUE 1\n');(include_b/'choice.h').write_text('#define VALUE 2\n');body='#include <choice.h>\nint f(void){return VALUE;}\n'
 pair('CPATH-is-an-input',compile(x,body,changes={'CPATH':str(include_a)}),compile(x,body,changes={'CPATH':str(include_b)}),False)
 body='const char *date(void){return __DATE__ " " __TIME__;}\n'
 pair('SOURCE_DATE_EPOCH-is-an-input',compile(x,body,changes={'SOURCE_DATE_EPOCH':'1000000000'}),compile(x,body,changes={'SOURCE_DATE_EPOCH':'1100000000'}),False)
 body='#warning locale-probe\nint f(void){return 1;}\n'
 pair('locale-C-vs-C.UTF-8',compile(x,body,changes={'LC_ALL':'C'}),compile(x,body,changes={'LC_ALL':'C.UTF-8'}),True)
 # Directory enumeration cannot silently stand in for an ordered archive request.
 one=x/'one.o';two=x/'two.o';compile(x,'int one(void){return 1;}\n');one.write_bytes((x/'unit.o').read_bytes());compile(x,'int two(void){return 2;}\n');two.write_bytes((x/'unit.o').read_bytes())
 hashes=[]
 for i,order in enumerate(([one,two],[two,one],sorted([two,one]))):
  archive=x/('order'+str(i)+'.a');subprocess.run([str(a.ar),'rcs',str(archive),*map(str,order)],check=True,capture_output=True);hashes.append(sha(archive.read_bytes()))
 assert hashes[0]!=hashes[1] and hashes[0]==hashes[2];rows.append(dict(name='archive-input-order',hashes=hashes,correct=True))
 data=dict(status='complete',cases=rows,compiler_version=subprocess.run([clang,'--version'],capture_output=True,text=True,check=True).stdout,archiver_version=subprocess.run([str(a.ar),'--version'],capture_output=True,text=True,check=True).stdout,implementation_sha256=sha(Path(__file__).read_bytes()),scope='Fixed small probes establish request-identity requirements; not a survey of arbitrary production tool reproducibility.')
 save(a.output/'results.json',data);save(a.output/'validation.json',dict(passed=True,probes=len(rows),raw_sha256=sha((a.output/'results.json').read_bytes())))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('clang','ar','output','measurement-lock'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args()
 with a.measurement_lock.open('a') as lock:fcntl.flock(lock,fcntl.LOCK_EX);run(a)
