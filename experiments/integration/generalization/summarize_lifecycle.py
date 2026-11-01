"""Portable first-request and resource tables, kept apart from edit timings."""
import argparse,hashlib,json,statistics
from pathlib import Path
from summarize import stats

def main(a):
 startup=json.loads(a.startup.read_text());resources=json.loads(a.resources.read_text());result=dict(schema_version=1,startup=[],resources=[],input_sha256={k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in [('startup',a.startup),('resources',a.resources)]})
 for project in ['xxhash','spdlog','re2c','curl']:
  for mode in ['serial','queue','ninja-ccache']:
   values=[r['seconds'] for r in startup['rows'] if r['project']==project and r['mode']==mode];assert len(values)==3
   result['startup'].append(dict(project=project,mode=mode,seconds=stats(values)))
   r=next(r for r in resources['rows'] if r['project']==project and r['mode']==mode);intervals=[b['time']-a['time'] for a,b in zip(r['samples'],r['samples'][1:])]
   result['resources'].append(dict(project=project,mode=mode,scenario=r['scenario'],process_tree_cpu_seconds=r['process_tree_cpu_seconds'],peak_sampled_descendant_pss_bytes=r['peak_sampled_descendant_pss_bytes'],peak_controller_pss_bytes=r['peak_controller_pss_bytes'],sample_count=len(r['samples']),sampling_interval_seconds=stats(intervals),peak_descendant_processes=max(s['descendants'] for s in r['samples'])))
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'lifecycle-summary.json').write_text(json.dumps(result,indent=2)+'\n')
 lines=['# First requests and separate resource diagnostics','','These clocks are separate from the edit replay. See [the report](README.md) for source scope, rejected attempts and queue fallbacks.','', '## First request','','Seconds, median [minimum–maximum], three fresh-process/empty-compilation-cache observations on a prepared graph. OS page cache is warm; download/configuration are excluded. Build and independent index run concurrently in the control.','', '| Target | Shared serial | Shared queue | Ninja + ccache + index |','| --- | ---: | ---: | ---: |']
 for project in ['xxhash','spdlog','re2c','curl']:
  cells=[]
  for mode in ['serial','queue','ninja-ccache']:
   s=next(r['seconds'] for r in result['startup'] if r['project']==project and r['mode']==mode);cells.append(f"{s['median']:.3f} [{s['minimum']:.3f}–{s['maximum']:.3f}]")
  lines.append('| '+project+' | '+' | '.join(cells)+' |')
 lines+=['','## Resource scenario','','One instrumented removal of `NDEBUG` after the final first-request observation. Sampling begins after its startup clock stops. These are observed aggregate descendant PSS peaks, not memory bounds or full-session peaks. The controller is separate. CPU includes the native provider, waited backend children and completed linker/build subprocesses; process tick precision is limited.','', '| Target / path | Descendant PSS (MiB) | Controller PSS (MiB) | Process-tree CPU (s) |','| --- | ---: | ---: | ---: |']
 for r in result['resources']:lines.append(f"| {r['project']} / {r['mode']} | {r['peak_sampled_descendant_pss_bytes']/1048576:.1f} | {r['peak_controller_pss_bytes']/1048576:.1f} | {r['process_tree_cpu_seconds']:.2f} |")
 lines+=['','The sampler walks child lists for every process task, including worker-thread subprocesses. Raw timestamps, sample counts and actual intervals are retained. re2c’s queue path is serial fallback. Only one resource observation per path is collected; it is not a distribution or a cold-disk test.']
 (a.output/'LIFECYCLE.md').write_text('\n'.join(lines)+'\n')

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--startup',type=Path,required=True);p.add_argument('--resources',type=Path,required=True);p.add_argument('--output',type=Path,required=True);main(p.parse_args())
