"""Pinned real-project compiler comparison: zlib, with generic native requests."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import random
import resource
import shlex
import shutil
import statistics
import struct
import subprocess
import tarfile
import time

import benchmark as base

HERE=base.HERE
VERSION='1.3.2'
SOURCE_SHA='bb329a0a2cd0274d05519d61c667c062e06990d72e125ee2dfa8de64f0119d16'
MODES=('make-serial','make-parallel','cli-batch','physical','memory')


def encode_inputs(files):
    result=bytearray(b'GAIACIN2'+struct.pack('<Q',len(files)))
    for path,body in sorted(files.items()):
        name=path.encode();result+=struct.pack('<IQ',len(name),len(body))+name+b'\0'+body+b'\0'
    return result


def encode_requests(commands):
    result=bytearray(b'GAIACRQ1'+struct.pack('<Q',len(commands)))
    for command in commands:
        result+=struct.pack('<I',len(command))
        for value in command:
            value=value.encode();result+=struct.pack('<I',len(value))+value
    return result


def run_checked(command,**kwargs):
    p=subprocess.run(command,capture_output=True,text=True,timeout=180,**kwargs)
    if p.returncode:raise RuntimeError(' '.join(map(str,command))+'\n'+p.stdout+p.stderr)
    return p


def prepare(args,work):
    start=time.perf_counter()
    if base.sha(args.archive)!=SOURCE_SHA:raise ValueError('zlib archive SHA differs from published pin')
    with tarfile.open(args.archive) as archive:archive.extractall(work,filter='data')
    root=work/('zlib-'+VERSION);clang=str(args.llvm/'bin/clang')
    env={**os.environ,'CC':clang,'CFLAGS':'-O2 -fPIC -fno-ident -fno-addrsig'}
    configure=run_checked(['./configure','--static'],cwd=root,env=env)
    (work/'configure.txt').write_text(configure.stdout+configure.stderr)
    dry=run_checked(['make','-n','libz.a'],cwd=root);(work/'upstream-build-plan.txt').write_text(dry.stdout)
    upstream=[];common=None;sources=[];names=[]
    for line in dry.stdout.splitlines():
        tokens=shlex.split(line)
        if not tokens or tokens[0]!=clang or '-c' not in tokens:continue
        source=next(v for v in tokens if v.endswith('.c'));obj=tokens[tokens.index('-o')+1]
        flags=[];i=1
        while i<len(tokens):
            if tokens[i]=='-o':i+=2;continue
            if tokens[i] not in ('-c',source):flags.append(tokens[i])
            i+=1
        if common is None:common=flags
        elif common!=flags:raise ValueError('CLI batch control requires common flags; per-request adapter supports distinct flags')
        sources.append(str(root/source));names.append(obj);upstream.append(tokens)
    if len(sources)!=15:raise ValueError('upstream library source list changed')
    # Make implicit compiler header search explicit for every consumer. The VFS
    # then needs only admitted inputs, without host-toolchain discovery fallback.
    search=subprocess.run([clang,'-E','-x','c','-','-v'],input='',capture_output=True,text=True,check=True)
    dirs=[];active=False
    for line in search.stderr.splitlines():
        if '#include <...> search starts here:' in line:active=True;continue
        if 'End of search list.' in line:active=False
        if active:dirs.append(line.strip())
    if not dirs:raise ValueError('no compiler include search list')
    flags=[*common,'--target=x86_64-unknown-linux-gnu','-nostdinc','-I'+str(root)]
    for directory in dirs:flags+=['-isystem',directory]
    commands=[[clang,*flags,'-c',source,'-o',obj] for source,obj in zip(sources,names)]
    plan=work/'requests.gcr';plan.write_bytes(encode_requests(commands))
    files={};dependencies=[]
    # Retain all project headers, including optional-but-present inputs whose
    # absence could otherwise change __has_include branches.
    for path in root.glob('*.h'):files[str(path)]=path.read_bytes()
    for source in sources:
        dep=run_checked([clang,*flags,'-M','-MT','gaia',source],cwd=root)
        paths=shlex.split(dep.stdout.replace('\\\n',' ').split(':',1)[1])
        logical=[os.path.normpath(p if p.startswith('/') else str(root/p)) for p in paths]
        dependencies.append(dict(source=source,files=logical))
        for path in logical:files[path]=Path(path).read_bytes()
    blob=work/'inputs.gci';blob.write_bytes(encode_inputs(files))
    project_count=sum(p.startswith(str(root)+'/') for p in files)
    return dict(project='zlib',version=VERSION,archive=str(args.archive),archive_sha256=SOURCE_SHA,
        source_url='https://zlib.net/fossils/zlib-'+VERSION+'.tar.gz',
        checksum_source='https://zlib.net/',root=str(root),bundle=str(blob),pin=base.sha(blob),
        plan=str(plan),plan_sha256=base.sha(plan),commands=commands,flags=flags,upstream_commands=upstream,
        sources=sources,objects=names,files=len(files),project_files=project_count,
        system_files=len(files)-project_count,payload_bytes=sum(map(len,files.values())),
        bundle_bytes=blob.stat().st_size,source_sha256={p:hashlib.sha256(body).hexdigest() for p,body in files.items()},
        dependencies=dependencies,include_search=dirs,producer_seconds=time.perf_counter()-start),files


def artifact_hashes(output,inputs):
    return {name:base.sha(output/name) for name in [*inputs['objects'],'libz.a']}


def consume(case,inputs):
    output=Path(case['output'])
    if case['mode'].startswith('make-'):
        # Remove only generated outputs from this experiment's build directory.
        for name in [*inputs['objects'],'libz.a']:(output/name).unlink(missing_ok=True)
    before=resource.getrusage(resource.RUSAGE_CHILDREN);start=time.perf_counter()
    p=run_checked(case['command'],cwd=output)
    compiled=time.perf_counter()
    result=json.loads(p.stdout) if case['mode'] in ('physical','memory') else {}
    if result and (not result['correct'] or result['compiled']!=len(inputs['sources']) or result['errors']):
        raise ValueError('incomplete native build')
    if not case['mode'].startswith('make-'):run_checked(case['archive_command'],cwd=output)
    finished=time.perf_counter();after=resource.getrusage(resource.RUSAGE_CHILDREN)
    result.update(wall_seconds=finished-start,compile_process_seconds=compiled-start,
        archive_seconds=finished-compiled,cpu_seconds=after.ru_utime-before.ru_utime+after.ru_stime-before.ru_stime,
        user_seconds=after.ru_utime-before.ru_utime,system_seconds=after.ru_stime-before.ru_stime,
        minor_faults=after.ru_minflt-before.ru_minflt,major_faults=after.ru_majflt-before.ru_majflt,
        stderr=p.stderr)
    result['artifacts_sha256']=artifact_hashes(output,inputs)
    return result


def upstream_tests(case,inputs,work):
    output=Path(case['output']);stage=work/('check-'+case['mode'])
    shutil.copytree(inputs['root'],stage,ignore=shutil.ignore_patterns('*.o','*.a'))
    for name in [*inputs['objects'],'libz.a']:shutil.copy2(output/name,stage/name)
    # The full library is already present. Upstream make builds test programs
    # and executes its normal/64-bit example and gzip pipelines.
    before=artifact_hashes(stage,inputs)
    p=run_checked(['make','-j1','check'],cwd=stage)
    after=artifact_hashes(stage,inputs)
    if before!=after:raise ValueError('upstream check rebuilt/replaced the library')
    if '*** zlib test OK ***' not in p.stdout or '*** zlib 64-bit test OK ***' not in p.stdout:
        raise ValueError('upstream test markers absent')
    log=work/(case['mode']+'-upstream-check.txt');log.write_text(p.stdout+p.stderr)
    return dict(mode=case['mode'],passed=True,log=str(log),library_unchanged=True)


def boundary_checks(host,clang,inputs,files,work,expected):
    output=work/'boundary';output.mkdir();outcomes=[]
    def cmd(blob,pin,plan):return [str(host),'memory',str(clang),inputs['root'],str(blob),pin,str(output),str(plan)]
    def reject(label,content,code,plan=None,pin=None,diagnostic=False):
        blob=output/(label+'.gci');blob.write_bytes(content)
        p=subprocess.run(cmd(blob,pin or base.sha(blob),plan or inputs['plan']),cwd=output,capture_output=True,text=True,timeout=180)
        if p.returncode!=code:raise ValueError(label+' failed differently: '+p.stderr)
        if diagnostic and (not p.stderr or not json.loads(p.stdout)['errors']):raise ValueError('missing diagnostic')
        outcomes.append(dict(check=label,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
    original=Path(inputs['bundle']).read_bytes()
    reject('wrong-pin',original,3,pin='0'*64)
    reject('truncated-input',original[:-1],3)
    bad=dict(files);bad['/bad/../escape.h']=b'';reject('unsafe-name',encode_inputs(bad),3)
    missing=dict(files);del missing[inputs['root']+'/zlib.h'];reject('missing-project-header',encode_inputs(missing),5,diagnostic=True)
    system=next(p for p in files if p.endswith('/stdio.h') and not p.startswith(inputs['root']+'/'))
    missing=dict(files);del missing[system];reject('missing-system-header',encode_inputs(missing),5,diagnostic=True)
    malformed=output/'bad-plan.gcr';malformed.write_bytes(Path(inputs['plan']).read_bytes()[:-1])
    reject('truncated-plan',original,2,plan=malformed)
    root=Path(inputs['root']);hidden=root.with_name(root.name+'-hidden');root.rename(hidden)
    try:
        p=run_checked(cmd(inputs['bundle'],inputs['pin'],inputs['plan']),cwd=output)
        if json.loads(p.stdout)['compiled']!=len(inputs['sources']):raise ValueError('hidden source build incomplete')
        for name in inputs['objects']:
            if base.sha(output/name)!=expected[name]:raise ValueError('hidden source build differs')
        outcomes.append(dict(check='project-tree-unavailable',correct=True))
    finally:hidden.rename(root)
    return outcomes


def report(data,path):
    lines=['# Real-project compiler invocation: zlib '+VERSION,'',
        f"Run `{data['run_id']}`; **{data['status']}**. {data['trials']} randomized blocks, fresh processes, warm filesystem cache.",'',
        'Configured upstream static library, all 15 translation units, -O2/PIC. Same pinned source, '
        'generated configuration, compiler/flags/explicit header search and deterministic archive. '
        'Native modes use the generic Odin/C++ request-plan adapter; no zlib logic in the native '
        'compiler code, no PCH/AST/result cache. Memory mode hashes a mapped collection containing '
        'project inputs plus admitted system headers and has no real-filesystem input fallback.','',
        '| Mode | Complete library median ms | Range ms | Child CPU ms | Native compile ms | Native mount/setup ms |',
        '| --- | ---: | --- | ---: | ---: | ---: |']
    for case in data['cases']:
        s=case['samples']
        if not s:continue
        med=lambda k:statistics.median(v[k] for v in s)
        wall=[v['wall_seconds']*1000 for v in s]
        native='compile_ns' in s[0]
        comp=f"{med('compile_ns')/1e6:.3f}" if native else '—'
        mount=f"{(med('map_ns')+med('setup_ns'))/1e6:.3f}" if native else '—'
        lines.append(f"| {case['mode']} | {statistics.median(wall):.3f} | {min(wall):.1f}–{max(wall):.1f} | {med('cpu_seconds')*1000:.3f} | {comp} | {mount} |")
    lines+=['','## Paired complete-library comparisons','',
            '| Comparison | Median paired change ms | Wins / blocks |','| --- | ---: | ---: |']
    cases={c['mode']:c for c in data['cases']}
    for mode,control in [('cli-batch','make-serial'),('physical','cli-batch'),('memory','physical'),('memory','cli-batch'),('memory','make-parallel')]:
        delta=[(a['wall_seconds']-b['wall_seconds'])*1000 for a,b in zip(cases[mode]['samples'],cases[control]['samples'])]
        if delta:lines.append(f"| {control} → {mode} | {statistics.median(delta):+.3f} | {sum(v<0 for v in delta)}/{len(delta)} |")
    lines+=['','make-serial and make-parallel run upstream make for libz.a, forcing all library '
        'objects/archive to rebuild before each observation; cleanup is outside timing. Parallel '
        f"make uses {data['jobs']} jobs. CLI batch is one normal clang command for all source files. "
        'Other modes compile sequentially and archive with the same ar rcsD command. Whole library '
        'time includes compiler/driver process startup, compilation/object writes, normal disposal '
        'and archive creation. make has its own archive/ranlib recipe. Linking/executing upstream '
        'tests is separate validation, not hidden work inside a reported build.','',
        'All timed objects and the final archive must match the CLI control byte for byte. Each '
        'mode warmup additionally passes upstream make check (normal and 64-bit tests) without '
        'changing the library. Native modes dispose per-request state and use normal exit. '
        'Parallel make has different execution concurrency; its CPU and wall time are both shown. '
        'This is one small C library, not a claim about C++, whole applications or general project builds.','']
    if data.get('upstream_tests'):lines+=['Upstream test logs: '+', '.join(r['log'] for r in data['upstream_tests'])+'.','']
    if data.get('boundary_checks'):lines+=['Boundary checks: '+', '.join(r['check'] for r in data['boundary_checks'])+'.','']
    if data.get('traces'):
        lines+=['## Separate compiler input traces','',
            '| Mode | Project input calls | System-header input calls | Bundle calls | Execs / cc1 execs |',
            '| --- | --- | --- | --- | ---: |']
        for row in data['traces']:
            c=row['input_path_calls']
            lines.append(f"| {row['mode']} | {c['project']} | {c['system']} | {c['bundle']} | {row['process_execs']} / {row['frontend_execs']} |")
        lines+=['','Untimed traces include compilation only, not archive creation. Counts match '
                'admitted logical/canonical filenames in file/read/mmap syscalls, including failed '
                'probes; unrelated runtime/output activity and directory probes are excluded. '
                'They are not whole-process syscall totals or disk reads. All traced objects and '
                'the existing archive remain byte-identical. Raw traces are local artifacts.','']
    path.write_text('\n'.join(lines))


def run(args):
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');work=HERE/'_work'/('project-'+run_id)
    work.mkdir();args.output.mkdir(parents=True,exist_ok=True)
    host,build=base.build(args,work,bridge='project_bridge.cpp',odin_source='project_host.odin')
    inputs,files=prepare(args,work);clang=args.llvm/'bin/clang';jobs=args.jobs
    data=dict(run_id=run_id,status='running',trials=args.trials,jobs=jobs,work=str(work),build=build,inputs=inputs,
        environment=dict(uname=list(os.uname()),cpu_count=os.cpu_count(),cache='warm; no eviction',
            clang_version=subprocess.check_output([str(clang),'--version'],text=True).strip()),
        source_sha256={n:base.sha(HERE/n) for n in ('project_bridge.cpp','project_host.odin','bridge.cpp','project_benchmark.py','benchmark.py')},
        toolchain_sha256={str(p):base.sha(p) for p in (clang,args.llvm/'lib/libclang-cpp.so',args.llvm/'lib/libLLVM.so.22.1')},cases=[])
    snapshots=work/'sources';snapshots.mkdir()
    for name in data['source_sha256']:shutil.copyfile(HERE/name,snapshots/name)
    data['source_snapshots']=str(snapshots)
    for mode in MODES:
        output=Path(inputs['root']) if mode.startswith('make-') else work/mode
        if not output.exists():output.mkdir()
        if mode.startswith('make-'):
            cmd=['make','-j'+str(jobs if mode=='make-parallel' else 1),'libz.a','CC='+str(clang),'CFLAGS='+shlex.join(inputs['flags'])]
        elif mode=='cli-batch':cmd=[str(clang),*inputs['flags'],'-c',*inputs['sources']]
        else:cmd=[str(host),mode,str(clang),inputs['root'],inputs['bundle'],inputs['pin'],str(output),inputs['plan']]
        data['cases'].append(dict(mode=mode,output=str(output),command=cmd,
            archive_command=['ar','rcsD','libz.a',*inputs['objects']],samples=[]))
    # CLI is the output identity reference, independent of the trial ordering.
    control=next(c for c in data['cases'] if c['mode']=='cli-batch');reference=consume(control,inputs)['artifacts_sha256']
    def take(case):
        sample=consume(case,inputs)
        if sample['artifacts_sha256']!=reference:raise ValueError('artifact bytes differ: '+case['mode'])
        return sample
    data['upstream_tests']=[]
    for case in data['cases']:
        case['warmup']=take(case);data['upstream_tests'].append(upstream_tests(case,inputs,work))
        print('verified full library and upstream tests:',case['mode'],flush=True)
    data['boundary_checks']=boundary_checks(host,clang,inputs,files,work,reference)
    def checkpoint():base.save(args.output/'results.json',data);report(data,args.output/'REPORT.md')
    checkpoint();rng=random.Random(20261102)
    for trial in range(args.trials):
        shuffled=data['cases'].copy();rng.shuffle(shuffled)
        for case in shuffled:case['samples'].append(take(case))
        checkpoint();print(f'zlib trials {trial+1}/{args.trials}',flush=True)
    for name,pin in inputs['source_sha256'].items():
        if base.sha(Path(name))!=pin:raise ValueError('admitted input changed: '+name)
    if base.sha(Path(inputs['bundle']))!=inputs['pin'] or base.sha(Path(inputs['plan']))!=inputs['plan_sha256']:
        raise ValueError('admitted artifacts changed')
    if base.sha(host)!=build['host_sha256']:raise ValueError('host changed')
    data['status']='complete';checkpoint()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,default=HERE/'_work/downloads'/('zlib-'+VERSION+'.tar.gz'))
    base.toolchain_arguments(parser)
    parser.add_argument('--jobs',type=int,default=min(8,os.cpu_count() or 1))
    parser.add_argument('--trials',type=int,default=15)
    parser.add_argument('--output',type=Path,default=HERE/'_work/runs/zlib')
    args=parser.parse_args()
    if args.trials<1 or args.jobs<1:parser.error('positive trials/jobs required')
    args.archive=args.archive.resolve();args.llvm=args.llvm.resolve();args.llvm_headers=args.llvm_headers.resolve()
    run(args)
