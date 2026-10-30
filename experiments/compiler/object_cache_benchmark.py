"""Hermetic local object-cache consumers: full snapshot versus explicit per-job views."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import random
import resource
import shlex
import shutil
import subprocess
import statistics
import sys
import time
import benchmark as base
import project_benchmark as project

HERE=base.HERE
MODES=('off','whole','scoped')
TIMED=('unchanged','implementation','heavy-implementation','shared-header','generated-header','flags')
PROBE='''#include "_gaia_shared.h"
#include "_gaia_generated.h"
#if __has_include("_gaia_optional.h")
#include "_gaia_optional.h"
#else
#define GAIA_OPTIONAL 0
#endif
#ifndef GAIA_FLAG
#define GAIA_FLAG 0
#endif
__attribute__((visibility("default"))) unsigned gaia_cache_probe(void);
unsigned gaia_cache_probe(void) {return GAIA_SHARED+GAIA_GENERATED+GAIA_OPTIONAL+GAIA_FLAG;}
'''
ENV_REMOVE=('CPATH','C_INCLUDE_PATH','CPLUS_INCLUDE_PATH','OBJC_INCLUDE_PATH','INCLUDE','LD_PRELOAD','LD_LIBRARY_PATH','CCC_OVERRIDE_OPTIONS','LLVM_PROFILE_FILE')


def cache_env():
    env={k:v for k,v in os.environ.items() if k not in ENV_REMOVE}
    env.update(SOURCE_DATE_EPOCH='0',TZ='UTC',LANG='C',LC_ALL='C')
    return env


def library_check(path,probe,version,heavy=False):
    code='''import ctypes,sys
p=ctypes.CDLL(sys.argv[1]);p.gaia_cache_probe.restype=ctypes.c_uint;p.ZSTD_versionNumber.restype=ctypes.c_uint
assert p.gaia_cache_probe()==int(sys.argv[2]);assert p.ZSTD_versionNumber()==int(sys.argv[3])
if sys.argv[4]=='1':
 p.gaia_cache_heavy_marker.restype=ctypes.c_uint;assert p.gaia_cache_heavy_marker()==123
'''
    project.run_checked([sys.executable,'-c',code,str(path),str(probe),str(version),str(int(heavy))],env=cache_env())


def reset_cache(seed,destination):
    if destination.exists():shutil.rmtree(destination)
    destination.mkdir()
    if seed:
        for p in Path(seed).glob('*.gco'):os.link(p,destination/p.name)


def report(d,path):
    lines=['# Local compiled-object cache','',f"Run `{d['run_id']}`; **{d['status']}**; {d['trials']} randomized blocks, warm page cache, fresh consumer process per build.",'',
       'Zstandard 1.5.7 portable C release library plus one explicit cache-invalidation probe (31 TUs). '
       'All modes use the same Odin/C++ binary, exact compile flags, per-request hermetic input views '
       'and ordered embedded LLD request. Off compiles all jobs. Whole keys additionally bind the complete '
       'admitted collection; scoped keys bind each complete visible namespace. All keys bind exact argv, '
       'logical working directory and admitted toolchain/execution-context identity.','',
       '| Scenario | Mode | Process ms | Child CPU ms | Executed compilers | Cache hits |',
       '| --- | --- | ---: | ---: | ---: | ---: |']
    for c in d['cases']:
        if not c['samples']:continue
        med=lambda k:statistics.median(x[k] for x in c['samples'])
        lines.append(f"| {c['scenario']} | {c['mode']} | {med('wall_seconds')*1000:.2f} | {med('cpu_seconds')*1000:.2f} | {med('compiler_executions'):.0f} | {med('cache_hits'):.0f} |")
    lines+=['','Every timed cache starts from a baseline-only seed, restored outside the consumer clock. '
        'Variant results from a previous observation are never left available, so an edit cannot silently '
        'turn into an all-hit unchanged build. Every build still performs a real link. Hits validate entry '
        'framing, key and payload SHA-256 before copying native object bytes into LLD input buffers. '
        'Successful misses publish entries via exclusive temporary files and atomic rename only after '
        'the complete build links successfully. Cache write failures leave a successful build usable.','',
        'Whole-process timing includes immutable-collection authentication, cache-key construction/lookup, '
        'payload integrity/copying, actual misses, linking, cache publication, captured-object validation '
        'hashes, reporting and normal teardown. Native workload counters stop before publication/reporting. '
        'Parent checks compare every object and ELF to fresh CLI references and execute the probe after '
        'timing. Input collection/admission production, reference builds, adapter build and baseline cache '
        'population are separately recorded producer/setup costs, not part of consumer latency.','',
        'Scoped inputs are caller-declared compiler namespaces: all admitted shared project/SDK headers '
        'and the selected job roots (plus any declared cross-root includes). There is no host-input fallback. '
        'The key covers optional-file presence as well as content; this is not a cache based only on '
        'previous positive dependency reads. Dependency discovery supplies this fixture, not a general '
        'complete SDK or arbitrary build-system adapter. Unsupported response files and volatile date/time '
        'macros are rejected. Toolchain/context identities are admitted by the benchmark before consumers; '
        'the child does not rehash installed compiler DSOs on every launch.','',
        'These are private local cache records with corruption detection, not authenticated remote artifacts. '
        'Publication is atomic but not fsync-durable, and there is no eviction/space quota. Compiler crashes, '
        'arbitrary plugins, PGO inputs, persistent services and general physical-filesystem equivalence '
        'are outside this prototype. All comparisons concern the same supplied immutable views.','']
    path.write_text('\n'.join(lines))


def prepare(a,work,host):
    start=time.perf_counter();parent=json.loads(a.inputs.read_text());oldroot=Path(parent['source']);root=work/'project'
    shutil.copytree(oldroot,root,ignore=shutil.ignore_patterns('*.o','*.a','*.so*'))
    lib=root/'lib';clang=base.admitted_tool(parent,'clang');lld=base.admitted_tool(parent,'ld.lld')
    for p,h in parent['source_sha256'].items():
        if base.sha(Path(p))!=h:raise ValueError('parent source changed')
    for path,pin in parent['toolchain_sha256'].items():
        if base.sha(Path(path))!=pin:raise ValueError('admitted toolchain changed: '+path)
    old=next(c for c in parent['cases'] if c['name']=='release-file')
    search=project.run_checked([str(clang),'--no-default-config','-E','-x','c','-','-v'],input='',env=cache_env())
    dirs=[];active=False
    for line in search.stderr.splitlines():
        if '#include <...> search starts here:' in line:active=True;continue
        if 'End of search list.' in line:active=False
        if active:dirs.append(line.strip())
    extra=['--no-default-config','--target=x86_64-unknown-linux-gnu','-nostdinc','-Werror=date-time','-fdebug-compilation-dir='+str(lib)]
    for directory in dirs:extra+=['-isystem',directory]
    commands=[[x.replace(str(oldroot),str(root)) for x in cmd]+extra for cmd in old['commands']]
    probe=lib/'_gaia_probe.c';probe.write_text(PROBE)
    shared=lib/'_gaia_shared.h';shared.write_text('#define GAIA_SHARED 1\n')
    generated=lib/'_gaia_generated.h';generated.write_text('#define GAIA_GENERATED 10\n')
    optional=lib/'_gaia_optional.h'
    command=commands[0].copy();command[command.index('-o')+1]='_gaia_probe.o'
    source_arg=next(x for x in command if x.endswith('.c'));command[command.index(source_arg)]=str(probe);commands.append(command)
    sources=[next(x for x in cmd if x.endswith('.c')) for cmd in commands]
    objects=[cmd[cmd.index('-o')+1] for cmd in commands];n=len(commands);all_bits=(1<<n)-1
    lightweight=lib/'common/zstd_common.c';heavy=lib/'compress/zstd_lazy.c'
    baseline={str(p):p.read_bytes() for p in lib.rglob('*.h')}
    baseline.update({p:Path(p).read_bytes() for p in sources})
    light_before=baseline[str(lightweight)]
    if b'return ZSTD_VERSION_NUMBER;' not in light_before:raise ValueError('version implementation fixture changed')
    heavy_suffix=b'\n__attribute__((visibility("default"))) unsigned gaia_cache_heavy_marker(void);\nunsigned gaia_cache_heavy_marker(void) {return 123;}\n'
    variants={
        'unchanged':({},[],11,10507),
        'implementation':({str(lightweight):light_before.replace(b'return ZSTD_VERSION_NUMBER;',b'return ZSTD_VERSION_NUMBER+1;')},[],11,10508),
        'heavy-implementation':({str(heavy):baseline[str(heavy)]+heavy_suffix},[],11,10507),
        'shared-header':({str(shared):b'#define GAIA_SHARED 2\n'},[],12,10507),
        'generated-header':({str(generated):b'#define GAIA_GENERATED 20\n'},[],21,10507),
        'flags':({},['-DGAIA_FLAG=4'],15,10507),
        'optional-header':({str(optional):b'#define GAIA_OPTIONAL 100\n'},[],111,10507),
    }
    context_descriptor=dict(schema='GAIA-LOCAL-C-CONTEXT-1',toolchain=parent['toolchain_sha256'],host_sha256=base.sha(host),
        environment={k:cache_env()[k] for k in ('SOURCE_DATE_EPOCH','TZ','LANG','LC_ALL')},include_environment_removed=ENV_REMOVE,
        contract='Explicit immutable per-job namespace; no host fallback; known C flags; no plugins, response/PGO side inputs; volatile macros rejected.')
    context_bytes=json.dumps(context_descriptor,sort_keys=True,separators=(',',':')).encode();context_id=hashlib.sha256(context_bytes).hexdigest()
    (work/'execution-context.json').write_bytes(context_bytes)
    link=[str(lld),'-shared','--threads=1','--build-id=sha1','-soname','libzstd.so.1','-o','libzstd.so',*objects]
    linkplan=work/'link.gcr';linkplan.write_bytes(project.encode_requests([link]));scenarios={};reference_seconds=0;admission_seconds=0
    def restore():
        for path,body in baseline.items():Path(path).write_bytes(body)
        optional.unlink(missing_ok=True)
    try:
        for name,(edits,flags,expected_probe,version) in variants.items():
            restore()
            for path,body in edits.items():Path(path).write_bytes(body)
            cmds=[[*cmd,*flags] for cmd in commands];plan=work/(name+'.gcr');plan.write_bytes(project.encode_requests(cmds))
            admitted={str(p):p.read_bytes() for p in lib.rglob('*.h')};admitted.update({p:Path(p).read_bytes() for p in sources})
            dependencies=[];t=time.perf_counter()
            for cmd in cmds:
                dep=cmd.copy();i=dep.index('-o');del dep[i:i+2];dep.remove('-c');dep+=['-M','-MT','gaia']
                result=project.run_checked(dep,cwd=lib,env=cache_env());paths=shlex.split(result.stdout.replace('\\\n',' ').split(':',1)[1])
                paths=[str(Path(p if p.startswith('/') else str(lib/p)).resolve()) for p in paths];dependencies.append(paths)
                for p in paths:admitted[p]=Path(p).read_bytes()
            blob=work/(name+'.gci');blob.write_bytes(project.encode_inputs(admitted));names=sorted(admitted)
            # Masks describe full compiler views, not cache lookup filters. Source
            # roots belong to their job; declared cross-root includes are visible too.
            masks=[]
            for path in names:
                if path in sources:
                    mask=1<<sources.index(path)
                    for i,deps in enumerate(dependencies):
                        if path in deps:mask|=1<<i
                else:mask=all_bits
                masks.append(mask)
            maskfile=work/(name+'.views');maskfile.write_text('GAIACV1\n'+'\n'.join(map(str,masks))+'\n')
            admission_seconds+=time.perf_counter()-t
            reference=work/(name+'-cli');reference.mkdir();t=time.perf_counter()
            def compile_ref(cmd):
                cmd=cmd.copy();i=cmd.index('-o')+1;cmd[i]=str(reference/cmd[i]);project.run_checked(cmd,cwd=lib,env=cache_env())
            with ThreadPoolExecutor(max_workers=8) as executor:list(executor.map(compile_ref,cmds))
            project.run_checked(link,cwd=reference,env=cache_env());reference_seconds+=time.perf_counter()-t
            expected={p:base.sha(reference/p) for p in [*objects,'libzstd.so']}
            library_check(reference/'libzstd.so',expected_probe,version,name=='heavy-implementation')
            scenarios[name]=dict(name=name,bundle=str(blob),pin=base.sha(blob),plan=str(plan),plan_sha256=base.sha(plan),
                masks=str(maskfile),mask_sha256=base.sha(maskfile),files=len(names),bundle_bytes=blob.stat().st_size,
                commands=cmds,dependencies=dependencies,expected=expected,probe=expected_probe,version=version,
                changed_paths=list(edits),flags=flags,reference=str(reference))
            print('admitted and CLI-verified',name,flush=True)
    finally:restore()
    info=dict(parent_run=parent['run_id'],source=str(root),logical_cwd=str(lib),objects=objects,jobs=n,
        sources=sources,light_index=sources.index(str(lightweight)),heavy_index=sources.index(str(heavy)),
        context_id=context_id,context_descriptor=context_descriptor,scenarios=scenarios,link=str(linkplan),link_sha256=base.sha(linkplan),
        producer_seconds=time.perf_counter()-start,admission_seconds=admission_seconds,reference_compile_seconds=reference_seconds,
        source_sha256={p:base.sha(Path(p)) for p in baseline},toolchain_sha256=parent['toolchain_sha256'])
    return info


def consume(c,info,seed=True):
    output=Path(c['output']);cache=Path(c['cache'])
    for p in [*info['objects'],'libzstd.so']:(output/p).unlink(missing_ok=True)
    reset_cache(c.get('seed') if seed else None,cache)
    before=resource.getrusage(resource.RUSAGE_CHILDREN);begin=time.perf_counter()
    p=project.run_checked(c['command'],cwd=output,env=cache_env());elapsed=time.perf_counter()-begin;after=resource.getrusage(resource.RUSAGE_CHILDREN)
    if p.stderr:raise ValueError(p.stderr)
    s=json.loads(p.stdout);scenario=info['scenarios'][c['scenario']];n=info['jobs']
    if not s['correct'] or s['errors'] or s['warnings'] or s['ready_objects']!=n or s['link_calls']!=1 or not s['can_run_again'] or s['cache_write_errors']:
        raise ValueError('incomplete build/cache publication')
    if s['buffer_hits']!=n or s['buffer_misses'] or any((output/p).exists() for p in info['objects']):raise ValueError('direct object handoff violated')
    if s['compiler_executions']!=c['expected_misses'] or s['cache_hits']!=n-c['expected_misses'] or s['compiled']!=c['expected_misses']:
        raise ValueError('wrong cache invalidation: '+c['name']+' '+str(s))
    if s['cache_writes']!=(0 if c['mode']=='off' else c['expected_misses']):raise ValueError('unexpected cache writes')
    if s['peak_active']>min(8,c['expected_misses']):raise ValueError('worker bound exceeded')
    artifacts=dict(zip(info['objects'],s['object_sha256']));artifacts['libzstd.so']=base.sha(output/'libzstd.so')
    if artifacts!=scenario['expected']:raise ValueError('cached object/library differs from independent CLI reference')
    library_check(output/'libzstd.so',scenario['probe'],scenario['version'],c['scenario']=='heavy-implementation')
    s.update(wall_seconds=elapsed,cpu_seconds=after.ru_utime-before.ru_utime+after.ru_stime-before.ru_stime,
             system_seconds=after.ru_stime-before.ru_stime,artifacts_sha256=artifacts,object_files_absent=True)
    return s


def run(a):
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');work=HERE/'_work'/('object-cache-'+run_id);work.mkdir();a.output.mkdir(parents=True,exist_ok=True)
    host=a.host.resolve();info=prepare(a,work,host)
    d=dict(run_id=run_id,status='running',trials=a.trials,work=str(work),inputs=info,host=str(host),host_sha256=base.sha(host),
        build=json.loads((host.parent.parent/'build.json').read_text()),cases=[],seeds={},validation=[],
        environment=dict(uname=list(os.uname()),cpu_count=os.cpu_count(),cache='warm; baseline-only local object cache'),
        source_sha256={n:base.sha(HERE/n) for n in ('object_cache_benchmark.py','cache_host.odin','cache_bridge.cpp','handoff_bridge.cpp','handoff_impl.h','pool_bridge.cpp','project_bridge.cpp','bridge.cpp','benchmark.py')})
    snapshots=work/'sources';snapshots.mkdir()
    for n in d['source_sha256']:shutil.copy2(HERE/n,snapshots/n)
    d['source_snapshots']=str(snapshots)
    def case(name,mode,scenario,misses,seed=None):
        output=work/name;output.mkdir();cache=work/(name+'-cache');s=info['scenarios'][scenario]
        cmd=[str(host),'memory',str(base.admitted_tool(info,'clang')),info['logical_cwd'],s['bundle'],s['pin'],str(output),s['plan'],'8','internal',
             str(base.admitted_tool(info,'ld.lld')),info['link'],'direct',mode,str(cache),s['masks'],info['context_id']]
        return dict(name=name,mode=mode,scenario=scenario,output=str(output),cache=str(cache),seed=seed,command=cmd,expected_misses=misses,samples=[])
    for mode in ('whole','scoped'):
        seed_case=case('seed-'+mode,mode,'unchanged',info['jobs']);seed_case['result']=consume(seed_case,info,False)
        seed_case['seed']=seed_case['cache'];d['seeds'][mode]=seed_case;print('seeded',mode,flush=True)
    for scenario in TIMED:
        for mode in MODES:
            misses=info['jobs']
            if mode!='off' and scenario=='unchanged':misses=0
            if mode=='scoped' and scenario in ('implementation','heavy-implementation'):misses=1
            c=case(scenario+'-'+mode,mode,scenario,misses,d['seeds'][mode]['cache'] if mode!='off' else None)
            c['warmup']=consume(c,info);d['validation'].append(dict(case=c['name'],passed=True,probe_executed=True,artifacts_match_cli=True))
            d['cases'].append(c);print('verified cache case',c['name'],flush=True)
    # Explicit optional-file presence changes the visible namespace and must miss.
    for mode in ('whole','scoped'):
        c=case('optional-header-'+mode,mode,'optional-header',info['jobs'],d['seeds'][mode]['cache']);c['result']=consume(c,info)
        d['validation'].append(dict(case=c['name'],passed=True,optional_membership_invalidated=True,result=c['result'],command=c['command']))
    def save():base.save(a.output/'results.json',d);report(d,a.output/'REPORT.md')
    save();rng=random.Random(20261108)
    for i in range(a.trials):
        order=d['cases'].copy();rng.shuffle(order)
        for c in order:c['samples'].append(consume(c,info));print('cache block',i+1,c['name'],flush=True)
        save()
    for p,h in info['source_sha256'].items():
        if base.sha(Path(p))!=h:raise ValueError('producer source tree changed')
    for s in info['scenarios'].values():
        if base.sha(Path(s['bundle']))!=s['pin'] or base.sha(Path(s['plan']))!=s['plan_sha256'] or base.sha(Path(s['masks']))!=s['mask_sha256']:raise ValueError('admitted inputs changed')
    if base.sha(host)!=d['host_sha256']:raise ValueError('host changed')
    d['status']='complete';save()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inputs',type=Path,default=HERE/'_work/runs/zstd-handoff/results.json')
    p.add_argument('--host',type=Path,default=HERE/'_work/cache-development/build/host')
    p.add_argument('--trials',type=int,default=5)
    p.add_argument('--output',type=Path,default=HERE/'_work/runs/object-cache')
    a=p.parse_args()
    if a.trials<1:p.error('positive trials required')
    run(a)
