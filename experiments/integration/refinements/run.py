"""Replay the unchanged production fixture with matched original/refined controls."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'workspace'

def transform(source):
 s=source
 def replace(old,new):
  nonlocal s
  if s.count(old)!=1:raise ValueError('runner shape changed: '+old[:80])
  s=s.replace(old,new)
 replace('from protocol import Host,admit,request,scan,sha','from refined_protocol import Host,admit,request,scan,sha')
 replace('HERE=Path(__file__).resolve().parent','HERE=Path('+repr(str(BASE))+')')
 replace("s=scan(host,targets,generation,context);facts=dict(s['facts']);rows=[]", "s=scan(host,targets,generation,context,commands={t:command(t,config) for t in targets},root=root,analysis=analysis);facts=dict(s['facts']);rows=[];ready_at=time.perf_counter_ns() if len(facts)==len(targets) else None")
 replace("   row=request(host,root,command(target,config),target,generation,context,analysis);facts[target]=row['facts'];rows.append({'target':target,**row})", """   def receive(info):
    nonlocal ready_at
    facts[target]=info
    if len(facts)==len(targets) and ready_at is None:ready_at=time.perf_counter_ns()
   row=request(host,root,command(target,config),target,generation,context,analysis,on_facts=receive if host.refined and not analysis else None);facts[target]=row['facts'];rows.append({'target':target,**row})
   if len(facts)==len(targets) and ready_at is None:ready_at=time.perf_counter_ns()""")
 replace("return {'facts':facts,'rows':rows,'dirty':s['dirty'],'scan_seconds':s['seconds']}", "return {'facts':facts,'rows':rows,'dirty':s['dirty'],'scan_seconds':s['seconds'],'restored':s.get('restored',[]),'projected':s.get('projected',[]),'facts_ready_at_ns':ready_at}")
 replace('for p in [a.host,a.clang,a.ninja,a.ccache]:','for p in [a.host,a.refined_host,a.clang,a.ninja,a.ccache]:')
 replace(" modes=['shared','independent','ninja-ccache']", " modes=['original','refined','ninja-ccache']")
 replace("build_host=Host(a.host,a.work/f'{block}-{mode}-build') if mode!='ninja-ccache' else None", "build_host=Host(a.refined_host if mode=='refined' else a.host,a.work/f'{block}-{mode}-build',refined=mode=='refined') if mode!='ninja-ccache' else None")
 replace("editor=Host(a.host,a.work/f'{block}-{mode}-editor') if mode!='shared' else build_host", "editor=Host(a.refined_host,a.work/f'{block}-{mode}-editor',refined=True) if mode=='ninja-ccache' else build_host")
 replace("if mode!='shared':e=build_trace(editor,gens[editor],False,True)", "if mode=='ninja-ccache':e=build_trace(editor,gens[editor],False,True)")
 replace("if r['dirty']:link()", "if r['dirty'] or r.get('restored'):link()")
 replace("if mode=='shared':\n       b=build();e={'facts':b['facts'],'ready_ns':b['ready_ns'],'dirty':b['dirty'],'rows':[]}", "if mode!='ninja-ccache':\n       b=build();e={'facts':b['facts'],'ready_ns':b['facts_ready_at_ns']-start if mode=='refined' else b['ready_ns'],'dirty':b['dirty'],'rows':[]}")
 replace("'preprocessor_cache_mode':b.get('preprocessor_cache_mode',False)", "'restored':b.get('restored',[]),'projected':b.get('projected',[]),'index_projected':e.get('projected',[]),'preprocessor_cache_mode':b.get('preprocessor_cache_mode',False)")
 replace("if mode=='shared' and block==0 and name=='noop':", "if mode=='refined' and block==0 and name=='noop':")
 replace("for name in ['host','archive','clang','ninja','ccache','work','output','lock']", "for name in ['host','refined_host','archive','clang','ninja','ccache','work','output','lock']")
 # The generated wrapper calls main itself rather than exposing its old CLI.
 s=s[:s.index("if __name__=='__main__':")]
 return s

def main(a):
 a.host=a.host.resolve();a.refined_host=a.refined_host.resolve();a.output=a.output.resolve();a.work=a.work.resolve()
 inputs=[BASE/'run.py',BASE/'host.cpp',BASE/'protocol.py',*HERE.glob('*.py'),a.host,a.refined_host];pins={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs};generated=transform((BASE/'run.py').read_text());namespace={'__file__':str(BASE/'run.py'),'__name__':'refined_replay'};sys.path.insert(0,str(HERE));exec(compile(generated,'<generated-refined-replay>','exec'),namespace)
 namespace['main'](a)
 assert pins=={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in pins}
 path=a.output/'results.json';d=json.loads(path.read_text());d['refinement_sources']=pins;d['generated_runner_sha256']=hashlib.sha256(generated.encode()).hexdigest();d['refinement_scope']='Frozen production fixture and full physical oracles. Original shared path versus cached identities, bounded multi-version result history, conservative numeric-macro projection and actual frontend events. Ninja + ccache uses refined standalone index as stronger control.';path.write_text(json.dumps(d,indent=2)+'\n')

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ['host','refined-host','archive','clang','ninja','ccache','work','output','lock']:p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--trials',type=int,default=3);main(p.parse_args())
