"""Strong separate-worker parallel control for shared parsed-source analysis."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
import os
from pathlib import Path
import random
import time
from run_ir import Host,sha,save

def usage(host):
    # Linux process-local counters, sampled outside operation timers.
    base=Path('/proc')/str(host.p.pid);fields=(base/'stat').read_text().rsplit(')',1)[1].split()
    rss=next(int(line.split()[1])*1024 for line in (base/'status').read_text().splitlines() if line.startswith('VmRSS:'))
    return dict(cpu_seconds=(int(fields[11])+int(fields[12]))/os.sysconf('SC_CLK_TCK'),rss_bytes=rss)

def run(a):
    a.output.mkdir(parents=True,exist_ok=False);compdir=a.output/'compiler';compdir.mkdir();analysisdir=a.output/'analysis';analysisdir.mkdir();compiler=Host(a.host,compdir);analysis=Host(a.host,analysisdir);origin=json.loads(a.origin.read_text());assert origin['status']=='complete' and origin['frozen_inputs_verified_after'];rows=[];rng=random.Random(8627);start_hash=sha(a.host.read_bytes());source_hash=sha(Path(__file__).read_bytes());host_source=sha(Path(__file__).with_name('ir_host.cpp').read_bytes());runner_source=sha(Path(__file__).with_name('run_ir.py').read_bytes())
    try:
      with ThreadPoolExecutor(max_workers=2) as pool:
       for source,prep in origin['preparation'].items():
        command=prep['command']
        # The source ID is relative to the original compiler's private project.
        source_path=next(Path(v) for v in command if v.endswith('.c'));project=source_path
        for _ in Path(source).parts:project=project.parent
        cwd=project
        out=compdir/'current.o';unused=analysisdir/'unused.o';baseline=prep['baseline_object_sha256']
        warm=compiler.call(command,cwd,out,mode='native',analysis='serial');assert warm['ok'] and sha(out.read_bytes())==baseline
        expected=warm['analysis_count'];warm_analysis=analysis.call(command,cwd,unused,mode='analysis');assert warm_analysis['ok'] and warm_analysis['analysis_count']==expected
        modes=['independent-serial','independent-parallel','shared-serial','shared-parallel']
        for block in range(a.trials):
          rng.shuffle(modes)
          for mode in modes:
            before=[usage(compiler),usage(analysis)];start=time.perf_counter()
            if mode=='independent-serial':
              check=analysis.call(command,cwd,unused,mode='analysis');result=compiler.call(command,cwd,out,mode='native')
            elif mode=='independent-parallel':
              left=pool.submit(analysis.call,command,cwd,unused,mode='analysis');right=pool.submit(compiler.call,command,cwd,out,mode='native');check=left.result();result=right.result()
            else:
              result=compiler.call(command,cwd,out,mode='native',analysis=mode.removeprefix('shared-'));check=result
            elapsed=time.perf_counter()-start;after=[usage(compiler),usage(analysis)];correct=result['ok'] and check['ok'] and check['analysis_count']==expected and sha(out.read_bytes())==baseline;assert correct,(mode,result,check)
            row=dict(source=source,block=block,mode=mode,seconds=elapsed,cpu_seconds=sum(v['cpu_seconds']-u['cpu_seconds'] for u,v in zip(before,after)),rss_sample_bytes=[v['rss_bytes'] for v in after],compiler=result,analysis=check,correct=correct);rows.append(row);print(source,block,mode,round(elapsed*1000,2),flush=True)
            save(a.output/'results.json',dict(status='running',cases=rows))
      assert sha(a.host.read_bytes())==start_hash and sha(Path(__file__).read_bytes())==source_hash and sha(Path(__file__).with_name('ir_host.cpp').read_bytes())==host_source and sha(Path(__file__).with_name('run_ir.py').read_bytes())==runner_source
      data=dict(status='complete',trials=a.trials,cases=rows,host_sha256=start_hash,implementation_sha256={Path(__file__).name:source_hash,'ir_host.cpp':host_source,'run_ir.py':runner_source},origin_sha256=sha(a.origin.read_bytes()),scope='Two initialized isolated Clang workers versus one initialized shared-frontend worker. Analysis is SHA256 over detached declaration names, not a production linter. Separate-worker RSS includes a warm idle second worker in shared modes; samples are not peak memory or PSS.',frozen_inputs_verified_after=True)
      save(a.output/'results.json',data);save(a.output/'validation.json',dict(passed=True,objects_checked=len(rows),analysis_checks=len(rows),raw_sha256=sha((a.output/'results.json').read_bytes())))
    finally:compiler.close();analysis.close()

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('host','origin','output','measurement-lock'):p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--trials',type=int,default=3);a=p.parse_args()
 with a.measurement_lock.open('a') as lock:fcntl.flock(lock,fcntl.LOCK_EX);run(a)
