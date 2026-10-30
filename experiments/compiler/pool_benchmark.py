"""Bounded Odin compiler workers followed by embedded LLD; same zlib inputs."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import random
import resource
import shlex
import shutil
import statistics
import subprocess
import time

import benchmark as base
import project_benchmark as project

HERE=base.HERE


def shared_tests(case,inputs,work):
    stage=work/('check-'+case['name'])
    shutil.copytree(inputs['root'],stage,ignore=shutil.ignore_patterns('*.o','*.a','*.so*'))
    for name in [*inputs['objects'],'libz.so']:shutil.copy2(Path(case['output'])/name,stage/name)
    (stage/'libz.so.1').symlink_to('libz.so')
    reference=hashes(stage,inputs)
    p=project.run_checked(['make','-j1','check','STATICLIB=libz.so','TEST_LIBS=libz.so'],cwd=stage,
                          env={**os.environ,'LD_LIBRARY_PATH':str(stage)})
    if hashes(stage,inputs)!=reference:raise ValueError('upstream tests rebuilt the library')
    if '*** zlib test OK ***' not in p.stdout or '*** zlib 64-bit test OK ***' not in p.stdout:
        raise ValueError('shared-library upstream checks absent')
    log=work/(case['name']+'-shared-check.txt');log.write_text(p.stdout+p.stderr)
    if 'libz.a' in p.stdout:raise ValueError('tests used the static library')
    return dict(name=case['name'],passed=True,shared_library=True,library_unchanged=True,log=str(log))


def hashes(output,inputs):return {n:base.sha(output/n) for n in [*inputs['objects'],'libz.so']}


def consume(case,inputs):
    output=Path(case['output'])
    for name in [*inputs['objects'],'libz.so']:(output/name).unlink(missing_ok=True)
    before=resource.getrusage(resource.RUSAGE_CHILDREN);begin=time.perf_counter()
    p=project.run_checked(case['command'],cwd=output)
    compiled=time.perf_counter();sample=json.loads(p.stdout) if case['kind']=='pool' else {}
    if p.stderr:raise ValueError('unexpected diagnostics: '+p.stderr)
    if sample:
        if not sample['correct'] or sample['compiled']!=len(inputs['sources']) or sample['errors'] or sample['warnings']:
            raise ValueError('compiler pool incomplete')
        if sample['peak_active']>case['workers'] or not sample['peak_active']:raise ValueError('worker bound violated')
        if sample['link_calls']!=(1 if case['link']=='internal' else 0):raise ValueError('link phase count differs')
        if not sample['can_run_again']:raise ValueError('linker process cannot be reused')
    if case['link']=='external':project.run_checked(case['link_command'],cwd=output)
    ended=time.perf_counter();after=resource.getrusage(resource.RUSAGE_CHILDREN)
    sample.update(wall_seconds=ended-begin,compiler_process_seconds=compiled-begin,external_link_seconds=ended-compiled,
        cpu_seconds=after.ru_utime-before.ru_utime+after.ru_stime-before.ru_stime,
        system_seconds=after.ru_stime-before.ru_stime,minor_faults=after.ru_minflt-before.ru_minflt)
    sample['artifacts_sha256']=hashes(output,inputs)
    return sample


def checks(case,inputs,work,expected):
    results=[];output=Path(case['output']);command=case['command'].copy()
    # Ordinary LLD diagnostic failure followed by successful reuse in this same
    # host; all compiler workers have already joined before either link call.
    command[9]='retry'
    p=project.run_checked(command,cwd=output);r=json.loads(p.stdout)
    if r['retry_result']==0 or r['link_calls']!=2 or not r['can_run_again'] or hashes(output,inputs)!=expected:
        raise ValueError('linker diagnostic recovery failed')
    results.append(dict(check='link-error-then-success-same-process',correct=True,result=r,stderr=p.stderr))
    blob=Path(inputs['bundle']).read_bytes();bad=work/'compile-error.gci'
    # Replace a required header with equal-length invalid bytes; retain record
    # framing and use a new trusted pin to exercise actual concurrent diagnostics.
    marker=Path(inputs['root'])/'zlib.h';body=marker.read_bytes();offset=blob.index(body)
    replacement=(b'#error gaia_pool_failure\n'+b' '*(len(body)-len(b'#error gaia_pool_failure\n')))
    bad.write_bytes(blob[:offset]+replacement+blob[offset+len(body):])
    command=case['command'].copy();command[4]=str(bad);command[5]=base.sha(bad)
    sentinel=b'previous-published-artifact';(output/'libz.so').write_bytes(sentinel)
    p=subprocess.run(command,cwd=output,capture_output=True,text=True,timeout=180);r=json.loads(p.stdout)
    if not p.returncode or r['link_calls'] or not r['errors'] or (output/'libz.so').read_bytes()!=sentinel:
        raise ValueError('failed compile reached linker/published output')
    results.append(dict(check='compile-error-suppresses-link-and-preserves-output',correct=True,result=r,stderr=p.stderr))
    # No physical project inputs can satisfy a missing VFS lookup.
    root=Path(inputs['root']);hidden=root.with_name(root.name+'-pool-hidden');root.rename(hidden)
    try:
        p=project.run_checked(case['command'],cwd=output);r=json.loads(p.stdout)
        if hashes(output,inputs)!=expected:raise ValueError('hidden project pipeline differs')
        results.append(dict(check='mapped-parallel-build-with-project-hidden',correct=True,result=r))
    finally:hidden.rename(root)
    return results


def report(data,path):
    lines=['# Bounded compiler queue and in-process ELF linking','',
        f"Run `{data['run_id']}`; **{data['status']}**. {data['trials']} randomized blocks; warm cache; fresh process per build.",'',
        'Same admitted zlib source/configuration/system headers as the real-project run. This '
        'comparison produces a real shared ELF library, not the previous static archive. All '
        'controls use the same Clang and LLD versions/options, fixed object order and single-threaded '
        'linker. Make controls compile the 15 object targets and invoke external LLD; pool controls '
        'use a fixed Odin worker set draining at most 64 admitted jobs, then join all workers before '
        'one serialized link. Object files remain file-backed and are read by LLD.','',
        '| Mode | Complete build ms | Range ms | Aggregate child CPU ms | Native compile wall ms | Link stage ms | Native peak RSS MiB |',
        '| --- | ---: | --- | ---: | ---: | ---: | ---: |']
    for c in data['cases']:
        s=c['samples']
        if not s:continue
        med=lambda k:statistics.median(v[k] for v in s)
        vals=[v['wall_seconds']*1000 for v in s];native=c['kind']=='pool'
        compile_ms=f"{med('compile_wall_ns')/1e6:.3f}" if native else '—'
        link_ms=f"{med('link_ns')/1e6:.3f}" if native and c['link']=='internal' else f"{med('external_link_seconds')*1000:.3f}"
        rss=f"{med('peak_rss_bytes')/1048576:.2f}" if native else '—'
        lines.append(f"| {c['name']} | {statistics.median(vals):.3f} | {min(vals):.1f}–{max(vals):.1f} | {med('cpu_seconds')*1000:.3f} | {compile_ms} | {link_ms} | {rss} |")
    lines+=['','## Paired complete-build comparisons','',
            '| Comparison | Median change ms | Wins / blocks |','| --- | ---: | ---: |']
    cases={c['name']:c for c in data['cases']}
    names=[(f'memory-{n}-internal',f'make-{data["jobs"]}') for n in data['workers']]
    names += [(f'memory-{data["jobs"]}-internal',f'memory-{data["jobs"]}-external'),
              (f'memory-{data["jobs"]}-internal',f'physical-{data["jobs"]}-internal')]
    for mode,control in names:
        if mode not in cases or control not in cases:continue
        delta=[(a['wall_seconds']-b['wall_seconds'])*1000 for a,b in zip(cases[mode]['samples'],cases[control]['samples'])]
        if delta:lines.append(f"| {control} → {mode} | {statistics.median(delta):+.3f} | {sum(v<0 for v in delta)}/{len(delta)} |")
    lines+=['','Link stage means the embedded LLD call (including context cleanup) or the complete '
        'external linker process, including startup/exit. These are intentionally different process '
        'boundaries; whole-build time remains decisive. Native peak RSS is the single multithreaded process VmHWM, including compiler/linker '
        'libraries. Make/child-process aggregate peak memory is not available here, so no memory '
        'comparison with make is implied. Worker counts bound concurrent frontend instances, not '
        'compiler memory in bytes. Native job intervals and peak active job count are retained. '
        'Each worker has private VFS metadata/current directory; every request has private compiler, '
        'LLVMContext and diagnostics. Only immutable payload bytes/argument vectors share. No PCH, '
        'AST/result cache, output-memory shortcut or successful fast exit is used.','',
        'A compile error stops new dispatch, drains/joins active workers and suppresses linking. '
        'The final link uses declared object order, not completion order. LLD is never invoked '
        'concurrently, and canRunAgain is checked. An unrecoverable linker context retires the '
        'process. Ordinary linker failure/reuse and compile-error publication suppression are '
        'tested separately. This is one finite target batch, not a persistent daemon or general '
        'build DAG/service protocol.','']
    path.write_text('\n'.join(lines))


def run(args):
    parent=json.loads(args.inputs.read_text());inputs=parent['inputs']
    for name,pin in inputs['source_sha256'].items():
        if base.sha(Path(name))!=pin:raise ValueError('admitted input changed: '+name)
    if base.sha(Path(inputs['bundle']))!=inputs['pin'] or base.sha(Path(inputs['plan']))!=inputs['plan_sha256']:
        raise ValueError('admitted bundle/plan changed')
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');work=HERE/'_work'/('pool-'+run_id);work.mkdir()
    args.output.mkdir(parents=True,exist_ok=True)
    if args.host:host=args.host.resolve();build=dict(host_sha256=base.sha(host),external_host=str(host))
    else:host,build=base.build(args,work,bridge='pool_bridge.cpp',odin_source='pool_host.odin',
        extra_libraries=[args.llvm/'lib/liblldELF.so',args.llvm/'lib/liblldCommon.so'])
    clang=args.llvm/'bin/clang';linker=args.llvm/'bin/ld.lld'
    link=[str(linker),'-shared','--threads=1','--build-id=sha1','-soname','libz.so.1','-o','libz.so',*inputs['objects']]
    linkplan=work/'link.gcr';linkplan.write_bytes(project.encode_requests([link]))
    data=dict(run_id=run_id,status='running',parent_run=parent['run_id'],work=str(work),trials=args.trials,
        jobs=args.jobs,workers=args.workers,inputs=inputs,build=build,link_command=link,link_plan_sha256=base.sha(linkplan),
        source_sha256={n:base.sha(HERE/n) for n in ('pool_bridge.cpp','pool_host.odin','project_bridge.cpp','bridge.cpp','pool_benchmark.py','benchmark.py')},
        environment={**parent['environment'],'uname':list(os.uname()),'cpu_count':os.cpu_count(),
            'clang_version':subprocess.check_output([str(clang),'--version'],text=True).strip(),
            'lld_version':subprocess.check_output([str(linker),'--version'],text=True).strip(),
            'cache':'warm; no eviction'},
        toolchain_sha256={str(p):base.sha(p) for p in (clang,linker,args.llvm/'lib/libclang-cpp.so',
            args.llvm/'lib/libLLVM.so.22.1',args.llvm/'lib/liblldELF.so',args.llvm/'lib/liblldCommon.so')},cases=[])
    sources=work/'sources';sources.mkdir()
    for name in data['source_sha256']:shutil.copyfile(HERE/name,sources/name)
    data['source_snapshots']=str(sources)
    for n in sorted({1,args.jobs}):
        data['cases'].append(dict(name=f'make-{n}',kind='make',workers=n,link='external',output=inputs['root'],
            command=['make',f'-j{n}',*inputs['objects'],'CC='+str(clang),'CFLAGS='+shlex.join(inputs['flags'])],
            link_command=link,samples=[]))
    variants=[('memory',n,'internal') for n in args.workers]+[('memory',args.jobs,'external'),('physical',args.jobs,'internal')]
    for mode,n,kind in variants:
        name=f'{mode}-{n}-{kind}';output=work/name;output.mkdir()
        command=[str(host),mode,str(clang),inputs['root'],inputs['bundle'],inputs['pin'],str(output),inputs['plan'],str(n),kind,str(linker),str(linkplan)]
        data['cases'].append(dict(name=name,kind='pool',workers=n,link=kind,output=str(output),command=command,link_command=link,samples=[]))
    reference=None;old=next(c for c in parent['cases'] if c['mode']=='cli-batch')['warmup']['artifacts_sha256']
    def take(case):
        nonlocal reference
        sample=consume(case,inputs)
        if any(sample['artifacts_sha256'][n]!=old[n] for n in inputs['objects']):raise ValueError('object bytes differ from prior CLI')
        if reference is None:reference=sample['artifacts_sha256']
        elif reference!=sample['artifacts_sha256']:raise ValueError('ELF/object bytes differ')
        return sample
    data['upstream_tests']=[]
    for case in data['cases']:
        case['warmup']=take(case);data['upstream_tests'].append(shared_tests(case,inputs,work))
        print('verified shared library and upstream tests:',case['name'],flush=True)
    test=next(c for c in data['cases'] if c['name']==f'memory-{args.jobs}-internal')
    data['checks']=checks(test,inputs,work,reference)
    def checkpoint():base.save(args.output/'results.json',data);report(data,args.output/'REPORT.md')
    checkpoint();rng=random.Random(20261103)
    for trial in range(args.trials):
        shuffled=data['cases'].copy();rng.shuffle(shuffled)
        for case in shuffled:case['samples'].append(take(case))
        checkpoint();print(f'queue/link trials {trial+1}/{args.trials}',flush=True)
    for name,pin in inputs['source_sha256'].items():
        if base.sha(Path(name))!=pin:raise ValueError('input changed during run')
    if base.sha(host)!=build['host_sha256']:raise ValueError('host changed')
    data['status']='complete';checkpoint()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,default=HERE/'_work/runs/zlib/results.json')
    base.toolchain_arguments(parser)
    parser.add_argument('--host',type=Path)
    parser.add_argument('--workers',type=int,nargs='+',default=[1,2,4,8])
    parser.add_argument('--jobs',type=int,default=8)
    parser.add_argument('--trials',type=int,default=15)
    parser.add_argument('--output',type=Path,default=HERE/'_work/runs/pool-link')
    args=parser.parse_args()
    if args.trials<1 or not 1<=args.jobs<=16 or any(not 1<=n<=16 for n in args.workers):parser.error('positive trials; workers/jobs 1..16')
    if len(set(args.workers))!=len(args.workers) or args.jobs not in args.workers:parser.error('unique worker counts must include jobs')
    args.llvm=args.llvm.resolve();args.llvm_headers=args.llvm_headers.resolve()
    run(args)
