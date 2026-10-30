"""Frozen historical compile costs: FIFO versus expensive-first dispatch in Odin."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import random
import resource
import shutil
import statistics
import subprocess
import time
import benchmark as base
import project_benchmark as project

HERE=base.HERE


def report(d,path):
    lines=['# Cost-aware compiler dispatch','',f"Run `{d['run_id']}`; **{d['status']}**; {d['trials']} randomized blocks, fresh processes, warm cache.",'',
      'Same Zstandard 1.5.7 release/debug library requests, compiler flags and fixed ordered linker '
      'input as the preceding experiment. Eight Odin workers dispatch either FIFO or descending '
      'predicted cost; ties retain original job order. Predictions are frozen medians of per-job '
      'elapsed spans from seven earlier, unprofiled, file-handoff builds per configuration. They '
      'are historical scheduling hints, not intrinsic CPU costs or estimates learned from test outcomes. '
      'Both policies read and validate the same cost table. Native controls use one identical binary.','',
      '| Mode | Whole build ms | CPU ms | Compile wall ms | Predicted longest start ms | Final one-job tail ms | Peak RSS MiB |',
      '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for c in d['cases']:
        s=c['samples']
        if not s:continue
        med=lambda k:statistics.median(v[k] for v in s)
        lines.append(f"| {c['name']} | {med('wall_seconds')*1000:.2f} | {med('cpu_seconds')*1000:.2f} | {med('compile_wall_ns')/1e6:.2f} | {med('longest_start_ns')/1e6:.2f} | {med('final_one_job_ns')/1e6:.2f} | {med('peak_rss_bytes')/1048576:.2f} |")
    lines+=['','| Paired FIFO → cost | Median wall delta ms | Wins |','| --- | ---: | ---: |']
    cases={c['name']:c for c in d['cases']}
    for config in ('release','debug'):
        for mode in ('file','direct'):
            a=cases[f'{config}-{mode}-cost'];b=cases[f'{config}-{mode}-fifo']
            delta=[1000*(x['wall_seconds']-y['wall_seconds']) for x,y in zip(a['samples'],b['samples'])]
            if delta:lines.append(f"| {config}-{mode} | {statistics.median(delta):+.2f} | {sum(x<0 for x in delta)}/{len(delta)} |")
    lines+=['','Prediction/training cost is outside consumer timing: this run reuses already measured '
      'historical spans. A first build has no such history; all-zero estimates retain FIFO. There is no '
      'claim that stale costs generalize across compiler/configuration/hardware changes. No optimizer '
      'flags, AST caches, object-result reuse, request contents or linker order change. The sort '
      'runs in Odin over at most 64 admitted jobs; worker concurrency remains bounded to eight.','',
      'Longest start is the predicted-longest job start relative to the first job start. Final '
      'one-job tail is the gap between the last two job completions. These are logical-job spans, '
      'not CPU utilization. Eight active jobs can contend for cores and memory; earlier dispatch '
      'does not imply equal wall-time savings. Complete process time includes normal teardown '
      'and, for direct mode, captured-object validation hashes after the native workload clock. '
      'File hashes are checked outside timing. Compare policies within the same handoff mode.','',
      'Every object identity and final shared ELF must match the prior CLI reference. Direct requires '
      '30 buffer hits, zero misses and no object files. Every mode warmup exercises the upstream '
      'simple/streaming examples with six byte-exact round trips and checks dynamic loader resolution. '
      'Malformed cost records fail before compiler dispatch; existing outputs must remain intact. '
      'Ordinary compiler/linker failure behavior is inherited from the validated handoff adapter. '
      'This is one independent target batch, not a general build-DAG scheduler or persistent service.','']
    path.write_text('\n'.join(lines))


def run(a):
    parent=json.loads(a.inputs.read_text())
    if parent['status']!='complete':raise ValueError('completed training dataset required')
    host=a.host.resolve();source=Path(parent['source']);objects=parent['objects'];n=parent['jobs']
    for p,h in parent['source_sha256'].items():
        if base.sha(Path(p))!=h:raise ValueError('training source changed: '+p)
    for p,h in parent['toolchain_sha256'].items():
        if base.sha(Path(p))!=h:raise ValueError('toolchain changed: '+p)
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');work=HERE/'_work'/('schedule-'+run_id);work.mkdir()
    a.output.mkdir(parents=True,exist_ok=True)
    d=dict(run_id=run_id,status='running',trials=a.trials,work=str(work),training_run=parent['run_id'],
        training_results=str(a.inputs.resolve()),training_results_sha256=base.sha(a.inputs),host=str(host),host_sha256=base.sha(host),
        jobs=n,workers=8,objects=objects,source=parent['source'],source_sha256=parent['source_sha256'],
        toolchain_sha256=parent['toolchain_sha256'],environment={**parent['environment'],'uname':list(os.uname()),'cache':'warm; no eviction'},
        costs={},cases=[],validation=[],checks=[])
    build=host.parent.parent/'build.json'
    if build.exists():
        d['build']=json.loads(build.read_text())
        if d['build']['host_sha256']!=d['host_sha256']:raise ValueError('build provenance differs')
    snapshots=work/'sources';snapshots.mkdir()
    names=['schedule_benchmark.py','schedule_host.odin','handoff_bridge.cpp','handoff_impl.h','pool_bridge.cpp','project_bridge.cpp','bridge.cpp','benchmark.py']
    d['adapter_source_sha256']={name:base.sha(HERE/name) for name in names}
    for name in names:shutil.copy2(HERE/name,snapshots/name)
    d['source_snapshots']=str(snapshots)
    for config in ('release','debug'):
        training=next(c for c in parent['cases'] if c['name']==config+'-file')
        costs=[int(statistics.median(s['jobs'][i][1]-s['jobs'][i][0] for s in training['samples'])) for i in range(n)]
        order=sorted(range(n),key=lambda i:-costs[i]);costfile=work/(config+'.costs');costfile.write_text('GAIACOST1\n'+'\n'.join(map(str,costs))+'\n')
        d['costs'][config]=dict(values_ns=costs,order=order,longest=order[0],path=str(costfile),sha256=base.sha(costfile),
            training_samples=len(training['samples']),plan_sha256=training['plan_sha256'],commands=training['commands'])
        for mode in ('file','direct'):
            old=next(c for c in parent['cases'] if c['name']==config+'-'+mode)
            for policy in ('fifo','cost'):
                name=f'{config}-{mode}-{policy}';output=work/name;output.mkdir();(output/'libzstd.so.1').symlink_to('libzstd.so')
                cmd=old['command'].copy();cmd[0]=str(host);cmd[6]=str(output);cmd.extend([policy,str(costfile)])
                if base.sha(Path(cmd[7]))!=old['plan_sha256']:raise ValueError('invocation plan changed')
                d['cases'].append(dict(name=name,config=config,mode=mode,policy=policy,output=str(output),command=cmd,
                    expected_schedule=order if policy=='cost' else list(range(n)),link_command=old['link_command'],
                    expected=old['warmup']['artifacts_sha256'],samples=[]))
    def verify(c,p):
        if p.stderr:raise ValueError(p.stderr)
        s=json.loads(p.stdout);output=Path(c['output'])
        if not s['correct'] or s['compiled']!=n or s['errors'] or s['warnings'] or s['link_calls']!=1 or not s['can_run_again'] or s['peak_active']!=8:raise ValueError('incomplete/bound-violating build')
        if s['schedule']!=c['expected_schedule']:raise ValueError('schedule differs')
        if len(s['jobs'])!=n or any(a<=0 or b<=a for a,b in s['jobs']):raise ValueError('job skipped')
        if c['mode']=='direct':
            if s['buffer_hits']!=n or s['buffer_misses'] or any((output/x).exists() for x in objects):raise ValueError('direct handoff failed')
            artifacts=dict(zip(objects,s['object_sha256']));s['object_files_absent']=True
        else:artifacts={x:base.sha(output/x) for x in objects}
        artifacts['libzstd.so']=base.sha(output/'libzstd.so')
        if artifacts!=c['expected']:raise ValueError('artifact identity changed')
        first=min(v[0] for v in s['jobs']);ends=sorted(v[1] for v in s['jobs']);longest=d['costs'][c['config']]['longest']
        s.update(artifacts_sha256=artifacts,longest_start_ns=s['jobs'][longest][0]-first,final_one_job_ns=ends[-1]-ends[-2])
        return s
    def take(c):
        output=Path(c['output'])
        for x in [*objects,'libzstd.so']:(output/x).unlink(missing_ok=True)
        before=resource.getrusage(resource.RUSAGE_CHILDREN);begin=time.perf_counter();p=project.run_checked(c['command'],cwd=output);elapsed=time.perf_counter()-begin;after=resource.getrusage(resource.RUSAGE_CHILDREN)
        s=verify(c,p);s.update(wall_seconds=elapsed,cpu_seconds=after.ru_utime-before.ru_utime+after.ru_stime-before.ru_stime,
            system_seconds=after.ru_stime-before.ru_stime)
        return s
    # Reuse the upstream examples already built independently of this queue host.
    examples=[Path(parent['work'])/x for x in ('simple_compression','simple_decompression','streaming_compression','streaming_decompression')]
    def validate(c):
        env={**os.environ,'LD_LIBRARY_PATH':c['output']};logs=[project.run_checked(['ldd',str(examples[0])],env=env).stdout]
        if str(Path(c['output'])/'libzstd.so.1') not in logs[0]:raise ValueError('wrong validation library loaded')
        for size in (0,73,1048576):
            body=bytes(((i*37)^(i//97))&255 for i in range(size));inp=work/'test-input';inp.write_bytes(body);archive=work/'test-input.zst'
            for compressor in (examples[0],examples[2]):
                p=project.run_checked([str(compressor),str(inp)],env=env);logs.append(p.stdout+p.stderr)
                if compressor==examples[0]:
                    p=project.run_checked([str(examples[1]),str(archive)],env=env);logs.append(p.stdout+p.stderr)
                p=subprocess.run([str(examples[3]),str(archive)],env=env,capture_output=True,timeout=180)
                if p.returncode or p.stdout!=body:raise ValueError('upstream round-trip failed')
                logs.append(f'{compressor.name}: {size} bytes match')
        log=a.output/(c['name']+'-examples.txt');log.write_text('\n'.join(logs))
        return dict(case=c['name'],passed=True,roundtrips=6,log=str(log))
    for c in d['cases']:
        c['warmup']=take(c);d['validation'].append(validate(c));print('verified',c['name'],flush=True)
    case=next(c for c in d['cases'] if c['name']=='release-direct-cost');output=Path(case['output'])
    # Missing/equal costs are stable FIFO, not a special workload-dependent fallback.
    zero=work/'zero.costs';zero.write_text('GAIACOST1\n'+'0\n'*n);cmd=case['command'].copy();cmd[-1]=str(zero)
    alternate={**case,'command':cmd,'expected_schedule':list(range(n))};s=take(alternate)
    d['checks'].append(dict(check='all-zero-costs-stable-fifo',passed=True,result=s))
    for name,body in [('short','GAIACOST1\n'+'0\n'*5),('negative','GAIACOST1\n-1\n'+'0\n'*(n-1)),('magic','BADMAGIC\n'+'0\n'*n)]:
        bad=work/(name+'.costs');bad.write_text(body);cmd=case['command'].copy();cmd[-1]=str(bad)
        before=base.sha(output/'libzstd.so');p=subprocess.run(cmd,cwd=output,capture_output=True,text=True,timeout=180)
        if p.returncode!=3 or 'invalid cost' not in p.stderr or base.sha(output/'libzstd.so')!=before or any((output/x).exists() for x in objects):raise ValueError('bad cost admission/publication gate failed')
        d['checks'].append(dict(check=name+'-cost-rejected-before-dispatch',passed=True,returncode=p.returncode,stderr=p.stderr))
    def save():base.save(a.output/'results.json',d);report(d,a.output/'REPORT.md')
    save();rng=random.Random(20261107)
    for i in range(a.trials):
        order=d['cases'].copy();rng.shuffle(order)
        for c in order:c['samples'].append(take(c));print('schedule block',i+1,c['name'],flush=True)
        save()
    for p,h in d['source_sha256'].items():
        if base.sha(Path(p))!=h:raise ValueError('source changed during run')
    for config in d['costs'].values():
        if base.sha(Path(config['path']))!=config['sha256']:raise ValueError('cost table changed during run')
    if base.sha(host)!=d['host_sha256'] or base.sha(a.inputs)!=d['training_results_sha256']:raise ValueError('host/training data changed')
    d['status']='complete';save()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inputs',type=Path,default=HERE/'_work/runs/zstd-handoff/results.json')
    p.add_argument('--host',type=Path,default=HERE/'_work/schedule-development/build/host')
    p.add_argument('--trials',type=int,default=7)
    p.add_argument('--output',type=Path,default=HERE/'_work/runs/cost-scheduling')
    a=p.parse_args()
    if a.trials<1:p.error('positive trials required')
    run(a)
