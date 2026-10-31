#!/usr/bin/env python3
"""Train once; assemble metadata/profiles-only and compiled-code caches separately."""
import argparse,json,subprocess,time
from pathlib import Path
from run_variants import VM,session,write,RUN_ENV

def main():
 a=argparse.ArgumentParser();a.add_argument('--prepared',type=Path,required=True);a.add_argument('--output',type=Path,required=True);args=a.parse_args();p=json.loads(args.prepared.read_text());out=args.output;out.mkdir(parents=True,exist_ok=True);java=Path(p['jdk'])/'bin/java';config=out/'training.aotconfig'
 training=session(java,p['app'],p,['-XX:+UseG1GC','-XX:AOTMode=record','-XX:AOTConfiguration='+str(config)],['first','warm0','warm1'],out/'training-outputs');write(out/'training.json',training)
 for name,flags in [('code',[]),('no-code',['-XX:+UnlockDiagnosticVMOptions','-XX:-AOTCodeCaching'])]:
  cache=out/(name+'.aot');cmd=[str(java),*VM,'-XX:+UseG1GC',*flags,'-XX:AOTMode=create','-XX:AOTConfiguration='+str(config),'-XX:AOTCache='+str(cache),'-cp',p['app']];begin=time.perf_counter();r=subprocess.run(cmd,text=True,capture_output=True,env=RUN_ENV);row=dict(command=cmd,seconds=time.perf_counter()-begin,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr,bytes=cache.stat().st_size if cache.exists() else 0);write(out/(name+'-setup.json'),row)
  if r.returncode:raise RuntimeError(row)
if __name__=='__main__':main()
