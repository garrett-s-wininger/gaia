#!/usr/bin/env python3
"""Charge independent CLI, reachability training, and native build explicitly."""
import argparse,json,subprocess,time,sys,resource
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import benchmark
from run_variants import VM,write

def main():
 a=argparse.ArgumentParser();a.add_argument('--prepared',type=Path,required=True);a.add_argument('--output',type=Path,required=True);a.add_argument('--build-only',action='store_true');a.add_argument('--modules',type=Path);a.add_argument('--configuration',type=Path);a.add_argument('--optimization',choices=['b','2'],default='b');a.add_argument('--gc',choices=['serial','epsilon'],default='serial');args=a.parse_args();p=json.loads(args.prepared.read_text());w=args.output;w.mkdir(parents=True,exist_ok=True);jdk=Path(p['jdk']);config=args.configuration or w/'reachability';out=w/'training-output';(out/'broken').mkdir(parents=True,exist_ok=True);(out/'broken/Broken.java').write_text('class Broken { this is invalid; }\n')
 if not args.build_only:
  refs={}
  for i in (0,1):refs[str(i)]=benchmark.cli(p,'native-reference'+str(i),True,target=i,output=w/('reference'+str(i)))
  write(w/'references.json',refs)
  cmd=[str(jdk/'bin/java'),*VM,'-agentlib:native-image-agent=config-output-dir='+str(config),'-cp',p['app'],'NativeCompiler',p['source'],p['second_source'],p['jdk'],str(out)]+([str(args.modules)] if args.modules else []);begin=time.perf_counter();r=subprocess.run(cmd,input='first\nedit\nfail\nwarm\nstop\n',capture_output=True,text=True);write(w/'training.json',dict(command=cmd,seconds=time.perf_counter()-begin,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr));
  if r.returncode:raise RuntimeError(r.stderr)
  success=0;failure=0
  for line in r.stdout.splitlines():
   if line.startswith('{'):
    row=json.loads(line)
    success+=bool(row['ok']);failure+=not row['ok']
    if row['ok'] and row['sha256'] not in [v['sha256'] for v in refs.values()]:raise ValueError('JVM endpoint output differs from CLI')
  if success!=3 or failure!=1:raise RuntimeError(('training functionality',r.stdout,r.stderr))
 cmd=[str(jdk/'bin/native-image'),'-J-Xmx4g','-J-XX:-UsePerfData','--parallelism=4','--no-fallback','-O'+args.optimization,'--gc='+args.gc,'--add-modules=jdk.compiler,jdk.zipfs','-H:ConfigurationFileDirectories='+str(config),'-cp',p['app'],'NativeCompiler',str(w/'native-compiler')];begin=time.perf_counter()
 usage_before=resource.getrusage(resource.RUSAGE_CHILDREN)
 with (w/'build.stdout').open('w') as stdout,(w/'build.stderr').open('w') as stderr:r=subprocess.run(cmd,stdout=stdout,stderr=stderr)
 write(w/'build.json',dict(command=cmd,seconds=time.perf_counter()-begin,returncode=r.returncode,children_peak_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,children_cpu_seconds=resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime+resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime-usage_before.ru_utime-usage_before.ru_stime,binary_bytes=(w/'native-compiler').stat().st_size if (w/'native-compiler').exists() else 0));print((w/'build.json').read_text())
if __name__=='__main__':main()
