"""Matched first request on a prepared graph; separate from cache priming."""
import argparse,json,time
from pathlib import Path
import run as replay
from diagnose import Sampler,child_cpu

def main(a):
 if a.output.exists():raise FileExistsError('choose a fresh output filename and cache namespace')
 if a.resources and a.resources.exists():raise FileExistsError('choose a fresh resource output filename')
 rows=[];resource_rows=[]
 for name in a.projects:
  directory,source,target,commands,links,bodies,header,tu,fanout=replay.graph(name);replay.job.cwd=directory;rules=directory/'CMakeFiles/rules.ninja';original=rules.read_text();manifest=directory/'build.ninja';saved=manifest.read_text();project_resources=[]
  for trial in range(a.trials):
   matched=[]
   for mode in ['serial','queue','ninja-ccache'] if trial%2==0 else ['ninja-ccache','queue','serial']:
    replay.write_bodies(bodies)
    if name=='re2c':replay.shell([replay.NINJA,'-j1','src/default_syntax_c.h'],directory)
    # Retain prepared generated inputs. Remove only the target's objects, not
    # unrelated generated artifacts or upstream configuration work.
    for c in commands.values():Path(c[c.index('-o')+1]).unlink(missing_ok=True)
    rules.write_text(replay.install_launcher(original) if mode=='ninja-ccache' else original)
    if mode=='ninja-ccache':replay.verify_launcher(directory,target)
    replay.ENV['CCACHE_DIR']=str(replay.WORK/'startup-cache'/a.output.stem/name/str(trial));replay.ENV['CCACHE_TEMPDIR']=str(replay.WORK/'ccache-tmp')
    if mode=='ninja-ccache' and Path(replay.ENV['CCACHE_DIR']).exists():raise FileExistsError('startup cache must be fresh')
    begin=replay.stamp();h=replay.Host(replay.QUEUE if mode=='queue' else replay.SERIAL,replay.WORK/'logs'/name/f'startup-{trial}-{mode}',True)
    try:
     if mode=='ninja-ccache':
      with replay.concurrent.futures.ThreadPoolExecutor(2) as pool:
       physical=pool.submit(replay.shell,[replay.NINJA,'-j1','-d','keepdepfile',target],directory);g=replay.admit_chunks(h,bodies);result=replay.build(h,replay.index_commands(commands),g,analysis=True);physical.result()
     else:g=replay.admit_chunks(h,bodies);result=replay.build(h,commands,g,defer=mode=='queue',links=links)
     elapsed=replay.stamp()-begin;matched.append(dict(project=name,trial=trial,mode=mode,seconds=elapsed,objects=replay.object_hashes(commands),facts=result['facts']))
     # Sample only after the primary first-request clock has stopped. Reuse the
     # same initialized process rather than paying for another diagnostic seed.
     if a.resources and trial==a.trials-1:
      changed={t:[v for v in c if v!='-DNDEBUG'] for t,c in commands.items()};previous_children=replay.require(h.request({'drain':True}))['child_cpu'] if mode=='queue' else 0;own=h.cpu();waited=child_cpu()
      with Sampler() as samples:
       if mode=='ninja-ccache':
        manifest.write_text(saved.replace('-DNDEBUG',''))
        with replay.concurrent.futures.ThreadPoolExecutor(2) as pool:
         physical=pool.submit(replay.shell,[replay.NINJA,'-j1','-d','keepdepfile',target],directory);diagnostic=replay.build(h,replay.index_commands(changed),g,analysis=True);physical.result()
       else:diagnostic=replay.build(h,changed,g,defer=mode=='queue',links=links)
      backend_cpu=diagnostic['drain']['child_cpu']-previous_children if mode=='queue' else 0
      project_resources.append(dict(project=name,mode=mode,scenario='remove-NDEBUG',process_tree_cpu_seconds=h.cpu()-own+child_cpu()-waited+backend_cpu,samples=samples.samples,peak_sampled_descendant_pss_bytes=max(s['aggregate_pss'] for s in samples.samples),peak_controller_pss_bytes=max(s['controller_pss'] for s in samples.samples),objects=replay.object_hashes(changed),facts=diagnostic['facts']))
    finally:h.close();rules.write_text(original);manifest.write_text(saved)
   reference=next(x for x in matched if x['mode']=='ninja-ccache')
   for r in matched:
    assert r['objects']==reference['objects'],(name,trial,r['mode'],'startup objects')
    assert r['facts']==reference['facts'],(name,trial,r['mode'],'startup facts')
   for r in matched:
    r.pop('objects');r.pop('facts');rows.append(r);print(name,trial,r['mode'],round(r['seconds'],3),flush=True)
   a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(dict(schema_version=1,scope='Matched fresh process and empty compilation caches, warm OS page cache, prepared target graph and generated inputs. Concurrent Ninja -j1 plus independent index versus one shared serial host or one shared frontend/backend queue. Download/configuration excluded. No extrapolated repeated-trace break-even.',rows=rows),indent=2)+'\n')
  if project_resources:
   reference=next(r for r in project_resources if r['mode']=='ninja-ccache')
   for r in project_resources:assert r['objects']==reference['objects'] and r['facts']==reference['facts'],(name,r['mode'],'resource outputs')
   for r in project_resources:r.pop('objects');r.pop('facts');resource_rows.append(r)
   a.resources.parent.mkdir(parents=True,exist_ok=True);a.resources.write_text(json.dumps(dict(scope='Separate sampled remove-NDEBUG diagnostic after final first-request trial; observed process-tree PSS peaks, not hard bounds; controller separate; CPU includes waited backend children; no instrumented timings enter primary results; objects and complete facts match physical control.',rows=resource_rows),indent=2)+'\n')

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('projects',nargs='*',default=list(replay.PROJECTS));p.add_argument('--trials',type=int,default=3);p.add_argument('--output',type=Path,required=True);p.add_argument('--resources',type=Path);main(p.parse_args())
