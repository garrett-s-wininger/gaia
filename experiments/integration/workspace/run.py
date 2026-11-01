"""Actual Ninja build + project symbol queries sharing dynamic observations."""
import argparse,concurrent.futures,fcntl,hashlib,json,os,random,resource,shlex,shutil,subprocess,tarfile,time
from pathlib import Path
from protocol import Host,admit,request,scan,sha
HERE=Path(__file__).resolve().parent

def save(path,d):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(d,indent=2)+'\n')
def materialize(root,edits):
 for p,v in edits.items():
  p=root/p
  if v is None:p.unlink(missing_ok=True)
  else:p.parent.mkdir(parents=True,exist_ok=True);p.write_text(v)
def usage():
 a=resource.getrusage(resource.RUSAGE_SELF);b=resource.getrusage(resource.RUSAGE_CHILDREN)
 return a.ru_utime+a.ru_stime+b.ru_utime+b.ru_stime

def memory(hosts):
 result=[]
 for host in hosts:
  values={}
  for line in Path(f'/proc/{host.process.pid}/smaps_rollup').read_text().splitlines():
   key,_,v=line.partition(':')
   if key in ['Rss','Pss','Private_Dirty']:values[key+'_kib']=int(v.split()[0])
  result.append(values)
 return result

def main(a):
 for name in ['host','archive','clang','ninja','ccache','work','output','lock']:setattr(a,name,getattr(a,name).resolve())
 a.work.mkdir(parents=True,exist_ok=False);root=a.work/'project';root.mkdir();start=time.perf_counter_ns()
 with tarfile.open(a.archive) as archive:archive.extractall(root,filter='data')
 roots=list(root.iterdir());assert len(roots)==1;root=roots[0]
 env=dict(os.environ,CXX=str(a.clang),CXXFLAGS='-Werror=date-time -Igaia/early -Igaia/late -DGAIA_CONFIG=0',CCACHE_DIR=str(a.work/'ccache'),CCACHE_COMPILERCHECK='content',CCACHE_BASEDIR='',LD_LIBRARY_PATH=str(a.ccache.parent.parent/'lib')+':'+os.environ.get('LD_LIBRARY_PATH',''))
 def checked(command,shell=False,extra_env=None):
  r=subprocess.run(command,cwd=root,env=dict(env,**(extra_env or {})),shell=shell,capture_output=True,text=True,timeout=240)
  if r.returncode:raise RuntimeError(str(command)+'\n'+r.stdout+r.stderr)
  return r
 checked(['python3','configure.py']);commands=checked([str(a.ninja),'-t','commands','ninja']).stdout.splitlines();compile_commands=[shlex.split(c) for c in commands if ' -c ' in c];assert len(compile_commands)==33
 generated=[c for c in commands if 'inline.sh' in c];final=[c for c in commands if ' -c ' not in c and c not in generated]
 (root/'build').mkdir(exist_ok=True)
 for command in generated:checked(command,True)
 initial=(root/'src/version.cc').read_text();probe='''
#include "gaia/active.h"
#if __has_include(<gaia_optional.h>)
#include <gaia_optional.h>
#else
static inline int gaia_optional_value(){return 0;}
#endif
#include <gaia_choice.h>
extern "C" int gaia_workspace_probe(){return gaia_input_value()+gaia_optional_value()+gaia_choice_value()+GAIA_CONFIG;}
'''
 base={'src/version.cc':initial+probe,'gaia/active.h':'#include "a.h"\n','gaia/a.h':'static inline int gaia_input_value(){return 1;}\n','gaia/b.h':'static inline int gaia_input_value(){return 1;}\n','gaia/early/keep.h':'// existing include directory\n','gaia/late/gaia_choice.h':'static inline int gaia_choice_value(){return 2;}\n'}
 materialize(root,base);original_header=(root/'src/version.h').read_text();base['src/version.h']=original_header
 scenarios=[('noop',{},False),('source',{'src/version.cc':base['src/version.cc']+'\nextern "C" int gaia_revision(){return 1;}\n'},False),('rewire',{'gaia/active.h':'#include "b.h"\n'},False),('old_header',{'gaia/a.h':'static inline int gaia_input_value(){return 9;}\n'},False),('new_header',{'gaia/b.h':'static inline int gaia_input_value(){return 7;}\n'},False),('optional_appear',{'gaia/early/gaia_optional.h':'static inline int gaia_optional_value(){return 5;}\n'},False),('optional_remove',{'gaia/early/gaia_optional.h':None},False),('shadow',{'gaia/early/gaia_choice.h':'static inline int gaia_choice_value(){return 9;}\n'},False),('unrelated',{'gaia/unrelated.h':'int unrelated;\n'},False),('header',{'src/version.h':original_header+'\nstatic __attribute__((used)) int gaia_header_value=23;\n'},False),('configuration',{},True),('burst',{'src/version.cc':base['src/version.cc']+'\nextern "C" int gaia_revision(){return 3;}\n'},True)]
 all_paths=set(base)|{p for _,edits,_ in scenarios for p in edits};targets=[c[c.index('-o')+1] for c in compile_commands];by_target=dict(zip(targets,compile_commands));outputs=[root/p for p in targets]
 ninja_body=(root/'build.ninja').read_text();ninja_body=ninja_body.replace('cxx = '+str(a.clang),'cxx = '+str(a.ccache)+' '+str(a.clang))
 def configure(config):
  (root/'build.ninja').write_text(ninja_body.replace('-DGAIA_CONFIG=0','-DGAIA_CONFIG=1') if config else ninja_body)
 def command(target,config):return ['-DGAIA_CONFIG=1' if config and p=='-DGAIA_CONFIG=0' else p for p in by_target[target]]
 def identity():
  paths=outputs+[root/'ninja']+[root/c[c.index('-MF')+1] for c in compile_commands]
  return {str(p.relative_to(root)):sha(p.read_bytes()) for p in paths}
 def link():
  for c in final:checked(c,True)
  assert checked([str(root/'ninja'),'--version']).stdout.strip().startswith('1.13.2')
 def reset():
  materialize(root,{p:base.get(p) for p in all_paths});configure(False)
 def bodies():
  result={str(p.relative_to(root)):p.read_text() for p in root.rglob('*') if p.is_file() and not str(p.relative_to(root)).startswith(('build/','.git/')) and p.suffix in ['.h','.hpp','.hh','.tcc','.cc','.c','.inc','.py','.sh']}
  for c in compile_commands:
   text=(root/c[c.index('-MF')+1]).read_text().replace('\\\n',' ')
   for name in text.split(':',1)[1].split():
    path=(root/name).resolve()
    if path.is_relative_to(root):result[str(path.relative_to(root))]=path.read_text()
  result['build/browse_py.h']=(root/'build/browse_py.h').read_text();return result

 def build_trace(host,generation,config,analysis=False):
  context='configuration-'+str(int(config));s=scan(host,targets,generation,context);facts=dict(s['facts']);rows=[]
  for target in s['dirty']:
   row=request(host,root,command(target,config),target,generation,context,analysis);facts[target]=row['facts'];rows.append({'target':target,**row})
  assert set(facts)==set(targets)
  return {'facts':facts,'rows':rows,'dirty':s['dirty'],'scan_seconds':s['seconds']}
 reset();checked([str(a.ninja),'-j4','-d','keepdepfile','ninja']);baseline_identity=identity();seed=a.work/'seed-cache';shutil.copytree(a.work/'ccache',seed)
 fixed=set()
 for c in compile_commands:
  args=[];i=0
  while i<len(c):
   if c[i] in ['-MF','-MT','-o']:i+=2;continue
   if c[i] in ['-MMD','-c']:i+=1;continue
   args.append(c[i]);i+=1
  text=checked(args+['-M']).stdout.replace('\\\n',' ')
  for name in text.split(':',1)[1].split():
   path=(root/name).resolve()
   if not path.is_relative_to(root):fixed.add(path)
 for c in compile_commands:
  text=(root/c[c.index('-MF')+1]).read_text().replace('\\\n',' ')
  for p in text.split(':',1)[1].split():
   p=(root/p).resolve()
   if not p.is_relative_to(root):fixed.add(p)
 for p in [a.host,a.clang,a.ninja,a.ccache]:
  fixed.add(p)
  for word in checked(['ldd',str(p)]).stdout.split():
   if word.startswith('/') and Path(word).is_file():fixed.add(Path(word).resolve())
 pins={str(p):sha(p.read_bytes()) for p in fixed};sources={p.name:sha(p.read_bytes()) for p in HERE.glob('*') if p.suffix in ['.py','.cpp']};source_pin=sha(a.archive.read_bytes())
 data={'status':'running','project':'Ninja 1.13.2 + labelled probes','compile_units':33,'archive_sha256':source_pin,'implementation':sources,'fixed_sdk_and_tools':pins,'environment_sha256':sha(json.dumps(env,sort_keys=True).encode()),'preparation_ns':time.perf_counter_ns()-start,'observations':[],'oracles':{},'warmups':[]}
 # Fail early if the admitted production namespace or query contract is incomplete.
 preflight=Host(a.host,a.work/'preflight')
 try:
  g=admit(preflight,root,bodies(),0);first=targets[0];b=request(preflight,root,command(first,False),first,g);e=request(preflight,root,command(first,False),first,g,analysis=True)
  assert b['facts']==e['facts'];assert sha((root/first).read_bytes())==baseline_identity[first]
  data['preflight']={'passed':True,'target':first,'symbols':b['facts']['symbols']}
 finally:preflight.close()
 # Full physical CLI builds and uncached syntax analyses are outside primary clocks.
 oracle=Host(a.host,a.work/'oracle-host');g=admit(oracle,root,bodies(),0)
 try:
  for name,edits,config in scenarios:
   materialize(root,edits);start=time.perf_counter_ns()
   with concurrent.futures.ThreadPoolExecutor(4) as pool:list(pool.map(lambda target:checked(command(target,config)),targets))
   link();facts={}
   for target in targets:
    args=command(target,config);args[args.index('-o')+1]=str(root/target);row=oracle.request(dict(args=args,cwd=str(root),output=str(root/target),generation=g,context='oracle',mode='analysis',logical=False,analysis='off',target=target));assert row['ok'],row;facts[target]=row['facts']
   data['oracles'][name]={'identity':identity(),'facts':facts,'preparation_ns':time.perf_counter_ns()-start};save(a.output/'results.json',data);print('oracle',name,flush=True)
 finally:oracle.close()
 modes=['shared','independent','ninja-ccache'];rng=random.Random(3271)
 for block in range(a.trials):
  order=list(modes);rng.shuffle(order)
  for mode in order:
   reset();checked([str(a.ninja),'-j4','-d','keepdepfile','ninja']);shutil.rmtree(a.work/'ccache');shutil.copytree(seed,a.work/'ccache')
   build_host=Host(a.host,a.work/f'{block}-{mode}-build') if mode!='ninja-ccache' else None
   editor=Host(a.host,a.work/f'{block}-{mode}-editor') if mode!='shared' else build_host
   hosts=[h for h in [build_host,editor] if h is not None];hosts=list(dict.fromkeys(hosts));gens={};start=time.perf_counter_ns()
   try:
    for h in hosts:gens[h]=admit(h,root,bodies(),0)
    if mode!='ninja-ccache':
     b=build_trace(build_host,gens[build_host],False);warm_build_rows=b['rows']
    if mode!='shared':e=build_trace(editor,gens[editor],False,True)
    assert identity()==baseline_identity
    data['warmups'].append({'block':block,'mode':mode,'ns':time.perf_counter_ns()-start,'source_bytes':sum(len(v.encode()) for v in bodies().values()),'worker_memory':memory(hosts)})
    for name,edits,config in scenarios:
     with a.lock.open('a') as lock:
      fcntl.flock(lock,fcntl.LOCK_EX);cpu=usage()+sum(h.cpu() for h in hosts);start=time.perf_counter_ns();materialize(root,edits);published={};stale_rejected=None
      for h in hosts:
       if name=='burst':
        old=gens[h];gens[h]=admit(h,root,{'src/version.cc':base['src/version.cc']+'\nextern "C" int gaia_revision(){return 2;}\n'},gens[h]);gens[h]=admit(h,root,edits,gens[h]);stale_rejected=not h.request(dict(scan=targets,generation=old,context='configuration-1'))['ok'];assert stale_rejected
       else:gens[h]=admit(h,root,edits,gens[h])
      def build():
       if mode=='ninja-ccache':
        configure(config)
        if name in ['optional_appear','optional_remove','shadow']:(root/'build/version.o').unlink(missing_ok=True)
        negative=name in ['optional_appear','optional_remove','shadow'];result=checked([str(a.ninja),'-j1','-d','keepdepfile','ninja'],extra_env={'CCACHE_NODIRECT':'true'} if negative else None);r={'rows':[],'dirty':None,'ninja_stdout':result.stdout,'preprocessor_cache_mode':negative}
       else:
        r=build_trace(build_host,gens[build_host],config)
        if r['dirty']:link()
       r['ready_ns']=time.perf_counter_ns()-start;return r
      def analyze():
       r=build_trace(editor,gens[editor],config,True);r['ready_ns']=time.perf_counter_ns()-start;return r
      if mode=='shared':
       b=build();e={'facts':b['facts'],'ready_ns':b['ready_ns'],'dirty':b['dirty'],'rows':[]}
      else:
       with concurrent.futures.ThreadPoolExecutor(2) as pool:
        bf=pool.submit(build);ef=pool.submit(analyze);b=bf.result();e=ef.result()
      elapsed=time.perf_counter_ns()-start;cpu=usage()+sum(h.cpu() for h in hosts)-cpu
     assert identity()==data['oracles'][name]['identity'],(mode,name,'objects/depfiles/binary')
     assert e['facts']==data['oracles'][name]['facts'],(mode,name,'symbol query')
     row={'block':block,'mode':mode,'scenario':name,'ns':elapsed,'build_ready_ns':b['ready_ns'],'editor_ready_ns':e['ready_ns'],'cpu_seconds_estimate':cpu,'build_dirty':b['dirty'],'editor_dirty':e['dirty'],'build_rows':b['rows'],'editor_rows':e['rows'],'build_scan_seconds':b.get('scan_seconds'),'editor_scan_seconds':e.get('scan_seconds'),'correct':True,'stale_rejected':stale_rejected,'preprocessor_cache_mode':b.get('preprocessor_cache_mode',False),'worker_memory':memory(hosts)};data['observations'].append(row);save(a.output/'results.json',data);print(block,mode,name,round(elapsed/1e6,2),flush=True)
     if mode=='shared' and block==0 and name=='noop':
      # Captured current file/query dependencies for the separate SIMD evaluator.
      relation={}
      for item in b['rows']:
       for observation in item['observations']:relation.setdefault(observation['path'],set()).add(item['target'])
      # The noop scan has no compiles; capture records from the actual warmup.
      if not relation:
       for item in warm_build_rows:
        for observation in item['observations']:relation.setdefault(observation['path'],set()).add(item['target'])
      save(a.work/'relation.json',{'targets':targets,'relation':{k:sorted(v) for k,v in relation.items()}})
   finally:
    for h in hosts:h.close()
 assert pins=={p:sha(Path(p).read_bytes()) for p in pins};assert sources=={p.name:sha(p.read_bytes()) for p in HERE.glob('*') if p.suffix in ['.py','.cpp']};data['status']='complete';data['frozen_inputs_verified_after']=True;save(a.output/'results.json',data)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ['host','archive','clang','ninja','ccache','work','output','lock']:p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--trials',type=int,default=3);main(p.parse_args())
