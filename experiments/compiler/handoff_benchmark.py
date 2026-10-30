"""Byte-identical zlib build: file outputs versus captured buffers passed to LLD."""
import argparse
from datetime import datetime, timezone
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
import pool_benchmark as pool

HERE=base.HERE
SYMBOL='_ZN4llvm12MemoryBuffer7getFileERKNS_5TwineEbbbSt8optionalINS_5AlignEE'
SOURCES=['handoff_bridge.cpp','handoff_impl.h','handoff_host.odin','handoff_benchmark.py',
         'pool_bridge.cpp','project_bridge.cpp','bridge.cpp','benchmark.py','project_benchmark.py','pool_benchmark.py']


def consume(case,inputs,export=False):
    output=Path(case['output'])
    for name in [*inputs['objects'],'libz.so']:(output/name).unlink(missing_ok=True)
    command=case['command'].copy()
    if export and case['handoff']=='direct':command[-1]='direct-export'
    before=resource.getrusage(resource.RUSAGE_CHILDREN);begin=time.perf_counter()
    p=project.run_checked(command,cwd=output)
    sample=json.loads(p.stdout) if case['kind']=='pool' else {}
    if p.stderr:raise ValueError(p.stderr)
    if case['kind']=='make':project.run_checked(case['link_command'],cwd=output)
    end=time.perf_counter();after=resource.getrusage(resource.RUSAGE_CHILDREN)
    sample.update(wall_seconds=end-begin,cpu_seconds=after.ru_utime-before.ru_utime+after.ru_stime-before.ru_stime,
        system_seconds=after.ru_stime-before.ru_stime,minor_faults=after.ru_minflt-before.ru_minflt)
    if sample.get('correct') is False or (case['kind']=='pool' and
        (sample['compiled']!=15 or sample['errors'] or sample['warnings'] or sample['link_calls']!=1 or
         not sample['can_run_again'] or sample['peak_active']>case['workers'])):raise ValueError('incomplete build')
    if case['handoff']=='direct':
        if sample['buffer_hits']!=15 or sample['buffer_misses'] or sample['buffer_bytes']!=sum(sample['object_sizes']):
            raise ValueError('object-buffer handoff not proven')
        present=[n for n in inputs['objects'] if (output/n).exists()]
        if present and not export:raise ValueError('direct link wrote object files')
        sample['object_files_absent']=not present
    if case['handoff'] in ('direct','buffer-file'):
        artifacts=dict(zip(inputs['objects'],sample['object_sha256']))
        if case['handoff']=='buffer-file' or export:
            if any(base.sha(output/n)!=h for n,h in artifacts.items()):raise ValueError('captured/exported bytes differ')
        artifacts['libz.so']=base.sha(output/'libz.so')
    else:artifacts=pool.hashes(output,inputs)
    sample['artifacts_sha256']=artifacts
    return sample


