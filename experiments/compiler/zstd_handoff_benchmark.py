"""Larger real C project: upstream Zstd release/debug, file versus direct handoff."""
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
PIN='eb33e51f49a15e023950cd7825ca74a4a2b43db8354825ac24fc1b7ee09e6fa3'


def report(d,path):
    lines=['# Zstandard object-buffer handoff','',f"Run `{d['run_id']}`; **{d['status']}**; {d['trials']} randomized blocks; warm cache.",'',
      'Zstandard 1.5.7, upstream dynamic-library C sources, legacy support off and upstream ZSTD_NO_ASM=1. '
      'Upstream release -O3 flags are retained; debug adds -g. This is the library target, not the entire '
      'Zstd repository. All controls share compile flags, ordered objects and single-threaded LLD. '
      'Native file/direct use the same binary. Fresh process per complete build, normal teardown. '
      'The CLI control uses a generated makefile containing the same admitted compile commands and external LLD; '
      'it is not a measurement of upstream makefile configuration overhead.','',
      '| Configuration | Whole build ms | CPU ms | Compile wall ms | LLD ms | Object MiB | Peak RSS MiB |',
      '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for c in d['cases']:
        s=c['samples']
        if not s:continue
        med=lambda k:statistics.median(x[k] for x in s)
        native=c['mode']!='cli'
        more=[f"{med('compile_wall_ns')/1e6:.2f}",f"{med('link_ns')/1e6:.2f}"] if native else ['—','—']
        more+=[f"{med('object_bytes')/1048576:.3f}",f"{med('peak_rss_bytes')/1048576:.2f}" if native else '—']
        lines.append(f"| {c['name']} | {med('wall_seconds')*1000:.2f} | {med('cpu_seconds')*1000:.2f} | "+' | '.join(more)+' |')
    lines+=['','| Paired comparison | Median delta ms | Wins |','| --- | ---: | ---: |']
    for config in ('release','debug'):
        cases={c['mode']:c for c in d['cases'] if c['config']==config}
        for target,control in [('direct','file'),('file','cli'),('direct','cli')]:
            delta=[1000*(x['wall_seconds']-y['wall_seconds']) for x,y in zip(cases[target]['samples'],cases[control]['samples'])]
            if delta:lines.append(f"| {config}: {control} → {target} | {statistics.median(delta):+.2f} | {sum(x<0 for x in delta)}/{len(delta)} |")
    lines+=['','Direct mode must record one borrowed buffer hit per TU, zero missing-object lookups and zero '
      'object files. Every timed object SHA-256 and shared ELF must match the matching CLI warmup. '
      'Direct object hashing occurs inside the child after its native workload clock and remains in '
      'whole-process time; file hashes are checked after timing. No output cache, PCH or compiler option '
      'changes between modes. Native peak RSS includes loaded toolchain and retained object buffers, '
      'and is not an aggregate process-tree measure for CLI.','',
      'Before timings, upstream simple and streaming compression/decompression examples exercise each '
      'library on empty, small and 1 MiB deterministic data; round-trip bytes must match. Loader resolution '
      'is checked against the measured library. This is a focused public-API check, not the full upstream '
      'fuzzer/test suite. Source pins and host identity are checked. Prior zlib diagnostic/failure tests '
      'cover this same native adapter; this run does not extend crash isolation guarantees.','']
    path.write_text('\n'.join(lines))


def run(a):
    source=a.source.resolve();lib=source/'lib'
    if a.host is None:
        prior=json.loads((HERE/'_work/runs/direct-handoff/results.json').read_text())
        a.host=Path(next(c for c in prior['cases'] if c['name']=='physical-8-direct')['command'][0])
    host=a.host.resolve();clang=a.llvm.resolve()/'bin/clang';lld=a.llvm.resolve()/'bin/ld.lld'
    if base.sha(HERE/'_work/downloads/zstd-1.5.7.tar.gz')!=PIN:raise ValueError('archive identity')
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');work=HERE/'_work'/('zstd-handoff-'+run_id);work.mkdir()
    a.output.mkdir(parents=True,exist_ok=True)
    dry=project.run_checked(['make','-n','libzstd.so.1.5.7','ZSTD_LEGACY_SUPPORT=0','ZSTD_NO_ASM=1','CC='+str(clang)],cwd=lib)
    (a.output/'upstream-plan.txt').write_text(dry.stdout)
    commands=[]
    for line in dry.stdout.splitlines():
        if not line.startswith(str(clang)+' '):continue
        args=shlex.split(line)
        if '-c' not in args:continue
        args=[x for x in args if x not in ('-MMD','-MP')]
        src=next(x for x in args if x.endswith('.c'));args[args.index(src)]=str(Path(src).resolve())
        i=args.index('-o')+1;args[i]=Path(args[i]).name
        commands.append(args)
    objects=[x[x.index('-o')+1] for x in commands]
    if not commands or len(commands)>64 or len(set(objects))!=len(objects):raise ValueError('invalid admitted jobs')
    d=dict(run_id=run_id,status='running',trials=a.trials,work=str(work),source=str(source),source_archive_sha256=PIN,
       source_url='https://github.com/meta/zstd/releases/download/v1.5.7/zstd-1.5.7.tar.gz',workers=8,
       host=str(host),host_sha256=base.sha(host),jobs=len(commands),objects=objects,cases=[],validation=[],
       source_sha256={str(p):base.sha(p) for p in source.rglob('*') if p.is_file() and p.suffix in ('.c','.h','.S','.mk')},
       environment=dict(uname=list(os.uname()),cpu_count=os.cpu_count(),cache='warm; no eviction'),
       toolchain_sha256={str(p):base.sha(p) for p in (clang,lld,a.llvm.resolve()/'lib/libclang-cpp.so',a.llvm.resolve()/'lib/libLLVM.so.22.1',a.llvm.resolve()/'lib/liblldELF.so')})
    snapshots=work/'sources';snapshots.mkdir()
    names=['zstd_handoff_benchmark.py','handoff_bridge.cpp','handoff_impl.h','handoff_host.odin','pool_bridge.cpp','project_bridge.cpp','bridge.cpp']
    d['adapter_source_sha256']={n:base.sha(HERE/n) for n in names}
    for n in names:shutil.copy2(HERE/n,snapshots/n)
    d['source_snapshots']=str(snapshots)
    # Same API examples are linked once, then pointed at each actual measured library.
    examples=[]
    def validate(c):
        out=Path(c['output']);env={**os.environ,'LD_LIBRARY_PATH':str(out)}
        if not examples:
            for n in ('simple_compression','simple_decompression','streaming_compression','streaming_decompression'):
                exe=work/n;project.run_checked([str(clang),'-O2','-I'+str(lib),str(source/'examples'/f'{n}.c'),'-L'+str(out),'-lzstd','-o',str(exe)])
                examples.append(exe)
        listing=project.run_checked(['ldd',str(examples[0])],env=env).stdout
        if str(out/'libzstd.so.1') not in listing:raise ValueError('test loaded a different zstd library')
        logs=[listing]
        for size in (0,73,1048576):
            inp=work/'test-input';body=bytes(((i*37)^(i//97))&255 for i in range(size));inp.write_bytes(body)
            for compressor in (examples[0],examples[2]):
                archive=work/'test-input.zst'
                p=project.run_checked([str(compressor),str(inp)],env=env);logs.append(p.stdout+p.stderr)
                if compressor==examples[0]:
                    p=project.run_checked([str(examples[1]),str(archive)],env=env);logs.append(p.stdout+p.stderr)
                p=subprocess.run([str(examples[3]),str(archive)],env=env,capture_output=True,timeout=180)
                if p.returncode or p.stdout!=body:raise ValueError('round-trip bytes differ')
                logs.append(f'{compressor.name}: {size} bytes round-trip matched')
        log=a.output/(c['name']+'-examples.txt');log.write_text('\n'.join(logs));return dict(case=c['name'],passed=True,roundtrips=6,log=str(log))
    for config in ('release','debug'):
        plan_commands=[[*x,*(['-g','-fdebug-compilation-dir='+str(lib)] if config=='debug' else [])] for x in commands]
        plan=work/(config+'.gcr');plan.write_bytes(project.encode_requests(plan_commands))
        link=[str(lld),'-shared','--threads=1','--build-id=sha1','-soname','libzstd.so.1','-o','libzstd.so',*objects]
        linkplan=work/(config+'-link.gcr');linkplan.write_bytes(project.encode_requests([link]))
        for mode in ('cli','file','direct'):
            name=config+'-'+mode;out=work/name;out.mkdir();(out/'libzstd.so.1').symlink_to('libzstd.so')
            if mode=='cli':
                mf=out/'Makefile';text='all: libzstd.so\nlibzstd.so: '+' '.join(objects)+'\n\t'+shlex.join(link)+'\n'
                for cmd,obj in zip(plan_commands,objects):text+=obj+':\n\t'+shlex.join(cmd)+'\n'
                mf.write_text(text);command=['make','-s','-j8']
            else:command=[str(host),'physical',str(clang),str(lib),'-','-',str(out),str(plan),'8','internal',str(lld),str(linkplan),mode]
            d['cases'].append(dict(name=name,config=config,mode=mode,output=str(out),command=command,plan_sha256=base.sha(plan),commands=plan_commands,link_command=link,samples=[]))
    refs={}
    def take(c):
        out=Path(c['output'])
        for n in [*objects,'libzstd.so']:(out/n).unlink(missing_ok=True)
        before=resource.getrusage(resource.RUSAGE_CHILDREN);t=time.perf_counter();p=project.run_checked(c['command'],cwd=out);elapsed=time.perf_counter()-t;after=resource.getrusage(resource.RUSAGE_CHILDREN)
        if p.stderr:raise ValueError(p.stderr)
        s=json.loads(p.stdout) if c['mode']!='cli' else {}
        if s and (not s['correct'] or s['compiled']!=len(objects) or s['errors'] or s['warnings'] or s['link_calls']!=1 or not s['can_run_again'] or s['peak_active']>8):raise ValueError('incomplete native result')
        if c['mode']=='direct':
            if s['buffer_hits']!=len(objects) or s['buffer_misses'] or any((out/n).exists() for n in objects):raise ValueError('direct materialization/provider failure')
            hashes=dict(zip(objects,s['object_sha256']));size=sum(s['object_sizes']);s['object_files_absent']=True
        else:hashes={n:base.sha(out/n) for n in objects};size=sum((out/n).stat().st_size for n in objects)
        hashes['libzstd.so']=base.sha(out/'libzstd.so')
        if c['config'] not in refs:refs[c['config']]=hashes
        elif hashes!=refs[c['config']]:raise ValueError('object/library bytes differ')
        s.update(wall_seconds=elapsed,cpu_seconds=after.ru_utime-before.ru_utime+after.ru_stime-before.ru_stime,
                 system_seconds=after.ru_stime-before.ru_stime,object_bytes=size,artifacts_sha256=hashes)
        return s
    for c in d['cases']:
        c['warmup']=take(c);d['validation'].append(validate(c));print('verified',c['name'],c['warmup']['wall_seconds'],c['warmup']['object_bytes'],flush=True)
    def save():base.save(a.output/'results.json',d);report(d,a.output/'REPORT.md')
    save();rng=random.Random(20261105)
    for i in range(a.trials):
        order=d['cases'].copy();rng.shuffle(order)
        for c in order:c['samples'].append(take(c));print('block',i+1,c['name'],flush=True)
        save()
    for p,h in d['source_sha256'].items():
        if base.sha(Path(p))!=h:raise ValueError('source changed')
    if base.sha(host)!=d['host_sha256']:raise ValueError('host changed')
    d['status']='complete';save()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=HERE/'_work/zstd-source/zstd-1.5.7')
    base.toolchain_arguments(p,headers=False)
    p.add_argument('--host',type=Path)
    p.add_argument('--trials',type=int,default=7)
    p.add_argument('--output',type=Path,default=HERE/'_work/runs/zstd-handoff')
    a=p.parse_args()
    if a.trials<1:p.error('positive trial count required')
    run(a)
