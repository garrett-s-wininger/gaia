#!/usr/bin/env python3
"""Prepared package DGM data, fresh class bindings/registries, complete JVM life."""
import argparse,hashlib,json,os,random,shutil,statistics,subprocess,time,zipfile
from datetime import datetime,timezone
from pathlib import Path
import prepare as prep
HERE=Path(__file__).resolve().parent
FIXTURES=HERE.parent
MODES=('records','registry','parser','basic')
def write(p,d):p.write_text(json.dumps(d,indent=2)+'\n')
def timed(cmd,env=None):
 b=time.perf_counter();p=subprocess.run([str(x) for x in cmd],capture_output=True,text=True,env=env);e=time.perf_counter()
 if p.returncode:raise RuntimeError(p.stdout+p.stderr)
 return p,e-b

def run(args):
 args.output.mkdir(parents=True,exist_ok=True);runid=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');work=HERE/'_work'/('module-index-'+runid);work.mkdir(parents=True)
 jdk=args.jdk.resolve();stock=(args.downloads/'groovy-6.0.0.jar').resolve();pico=(args.downloads/'picocli-4.7.7.jar').resolve();sources=(args.downloads/'groovy-6.0.0-sources.jar').resolve()
 if prep.sha(stock)!='6bcbec490ac1ade0dca6566dca9d02897cbb8fc31ee4008e950451aa83b1ac76':raise ValueError('wrong stock artifact')
 begin=time.perf_counter();patches,pins=prep.prepare(jdk,stock,sources,work/'patched');patch_seconds=time.perf_counter()-begin;variants={'stock':stock,**patches};classes=work/'classes';classes.mkdir()
 prep.checked([jdk/'bin/java','-cp',stock,'org.codehaus.groovy.tools.FileSystemCompiler','-d',classes,FIXTURES/'StaticLogic.groovy'])
 prep.checked([jdk/'bin/javac','-cp',str(stock)+os.pathsep+str(pico)+os.pathsep+str(classes),'-d',classes,FIXTURES/'FrameworkPhases.java',FIXTURES/'Command.java',HERE/'ModuleProbe.java'])
 app=work/'phases.jar';prep.checked([jdk/'bin/jar','--create','--file',app,'-C',classes,'.'])
 contexts={};setup={}
 for variant,jar in variants.items():
  cp=str(jar)+os.pathsep+str(pico);names=set()
  for artifact in (jar,pico):
   with zipfile.ZipFile(artifact) as z:names.update(n[:-6] for n in z.namelist() if n.endswith('.class') and not n.startswith('META-INF/') and n!='module-info.class')
  cl=work/(variant+'.classlist');cl.write_text((jdk/'lib/classlist').read_text().rstrip()+'\n'+'\n'.join(sorted(names))+'\n');archive=work/(variant+'.jsa')
  p,seconds=timed([jdk/'bin/java','-Xshare:dump','-Xmixed','-XX:SharedClassListFile='+str(cl),'-XX:SharedArchiveFile='+str(archive),'-cp',cp]);(work/(variant+'-dump.log')).write_text(p.stdout+p.stderr)
  contexts[variant]=dict(jar=jar,archive=archive,cp=cp+os.pathsep+str(app));setup[variant]=dict(archive_seconds=seconds,archive_bytes=archive.stat().st_size,archive_sha256=prep.sha(archive),classlist_sha256=prep.sha(cl),jar_sha256=prep.sha(jar))
 module_probes={};identity=None
 for variant,ctx in contexts.items():
  p,_=timed([jdk/'bin/java','-Xshare:on','-XX:SharedArchiveFile='+str(ctx['archive']),'-cp',ctx['cp'],'ModuleProbe']);probe=json.loads(p.stdout)
  actual=(probe['digest'],probe['table_entries'])
  if identity is None:identity=actual
  if actual!=identity:raise ValueError('module tables changed')
  if (variant=='indexed')!=probe['indexed']:raise ValueError('wrong module implementation')
  module_probes[variant]=probe
 data=dict(run_id=runid,status='running',trials=args.trials,scope='Fresh ordinary-bytecode JVMs with normal shutdown and warm pages; each variant has matching classic static CDS. Same packaged DGM bytes and fresh class/registry/extension bindings.',jdk=timed([jdk/'bin/java','-version'])[0].stderr,preparation=pins,patch_build_seconds=patch_seconds,setup=setup,module_probes=module_probes,work=str(work),cases=[],source_sha256={p.name:prep.sha(p) for p in (HERE/'prepare.py',HERE/'benchmark.py',FIXTURES/'FrameworkPhases.java',FIXTURES/'Command.java',FIXTURES/'StaticLogic.groovy')})
 frozen=work/'sources';frozen.mkdir()
 for name in data['source_sha256']:shutil.copyfile((HERE/name if (HERE/name).exists() else FIXTURES/name),frozen/name)
 samples={(m,v):[] for m in MODES for v in variants};rng=random.Random(7913);records=None
 def execute(mode,variant,token,seed):
  ctx=contexts[variant];cmd=[jdk/'bin/java','-Xshare:on','-XX:SharedArchiveFile='+str(ctx['archive']),'-cp',ctx['cp']]
  cmd+=['Command','--mode','picocli','--token',token,'--count',str(seed)] if mode=='parser' else ['FrameworkPhases',mode,token,str(seed)]
  return timed(cmd,env=dict(os.environ,GAIA_REQUEST_TOKEN=token))
 for block in range(-1,args.trials):
  order=list(samples);rng.shuffle(order)
  for mode,variant in order:
   token=f'd{block+1}-{mode}-{variant}';seed=5+max(0,block);p,seconds=execute(mode,variant,token,seed);value=json.loads(p.stdout)
   if value['token']!=token:raise ValueError('stale runtime binding')
   if mode=='records':
    sig=(value['records'],value['digest'])
    if records is None:records=sig
    if sig!=records:raise ValueError('DGM knowledge differs')
   elif mode=='registry':
    if value['result']!='ready' or value['groovy']!='6.0.0':raise ValueError('registry differs')
   elif mode=='parser':
    if value['sum']!=seed*(seed+1)//2 or value['mode']!='picocli':raise ValueError('parser differs')
   elif value['result']!=str(seed*(seed+1)//2) or value['groovy']!='6.0.0':raise ValueError('dynamic result differs')
   if block>=0:samples[mode,variant].append(dict(block=block,seconds=seconds,result=value,validated=True))
   print(block,mode,variant,f'{seconds*1000:.2f}ms',flush=True)
 data['cases']=[dict(mode=m,variant=v,samples=ss) for (m,v),ss in samples.items()];data['status']='complete';data['record_identity']=dict(count=records[0],sha256=records[1]);write(args.output/'results.json',data)
 summary={k:v for k,v in data.items() if k not in ('cases','work')};summary['raw_sha256']=prep.sha(args.output/'results.json');summary['cases']=[]
 for (mode,variant),ss in samples.items():
  base=samples[mode,'stock'];phases={k:statistics.median(s['result'][k]/1e6 for s in ss) for k in ss[0]['result'] if k.endswith('_ns') and k!='main_ns'}
  summary['cases'].append(dict(mode=mode,variant=variant,median_ms=statistics.median(s['seconds']*1000 for s in ss),paired_wins_vs_stock=sum(a['seconds']<b['seconds'] for a,b in zip(ss,base)),blocks=len(ss),phase_medians_ms=phases))
 write(args.output/'summary.json',summary);write(args.output/'validation.json',dict(passed=True,timed_operations=args.trials*len(samples),all_current_tokens_dynamic_results_and_DGM_records_match=True,raw_sha256=summary['raw_sha256']))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--jdk',type=Path,default=HERE/'_work/toolchain/jdk-25.0.5.0.3');p.add_argument('--downloads',type=Path,default=HERE/'_work/downloads');p.add_argument('--output',type=Path,default=HERE/'_work/dgm-results');p.add_argument('--trials',type=int,default=7);run(p.parse_args())
