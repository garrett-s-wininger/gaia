"""Separate sampled resource diagnostic; never contributes primary timings."""
import argparse,json,os,resource,threading,time
from pathlib import Path
import run as replay

def descendants(pid):
 result=[];pending=[pid];seen={pid}
 while pending:
  current=pending.pop()
  # Linux child lists belong to tasks. Popen from a pool thread is absent
  # from the main task's list even though its process PPID is the controller.
  try:tasks=list(Path(f'/proc/{current}/task').iterdir())
  except OSError:continue
  for task in tasks:
   try:children=[int(x) for x in (task/'children').read_text().split()]
   except (OSError,ValueError):continue
   for child in children:
    if child not in seen:seen.add(child);result.append(child);pending.append(child)
 return result
def pss(pid):
 try:
  for line in Path(f'/proc/{pid}/smaps_rollup').read_text().splitlines():
   if line.startswith('Pss:'):return int(line.split()[1])*1024
 except OSError:pass
 return 0
class Sampler:
 def __init__(self):self.done=threading.Event();self.samples=[];self.thread=threading.Thread(target=self.sample)
 def sample(self):
  while not self.done.is_set():
   start=time.monotonic();pids=descendants(os.getpid());self.samples.append(dict(time=start,descendants=len(pids),aggregate_pss=sum(pss(p) for p in pids),controller_pss=pss(os.getpid())));self.done.wait(.005)
 def __enter__(self):self.thread.start();return self
 def __exit__(self,*args):self.done.set();self.thread.join()
def child_cpu():
 r=resource.getrusage(resource.RUSAGE_CHILDREN);return r.ru_utime+r.ru_stime

def main(a):
 if a.output.exists():raise FileExistsError('choose a fresh diagnostic output filename')
 rows=[]
 for name in a.projects:
  directory,source,target,commands,links,bodies,header,tu,fanout=replay.graph(name);replay.job.cwd=directory
  changed={t:[v for v in c if v!='-DNDEBUG'] for t,c in commands.items()}
  rules=directory/'CMakeFiles/rules.ninja';original=rules.read_text();manifest=directory/'build.ninja';saved=manifest.read_text()
  for mode in ['serial','queue','ninja-ccache']:
   replay.write_bodies(bodies);h=replay.Host(replay.QUEUE if mode=='queue' else replay.SERIAL,replay.WORK/'logs'/name/('diagnostic-'+mode),True)
   try:
    g=replay.admit_chunks(h,bodies);launcher=replay.install_launcher(original)
    rules.write_text(launcher if mode=='ninja-ccache' else original)
    replay.ENV['CCACHE_DIR']=str(replay.WORK/'ccache-diagnostic'/a.output.stem/name);replay.ENV['CCACHE_TEMPDIR']=str(replay.WORK/'ccache-tmp')
    if mode=='ninja-ccache':
     if Path(replay.ENV['CCACHE_DIR']).exists():raise FileExistsError('diagnostic cache must be fresh')
     replay.shell([replay.NINJA,'-t','clean',target],directory);replay.shell([replay.NINJA,'-j1','-d','keepdepfile',target],directory);replay.build(h,replay.index_commands(commands),g,analysis=True)
     replay.verify_launcher(directory,target)
    else:replay.build(h,commands,g,defer=mode=='queue',links=links)
    previous_children=replay.require(h.request({'drain':True}))['child_cpu'] if mode=='queue' else 0
    own=h.cpu();waited=child_cpu()
    with Sampler() as samples:
     if mode=='ninja-ccache':
      manifest.write_text(saved.replace('-DNDEBUG',''))
      with replay.concurrent.futures.ThreadPoolExecutor(2) as pool:
       physical=pool.submit(replay.shell,[replay.NINJA,'-j1','-d','keepdepfile',target],directory);result=replay.build(h,replay.index_commands(changed),g,analysis=True);physical.result()
     else:result=replay.build(h,changed,g,defer=mode=='queue',links=links)
    backend_cpu=result['drain']['child_cpu']-previous_children if mode=='queue' else 0
    rows.append(dict(project=name,mode=mode,scenario='remove-NDEBUG',process_tree_cpu_seconds=h.cpu()-own+child_cpu()-waited+backend_cpu,samples=samples.samples,peak_sampled_descendant_pss_bytes=max(s['aggregate_pss'] for s in samples.samples),peak_controller_pss_bytes=max(s['controller_pss'] for s in samples.samples)))
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(dict(scope='separate instrumented diagnostic; observed PSS peaks, not hard bounds; controller separate; no primary timings',rows=rows),indent=2)+'\n');print(name,mode,rows[-1]['peak_sampled_descendant_pss_bytes'],flush=True)
   finally:h.close();manifest.write_text(saved);rules.write_text(original);replay.write_bodies(bodies)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('projects',nargs='*',default=list(replay.PROJECTS));p.add_argument('--output',type=Path,required=True);main(p.parse_args())
