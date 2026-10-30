"""Full process wall/CPU partition plus separate phase-scoped execution profiles."""
import argparse
import ast
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import pstats
import random
import re
import resource
import statistics
import subprocess
import sys
import time

import benchmark


def consume(command,log=None,profile=None,fast=False,batch=False):
    cmd=command[:]
    if log is not None:
        cmd[1:1]=['-X','gaia_phases='+str(log)]
        if fast:cmd[1:1]=['-X','gaia_exit=fast']
        if batch:cmd[1:1]=['-X','gaia_gc=batch']
        if profile is not None:cmd[1:1]=['-X','gaia_profile='+str(profile)]
    before=resource.getrusage(resource.RUSAGE_CHILDREN);parent_cpu=time.process_time();start=time.perf_counter()
    process=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    spawned=time.perf_counter()
    try:stdout,stderr=process.communicate(timeout=120)
    except subprocess.TimeoutExpired:
        process.kill();process.communicate();raise
    ended=time.perf_counter();parent_cpu=time.process_time()-parent_cpu
    after=resource.getrusage(resource.RUSAGE_CHILDREN)
    if process.returncode:raise RuntimeError(stderr+'\n'+stdout)
    result=json.loads(stdout);child_user=after.ru_utime-before.ru_utime;child_sys=after.ru_stime-before.ru_stime
    result.update(process_wall_seconds=ended-start,child_user_seconds=child_user,child_system_seconds=child_sys,
                  child_cpu_seconds=child_user+child_sys,parent_cpu_seconds=parent_cpu,
                  popen_seconds=spawned-start,stdout_bytes=len(stdout.encode()),stderr=stderr,pid=process.pid)
    if log is not None:
        telemetry=ast.literal_eval(log.read_text());points=telemetry['points'];segments=[]
        if points[0][0]!='worker_entered':raise ValueError('missing worker entry')
        if any(b[1]<a[1] or b[2]<a[2] for a,b in zip(points,points[1:])):raise ValueError('nonmonotonic worker phases')
        segments.append(dict(start='parent_launch',end=points[0][0],wall_seconds=points[0][1]-start,cpu_seconds=points[0][2]))
        for a,b in zip(points,points[1:]):segments.append(dict(start=a[0],end=b[0],wall_seconds=b[1]-a[1],cpu_seconds=b[2]-a[2]))
        segments.append(dict(start=points[-1][0],end='parent_exit_observed',wall_seconds=ended-points[-1][1],
                             cpu_seconds=child_user+child_sys-points[-1][2]))
        if abs(sum(s['wall_seconds'] for s in segments)-(ended-start))>1e-7:raise ValueError('wall partition differs')
        if abs(sum(s['cpu_seconds'] for s in segments)-(child_user+child_sys))>1e-7:raise ValueError('CPU partition differs')
        result.update(lifecycle_points=points,lifecycle_segments=segments,lifecycle_log=str(log),gc_events=telemetry['gc_events'])
    return result


def bucket(filename,name):
    if 'marshal.loads' in name or 'PyMarshal' in name:return 'bytecode decoding'
    if '__build_class__' in name:return 'class construction'
    if filename.endswith('process_phases.py'):return 'observer'
    if filename.endswith(('native_loader.py','native_catalog.py','bundle_access.py','indexed_path_loader.py','persistent_zip_loader.py','stdlib_snapshot.py','precomputed_index.py')) or '_gaia_native.' in name:return 'bundle/provider'
    if 'importlib._bootstrap' in filename:return 'import machinery'
    if '/django_fixture/' in filename:return 'application fixture'
    if '/django/' in filename:return 'Django'
    if '/rest_framework/' in filename or '/django_filters/' in filename:return 'REST/filter'
    if filename=='~' and any(k in name for k in ('posix.','_io.')):return 'filesystem primitives'
    if filename.endswith('django_worker.py') or filename.endswith('catalog_worker.py'):return 'worker/harness'
    return 'other stdlib/runtime'


