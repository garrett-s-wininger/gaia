"""Exact SHA-256 substitution in the real retained observation/index scan."""
import argparse,fcntl,json,os,random,shlex,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workspace'))
from protocol import Host,admit,request,scan,sha
HERE=Path(__file__).resolve().parent

class EnvironmentHost(Host):
 def __init__(self,path,work,env):
  work.mkdir(parents=True,exist_ok=True);self.log=(work/'stderr.txt').open('wb')
  try:self.process=subprocess.Popen([str(path)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,text=True,env=env)
  except BaseException:self.log.close();raise
  self.cpu_start=self.cpu()

def main(a):
 for name in ['llvm_host','crypto_host','project','ninja','work','output','lock']:setattr(a,name,getattr(a,name).resolve())
 a.work.mkdir(parents=True,exist_ok=False);a.output.mkdir(parents=True,exist_ok=True);root=a.project
 env=dict(os.environ,LD_LIBRARY_PATH=str(a.ninja.parent.parent/'lib')+':'+os.environ.get('LD_LIBRARY_PATH',''));env.pop('OPENSSL_ia32cap',None)
 text=subprocess.check_output([str(a.ninja),'-t','commands','ninja'],cwd=root,env=env,text=True)
 commands=[shlex.split(line) for line in text.splitlines() if ' -c ' in line];commands=[c[1:] if Path(c[0]).name=='ccache' else c for c in commands];assert len(commands)==33
 targets=[c[c.index('-o')+1] for c in commands];source={str(p.relative_to(root)):p.read_text() for p in root.rglob('*') if p.is_file() and not str(p.relative_to(root)).startswith('build/') and p.suffix in ['.h','.hpp','.hh','.tcc','.cc','.c','.inc']};source['build/browse_py.h']=(root/'build/browse_py.h').read_text();input_pins={n:sha(v.encode()) for n,v in source.items()}
 for c,t in zip(commands,targets):
  c[c.index('-o')+1]=str(a.work/(Path(t).name+'.unused'));c[c.index('-MF')+1]=str(a.work/(Path(t).name+'.d'))
 paths={a.llvm_host,a.crypto_host,*HERE.glob('*.py'),Path(__file__).resolve().parents[1]/'workspace/host.cpp',Path(__file__).resolve().parents[1]/'workspace/protocol.py'}
 for path in [a.llvm_host,a.crypto_host]:
  for word in subprocess.check_output(['ldd',str(path)],text=True).split():
   if word.startswith('/') and Path(word).is_file():paths.add(Path(word).resolve())
 pins={str(p):sha(p.read_bytes()) for p in paths};hosts={};generations={};warmups=[];rows=[];reference=None
 try:
  for mode,binary,override in [('llvm',a.llvm_host,None),('crypto_auto',a.crypto_host,None),('crypto_masked',a.crypto_host,'0:0:0:0:0')]:
   actual=dict(env)
   if override:actual['OPENSSL_ia32cap']=override
   start=time.perf_counter_ns();h=EnvironmentHost(binary,a.work/mode,actual);hosts[mode]=h;generations[mode]=admit(h,root,source,0)
   facts={}
   for c,t in zip(commands,targets):facts[t]=request(h,root,c,t,generations[mode],analysis=True)['facts']
   if reference is None:reference=facts
   else:assert facts==reference
   warmups.append({'mode':mode,'ns':time.perf_counter_ns()-start,'symbol_records':sum(v['symbols'] for v in facts.values())})
  randomizer=random.Random(9227)
  for block in range(7):
   order=[(m,c) for m in hosts for c in ['retained','admit_unchanged']];randomizer.shuffle(order)
   for mode,case in order:
    with a.lock.open('a') as lock:
     fcntl.flock(lock,fcntl.LOCK_EX)
     for repeat in range(10):
      start=time.perf_counter_ns()
      if case=='admit_unchanged':generations[mode]=admit(hosts[mode],root,{},generations[mode])
      response=scan(hosts[mode],targets,generations[mode]);elapsed=time.perf_counter_ns()-start
      assert not response['dirty'] and response['facts']==reference
      rows.append({'block':block,'mode':mode,'case':case,'repeat':repeat,'ns':elapsed,'host_scan_seconds':response['seconds'],'correct':True})
   print('hash block',block,flush=True)
  # Changing the source must replace, rather than bless, a retained identity.
  changed='src/version.cc';body=source[changed]+'\nextern "C" int gaia_hash_new_symbol(){return 93;}\n';new_facts=[]
  target=next(t for c,t in zip(commands,targets) if 'src/version.cc' in c);cmd=commands[targets.index(target)]
  for mode,h in hosts.items():
   generations[mode]=admit(h,root,{changed:body},generations[mode]);s=scan(h,targets,generations[mode]);assert target in s['dirty'];r=request(h,root,cmd,target,generations[mode],analysis=True);assert r['facts']['sha256']!=reference[target]['sha256'];new_facts.append(r['facts'])
  assert new_facts[0]==new_facts[1]==new_facts[2]
 finally:
  for h in hosts.values():h.close()
 assert pins=={p:sha(Path(p).read_bytes()) for p in pins};assert input_pins=={p:sha((root/p).read_bytes()) for p in input_pins}
 d={'status':'complete','scope':'Real 33-TU current observation and declaration-index scans. SHA-256 contract unchanged. LLVM portable hash versus OpenSSL dispatched and all-capability-masked paths. No full rebuild speedup extrapolation.','cpu_mask':'OPENSSL_ia32cap=0:0:0:0:0','openssl_version':subprocess.check_output(['openssl','version'],text=True).strip(),'implementation_and_tools':pins,'input_pins':input_pins,'warmups':warmups,'observations':rows,'changed_generation_checks':3,'frozen_inputs_verified_after':True}
 (a.output/'results.json').write_text(json.dumps(d,indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['llvm-host','crypto-host','project','ninja','work','output','lock']:p.add_argument('--'+name,type=Path,required=True)
 main(p.parse_args())
