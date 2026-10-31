"""Tightly adjacent no-agent rebuilt/index pairs; separate isolated initialization probe."""
import argparse,json,os,random,statistics,time,resource
from pathlib import Path
from profile import checked,sha
HERE=Path(__file__).resolve().parent

def main():
 p=argparse.ArgumentParser();p.add_argument('--tools',type=Path,required=True);p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--blocks',type=int,default=7);a=p.parse_args();tools=a.tools.resolve();data=json.loads(a.run.read_text());work=Path(data['work']);jdk=tools/'toolchain/jdk-25.0.5.0.3';out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);classes=out/'classes';classes.mkdir()
 start=time.perf_counter_ns();checked([jdk/'bin/javac','--release','17','-d',classes,HERE/'InitProbe.java']);build_ns=time.perf_counter_ns()-start
 rows=[]
 for block in range(-1,a.blocks):
  workloads=['registry','init'];random.Random(991+block).shuffle(workloads)
  for workload in workloads:
   variants=['rebuilt','indexed'];random.Random(155+block).shuffle(variants)
   for variant in variants:
    token=f'confirm-{block+1}-{workload}-{variant}';jar=Path(data['preparation']['variants'][variant]['jar']);cp=os.pathsep.join(map(str,[jar,tools/'downloads/picocli-4.7.7.jar',work/'phases.jar',classes]));cmd=[jdk/'bin/java','-Xshare:on','-XX:SharedArchiveFile='+str(work/(variant+'.jsa')),'-cp',cp]
    cmd+=['InitProbe',token] if workload=='init' else ['FrameworkPhases','registry',token,str(9+max(0,block))]
    cpu_before=resource.getrusage(resource.RUSAGE_CHILDREN);pressure_before=Path('/proc/pressure/cpu').read_text();start=time.perf_counter_ns();proc=checked(cmd,env=dict(os.environ,GAIA_REQUEST_TOKEN=token));ns=time.perf_counter_ns()-start;cpu_after=resource.getrusage(resource.RUSAGE_CHILDREN);pressure_after=Path('/proc/pressure/cpu').read_text();value=json.loads(proc.stdout)
    if value['token']!=token or (workload=='registry' and value['result']!='ready'):raise ValueError(value)
    if block>=0:rows.append(dict(block=block,workload=workload,variant=variant,wall_ns=ns,child_user_ns=int((cpu_after.ru_utime-cpu_before.ru_utime)*1e9),child_system_ns=int((cpu_after.ru_stime-cpu_before.ru_stime)*1e9),cpu_pressure_before=pressure_before,cpu_pressure_after=pressure_after,result=value))
    (out/'checkpoint.json').write_text(json.dumps(rows,indent=2))
 summary=[]
 for workload in ['registry','init']:
  base=[r for r in rows if r['workload']==workload and r['variant']=='rebuilt']
  for variant in ['rebuilt','indexed']:
   values=[r for r in rows if r['workload']==workload and r['variant']==variant];key='init_ns' if workload=='init' else 'registry_ns'
   summary.append(dict(workload=workload,variant=variant,median_ms=statistics.median(r['wall_ns']/1e6 for r in values),min_ms=min(r['wall_ns']/1e6 for r in values),max_ms=max(r['wall_ns']/1e6 for r in values),phase_median_ms=statistics.median(r['result'][key]/1e6 for r in values),paired_wins_vs_rebuilt=sum(r['wall_ns']<b['wall_ns'] for r,b in zip(values,base))))
 result=dict(schema='GAIA-JVMTI-CONFIRM-1',blocks=a.blocks,agent=False,prior_run_sha256=sha(a.run),probe_build_ns=build_ns,source_sha256={p.name:sha(p) for p in [HERE/'InitProbe.java',HERE/'confirm.py']},rows=rows,summary=summary)
 (out/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