def report(data,path):
    lines=['# Direct compiler-to-linker object buffers','',f"Run `{data['run_id']}`; **{data['status']}**; {data['trials']} randomized warm-cache blocks.",'',
      'Fresh process per build, normal compiler disposal and process exit. Same zlib 1.3.2 inputs, '
      'Clang/LLD 22.1.8 flags, object order and single-threaded linker as the preceding queue experiment. '
      'File, buffer-file and direct cases use the same native binary. Buffer-file emits to memory then '
      'writes objects before linking; direct passes borrowed payloads to LLD without object files or memfd. '
      'The final shared library remains a real file.','',
      '| Mode | Whole process ms | Range ms | Child CPU ms | Compile wall ms | LLD call ms | Peak RSS MiB |',
      '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for c in data['cases']:
        s=c['samples']
        if not s:continue
        med=lambda k:statistics.median(x[k] for x in s)
        native=c['kind']=='pool';vals=[x['wall_seconds']*1000 for x in s]
        extra=[f"{med('compile_wall_ns')/1e6:.3f}",f"{med('link_ns')/1e6:.3f}",f"{med('peak_rss_bytes')/1048576:.2f}"] if native else ['—']*3
        lines.append(f"| {c['name']} | {statistics.median(vals):.3f} | {min(vals):.1f}–{max(vals):.1f} | {med('cpu_seconds')*1000:.3f} | "+' | '.join(extra)+' |')
    lines+=['','## Paired wall time','', '| Change | Median delta ms | Wins |','| --- | ---: | ---: |']
    cases={c['name']:c for c in data['cases']}
    pairs=[('physical-8-direct','make-8'),('physical-8-file','make-8'),('physical-8-direct','physical-8-file'),
           ('physical-8-buffer-file','physical-8-file'),('physical-8-direct','physical-8-buffer-file'),
           ('physical-1-direct','physical-1-file'),('memory-8-direct','memory-8-file'),('memory-8-direct','physical-8-direct')]
    for target,control in pairs:
        delta=[1000*(a['wall_seconds']-b['wall_seconds']) for a,b in zip(cases[target]['samples'],cases[control]['samples'])]
        if delta:lines.append(f"| {control} → {target} | {statistics.median(delta):+.3f} | {sum(x<0 for x in delta)}/{len(delta)} |")
    lines+=['','## Boundary and interpretation','',
      'Direct mode captures Clang object output in native SmallVector buffers. A Linux executable '
      'symbol interposition adapter, pinned to this LLVM ABI, substitutes MemoryBuffer::getFile '
      'only during the serialized embedded link. LLD retains its normal readFile/input/context bookkeeping '
      'and owns borrowed buffer wrappers; payloads outlive the link context. The symbol is delegated '
      'normally outside this scope. This is an experimental integration, not an upstream supported '
      'object-provider API or a proposed standard. No binary patching or LLD rebuild is used. Missing '
      'object lookups fail rather than reading stale files.','',
      'Timed direct runs require exactly 15 buffer hits, zero object misses and zero object files. '
      'All object SHA-256 values and shared libraries must match the prior CLI/file control. Each '
      'configuration warmup passes upstream normal/64-bit checks. Direct warmups export objects only '
      'after linking to let upstream make check inspect the existing artifacts; timed direct runs '
      'never export. Direct/buffer-file hashes are computed inside the child after the native workload '
      'clock; file hashes are checked outside the whole-process clock. Whole-process results therefore '
      'include a small extra validation cost for captured modes. All modes perform normal teardown.','',
      'Compile/link wall counters exclude process startup and final teardown. LLD call time excludes '
      'handoff map setup; whole-process time includes it. Buffer-file export times are per job and '
      'overlap across workers; their sum is not a wall-time savings estimate. The worker/job count '
      'is bounded but compiler memory and per-object byte size have no hard allocator cap. Warm cache '
      'is not cold storage. CPU and scheduling variance can overwhelm small I/O savings.','']
    path.write_text('\n'.join(lines))


def run(args):
    parent=json.loads((HERE/'_work/runs/zlib/results.json').read_text());inputs=parent['inputs']
    for n,h in inputs['source_sha256'].items():
        if base.sha(Path(n))!=h:raise ValueError('source changed: '+n)
    if base.sha(Path(inputs['bundle']))!=inputs['pin'] or base.sha(Path(inputs['plan']))!=inputs['plan_sha256']:raise ValueError('input pin mismatch')
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');work=HERE/'_work'/('handoff-'+run_id);work.mkdir()
    args.output.mkdir(parents=True,exist_ok=True)
    if args.host:host=args.host.resolve();build=dict(host_sha256=base.sha(host),external_host=str(host))
    else:host,build=base.build(args,work,bridge='handoff_bridge.cpp',odin_source='handoff_host.odin',extra_libraries=[
        args.llvm/'lib/liblldELF.so',args.llvm/'lib/liblldCommon.so','-ldl','-Wl,--export-dynamic-symbol='+SYMBOL])
    clang=args.llvm/'bin/clang';linker=args.llvm/'bin/ld.lld'
    link=[str(linker),'-shared','--threads=1','--build-id=sha1','-soname','libz.so.1','-o','libz.so',*inputs['objects']]
    linkplan=work/'link.gcr';linkplan.write_bytes(project.encode_requests([link]))
    data=dict(run_id=run_id,status='running',trials=args.trials,inputs=inputs,work=str(work),build=build,
        parent_run=parent['run_id'],link_command=link,link_plan_sha256=base.sha(linkplan),
        source_sha256={n:base.sha(HERE/n) for n in SOURCES},environment=parent['environment'],cases=[],upstream_tests=[])
    data['environment']={**data['environment'],'uname':list(os.uname()),'cpu_count':os.cpu_count(),'cache':'warm; no eviction'}
    data['toolchain_sha256']={str(p):base.sha(p) for p in (clang,linker,args.llvm/'lib/libclang-cpp.so',args.llvm/'lib/libLLVM.so.22.1',args.llvm/'lib/liblldELF.so',args.llvm/'lib/liblldCommon.so')}
    snapshots=work/'sources';snapshots.mkdir()
    for n in SOURCES:shutil.copy2(HERE/n,snapshots/n)
    data['source_snapshots']=str(snapshots)
    data['cases'].append(dict(name='make-8',kind='make',workers=8,handoff='file',output=inputs['root'],
        command=['make','-j8',*inputs['objects'],'CC='+str(clang),'CFLAGS='+shlex.join(inputs['flags'])],link_command=link,samples=[]))
    variants=[('physical',8,'file'),('physical',8,'buffer-file'),('physical',8,'direct'),
              ('physical',1,'file'),('physical',1,'direct'),('memory',8,'file'),('memory',8,'direct')]
    for mode,n,handoff in variants:
        name=f'{mode}-{n}-{handoff}';output=work/name;output.mkdir()
        command=[str(host),mode,str(clang),inputs['root'],inputs['bundle'],inputs['pin'],str(output),inputs['plan'],str(n),'internal',str(linker),str(linkplan),handoff]
        data['cases'].append(dict(name=name,kind='pool',workers=n,handoff=handoff,output=str(output),command=command,samples=[]))
    expected=json.loads((HERE/'_work/runs/pool-link/results.json').read_text())['cases'][0]['warmup']['artifacts_sha256']
    def take(case,export=False):
        s=consume(case,inputs,export)
        if s['artifacts_sha256']!=expected:raise ValueError('artifact identity changed: '+case['name'])
        return s
    for c in data['cases']:
        c['warmup']=take(c,True);result=pool.shared_tests(c,inputs,work)
        log=args.output/Path(result['log']).name;shutil.copy2(result['log'],log);result['log']=str(log)
        data['upstream_tests'].append(result);print('verified',c['name'],flush=True)
    # Ordinary linker diagnostics and successful reuse with retained borrowed objects.
    c=next(c for c in data['cases'] if c['name']=='memory-8-direct');out=Path(c['output']);cmd=c['command'].copy();cmd[9]='retry'
    p=project.run_checked(cmd,cwd=out);s=json.loads(p.stdout)
    if s['retry_result']==0 or s['link_calls']!=2 or not s['can_run_again'] or s['buffer_hits']!=15 or base.sha(out/'libz.so')!=expected['libz.so']:raise ValueError('direct linker reuse failed')
    data['checks']=[dict(check='link-error-then-success-same-process',passed=True,result=s,stderr=p.stderr)]
    blob=Path(inputs['bundle']).read_bytes();body=(Path(inputs['root'])/'zlib.h').read_bytes();offset=blob.index(body)
    replacement=b'#error gaia_direct_failure\n';replacement+=b' '*(len(body)-len(replacement))
    bad=work/'bad.gci';bad.write_bytes(blob[:offset]+replacement+blob[offset+len(body):]);cmd=c['command'].copy();cmd[4]=str(bad);cmd[5]=base.sha(bad)
    sentinel=b'previous published artifact';(out/'libz.so').write_bytes(sentinel)
    p=subprocess.run(cmd,cwd=out,capture_output=True,text=True,timeout=180);s=json.loads(p.stdout)
    if not p.returncode or not s['errors'] or s['link_calls'] or (out/'libz.so').read_bytes()!=sentinel:raise ValueError('compile failure publication gate')
    data['checks'].append(dict(check='compile-error-suppresses-link-preserves-output',passed=True,result=s,stderr=p.stderr))
    root=Path(inputs['root']);hidden=root.with_name(root.name+'-handoff-hidden');root.rename(hidden)
    try:s=take(c);data['checks'].append(dict(check='mapped-inputs-with-project-hidden',passed=True,result=s))
    finally:hidden.rename(root)
    # Existing stale file must never satisfy a missing captured object.
    missing=work/'missing.gcr';missing.write_bytes(project.encode_requests([[*link,'absent.o']]))
    (out/'absent.o').write_bytes(b'not an ELF object');cmd=c['command'].copy();cmd[11]=str(missing)
    p=subprocess.run(cmd,cwd=out,capture_output=True,text=True,timeout=180);s=json.loads(p.stdout)
    if not p.returncode or s['buffer_misses']!=1 or 'cannot open absent.o' not in p.stderr:raise ValueError('stale file fallback allowed')
    data['checks'].append(dict(check='missing-object-rejects-stale-file',passed=True,result=s,stderr=p.stderr));(out/'absent.o').unlink()
    def save():base.save(args.output/'results.json',data);report(data,args.output/'REPORT.md');base.save(args.output/'upstream-tests.json',data['upstream_tests'])
    save();rng=random.Random(20261104)
    for trial in range(args.trials):
        order=data['cases'].copy();rng.shuffle(order)
        for c in order:c['samples'].append(take(c))
        save();print(f'handoff block {trial+1}/{args.trials}',flush=True)
    for n,h in inputs['source_sha256'].items():
        if base.sha(Path(n))!=h:raise ValueError('input changed during run')
    if base.sha(host)!=build['host_sha256']:raise ValueError('host changed')
    data['status']='complete';save()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    base.toolchain_arguments(p)
    p.add_argument('--host',type=Path);p.add_argument('--trials',type=int,default=15)
    p.add_argument('--output',type=Path,default=HERE/'_work/runs/direct-handoff')
    args=p.parse_args()
    if args.trials<1:p.error('trials must be positive')
    run(args)
