"""Diagnose a created-header cache result against fresh Clang on a prepared fixture."""
import argparse,hashlib,json,os,shlex,subprocess
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main(a):
 root=a.project.resolve();a.output.mkdir(parents=True,exist_ok=False);work=a.output.resolve();env=dict(os.environ,CCACHE_DIR=str(a.cache.resolve()),CCACHE_COMPILERCHECK='content',CCACHE_BASEDIR='',LD_LIBRARY_PATH=str(a.ccache.resolve().parent.parent/'lib')+':'+os.environ.get('LD_LIBRARY_PATH',''))
 command=shlex.split(subprocess.check_output([str(a.ninja.resolve()),'-t','commands','build/version.o'],cwd=root,env=env,text=True).strip());rows=[]
 for mode in ['direct','preprocessor']:
  log=work/(mode+'.log');actual=dict(env,CCACHE_LOGFILE=str(log))
  if mode=='preprocessor':actual['CCACHE_NODIRECT']='true'
  r=subprocess.run(command,cwd=root,env=actual,capture_output=True,text=True);assert r.returncode==0,r.stderr
  rows.append({'mode':mode,'object_sha256':sha(root/'build/version.o'),'depfile_sha256':sha(root/'build/version.o.d'),'depfile':(root/'build/version.o.d').read_text(),'log':log.read_text()})
  (work/(mode+'.o')).write_bytes((root/'build/version.o').read_bytes())
 ref=command[1:];r=subprocess.run(ref,cwd=root,env=env,capture_output=True,text=True);assert r.returncode==0,r.stderr;oracle=sha(root/'build/version.o');assert rows[0]['object_sha256']!=oracle;assert rows[1]['object_sha256']==oracle
 result={'status':'complete','scope':'Prepared Ninja fixture, newly created optional header; direct cache and preprocessing cache compared with uncached CLI. Not a claim about every ccache configuration.','command':command,'oracle_object_sha256':oracle,'observations':rows,'direct_stale':True,'preprocessor_correct':True}
 (a.output/'results.json').write_text(json.dumps(result,indent=2)+'\n');print('Direct stale; preprocessor mode and stock CLI agree')
if __name__=='__main__':
 p=argparse.ArgumentParser()
 for n in ['project','cache','ccache','ninja','output']:p.add_argument('--'+n,type=Path,required=True)
 main(p.parse_args())
