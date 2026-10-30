"""Observed dependency validation plus explicit incremental snapshot production."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import random
import resource
import shutil
import statistics
import struct
import subprocess
import time
import benchmark as base
import project_benchmark as project
import object_cache_benchmark as cache
from check_object_cache import decode_inputs

HERE=base.HERE
TIMED=('unchanged','implementation','shared-header','generated-header','optional-header','shadow-header','unused-header','new-directory')
PROBE='''#include "_gaia_shared.h"
#include "_gaia_generated.h"
#include <_gaia_choice.h>
#if __has_include("_gaia_optional.h")
#include "_gaia_optional.h"
#else
#define GAIA_OPTIONAL 0
#endif
#if __has_include("_gaia_newdir/feature.h")
#include "_gaia_newdir/feature.h"
#else
#define GAIA_DIRECTORY 0
#endif
#ifndef GAIA_FLAG
#define GAIA_FLAG 0
#endif
__attribute__((visibility("default"))) unsigned gaia_cache_probe(void);
unsigned gaia_cache_probe(void) {return GAIA_SHARED+GAIA_GENERATED+GAIA_OPTIONAL+GAIA_CHOICE+GAIA_DIRECTORY+GAIA_FLAG;}
'''


def delta_bytes(baseline,variant,masks,base_pin,mask_pin):
    changed=[p for p in sorted(set(baseline)|set(variant)) if baseline.get(p)!=variant.get(p)]
    data=bytearray(b'GAIADP01'+bytes.fromhex(base_pin)+bytes.fromhex(mask_pin)+struct.pack('<Q',len(changed)))
    for path in changed:
        exists=path in variant;name=path.encode();body=variant.get(path,b'')
        data+=struct.pack('<IBQQ',len(name),1 if exists else 2,masks.get(path,0) if exists else 0,len(body))+name+b'\0'+body+b'\0'
    return data,changed


def install_changes(base_files,scenario):
    for name in scenario['changed_paths']:
        path=Path(name)
        if name in scenario['changes']:
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(bytes.fromhex(scenario['changes'][name]))
        else:path.unlink(missing_ok=True)


def restore_changes(base_files,scenario):
    for name in scenario['changed_paths']:
        path=Path(name)
        if name in base_files:path.write_bytes(base_files[name])
        else:
            path.unlink(missing_ok=True)
            try:path.parent.rmdir()
            except OSError:pass


def prepare(a,work):
    parent=json.loads(a.inputs.read_text());old=parent['inputs'];oldroot=Path(old['source']);root=work/'project'
    for p,h in old['toolchain_sha256'].items():
        if base.sha(Path(p))!=h:raise ValueError('toolchain changed')
    shutil.copytree(oldroot,root,ignore=shutil.ignore_patterns('*.o','*.a','*.so*'))
    lib=root/'lib';original=old['scenarios']['unchanged'];oldfiles=decode_inputs(original['bundle'])
    oldmasks=list(map(int,Path(original['masks']).read_text().split()[1:]));masks={}
    files={}
    for (name,body),mask in zip(sorted(oldfiles.items()),oldmasks):
        name=name.replace(str(oldroot),str(root));files[name]=body;masks[name]=mask
    commands=[[arg.replace(str(oldroot),str(root)) for arg in cmd] for cmd in original['commands']]
    sources=[s.replace(str(oldroot),str(root)) for s in old['sources']];n=old['jobs'];bits=(1<<n)-1
    early=lib/'_gaia_early';late=lib/'_gaia_late';early.mkdir();late.mkdir()
    files[sources[-1]]=PROBE.encode();files[str(early/'_anchor.h')]=b'/* unused anchor A */\n';files[str(late/'_gaia_choice.h')]=b'#define GAIA_CHOICE 7\n'
    for path in files:
        if path.startswith(str(root)+'/'):
            Path(path).parent.mkdir(parents=True,exist_ok=True);Path(path).write_bytes(files[path])
        if path not in masks:masks[path]=bits
    for cmd in commands:cmd+=['-I'+str(early),'-I'+str(late)]
    lightweight=str(lib/'common/zstd_common.c');shared=str(lib/'_gaia_shared.h');generated=str(lib/'_gaia_generated.h')
    optional=str(lib/'_gaia_optional.h');shadow=str(early/'_gaia_choice.h');unused=str(early/'_anchor.h');newdir=str(lib/'_gaia_newdir/feature.h')
    variants={
      'unchanged':({},[],18,10507),
      'implementation':({lightweight:files[lightweight].replace(b'return ZSTD_VERSION_NUMBER;',b'return ZSTD_VERSION_NUMBER+1;')},[],18,10508),
      'shared-header':({shared:b'#define GAIA_SHARED 2\n'},[],19,10507),
      'generated-header':({generated:b'#define GAIA_GENERATED 20\n'},[],28,10507),
      'optional-header':({optional:b'#define GAIA_OPTIONAL 100\n'},[],118,10507),
      'shadow-header':({shadow:b'#define GAIA_CHOICE 99\n'},[],110,10507),
      'unused-header':({unused:b'/* unused anchor B */\n'},[],18,10507),
      'new-directory':({newdir:b'#define GAIA_DIRECTORY 1000\n'},[],1018,10507),
      'flags':({},['-DGAIA_FLAG=4'],22,10507),
    }
    objects=old['objects'];link=[str(base.admitted_tool(old,'ld.lld')),'-shared','--threads=1','--build-id=sha1','-soname','libzstd.so.1','-o','libzstd.so',*objects]
    linkplan=work/'link.gcr';linkplan.write_bytes(project.encode_requests([link]))
    base_blob=work/'base.gci';base_blob.write_bytes(project.encode_inputs(files));base_views=work/'base.views';base_views.write_text('GAIACV1\n'+'\n'.join(str(masks[p]) for p in sorted(files))+'\n')
    scenarios={};started=time.perf_counter();reference_seconds=0
    for name,(edits,flags,probe,version) in variants.items():
        variant={**files,**edits};vmasks={**masks,**{p:bits for p in edits if p not in masks}}
        blob=work/(name+'.gci');blob.write_bytes(project.encode_inputs(variant));views=work/(name+'.views');views.write_text('GAIACV1\n'+'\n'.join(str(vmasks[p]) for p in sorted(variant))+'\n')
        patch,changed=delta_bytes(files,variant,vmasks,base.sha(base_blob),base.sha(base_views));delta=work/(name+'.gdp');delta.write_bytes(patch)
        cmds=[[*cmd,*flags] for cmd in commands];plan=work/(name+'.gcr');plan.write_bytes(project.encode_requests(cmds))
        s=dict(name=name,bundle=str(blob),pin=base.sha(blob),masks=str(views),mask_pin=base.sha(views),delta=str(delta),delta_pin=base.sha(delta),
            changed_paths=changed,changes={p:variant[p].hex() for p in changed if p in variant},plan=str(plan),plan_pin=base.sha(plan),
            files=len(variant),commands=cmds,probe=probe,version=version)
        ref=work/(name+'-cli');ref.mkdir();install_changes(files,s);t=time.perf_counter()
        try:
            def compile_one(cmd):
                cmd=cmd.copy();i=cmd.index('-o')+1;cmd[i]=str(ref/cmd[i]);project.run_checked(cmd,cwd=lib,env=cache.cache_env())
            with ThreadPoolExecutor(max_workers=8) as executor:list(executor.map(compile_one,cmds))
            project.run_checked(link,cwd=ref,env=cache.cache_env())
        finally:restore_changes(files,s)
        reference_seconds+=time.perf_counter()-t;s['expected']={p:base.sha(ref/p) for p in [*objects,'libzstd.so']};s['reference']=str(ref)
        cache.library_check(ref/'libzstd.so',probe,version);scenarios[name]=s;print('CLI verified',name,flush=True)
    descriptor={**old['context_descriptor'],'host_sha256':base.sha(a.host),'provider_contract':'GAIA-RECORDED-VFS-1; independent regular files, implicit directories; fixed metadata; no alias nodes'}
    context_id=hashlib.sha256(json.dumps(descriptor,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return dict(parent_run=parent['run_id'],root=str(root),cwd=str(lib),jobs=n,objects=objects,sources=sources,context_id=context_id,context=descriptor,
        baseline=str(base_blob),baseline_pin=base.sha(base_blob),base_views=str(base_views),base_view_pin=base.sha(base_views),link=str(linkplan),link_pin=base.sha(linkplan),
        scenarios=scenarios,producer_setup_seconds=time.perf_counter()-started,reference_compile_seconds=reference_seconds,
        baseline_file_sha256={p:hashlib.sha256(body).hexdigest() for p,body in files.items()},base_file_bytes=sum(map(len,files.values())),
        special_paths=dict(optional=optional,shadow=shadow,newdir=newdir,unused=unused),toolchain_sha256=old['toolchain_sha256']),files


def report(d,path):
    lines=['# Dependency journals and incremental snapshot production','',f"Run `{d['run_id']}`; **{d['status']}**; {d['trials']} randomized blocks; warm cache; fresh producer and consumer processes.",'',
      'Same 31-TU Zstandard-plus-probe target, explicit input views, compiler flags and ordered LLD inputs '
      'per scenario. Scoped keys conservatively bind every visible input. Journal candidates bind '
      'argv/cwd/context and validate the prior observed filesystem queries against the new view before '
      'reuse. Every timed cache starts from a baseline-only seed.','',
      '| Scenario | Snapshot | Cache | Producer ms | Consumer ms | Combined ms | Compilers | Hits |',
      '| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for c in d['cases']:
        if not c['samples']:continue
        med=lambda k:statistics.median(v[k] for v in c['samples'])
        lines.append(f"| {c['scenario']} | {c['snapshot']} | {c['policy']} | {med('producer_seconds')*1000:.2f} | {med('consumer_seconds')*1000:.2f} | {med('pipeline_seconds')*1000:.2f} | {med('compiler_executions'):.0f} | {med('cache_hits'):.0f} |")
    lines+=['','Combined timing begins before launching the snapshot producer and ends after normal consumer '
      'exit. It includes snapshot construction/publication, receipt handoff/validation, collection '
      'authentication, dependency checks, actual misses, linking, cache publication, reporting/result '
      'hashes and both process lifecycles. Parent reference/runtime checks follow timing. Source edit '
      'notification/delta creation, cache reset, initial SDK admission, CLI reference builds and initial '
      'cache population are outside the combined clock.','',
      'Full refresh rereads every named input from the host filesystem; delta production applies explicit '
      'caller-supplied changes to an authenticated prior snapshot and opens zero loose project/SDK files. '
      'Both serialize and hash the complete new collection, and must produce identical bundle/view pins. '
      'This compares updating an existing admitted namespace, not discovering a complete SDK after '
      'arbitrary new compiler configurations. No filesystem watcher or change-discovery service is implemented.','',
      'The journal records metadata/existence/open/realpath/directory/locality/cwd results, including '
      'negative outcomes. Opened bytes are content-hashed; all replay uses the actual new hermetic view. '
      'Numeric InMemoryFS IDs are normalized to canonical path identity because this provider has only '
      'independent regular files and implicit directories, with fixed metadata and no hardlinks/symlinks. '
      'Unrepresentable or oversized observations bypass publication. The LLVM-specific shim is not a '
      'portable general filesystem observation protocol.','',
      'Each action retains one latest journal/object candidate in a single atomically replaced record '
      'whose checksum binds action, lengths, journal and payload. Incompatible candidates miss; corruption '
      'is rejected. Historical variants, eviction/quotas, authenticated remote records, crash isolation '
      'and arbitrary plugins/side inputs remain outside this prototype. Diagnostics bypass storage. '
      'All object/ELF hashes must match independently rebuilt CLI references and observable probe values.','']
    path.write_text('\n'.join(lines))


def run(a):
    a.host=a.host.resolve();a.producer=a.producer.resolve();a.output.mkdir(parents=True,exist_ok=True)
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');work=HERE/'_work'/('dependency-cache-'+run_id);work.mkdir()
    info,files=prepare(a,work)
    d=dict(run_id=run_id,status='running',trials=a.trials,work=str(work),inputs=info,host=str(a.host),producer=str(a.producer),
        host_sha256=base.sha(a.host),producer_sha256=base.sha(a.producer),build=json.loads((a.host.parent.parent/'build.json').read_text()),cases=[],seeds={},checks=[],
        source_sha256={name:base.sha(HERE/name) for name in ('dependency_cache_benchmark.py','dependency_host.odin','dependency_bridge.cpp','dependency_impl.h','snapshot_host.odin','cache_bridge.cpp','handoff_bridge.cpp','handoff_impl.h','pool_bridge.cpp','project_bridge.cpp','bridge.cpp','benchmark.py')})
    src=work/'sources';src.mkdir()
    for name in d['source_sha256']:shutil.copy2(HERE/name,src/name)
    d['source_snapshots']=str(src)
    def make_case(name,scenario,snapshot,policy,misses,seed=None):
        out=work/name;out.mkdir();store=work/(name+'-cache');s=info['scenarios'][scenario]
        consumer=[str(a.host),'memory',str(base.admitted_tool(info,'clang')),info['cwd'],s['bundle'],s['pin'],str(out),s['plan'],'8','internal',str(base.admitted_tool(info,'ld.lld')),info['link'],'direct',policy,str(store),s['masks'],info['context_id']]
        producer=[str(a.producer),snapshot,info['baseline'],info['base_views'],s['delta'],str(out/'produced.gci'),str(out/'produced.views'),s['pin'],str(info['jobs'])]
        return dict(name=name,scenario=scenario,snapshot=snapshot,policy=policy,output=str(out),cache=str(store),seed=seed,command=consumer,producer_command=producer,expected_misses=misses,samples=[])
    def take(c):
        s=info['scenarios'][c['scenario']];out=Path(c['output']);store=Path(c['cache'])
        if store.exists():shutil.rmtree(store)
        store.mkdir()
        if c['seed']:
            for p in Path(c['seed']).iterdir():os.link(p,store/p.name)
        for name in [*info['objects'],'libzstd.so']:(out/name).unlink(missing_ok=True)
        install_changes(files,s)
        before=resource.getrusage(resource.RUSAGE_CHILDREN);begin=time.perf_counter()
        try:
            p=project.run_checked(c['producer_command'],env=cache.cache_env());producer_end=time.perf_counter();produced=json.loads(p.stdout)
            if p.stderr or produced['pin']!=s['pin'] or produced['view_pin']!=s['mask_pin'] or produced['loose_reads']!=(0 if c['snapshot']=='delta' else s['files']):raise ValueError('snapshot output differs')
            cmd=c['command'].copy();cmd[4]=c['producer_command'][5];cmd[5]=produced['pin'];cmd[15]=c['producer_command'][6]
            p=project.run_checked(cmd,cwd=out,env=cache.cache_env());end=time.perf_counter();after=resource.getrusage(resource.RUSAGE_CHILDREN)
        finally:restore_changes(files,s)
        if p.stderr:raise ValueError(p.stderr)
        result=json.loads(p.stdout);n=info['jobs']
        if not result['correct'] or result['errors'] or result['warnings'] or result['ready_objects']!=n or result['link_calls']!=1 or not result['can_run_again'] or result['cache_write_errors']:
            raise ValueError('incomplete consumer: '+str(result))
        if result['compiler_executions']!=c['expected_misses'] or result['cache_hits']!=n-c['expected_misses']:raise ValueError('bad dependency invalidation: '+c['name']+' '+str(result))
        if result['buffer_hits']!=n or result['buffer_misses'] or any((out/x).exists() for x in info['objects']):raise ValueError('direct object contract failed')
        actual=dict(zip(info['objects'],result['object_sha256']));actual['libzstd.so']=base.sha(out/'libzstd.so')
        if actual!=s['expected']:raise ValueError('cache output differs from CLI: '+c['name'])
        cache.library_check(out/'libzstd.so',s['probe'],s['version'])
        result.update(producer_seconds=producer_end-begin,consumer_seconds=end-producer_end,pipeline_seconds=end-begin,
            cpu_seconds=after.ru_utime-before.ru_utime+after.ru_stime-before.ru_stime,producer=produced,artifacts_sha256=actual,object_files_absent=True)
        return result
    for policy in ('scoped','journal'):
        c=make_case('seed-'+policy,'unchanged','delta',policy,info['jobs']);c['result']=take(c);d['seeds'][policy]=c
        print('seeded',policy,flush=True)
    for scenario in TIMED:
        for snapshot,policy in [('delta','off'),('delta','scoped'),('delta','journal'),('full','journal')]:
            misses=info['jobs']
            if policy!='off' and scenario=='unchanged':misses=0
            if policy=='scoped' and scenario=='implementation':misses=1
            if policy=='journal':misses=0 if scenario in ('unchanged','unused-header') else 1
            c=make_case(scenario+'-'+snapshot+'-'+policy,scenario,snapshot,policy,misses,d['seeds'][policy]['cache'] if policy!='off' else None)
            c['warmup']=take(c);d['cases'].append(c);print('verified',c['name'],flush=True)
    # All flags remain part of candidate identity; no dependency trick elides them.
    c=make_case('flags-delta-journal','flags','delta','journal',info['jobs'],d['seeds']['journal']['cache']);c['result']=take(c)
    d['checks'].append(dict(check='global-flags-invalidate-all-actions',passed=True,case=c))
    def save():base.save(a.output/'results.json',d);report(d,a.output/'REPORT.md')
    save();rng=random.Random(20261109)
    for i in range(a.trials):
        order=d['cases'].copy();rng.shuffle(order)
        for c in order:c['samples'].append(take(c));print('dependency block',i+1,c['name'],flush=True)
        save()
    for p,h in info['baseline_file_sha256'].items():
        if base.sha(Path(p))!=h:raise ValueError('baseline source/SDK changed')
    for s in info['scenarios'].values():
        for path,pin in [(s['bundle'],s['pin']),(s['masks'],s['mask_pin']),(s['delta'],s['delta_pin']),(s['plan'],s['plan_pin'])]:
            if base.sha(Path(path))!=pin:raise ValueError('admitted fixture changed')
    if base.sha(a.host)!=d['host_sha256'] or base.sha(a.producer)!=d['producer_sha256']:raise ValueError('host changed')
    d['status']='complete';save()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inputs',type=Path,default=HERE/'_work/runs/object-cache/results.json')
    p.add_argument('--host',type=Path,default=HERE/'_work/dependency-development/build/host')
    p.add_argument('--producer',type=Path,default=HERE/'_work/dependency-development/snapshot-host')
    p.add_argument('--trials',type=int,default=5)
    p.add_argument('--output',type=Path,default=HERE/'_work/runs/dependency-cache')
    a=p.parse_args()
    if a.trials<1:p.error('positive trials required')
    run(a)
