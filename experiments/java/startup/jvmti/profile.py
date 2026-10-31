"""Matched full-process JVMTI overhead and bounded startup attribution, not a speedup."""
import argparse, hashlib, json, os, platform, random, statistics, subprocess, time
from pathlib import Path
HERE=Path(__file__).resolve().parent

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def checked(cmd, **kw):
 p=subprocess.run(list(map(str,cmd)),capture_output=True,text=True,timeout=60,**kw)
 if p.returncode: raise RuntimeError(p.stdout+p.stderr)
 return p

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--tools',type=Path,required=True);ap.add_argument('--baseline-run',type=Path);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--blocks',type=int,default=5);args=ap.parse_args()
 tools=args.tools.resolve();base=json.loads((args.baseline_run or tools/'dgm-final/results.json').read_text());old=Path(base['work']);jdk=tools/'toolchain/jdk-25.0.5.0.3';java=jdk/'bin/java'
 jars=[tools/'downloads/groovy-6.0.0.jar',tools/'downloads/picocli-4.7.7.jar',old/'phases.jar'];archive=old/'stock.jsa';out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
 lib=out/'libgaia_jvmti.so';checked(['c++','-std=c++20','-O2','-g','-shared','-fPIC','-pthread','-I'+str(jdk/'include'),'-I'+str(jdk/'include/linux'),HERE/'agent.cpp','-o',lib])
 modes=['none','idle','classes','cpu','alloc'];rows=[]
 def invoke(mode,workload,label,logging=False):
  token='jvmti-'+label;cmd=[java]
  profile=out/(label+'.json')
  if mode!='none':cmd.append('-agentpath:'+str(lib)+'='+mode+':'+str(profile))
  if logging:cmd.append('-Xlog:class+load=info,class+init=info:file='+str(out/(label+'.log')))
  cmd += ['-Xshare:on','-XX:SharedArchiveFile='+str(archive),'-cp',os.pathsep.join(map(str,jars)),'FrameworkPhases',workload,token,'9']
  start=time.perf_counter_ns();p=checked(cmd,env=dict(os.environ,GAIA_REQUEST_TOKEN=token));wall=time.perf_counter_ns()-start;value=json.loads(p.stdout)
  if value['token']!=token or value.get('result')!=('45' if workload=='basic' else 'ready'):raise ValueError(value)
  row=dict(mode=mode,workload=workload,label=label,wall_ns=wall,result=value,stderr=p.stderr)
  if mode!='none':
   data=json.loads(profile.read_text());row['profile']=profile.name
   if data['errors']:raise ValueError(data['errors'])
   if data['capabilities']['method_entry'] or data['capabilities']['class_hook'] or data['capabilities']['retransform']:raise ValueError('unexpected intrusive capability')
  return row
 # Every configuration gets an ordinary warm-page-cache first execution.
 for mode in modes:invoke(mode,'registry','warm-'+mode)
 for block in range(args.blocks):
  order=[(m,w) for m in modes for w in ['registry','basic']];random.Random(20261031+block).shuffle(order)
  for mode,workload in order:
   rows.append(invoke(mode,workload,f'{block}-{mode}-{workload}'));(out/'checkpoint.json').write_text(json.dumps(rows,indent=2))
 sharing=[]
 for mode in modes:
  row=invoke(mode,'registry','sharing-'+mode,True);lines=(out/(row['label']+'.log')).read_text().splitlines();framework=[s for s in lines if '[class,load]' in s and any(n in s for n in ['groovy.','picocli.'])];sharing.append(dict(mode=mode,framework_loads=len(framework),shared_framework_loads=sum('source: shared objects file' in s for s in framework),class_initializations=sum('[class,init]' in s and ' Initializing ' in s for s in lines)))
 summary=[]
 for workload in ['registry','basic']:
  control=statistics.median(r['wall_ns'] for r in rows if r['mode']=='none' and r['workload']==workload)
  for mode in modes:
   samples=[r['wall_ns']/1e6 for r in rows if r['mode']==mode and r['workload']==workload];median=statistics.median(samples);summary.append(dict(workload=workload,mode=mode,median_ms=median,min_ms=min(samples),max_ms=max(samples),overhead_percent=(median*1e6/control-1)*100))
 result=dict(schema='GAIA-JVMTI-PROFILE-1',blocks=args.blocks,page_cache='warm; fresh JVM per request; normal exit and agent JSON flush included',platform=platform.platform(),jdk=checked([java,'-version']).stderr,inputs={str(p):sha(p) for p in [*jars,archive,HERE/'agent.cpp',HERE/'profile.py']},rows=rows,summary=summary,sharing=sharing)
 (out/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps(dict(output=str(out),summary=summary,sharing=sharing),indent=2))
if __name__=='__main__':main()
