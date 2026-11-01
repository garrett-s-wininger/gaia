"""Replay controlled edits on actual upstream target graphs, with frozen reuse."""
import argparse,concurrent.futures,hashlib,json,os,shlex,statistics,subprocess,sys,time
from pathlib import Path
from prepare import WORK,TOOLS,PROJECTS,REPO
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'refinements'))
from refined_protocol import Host,require

NINJA=TOOLS/'bin/ninja';CCACHE=TOOLS/'bin/ccache';ROOT=WORK
ENV=dict(os.environ,LD_LIBRARY_PATH=str(TOOLS/'lib')+':'+os.environ.get('LD_LIBRARY_PATH',''),CCACHE_BASEDIR='',CCACHE_COMPILERCHECK='content')
SERIAL=REPO/'experiments/_work/refinements/host-final';QUEUE=WORK/'queue'
def digest(body):return hashlib.sha256(body).hexdigest()
def shell(command,cwd):
 p=subprocess.run(command,cwd=cwd,env=ENV,shell=isinstance(command,str),stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 if p.returncode:raise RuntimeError(p.stdout.decode(errors='replace')[-3000:])
 return p.stdout.decode()
def stamp():return time.perf_counter()
def install_launcher(original):
 lines=[];count=0
 for line in original.splitlines(keepends=True):
  if 'command = ' in line and '-c $in' in line:
   for compiler in ['/usr/lib/llvm22/bin/clang++','/usr/lib/llvm22/bin/clang']:
    if compiler+' ' in line:line=line.replace(compiler+' ',str(CCACHE)+' '+compiler+' ',1);count+=1;break
  lines.append(line)
 if not count:raise ValueError('no compiler rules received a ccache launcher')
 return ''.join(lines)
def verify_launcher(directory,target):
 commands=shell([NINJA,'-t','commands',target],directory).splitlines();compiles=[shlex.split(c) for c in commands if '-c ' in c and '/usr/lib/llvm22/bin/clang' in c]
 assert compiles and all(c[0]==str(CCACHE) for c in compiles),'ccache missing from rendered compilation commands'
def cache_stats(directory):
 text=shell([CCACHE,'--print-stats'],directory);return {k:int(v) for k,v in (line.split() for line in text.splitlines())}
def object_hashes(commands):return {t:digest(Path(c[c.index('-o')+1]).read_bytes()) for t,c in commands.items()}
def write_bodies(bodies):
 for p,b in bodies.items():
  p=Path(p)
  if not p.exists() or p.read_text()!=b:p.parent.mkdir(parents=True,exist_ok=True);p.write_text(b)
def admit_chunks(h,bodies,g=0):
 if not bodies:return require(h.request(dict(edits={},source_root=str(ROOT),expected_generation=g)))['generation']
 batch={};size=0
 for p,b in bodies.items():
  n=len(json.dumps({p:b}).encode())
  if n>4*1024*1024-1024:raise ValueError('single source exceeds frozen request limit: '+p)
  if batch and size+n>1048576:g=require(h.request(dict(edits=batch,source_root=str(ROOT),expected_generation=g)))['generation'];batch={};size=0
  batch[p]=b;size+=n
 if batch:g=require(h.request(dict(edits=batch,source_root=str(ROOT),expected_generation=g)))['generation']
 return g
def job(h,c,t,g,analysis=False,defer=False,physical=False,on_facts=None):
 return h.request(dict(args=c,cwd=str(job.cwd),output=c[c.index('-o')+1],target=t,generation=g,context='generalization',family='fixed-toolchain-generalization-v1',mode='analysis' if physical and analysis else 'native' if physical else 'observed',analysis='off',analysis_only=analysis,logical=not physical,store=True,emit_facts=True,defer_backend=defer),on_facts=on_facts)
def scan(h,commands,g,analysis=False):
 return require(h.request(dict(scan=list(commands),commands=commands,cwd=str(job.cwd),context='generalization',family='fixed-toolchain-generalization-v1',generation=g,analysis_only=analysis)))
def index_commands(commands):
 result={}
 for t,c in commands.items():
  c=list(c);c[c.index('-o')+1]+='.index';c[c.index('-MF')+1]+='.index';result[t]=c
 return result
def build(h,commands,g,defer=False,analysis=False,links=()):
 start=stamp();s=scan(h,commands,g,analysis);facts=dict(s['facts']);rows=[];ready=stamp() if len(facts)==len(commands) else None
 for t in s['dirty']:
  def receive(info):
   nonlocal ready
   facts[t]=info
   if len(facts)==len(commands) and ready is None:ready=stamp()
  r=job(h,commands[t],t,g,analysis,defer,on_facts=receive)
  if not r.get('ok') and defer and 'option outside admitted subset' in r.get('error',''):
   require(h.request({'drain':True}));r=job(h,commands[t],t,g,analysis,False,on_facts=receive);r['queue_fallback']='unsupported object-only flag'
  require(r);facts[t]=r['facts'];rows.append(dict(target=t,**{k:v for k,v in r.items() if k not in ['observations','facts']}))
  if len(facts)==len(commands) and ready is None:ready=stamp()
 drain=require(h.request({'drain':True})) if defer else None
 if not analysis and (s['dirty'] or s.get('restored')):
  for line in links:shell(line,job.cwd)
 return dict(seconds=stamp()-start,facts_seconds=ready-start,facts=facts,dirty=s['dirty'],restored=s.get('restored',[]),projected=s.get('projected',[]),rows=rows,drain=drain)

def graph(name):
 builddir=WORK/'build'/name;setup=json.loads((builddir/'setup.json').read_text());source=Path(setup['source']);target=setup['target'];job.cwd=builddir
 lines=shell([NINJA,'-t','commands',target],builddir).splitlines();commands={};links=[]
 for line in lines:
  args=shlex.split(line)
  if '-c' in args and '-o' in args and args[0].startswith('/usr/lib/llvm22/bin/clang'):
   for flag in ['-o','-MF']:
    if flag in args:args[args.index(flag)+1]=str((builddir/args[args.index(flag)+1]).resolve())
   t=str(Path(args[args.index('-o')+1]).relative_to(builddir));commands[t]=args
  elif ('/usr/bin/ar ' in line or '/usr/lib/llvm22/bin/clang' in line) and '-o ' in line or '/usr/bin/ar ' in line:links.append(line)
 deps=shell([NINJA,'-t','deps'],builddir);paths=set();fanout={};current=None
 for line in deps.splitlines():
  if line and not line[0].isspace():current=line.split(': #deps')[0]
  elif line.startswith('    '):
   p=(builddir/line.strip()).resolve()
   if current in commands and p.is_file() and p.is_relative_to(ROOT):paths.add(p)
   if current in commands and p.is_relative_to(source) and p.suffix in ['.h','.hpp','.hh','.hxx']:fanout.setdefault(p,set()).add(current)
 for c in commands.values():paths.add(Path(c[c.index('-c')+1]).resolve())
 # Admit the target's observed compilation closure, not unrelated tests and
 # benchmarks. This is a closed-graph experiment, not whole-repository ingestion.
 bodies={str(p):p.read_text() for p in sorted(paths)}
 # Choose from graph topology before timing, rather than selecting the fastest case.
 header=max(fanout,key=lambda p:(len(fanout[p]),str(p)));tu=Path(next(iter(commands.values()))[next(iter(commands.values())).index('-c')+1])
 return builddir,source,target,commands,links,bodies,header,tu,len(fanout[header])

def main(a):
 a.output.mkdir(parents=True,exist_ok=True);allresults=[]
 freeze=json.loads((Path(__file__).parent/'freeze.json').read_text())
 for path,expected in freeze['algorithm_pins'].items():assert digest((REPO/path).read_bytes())==expected,path
 for name in a.projects:
  builddir,source,target,basecommands,links,base,header,tu,fanout=graph(name);job.cwd=builddir
  # Install a standard compiler launcher without altering compile commands or flags.
  rules=builddir/'CMakeFiles/rules.ninja';original=rules.read_text();launcher=install_launcher(original)
  header_guard='\n#ifndef GAIA_GENERALIZATION_HEADER_PROBE\n#define GAIA_GENERALIZATION_HEADER_PROBE\nstatic inline int gaia_generalization_header_probe(void){return 1;}\n#endif\n'
  cases=[('no_op',{},'base'),('single_source_comment',{str(tu):base[str(tu)]+'\n/* generic comment probe */\n'},'base'),('single_source_semantic',{str(tu):base[str(tu)]+'\nint gaia_generalization_probe(void){return 7;}\n'},'base'),('observed_header_comment',{str(header):base[str(header)]+'\n/* generic header comment */\n'},'base'),('observed_header_semantic',{str(header):base[str(header)]+header_guard},'base'),('unused_numeric_definition',{},'unused'),('widely_used_definition',{},'assertions'),('compiler_option_change',{},'optimization'),('return_to_seen_state',{},'base')]
  generator=None
  if name=='re2c':
   generator=source/'include/syntax/c';base[str(generator)]=generator.read_text();cases.append(('explicit_generated_input_change',{str(generator):base[str(generator)]+'\n// generic generator input comment\n'},'base'))
  def config(which):
   result={t:list(c) for t,c in basecommands.items()}
   for c in result.values():
    if which=='unused':c.append('-DGAIA_UNUSED_NUMERIC_PROBE=17')
    if which=='assertions':c[:]=[x for x in c if x!='-DNDEBUG']
    if which=='optimization':c[:]=['-O1' if x=='-O3' else x for x in c]
   return result
  # Correctness oracles are produced outside primary clocks, once per distinct state.
  oracle={};initial_outputs={};oracle_host=Host(SERIAL,WORK/'logs'/name/'oracle',True);og=admit_chunks(oracle_host,{})
  try:
   for case,edits,which in [('setup',{},'base'),*cases]:
    write_bodies({**base,**edits});rules.write_text(original)
    commands=config(which)
    # Temporary Ninja variable changes represent command-line configuration edits.
    text=(builddir/'build.ninja').read_text();saved=text
    if which=='unused':text=text.replace('FLAGS = ','FLAGS = -DGAIA_UNUSED_NUMERIC_PROBE=17 ')
    if which=='assertions':text=text.replace('-DNDEBUG','')
    if which=='optimization':text=text.replace('-O3','-O1')
    (builddir/'build.ninja').write_text(text)
    try:shell([NINJA,'-j2','-d','keepdepfile',target],builddir)
    finally:(builddir/'build.ninja').write_text(saved)
    # Ninja uses its normal physical compiler. Independently execute an uncached
    # physical frontend for complete facts, and compare native object emission.
    stock=object_hashes(commands);facts={};deps_expected={}
    for t,c in commands.items():
     r=require(job(oracle_host,c,t,og,physical=True));facts[t]=r['facts'];deps_expected[t]=digest(Path(c[c.index('-MF')+1]).read_bytes())
    assert stock==object_hashes(commands),(name,case,'physical ToolInvocation vs compiler object mismatch')
    oracle[case]=dict(objects=stock,facts=facts,deps=deps_expected,bodies={p:Path(p).read_text() for p in base})
    if case=='setup':initial_outputs={t:Path(c[c.index('-o')+1]).read_bytes() for t,c in commands.items()}
  finally:oracle_host.close();write_bodies(base);rules.write_text(original)
  metadata=dict(project=name,translation_units=len(basecommands),source_files=len(base),source_bytes=sum(len(x.encode()) for x in base.values()),header=str(header.relative_to(source)),header_fanout=fanout,translation_unit=str(tu.relative_to(source)) if tu.is_relative_to(source) else str(tu.relative_to(builddir)),generated_input=str(generator.relative_to(source)) if generator else None,setup=json.loads((builddir/'setup.json').read_text()))
  (a.output/(name+'-graph.json')).write_text(json.dumps(metadata,indent=2)+'\n')
  for trial in range(a.trials):
   for mode in ['serial','queue','ninja-ccache'] if trial%2==0 else ['ninja-ccache','queue','serial']:
    write_bodies(base);rules.write_text(launcher if mode=='ninja-ccache' else original)
    ENV['CCACHE_DIR']=str(WORK/'ccache'/name/a.output.name/str(trial));ENV['CCACHE_TEMPDIR']=str(WORK/'ccache-tmp');Path(ENV['CCACHE_TEMPDIR']).mkdir(exist_ok=True)
    h=Host(QUEUE if mode=='queue' else SERIAL,WORK/'logs'/name/f'{trial}-{mode}',True);start=stamp();g=admit_chunks(h,base)
    try:
     if mode=='ninja-ccache':
      # Populate this trial's fresh ccache with the same starting version.
      shell([NINJA,'-t','clean',target],builddir);shell([NINJA,'-j1','-d','keepdepfile',target],builddir)
      verify_launcher(builddir,target);initial_cache_stats=cache_stats(builddir)
      assert sum(initial_cache_stats.get(k,0) for k in ['cache_miss','direct_cache_hit','preprocessed_cache_hit'])>=len(basecommands),'no observed ccache calls'
      assert initial_cache_stats.get('files_in_cache',0)>0,'ccache stored no results'
      build(h,index_commands(basecommands),g,analysis=True)
     else:build(h,basecommands,g,defer=mode=='queue',links=links)
     setup_seconds=stamp()-start;previous=base
     for case,edits,which in cases:
      desired=oracle[case]['bodies'];commands=config(which);changed={p:b for p,b in desired.items() if previous.get(p)!=b};start=stamp();write_bodies(changed)
      generation_seconds=0
      if generator:
       begin=stamp();shell([NINJA,'-j1','src/default_syntax_c.h'],builddir);generation_seconds=stamp()-begin
      # Generated outputs are admitted after the upstream generation rule runs.
      g=admit_chunks(h,changed,g) if changed else g
      saved=(builddir/'build.ninja').read_text();text=saved
      if which=='unused':text=text.replace('FLAGS = ','FLAGS = -DGAIA_UNUSED_NUMERIC_PROBE=17 ')
      if which=='assertions':text=text.replace('-DNDEBUG','')
      if which=='optimization':text=text.replace('-O3','-O1')
      if mode=='ninja-ccache':(builddir/'build.ninja').write_text(text)
      try:
       if mode=='ninja-ccache':
        def physical():
         begin=stamp();out=shell([NINJA,'-j1','-d','keepdepfile',target],builddir);return dict(seconds=stamp()-begin,output=out)
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
         pending=pool.submit(physical);result=build(h,index_commands(commands),g,analysis=True);build_result=pending.result()
       else:result=build(h,commands,g,defer=mode=='queue',links=links);build_result=None
       elapsed=stamp()-start;expected=oracle[case]
       assert object_hashes(commands)==expected['objects'],(name,mode,case,'objects')
       if result['facts']!=expected['facts']:
        (a.output/'facts-mismatch.json').write_text(json.dumps(dict(project=name,mode=mode,case=case,actual=result['facts'],expected=expected['facts']),indent=2)+'\n')
        raise AssertionError((name,mode,case,'facts'))
       if mode!='ninja-ccache':assert {t:digest(Path(c[c.index('-MF')+1]).read_bytes()) for t,c in commands.items()}==expected['deps'],(name,mode,case,'depfiles')
       result.pop('facts');row=dict(project=name,trial=trial,mode=mode,case=case,seconds=elapsed,setup_seconds=setup_seconds,generator_seconds=generation_seconds,physical_build=build_result,ccache_stats=cache_stats(builddir) if mode=='ninja-ccache' else None,**{('component_'+k if k=='seconds' else k):v for k,v in result.items()});allresults.append(row)
       (a.output/'results.json').write_text(json.dumps(dict(schema_version=1,rows=allresults,freeze=freeze),indent=2)+'\n');print(name,trial,mode,case,round(elapsed*1000,2),flush=True)
      finally:
       if mode=='ninja-ccache':(builddir/'build.ninja').write_text(saved)
      previous=desired
    finally:h.close();rules.write_text(original);write_bodies(base)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('projects',nargs='*',default=list(PROJECTS));p.add_argument('--trials',type=int,default=3);p.add_argument('--output',type=Path,required=True);main(p.parse_args())
