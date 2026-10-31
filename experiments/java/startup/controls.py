#!/usr/bin/env python3
"""Honest empty/parser controls; Linux monotonic phase correlation, diagnostic."""
import argparse,hashlib,json,os,random,re,statistics,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent

def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def run(args):
 d=json.loads(args.run.read_text());original=Path(d['work']);jdk=Path(d['setup']['archive_command'][0]).parents[1]
 args.output.mkdir(parents=True,exist_ok=True);work=args.output/'work';work.mkdir();classes=work/'classes';classes.mkdir()
 jars=[HERE/'_work/downloads'/name for name in d['jars']];groovy,pico=jars
 subprocess.run([str(jdk/'bin/javac'),'-cp',str(pico),'-d',str(classes),str(HERE/'EmptyMain.java'),str(HERE/'PlainPicocli.java')],check=True)
 app=work/'controls.jar';subprocess.run([str(jdk/'bin/jar'),'--create','--file',str(app),'-C',str(classes),'.'],check=True)
 variants={
  'empty':('EmptyMain',[],[app]),
  'picocli-only':('PlainPicocli',[],[pico,app]),
  'with-groovy':('PlainPicocli',[],[groovy,pico,app]),
  'with-groovy-no-closures':('PlainPicocli',['-Dpicocli.disable.closures=true'],[groovy,pico,app]),
  'with-groovy-cds':('PlainPicocli',['-Xshare:on','-XX:SharedArchiveFile='+str(original/'frameworks.jsa')],[groovy,pico,app]),
  'with-groovy-no-closures-cds':('PlainPicocli',['-Xshare:on','-XX:SharedArchiveFile='+str(original/'frameworks.jsa'),'-Dpicocli.disable.closures=true'],[groovy,pico,app])}
 data=dict(scope='Separate diagnostic harness; normal complete JVM lifetime. Monotonic phase timestamps correlated on this Linux JVM and validated inside launch/wait interval. Not directly interchangeable with original fixture timings.',trials=args.trials,source_run=d['run_id'],source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [HERE/'EmptyMain.java',HERE/'PlainPicocli.java',HERE/'controls.py']},cases=[],diagnostics=[])
 rng=random.Random(7816);samples={v:[] for v in variants}
 def command(v,token,extra=()):
  main,flags,cp=variants[v];tail=[token] if main=='EmptyMain' else ['--token',token]
  return [str(jdk/'bin/java'),*flags,*extra,'-cp',os.pathsep.join(str(p.resolve()) for p in cp),main,*tail]
 for block in range(-1,args.trials):
  order=list(variants);rng.shuffle(order)
  for variant in order:
   token=f'p{block+1}-{variant}';begin=time.monotonic_ns();p=subprocess.run(command(variant,token),capture_output=True,text=True,env=dict(os.environ,GAIA_REQUEST_TOKEN=token));end=time.monotonic_ns()
   if p.returncode or json.loads(p.stdout)!=dict(token=token,sum=15):raise ValueError(p.stdout+p.stderr)
   line=next(l for l in p.stderr.splitlines() if l.startswith('PHASES '));v=json.loads(line[7:]);a,b,c,h=(v[x] for x in ('main_ns','constructed_ns','executed_ns','hook_ns'))
   if not begin<=a<=b<=c<=h<=end:raise ValueError('JVM/Python monotonic clock alignment not established')
   if block>=0:samples[variant].append(dict(block=block,seconds=(end-begin)/1e9,launch_to_main_ns=a-begin,construct_ns=b-a,execute_ns=c-b,after_execute_to_hook_ns=h-c,hook_to_exit_ns=end-h,validated=True))
 for variant in variants:
  log=work/(variant+'.log');token='diag-'+variant;p=subprocess.run(command(variant,token,['-Xlog:class+load=info,class+init=info:file='+str(log)]),capture_output=True,text=True,env=dict(os.environ,GAIA_REQUEST_TOKEN=token));assert p.returncode==0
  text=log.read_text();lines=text.splitlines();loads=[l for l in lines if '[class,load]' in l and ' source: ' in l];data['diagnostics'].append(dict(variant=variant,loaded_classes=len(loads),groovy_loaded=sum('groovy' in l.split(' source: ')[0] for l in loads),groovy_initialized=sum('[class,init]' in l and 'Initializing' in l and 'groovy' in l for l in lines),log_sha256=hashlib.sha256(text.encode()).hexdigest()))
 data['cases']=[dict(variant=v,samples=ss) for v,ss in samples.items()];write(args.output/'results.json',data)
 summary={k:v for k,v in data.items() if k!='cases'};summary['raw_sha256']=hashlib.sha256((args.output/'results.json').read_bytes()).hexdigest();summary['cases']=[dict(variant=v,median_ms=statistics.median(s['seconds']*1000 for s in ss),phase_medians_ms={k:statistics.median(s[k]/1e6 for s in ss) for k in ('launch_to_main_ns','construct_ns','execute_ns','after_execute_to_hook_ns','hook_to_exit_ns')}) for v,ss in samples.items()];write(args.output/'summary.json',summary);write(args.output/'validation.json',dict(passed=True,timed_operations=args.trials*len(samples),all_outputs_tokens_and_phase_bounds_match=True,raw_sha256=summary['raw_sha256']))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--trials',type=int,default=7);run(p.parse_args())
