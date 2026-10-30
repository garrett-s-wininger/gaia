"""Fresh versus repeated complete zlib builds, plus separate LLVM phase traces."""
from datetime import datetime,timezone
import json
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


def run():
    parent=json.loads((HERE/'_work/runs/direct-handoff/results.json').read_text());inputs=parent['inputs']
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');work=HERE/'_work'/('lifecycle-'+run_id);work.mkdir()
    out=HERE/'_work/runs/compiler-lifecycle';out.mkdir(exist_ok=True)
    host=HERE/'_work/followup-hosts/lifecycle/build/host';profile_host=HERE/'_work/followup-hosts/profile/build/host'
    template=next(c for c in parent['cases'] if c['name']=='physical-8-direct')['command']
    expected=parent['cases'][0]['warmup']['artifacts_sha256'];cases=[]
    for mode in ('file','direct'):
        for resident in (False,True):
            name=mode+('-repeat4' if resident else '-fresh4');output=work/name;output.mkdir()
            command=template.copy();command[0]=str(host);command[6]=str(output);command[-1]=mode
            cases.append(dict(name=name,mode=mode,resident=resident,output=str(output),command=command,samples=[]))
    d=dict(run_id=run_id,status='running',trials=7,builds_per_sample=4,parent_run=parent['run_id'],work=str(work),
        host_sha256=base.sha(host),profile_host_sha256=base.sha(profile_host),cases=cases,inputs=inputs,
        build_provenance={n:json.loads((HERE/f'_work/handoff-{n}/build.json').read_text()) for n in ('lifecycle','profile')},
        source_sha256={n:base.sha(HERE/n) for n in ('lifecycle_benchmark.py','lifecycle_bridge.cpp','lifecycle_host.odin','profile_bridge.cpp','pool_bridge.cpp','handoff_bridge.cpp','handoff_impl.h','handoff_host.odin','project_bridge.cpp','bridge.cpp')})
    sources=work/'sources';sources.mkdir()
    for n in d['source_sha256']:shutil.copy2(HERE/n,sources/n)
    d['source_snapshots']=str(sources)
    def take(c,count=4):
        output=Path(c['output'])
        for n in [*inputs['objects'],'libz.so']:(output/n).unlink(missing_ok=True)
        cpu_before=resource.getrusage(resource.RUSAGE_CHILDREN);begin=time.perf_counter_ns();records=[];launch=[];exit=[];groups=[]
        for _ in range(1 if c['resident'] else count):
            command=[*c['command'],str(count if c['resident'] else 1)]
            entered=time.perf_counter_ns();p=project.run_checked(command,cwd=output);ended=time.perf_counter_ns()
            if p.stderr:raise ValueError(p.stderr)
            rows=[json.loads(x) for x in p.stdout.splitlines()];builds=[x for x in rows if 'correct' in x]
            if len(builds)!=(count if c['resident'] else 1):raise ValueError('build skipped')
            if any(not x['correct'] or x['compiled']!=15 or x['link_calls']!=1 or x['errors'] or x['warnings'] or not x['can_run_again'] for x in builds):raise ValueError('incomplete iteration')
            if c['mode']=='direct':
                for x in builds:
                    if x['buffer_hits']!=15 or x['buffer_misses'] or dict(zip(inputs['objects'],x['object_sha256']))!={n:expected[n] for n in inputs['objects']}:raise ValueError('repeat objects differ')
                if any((output/n).exists() for n in inputs['objects']):raise ValueError('direct wrote objects')
            else:
                if any(base.sha(output/n)!=expected[n] for n in inputs['objects']):raise ValueError('file objects differ')
            if base.sha(output/'libz.so')!=expected['libz.so']:raise ValueError('shared library differs')
            # Child C++ steady_clock and parent perf_counter both CLOCK_MONOTONIC.
            launch.append(rows[0]['ns']-entered);exit.append(ended-rows[-1]['ns'])
            if launch[-1]<0 or exit[-1]<0:raise ValueError('clock domains differ')
            records+=builds;groups.append(rows)
        ended=time.perf_counter_ns();after=resource.getrusage(resource.RUSAGE_CHILDREN)
        # The whole group includes parent-side artifact checks for fresh mode.
        # Also retain sum of actual subprocess intervals for a boundary without those checks.
        process_ns=sum((g[-1]['ns']-g[0]['ns'])+l+e for g,l,e in zip(groups,launch,exit))
        return dict(wall_seconds=(ended-begin)/1e9,process_seconds=process_ns/1e9,per_build_seconds=process_ns/1e9/count,
            cpu_seconds=after.ru_utime-cpu_before.ru_utime+after.ru_stime-cpu_before.ru_stime,
            launch_to_main_ns=launch,after_main_ns=exit,builds=records,events=groups)
    for c in cases:c['warmup']=take(c,1)
    def report():
        lines=['# Compiler process lifetime and phase attribution','',f"Run `{run_id}`; **{d['status']}**; seven randomized blocks, four complete zlib builds per observation.",'',
         'Fresh4 launches four processes; repeat4 launches once and performs four independent complete builds. '
         'Each iteration admits requests, starts/joins workers, creates/disposes compiler state and objects, '
         'and links again. No completed-object or AST reuse. This is an in-process batch, not a daemon/IPC protocol. '
         'Same executable and immutable inputs for all controls.','',
         '| Mode | Per-build process ms | CPU per build ms | Launch → main ms per launch | After main ms per exit |',
         '| --- | ---: | ---: | ---: | ---: |']
        for c in cases:
            if not c['samples']:continue
            med=lambda k:statistics.median(x[k] for x in c['samples'])
            entry=statistics.median(v/1e6 for x in c['samples'] for v in x['launch_to_main_ns'])
            exit=statistics.median(v/1e6 for x in c['samples'] for v in x['after_main_ns'])
            lines.append(f"| {c['name']} | {med('per_build_seconds')*1000:.3f} | {med('cpu_seconds')*1000/4:.3f} | {entry:.3f} | {exit:.3f} |")
        lines+=['','| Paired change | Median per-build delta ms | Wins |','| --- | ---: | ---: |']
        by={c['name']:c for c in cases}
        for mode in ('file','direct'):
            delta=[(x['per_build_seconds']-y['per_build_seconds'])*1000 for x,y in zip(by[mode+'-repeat4']['samples'],by[mode+'-fresh4']['samples'])]
            if delta:lines.append(f"| {mode}: fresh → repeat | {statistics.median(delta):+.3f} | {sum(x<0 for x in delta)}/{len(delta)} |")
        lines+=['','Per-build process time is the sum of measured subprocess intervals divided by four; parent '
            'artifact verification between fresh processes is excluded. Group wall time including those checks '
            'is retained separately. Launch-to-main includes process creation, loader/runtime initialization '
            'and scheduling; after-main includes reporting/exit/teardown and parent completion observation. '
            'These are observed clock boundaries, not exclusively loader/destructor CPU. Child clocks use '
            'C++ steady_clock; nonnegative alignment with parent Linux perf_counter is checked.','',
            'Every iteration reports 15 fresh compilations and one link. Every captured object identity '
            'matches; every process output library matches. File-mode objects are verified after each process '
            '(only the final iteration of repeat4 is externally inspectable). Direct mode creates no object '
            'files. Warmups and timed runs use normal cleanup. Phase profiles are separate instrumented '
            'runs and never included in these latency observations.','']
        if d.get('profiles'):
            lines+=['## Separate instrumented compiler phases','',
                '| Workers | Sum job spans ms | Frontend ms | Backend ms | Optimizer ms | CodeGenPasses ms |',
                '| --- | ---: | ---: | ---: | ---: | ---: |']
            for profile in d['profiles']:
                totals=profile['event_totals_us']
                lines.append('| '+str(profile['workers'])+' | '+' | '.join(f"{totals.get(n,0)/1000:.3f}" for n in ('GaiaJob','Frontend','Backend','Optimizer','CodeGenPasses'))+' |')
            lines+=['','These are sums of trace event durations across jobs, not CPU-time samples. '
                'Eight-worker spans overlap and include descheduling. Backend contains optimizer/codegen '
                'subphases; those columns must not be added together. Trace instrumentation adds overhead '
                'and is never used to infer whole-build speedups. Full traces and all event totals are retained.','']
        (out/'REPORT.md').write_text('\n'.join(lines));base.save(out/'results.json',d)
    report();rng=random.Random(20261106)
    for i in range(7):
        order=cases.copy();rng.shuffle(order)
        for c in order:c['samples'].append(take(c));print('lifecycle block',i+1,c['name'],flush=True)
        report()
    # Separate diagnostic-only traces, with main-thread aggregation after workers finish.
    d['profiles']=[]
    for workers in (1,8):
        output=work/f'profile-{workers}';output.mkdir();cmd=template.copy();cmd[0]=str(profile_host);cmd[6]=str(output);cmd[8]=str(workers)
        p=project.run_checked(cmd,cwd=output);s=json.loads(p.stdout)
        if not s['correct'] or s['buffer_hits']!=15 or base.sha(output/'libz.so')!=expected['libz.so']:raise ValueError('profile artifacts differ')
        if dict(zip(inputs['objects'],s['object_sha256']))!={n:expected[n] for n in inputs['objects']}:raise ValueError('profile objects differ')
        trace=json.loads((output/'compiler-trace.json').read_text());totals={}
        for e in trace['traceEvents']:
            if e.get('name','').startswith('Total '):totals[e['name'][6:]]=e.get('dur',0)
        # Preserve native units (microseconds) and raw trace for independent review.
        target=out/f'compiler-{workers}-trace.json';shutil.copy2(output/'compiler-trace.json',target)
        event_totals={}
        for e in trace['traceEvents']:
            if e.get('ph')=='X' and not e.get('name','').startswith('Total '):
                event_totals[e['name']]=event_totals.get(e['name'],0)+e.get('dur',0)
        d['profiles'].append(dict(workers=workers,command=cmd,result=s,totals_us=totals,event_totals_us=event_totals,trace=str(target)))
        print('phase profile',workers,flush=True)
    for n,h in inputs['source_sha256'].items():
        if base.sha(Path(n))!=h:raise ValueError('input changed')
    if base.sha(host)!=d['host_sha256'] or base.sha(profile_host)!=d['profile_host_sha256']:raise ValueError('host changed')
    d['status']='complete';report()

if __name__=='__main__':run()