def profiles(prefix):
    result=[]
    for path in sorted(prefix.parent.glob(prefix.name+'.*.pstats')):
        stats=pstats.Stats(str(path));groups=Counter();functions=[]
        for (filename,line,name),(_,calls,own,inclusive,_) in stats.stats.items():
            groups[bucket(filename,name)]+=own
            functions.append(dict(file=filename,line=line,function=name,calls=calls,self_seconds=own,inclusive_seconds=inclusive))
        if abs(sum(groups.values())-stats.total_tt)>1e-7:raise ValueError('profile buckets differ')
        result.append(dict(phase=path.name[len(prefix.name)+1:-len('.pstats')],path=str(path),total_self_seconds=stats.total_tt,
                           buckets=dict(groups),functions=sorted(functions,key=lambda f:f['self_seconds'],reverse=True)))
    return result


def interval(sample,start,end,key='wall_seconds'):
    points={name:(wall,cpu) for name,wall,cpu in sample['lifecycle_points']}
    if start not in points or end not in points:return 0
    column=0 if key=='wall_seconds' else 1
    return points[end][column]-points[start][column]


def render(data,path):
    lines=['# Whole-process lifecycle characterization','',f"Run: `{data['run_id']}`. Status: **{data['status']}**.",'',
           f"{data['trials']} randomized fresh processes per workload/mode after correctness warmups; warm filesystem cache. "
           'Same retained compact artifacts and native binary as the parent run. Baseline has no observer, '
           'observed has lifecycle timestamps, and fast-exit is a diagnostic control that completes all '
           'application validation and explicit provider/SQLite closes before bypassing interpreter '
           'finalization with os._exit. Fast-exit is not a production optimization or equivalent lifetime '
           'contract. Batch disables automatic GC during construction, restores its original enabled '
           'state and explicitly runs a full collection before exit; deferred collection cost is '
           'included. Native admission/integrity and payload checks stay enabled.','',
           '| Workload | Mode | Process wall ms | Child CPU ms | Parent CPU ms | Worker peak RSS MiB | Output bytes |',
           '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for c in data['cases']:
        s=c['samples']
        if not s:continue
        def med(k):return statistics.median(v[k] for v in s)*1000
        rss=f"{statistics.median(v['peak_rss_bytes'] for v in s)/1048576:.2f}" if 'peak_rss_bytes' in s[0] else '—'
        lines.append(f"| {c['workload']} | {c['mode']} | {med('process_wall_seconds'):.3f} | {med('child_cpu_seconds'):.3f} | {med('parent_cpu_seconds'):.3f} | {rss} | {s[0]['stdout_bytes']} |")
    lines+=['','## Observed lifecycle wall intervals','',
            '| Workload | Launch → worker entry | Observer setup | Common imports | CLI/input prep | Workload | Validation/output/close → main return | Return → telemetry write | Telemetry/finalization/wait tail |',
            '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for c in data['cases']:
        s=c['samples']
        if c['mode']!='observed' or not s:continue
        def med_interval(a,b):return statistics.median(interval(v,a,b) for v in s)*1000
        pre=statistics.median(v['lifecycle_segments'][0]['wall_seconds'] for v in s)*1000
        tail=statistics.median(v['lifecycle_segments'][-1]['wall_seconds'] for v in s)*1000
        values=[pre,med_interval('worker_entered','observer_ready'),med_interval('observer_ready','common_prepared'),
                med_interval('common_prepared','workload_begin'),med_interval('workload_begin','workload_finished'),
                med_interval('workload_finished','worker_returned'),med_interval('worker_returned','telemetry_write_begin'),tail]
        lines.append(f"| {c['workload']} | "+' | '.join(f'{v:.3f}' for v in values)+' |')
    lines+=['','Each individual process is partitioned exactly using Linux monotonic timestamps shared '
            'between parent/child. Independent medians do not add. CPU comes from per-child rusage '
            'deltas plus child process-time checkpoints; a tail CPU residual can have small accounting '
            'noise. Parent spawn/pipe/wait CPU is separate. Launch→entry includes spawn/exec, interpreter '
            'initialization and time/sys imports. The last tail includes telemetry writing, remaining '
            'interpreter finalization and parent pipe/wait completion; it is not all proven shutdown '
            'time. Compare normal/fast controls for evidence. Observer mode explicitly flushes stdout '
            'and writes a small repr sidecar at exit. Baseline controls measure that observer tax.','',
            'Minimal control does no application work. Harness control imports the common Django worker '
            'and its general loader dependencies without running main. Shared harness preparation is '
            'experimental overhead rather than an intrinsic cost of the dependency format.','']
    lines+=['## GC observed before finalization','',
            '| Workload | Mode | Collections (median) | GC wall ms | Collected objects (median) |',
            '| --- | --- | ---: | ---: | ---: |']
    for c in data['cases']:
        s=c['samples']
        if c['mode'] not in ('observed','batch') or not s:continue
        count=statistics.median(len(v['gc_events']) for v in s)
        wall=statistics.median(sum(e['wall_seconds'] for e in v['gc_events']) for v in s)*1000
        collected=statistics.median(sum(e['collected'] for e in v['gc_events']) for v in s)
        lines.append(f"| {c['workload']} | {c['mode']} | {count} | {wall:.3f} | {collected} |")
    lines+=['','GC callbacks are removed before final telemetry writing; finalization GC after that '
            'point is not captured. Recorded GC durations are nested within the lifecycle intervals '
            'and must not be added to them. The batch control changes GC/finalizer timing and is '
            'a workload-specific experiment, not a production recommendation. Worker VmHWM is sampled '
            'before deferred batch collection; any later finalizer allocations are outside that RSS '
            'sample. Absolute times can differ substantially from earlier runs; no speedup from '
            'characterization instrumentation is claimed.','']
    if data.get('profiles'):
        lines+=['## Separate execution profiles','',
                'One normal-exit profile process per workload, split at lifecycle boundaries. Profiled '
                'times are diagnostic self-time/call counts, never unprofiled benchmark observations. '
                'cProfile initialization precedes common imports and changes bootstrap import state; '
                'application dependency outputs/execution sets still validate. Interpreter startup '
                'before worker entry and finalization after the atexit callback are outside profiling. '
                'No cumulative-time summation is used. Raw per-function records and disjoint buckets '
                'are retained in profiles.json; profile phases include observer bookkeeping.','']
        for row in data['profiles']:
            lines.append(f"{row['workload']}: ")
            for phase in row['phases']:
                if phase['total_self_seconds']<.005:continue
                top=sorted(phase['buckets'].items(),key=lambda kv:kv[1],reverse=True)[:4]
                lines.append('- '+phase['phase']+': '+', '.join(f'{k} {v*1000:.1f} ms' for k,v in top))
            lines.append('')
    if data.get('diagnostics'):
        files=data['diagnostics']['bootstrap_source_compiles']
        lines+=['## Bootstrap source compilation audit','',
                f'A separate untimed compile audit preserves application outputs/execution sets and '
                f'records **{len(files)} consumer/harness source modules** compiled on startup, plus '
                'the worker script and fixture/dynamic code. No source text is retained. This is '
                'additional to the admitted dependency bytecode; the experimental harness itself '
                'has no generated caches under -B. Precompiled consumer bootstrap and narrower '
                'imports are concrete follow-up tests. Compilation events, sizes and a separate '
                'import-time graph are retained in diagnostics.json; import-time cumulative intervals '
                'overlap and are not summed into benchmark clocks.','']
    lines += ['## Interpretation', '',
              'Common consumer bootstrap and late finalization are substantial components of '
              'these commands. The common harness imports comparison adapters beyond the selected '
              'backend. Bootstrap source compilation and narrower imports are concrete follow-up '
              'tests, distinct from dependency-format costs. Profiled code/class construction '
              'suggests initialized-state reuse as a further experiment with explicit isolation, '
              'memory, invalidation and lifetime requirements. GC batching must be judged by '
              'full process time, including its deferred collection, rather than readiness alone. '
              'See ../../FINDINGS.md#whole-process-lifecycle-characterization for interpretation '
              'of the retained run. No bootstrap or reuse speedup is claimed here.', '']
    path.write_text('\n'.join(lines))


def diagnostics(command,expected,work):
    plan=work/'django-command.json';benchmark.write_json(plan,command)
    compiled=work/'django-compiles.json'
    audit=subprocess.run([sys.executable,'-I','-S','-B',str(benchmark.HERE/'compile_probe.py'),str(plan),str(compiled)],capture_output=True,text=True,check=True)
    imported=subprocess.run([command[0],'-X','importtime',*command[1:]],capture_output=True,text=True,check=True)
    for result in (audit,imported):
        sample=json.loads(result.stdout)
        for key in ('module_origins','executed_files','api_result','resource_hashes','source_inspection'):
            if sample[key]!=expected[key]:raise ValueError('diagnostic app differs: '+key)
    graph=work/'django-importtime.txt';graph.write_text(imported.stderr);rows=[]
    for line in imported.stderr.splitlines():
        match=re.match(r'import time:\s+(\d+)\s+\|\s+(\d+)\s+\|(.+)',line)
        if match:rows.append(dict(self_us=int(match[1]),inclusive_us=int(match[2]),module=match[3].strip()))
    events=json.loads(compiled.read_text())
    files=[e for e in events if Path(e['filename']).parent==benchmark.HERE and not e['filename'].endswith('/django_worker.py')]
    return dict(compile_events=events,bootstrap_source_compiles=files,import_graph_path=str(graph),import_rows=rows,
                probe_sha256=hashlib.sha256((benchmark.HERE/'compile_probe.py').read_bytes()).hexdigest())


def run(args):
    parent=json.loads(args.inputs.read_text());run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    work=benchmark.HERE/'_work'/('process-'+run_id);work.mkdir(parents=True);args.output.mkdir(parents=True,exist_ok=True)
    commands={'empty':[sys.executable,'-I','-S','-B',str(benchmark.HERE/'process_floor_worker.py'),'empty'],
              'harness':[sys.executable,'-I','-S','-B',str(benchmark.HERE/'process_floor_worker.py'),'harness']}
    references={}
    for w in ('1024','131072','django'):
        case=next(c for c in parent['cases'] if c['workload']==w and c['mode']=='compact')
        commands[w]=case['command'];references[w]=case['samples'][0]
    data=dict(run_id=run_id,parent_run=parent['run_id'],status='running',trials=args.trials,
              environment=benchmark.environment(work),cases=[],profiles=[])
    names=('process_phases.py','process_floor_worker.py','django_worker.py','catalog_worker.py','native_loader.py','native_catalog.py')
    data['implementation_sha256']={n:hashlib.sha256((benchmark.HERE/n).read_bytes()).hexdigest() for n in names}
    for w,command in commands.items():
        for mode in ('baseline','observed','batch','fast'):
            data['cases'].append(dict(workload=w,mode=mode,command=command,samples=[]))
    def validate(w,s):
        if not s['correct']:raise ValueError('incorrect worker')
        if w=='django':
            for k in ('module_origins','executed_files','api_result','resource_hashes','source_inspection','code_handoff_counts','stdlib_origins'):
                if s[k]!=references[w][k]:raise ValueError('application differs: '+k)
            if s['network_events']:raise ValueError('network attempted')
        elif w not in ('empty','harness'):
            if s['imported']!=33 or s['modules']!=int(w):raise ValueError('import count differs')
    def take(c,label):
        log=None if c['mode']=='baseline' else work/(c['workload']+'-'+c['mode']+'-'+label+'.phases')
        s=consume(c['command'],log,fast=c['mode']=='fast',batch=c['mode']=='batch');validate(c['workload'],s);return s
    for c in data['cases']:
        c['warmup']=take(c,'warmup');print('verified',c['workload'],c['mode'],flush=True)
    def checkpoint():
        benchmark.write_json(args.output/'results.json',data);render(data,args.output/'REPORT.md')
    checkpoint();rng=random.Random(20261106)
    for trial in range(args.trials):
        cases=data['cases'].copy();rng.shuffle(cases)
        for c in cases:c['samples'].append(take(c,str(trial)))
        checkpoint();print(f'lifecycle trials {trial+1}/{args.trials}',flush=True)
    for w,command in commands.items():
        prefix=work/(w+'-profile');log=work/(w+'-profile.phases')
        sample=consume(command,log,profile=prefix);validate(w,sample)
        data['profiles'].append(dict(workload=w,observation=sample,phases=profiles(prefix)))
        print('profiled',w,flush=True)
    benchmark.write_json(args.output/'profiles.json',data['profiles'])
    for row in data['profiles']:
        for phase in row['phases']:phase.pop('functions',None)
    data['diagnostics']=diagnostics(commands['django'],references['django'],work)
    benchmark.write_json(args.output/'diagnostics.json',data['diagnostics'])
    data['status']='complete';checkpoint()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,default=benchmark.HERE/'_work/runs/unified-catalog/results.json')
    parser.add_argument('--output',type=Path,default=benchmark.HERE/'_work/runs/process-characterization')
    parser.add_argument('--trials',type=int,default=15)
    args=parser.parse_args()
    if args.trials<1:parser.error('positive trials required')
    run(args)
