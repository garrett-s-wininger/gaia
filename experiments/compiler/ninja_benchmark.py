"""Matched incremental Zstandard builds: Ninja, Ninja+ccache, Gaia journal cache."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import resource
import shlex
import shutil
import statistics
import subprocess
import tarfile
import time

import benchmark as base
import dependency_cache_benchmark as dependency
import condition_index
import incremental_conditions
import retained_conditions
import inline_snapshot
from resident_host import ResidentHost
from blake3_digest import Blake3
from result_history import LinkedResults
import object_cache_benchmark as cache
import project_benchmark as project
from zstd_handoff_benchmark import PIN

HERE=base.HERE
ENGINES=('ninja','ninja-ccache','gaia-journal','gaia-history','gaia-fast','gaia-selective','gaia-batched','gaia-incremental','gaia-shared','gaia-memo','gaia-inline','gaia-resident','gaia-fast-sha','gaia-blake3','gaia-linked','gaia-rebound','gaia-retained','gaia-native-verify','gaia-native-emit','gaia-shared-inputs','gaia-logical-inputs')
SCENARIOS=('unchanged','implementation','shared-header','generated-header','unused-header',
           'high-fanout-header','flags','revert','clean')
PROBE=b'''#include "_gaia_shared.h"
#include "_gaia_generated.h"
#ifndef GAIA_FLAG
#define GAIA_FLAG 0
#endif
__attribute__((visibility("default"))) unsigned gaia_cache_probe(void);
unsigned gaia_cache_probe(void) {return GAIA_SHARED+GAIA_GENERATED+GAIA_FLAG;}
'''


def ninja_path(value):
    """Escape a Ninja path token, independently of shell command quoting."""
    value=str(value)
    if '\n' in value or '\r' in value:raise ValueError('newline in Ninja path')
    return value.replace('$','$$').replace(' ','$ ').replace(':','$:')


def ninja_command(argv):
    return shlex.join(map(str,argv)).replace('$','$$')


def write_ninja(path,commands,link,cwd,output,ccache=None):
    # -f alone does not relocate Ninja's persistent dependency/command logs.
    # Each engine must restore its own logs along with its object files.
    lines=['builddir = '+ninja_path(output)]
    for i,cmd in enumerate(commands):
        obj=output/Path(cmd[cmd.index('-o')+1]).name
        actual=cmd.copy();actual[actual.index('-o')+1]=str(obj)
        actual+=['-MD','-MF',str(obj)+'.d','-MT',str(obj)]
        if ccache:actual.insert(0,str(ccache))
        lines += [f'rule cc{i}',
            '  command = cd '+ninja_command([cwd])+' && '+ninja_command(actual),
            '  description = CC '+obj.name,
            '  depfile = '+ninja_path(str(obj)+'.d'),'  deps = gcc',
            f'build {ninja_path(obj)}: cc{i} '+ninja_path(next(x for x in cmd if x.endswith('.c')))]
    lines += ['rule link','  command = cd '+ninja_command([output])+' && '+ninja_command(link),
              '  description = LINK libzstd.so',
              'build '+ninja_path(output/'libzstd.so')+': link '+
              ' '.join(ninja_path(output/Path(cmd[cmd.index('-o')+1]).name) for cmd in commands),
              'default '+ninja_path(output/'libzstd.so')]
    path.write_text('\n'.join(lines)+'\n')


def observed_delta(files,stats):
    """Scan an admitted namespace, reading only changed files; no watcher assumed."""
    edits={};scans=reads=0
    for name,body in files.items():
        st=Path(name).stat();scans+=1
        if (st.st_mtime_ns,st.st_size)!=stats[name]:
            current=Path(name).read_bytes();reads+=1
            if current!=body:edits[name]=current
    return edits,dict(stat_calls=scans,changed_file_reads=reads)


def prepare(a,work):
    if base.sha(a.archive)!=PIN:raise ValueError('Zstandard archive identity differs')
    start=time.perf_counter()
    with tarfile.open(a.archive) as archive:archive.extractall(work,filter='data')
    root=work/'zstd-1.5.7';cwd=root/'lib';clang=a.llvm/'bin/clang';lld=a.llvm/'bin/ld.lld'
    dry=project.run_checked(['make','-n','libzstd.so.1.5.7','ZSTD_LEGACY_SUPPORT=0','ZSTD_NO_ASM=1','CC='+str(clang)],cwd=cwd)
    commands=[]
    for line in dry.stdout.splitlines():
        cmd=shlex.split(line)
        if not cmd or cmd[0]!=str(clang) or '-c' not in cmd:continue
        cmd=[x for x in cmd if x not in ('-MMD','-MP')]
        source=next(x for x in cmd if x.endswith('.c'));cmd[cmd.index(source)]=str((cwd/source).resolve())
        cmd[cmd.index('-o')+1]=Path(cmd[cmd.index('-o')+1]).name
        commands.append(cmd)
    if len(commands)!=30:raise ValueError('expected pinned 30-TU portable library')
    search=project.run_checked([str(clang),'--no-default-config','-E','-x','c','-','-v'],input='',env=cache.cache_env())
    includes=[];active=False
    for line in search.stderr.splitlines():
        if '#include <...> search starts here:' in line:active=True;continue
        if 'End of search list.' in line:active=False
        if active:includes+=['-isystem',line.strip()]
    if not includes:raise ValueError('missing SDK include search')
    common=['--no-default-config','--target=x86_64-unknown-linux-gnu','-nostdinc','-Werror=date-time',
            '-fdebug-compilation-dir='+str(cwd),*includes]
    commands=[[*cmd,*common] for cmd in commands]
    shared=cwd/'_gaia_shared.h';shared.write_text('#define GAIA_SHARED 1\n')
    generated=cwd/'_gaia_generated.h';generated.write_text('#define GAIA_GENERATED 10\n')
    unused=cwd/'_gaia_unused.h';unused.write_text('/* unused input A */\n')
    probe=cwd/'_gaia_probe.c';probe.write_bytes(PROBE)
    cmd=commands[0].copy();source=next(x for x in cmd if x.endswith('.c'));cmd[cmd.index(source)]=str(probe)
    cmd[cmd.index('-o')+1]='_gaia_probe.o';commands.append(cmd)
    objects=[cmd[cmd.index('-o')+1] for cmd in commands]
    if len(set(objects))!=len(objects):raise ValueError('duplicate output')
    files={str(p):p.read_bytes() for p in root.rglob('*.h')}
    dependencies=[]
    for cmd in commands:
        dep=cmd.copy();i=dep.index('-o');del dep[i:i+2];dep.remove('-c');dep+=['-M','-MT','gaia']
        result=project.run_checked(dep,cwd=cwd,env=cache.cache_env())
        paths=shlex.split(result.stdout.replace('\\\n',' ').split(':',1)[1])
        paths=[str((cwd/p).resolve()) for p in paths];dependencies.append(paths)
        for p in paths:files[p]=Path(p).read_bytes()
    light=str(cwd/'common/zstd_common.c');high=str(cwd/'common/compiler.h')
    changed=files[light].replace(b'return ZSTD_VERSION_NUMBER;',b'return ZSTD_VERSION_NUMBER+1;')
    if changed==files[light]:raise ValueError('source edit missing')
    marker=b'\n#ifndef GAIA_FANOUT_MARKER\n#define GAIA_FANOUT_MARKER\n__attribute__((used)) static const unsigned gaia_fanout_marker = 901;\n#endif\n'
    scenarios={
        'unchanged':({},[],11,10507),
        'implementation':({light:changed},[],11,10508),
        'shared-header':({str(shared):b'#define GAIA_SHARED 2\n'},[],12,10507),
        'generated-header':({str(generated):b'#define GAIA_GENERATED 20\n'},[],21,10507),
        'unused-header':({str(unused):b'/* unused input B */\n'},[],11,10507),
        'high-fanout-header':({high:files[high]+marker},[],11,10507),
        'flags':({},['-DGAIA_FLAG=4'],15,10507),
        'revert':({},[],11,10507),'clean':({},[],11,10507),
    }
    masks={p:(1<<len(commands))-1 for p in files}
    blob=work/'baseline.gci';blob.write_bytes(project.encode_inputs(files))
    views=work/'baseline.views';views.write_text('GAIACV1\n'+'\n'.join(str(masks[p]) for p in sorted(files))+'\n')
    link=[str(lld),'-shared','--threads=1','--build-id=sha1','-soname','libzstd.so.1','-o','libzstd.so',*objects]
    linkplan=work/'link.gcr';linkplan.write_bytes(project.encode_requests([link]))
    plan=work/'commands.gcr';plan.write_bytes(project.encode_requests(commands))
    context=dict(contract='GAIA-RECORDED-VFS-1',host_sha256=base.sha(a.host),
        tools={str(p):base.sha(p) for p in (clang,lld,a.llvm/'lib/libclang-cpp.so',a.llvm/'lib/libLLVM.so.22.1',a.llvm/'lib/liblldELF.so',a.llvm/'lib/liblldCommon.so')})
    for extra_tool in (a.sha256_library,a.blake3_library,a.blake3_helper,getattr(a,'condition_verifier',None)):
        if extra_tool:context['tools'][str(extra_tool)]=base.sha(extra_tool)
    stats={p:(Path(p).stat().st_mtime_ns,Path(p).stat().st_size) for p in files}
    times={p:(Path(p).stat().st_atime_ns,Path(p).stat().st_mtime_ns) for p in files}
    return dict(root=root,cwd=cwd,commands=commands,objects=objects,files=files,masks=masks,scenarios=scenarios,
        blob=blob,views=views,link=link,linkplan=linkplan,plan=plan,context=context,
        context_id=hashlib.sha256(json.dumps(context,sort_keys=True).encode()).hexdigest(),stats=stats,times=times,
        dependencies=dependencies,high_readers=sum(high in deps for deps in dependencies),
        setup_seconds=time.perf_counter()-start)


def report(d,path):
    engines=list(dict.fromkeys(c['engine'] for c in d['cases']))
    lines=['# Incremental build decisions and history','',f"Run `{d['run_id']}`; **{d['status']}**; {d['trials']} randomized blocks; warm page cache.",'',
        'Same Zstandard 1.5.7 portable C library plus one probe, eight workers, exact compiler flags and ordered linker inputs. '
        'Ninja retains normal no-op/link skipping. Gaia journal always runs the producer and LLVM host; history adds up to '
        'three validated journal candidates per action; fast checks the whole namespace; selective checks conditions from successful journals; batched combines job masks; incremental reuses parsed per-action fragments.','',
        '| Scenario | '+' | '.join(e+' ms' for e in engines)+' |',
        '| --- | '+' | '.join('---:' for _ in engines)+' |']
    for name in SCENARIOS:
        cases={c['engine']:c for c in d['cases'] if c['scenario']==name}
        if not cases or any(not c['samples'] for c in cases.values()):continue
        lines.append('| '+name+' | '+' | '.join(f"{statistics.median(s['seconds'] for s in cases[e]['samples'])*1000:.2f}" for e in engines)+' |')
    lines += ['','Clock starts after the editor applies a change and before the build request. Every fast-path sample includes '
        'request identity creation, watch-list preparation, a fresh lightweight Odin process, input metadata checks, receipt validation '
        'and retained-result loading. A hit launches no producer/LLVM process and performs no link. A miss includes the original '
        'stat scan, delta/plan encoding, producer publication, receipt handoff, native compilation/cache/linking and new receipt publication. All condition producers include extraction, cache validation, construction and publication in this clock.','',
        'The whole-namespace gate watches every admitted file. The selective gate checks per-job virtual membership, path ancestors and queried directory listings, and watches contents of queried regular files plus native tools. Missing/corrupt receipts or outputs and changed requests '
        'fall back. Output contents are rehashed if their metadata changes; preserved-metadata mutations are outside this stat-visible '
        'contract. Inputs must match the preflight stamp again before a receipt can be published after success. LLVM libraries are '
        'not linked into the lightweight checker. No daemon or hidden compiler residency is assumed.','',
        'Each observation restores independent output/cache/Ninja log state outside timing. Revert starts from an edited build after '
        'visiting baseline and edited states. History retains at most three complete records per action, including the latest; '
        'this is not a global cache quota. The incremental fragment cache retains only the current request, with at most 64 entries and 8 MiB, validates its checksum, and keys reuse by action, selected journal and logical cwd. Namespace classification and backing-file verification are always rebuilt. Every object candidate still validates framing, checksum, action identity and recorded filesystem '
        'observations. Concurrent rotation may lose reuse opportunities, but incomplete/corrupt candidates must miss.','',
        'All object identities and libraries match independent CLI references, and runtime probes follow each build. The high-fanout '
        'header has '+str(d['high_fanout_readers'])+' independently identified readers. Expected compiler/link counts are checked. '
        'Initial SDK admission, graph generation, editor writes, state restoration and parent validation are excluded for all engines. '
        'Fixed known namespace, ordinary stat-visible edits, one C target and a warm-cache virtualized Linux host limit generalization. '
        'Native compiler tests cover optional-header and earlier-include appearance. Directory listing and visibility semantics are tested against synthetic query journals for the explicit provider. No physical watcher, arbitrary SDK or POSIX/symlink equivalence is claimed.','',
        'Tool versions, source/tool identities, native counters and samples are in ignored `results.json`. Reports and compact '
        'validation/summary files can be retained in version control.','']
    path.write_text('\n'.join(lines))


def run(a):
    if a.decision is None:a.decision=a.producer.parent/'decision-host'
    for name in ('host','producer','decision','archive','llvm','ninja','ccache','output'):
        setattr(a,name,getattr(a,name).resolve())
    for name in ('sha256_library','blake3_library','blake3_helper','condition_verifier'):
        if getattr(a,name):setattr(a,name,getattr(a,name).resolve())
    a.output.mkdir(parents=True,exist_ok=True)
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    work=HERE/'_work'/('ninja-'+run_id);work.mkdir(parents=True)
    info=prepare(a,work);files=info['files']
    env={k:v for k,v in cache.cache_env().items() if not k.startswith('CCACHE_')}
    if a.tool_library_path:env['LD_LIBRARY_PATH']=str(a.tool_library_path.resolve())
    config=work/'ccache.conf';config.write_text('compiler_check = content\nmax_size = 1G\nremote_storage =\n')
    env.update(CCACHE_CONFIGPATH=str(config),CCACHE_DIR=str(work/'ccache'),CCACHE_TEMPDIR=str(work/'ccache-tmp'))
    pinned_tools={**info['context']['tools'],str(a.producer):base.sha(a.producer),str(a.host):base.sha(a.host)}
    tool_stats={p:(Path(p).stat().st_mtime_ns,Path(p).stat().st_size) for p in pinned_tools}
    baseline_changes={p for edits,_,_,_ in info['scenarios'].values() for p in edits}
    def state(name):
        for p in baseline_changes:
            if Path(p).read_bytes()!=files[p] or Path(p).stat().st_mtime_ns!=info['times'][p][1]:
                Path(p).write_bytes(files[p]);os.utime(p,ns=info['times'][p])
        for p,body in info['scenarios'][name][0].items():Path(p).write_bytes(body)
        if name=='revert':
            for p in info['scenarios']['implementation'][0]:Path(p).write_bytes(files[p])
    def commands(name):return [[*cmd,*info['scenarios'][name][1]] for cmd in info['commands']]
    def hashes(output):return {n:base.sha(output/n) for n in [*info['objects'],'libzstd.so']}
    expected={};references=work/'references';references.mkdir()
    for name in a.scenarios:
        if name in ('revert','clean') and 'unchanged' in expected:
            expected[name]=expected['unchanged'];continue
        state(name);out=references/name;out.mkdir()
        def compile_one(cmd):
            cmd=cmd.copy();cmd[cmd.index('-o')+1]=str(out/cmd[cmd.index('-o')+1])
            p=project.run_checked(cmd,cwd=info['cwd'],env=env)
            if p.stderr:raise ValueError('reference diagnostic: '+p.stderr)
        with ThreadPoolExecutor(max_workers=8) as executor:list(executor.map(compile_one,commands(name)))
        project.run_checked(info['link'],cwd=out,env=env);expected[name]=hashes(out)
        print('reference verified',name,flush=True)
    state('unchanged')
    output=work/'build';output.mkdir();store=work/'gaia-cache';store.mkdir()
    blake3=Blake3(a.blake3_helper) if a.blake3_helper else None
    from native_conditions import Verifier
    from shared_inputs import Session
    from logical_workspace import Workspace,Checker,LogicalEmitter,logical_projection
    verifiers={e:Verifier(a.condition_verifier,m) for e,m in [('gaia-native-verify','verify'),('gaia-native-emit','emit'),('gaia-shared-inputs','emit')] if e in a.engines}
    verifiers['gaia-logical-inputs']=LogicalEmitter()
    residents={};decision_workers={};producers={};producer_seeds={};input_sessions={};input_seeds={};logical_workspaces={};logical_seeds={}
    def build(engine,name):
        resident=residents.get(engine)
        def decide(argv):
            if engine=='gaia-logical-inputs':return decision_workers[engine].call(argv)
            if engine in ('gaia-rebound','gaia-retained','gaia-native-verify','gaia-native-emit','gaia-shared-inputs','gaia-logical-inputs'):
                if engine not in decision_workers:decision_workers[engine]=ResidentHost(a.decision,env,completion_metadata=True)
                return decision_workers[engine].request(argv)
            return json.loads(project.run_checked(argv,env=env).stdout)
        cmds=commands(name)
        is_gaia=engine.startswith('gaia-');fast=engine in ('gaia-fast','gaia-selective','gaia-batched','gaia-incremental','gaia-shared','gaia-memo','gaia-inline','gaia-resident','gaia-fast-sha','gaia-blake3','gaia-linked','gaia-rebound','gaia-retained','gaia-native-verify','gaia-native-emit','gaia-shared-inputs','gaia-logical-inputs');selective=engine in ('gaia-selective','gaia-batched','gaia-incremental','gaia-shared','gaia-memo','gaia-inline','gaia-resident','gaia-fast-sha','gaia-blake3','gaia-linked','gaia-rebound','gaia-retained','gaia-native-verify','gaia-native-emit','gaia-shared-inputs','gaia-logical-inputs')
        if not is_gaia:
            write_ninja(output/'build.ninja',cmds,info['link'],info['cwd'],output,a.ccache if engine=='ninja-ccache' else None)
        before=resource.getrusage(resource.RUSAGE_CHILDREN);decision_cpu=decision_workers[engine].cpu_seconds() if engine in decision_workers else 0;resident_cpu=resident.cpu_seconds() if resident else 0;begin=time.perf_counter();extra={}
        if is_gaia:
            for tool,pin in pinned_tools.items():
                st=Path(tool).stat()
                if (st.st_mtime_ns,st.st_size)!=tool_stats[tool] and base.sha(Path(tool))!=pin:
                    raise ValueError('toolchain changed; readmit before using cached outputs: '+tool)
        logical_admission=None
        if engine=='gaia-logical-inputs':
            admitted_begin=time.perf_counter_ns();fresh_workspace=engine not in logical_workspaces
            if fresh_workspace:
                logical_workspaces[engine]=Workspace(files,info['masks'],len(cmds))
                if engine in decision_workers:decision_workers[engine].workspace=logical_workspaces[engine]
                else:decision_workers[engine]=Checker(logical_workspaces[engine],{**pinned_tools,str(a.decision):base.sha(a.decision)})
            packet=info['scenarios'][name][0]
            if name=='revert':packet={p:files[p] for p in info['scenarios']['implementation'][0]}
            logical_generation,logical_admission=logical_workspaces[engine].apply(packet)
            logical_admission['total_ingress_ns']=time.perf_counter_ns()-admitted_begin
            logical_admission['source']='explicit admitted edit packet'
            logical_admission['packet_bytes']=sum(map(len,packet.values()))
            logical_admission['generation']=logical_generation.number
            logical_admission['initial_admission']=logical_workspaces[engine].initial_admission if fresh_workspace else None
            decision_workers[engine].begin()
        decision=None;skip=False;history_stats=None
        if fast:
            watch=output/'decision.inputs';outlist=output/'decision.outputs'
            names=sorted((set() if selective else set(files))|set(info['context']['tools'])|{str(a.host),str(a.producer),str(a.decision)})
            watch.write_text('GAIA-WATCH-1\n'+'\n'.join(names)+'\n')
            outputs=[str(output/'libzstd.so'),str(output/'last-result.json')]
            spec=dict(commands=cmds,link=info['link'],cwd=str(info['cwd']),context=info['context_id'],outputs=outputs)
            if engine in ('gaia-blake3','gaia-linked','gaia-rebound','gaia-retained','gaia-native-verify','gaia-native-emit','gaia-shared-inputs','gaia-logical-inputs'):spec['native_digest_contract']='GAIACIN3/GAIAJR02/BLAKE3-256'
            if engine in ('gaia-shared-inputs','gaia-logical-inputs'):spec['native_digest_contract']='GAIACIN4/GAIAJR02/BLAKE3-256'
            if selective:
                namespace=output/'namespace.gns'
                if engine!='gaia-logical-inputs':namespace.write_bytes(condition_index.encode_namespace(info['masks']))
                index=output/'conditions.gcq';outputs.append(str(index));spec['condition_contract']='GAIACQ01'
            else:spec.update(namespace=sorted(files),masks=info['masks'])
            if engine=='gaia-logical-inputs':spec['condition_contract']='GAIALQ01/authoritative-generations'
            outlist.write_text('GAIA-WATCH-1\n'+'\n'.join(outputs)+'\n')
            request=hashlib.sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest()
            decision_cmd=[str(a.decision),'selective-check' if selective else 'check',str(output/'receipt'),request,str(watch),str(outlist)]
            if selective:decision_cmd += [str(namespace),str(index)]
            decision=decide(decision_cmd)
            if decision['hit']:
                previous=json.loads((output/'last-result.json').read_text())
                result=dict(object_sha256=previous['object_sha256'],compiler_executions=0,compiled=0,link_calls=0,
                            cache_hits=len(cmds),historical_hits=0,errors=0,warnings=0,correct=True)
                extra=dict(native=result,decision=decision,producer=None,snapshot_seconds=0,native_launches=0)
                cmd=decision_cmd;skip=True
            else:
                (output/'receipt').unlink(missing_ok=True)
                if engine in ('gaia-linked','gaia-rebound','gaia-retained','gaia-native-verify','gaia-native-emit','gaia-shared-inputs','gaia-logical-inputs'):
                    history=LinkedResults(output/'linked-results',a.decision,env,runner=decide)
                    destinations={name:output/name for name in ('libzstd.so','last-result.json','conditions.gcq','condition-fragments.gcf')}
                    previous,history_stats=history.restore(request,destinations,watch,namespace,index,output/'receipt',outlist,'last-result.json')
                    extra['linked_results']=history_stats
                    if previous is not None:
                        result=dict(object_sha256=previous['object_sha256'],compiler_executions=0,compiled=0,link_calls=0,
                                    cache_hits=len(cmds),historical_hits=0,errors=0,warnings=0,correct=True)
                        decision=dict(decision,hit=True,historical_result=True)
                        extra.update(native=result,decision=decision,producer=None,snapshot_seconds=0,native_launches=0)
                        cmd=decision_cmd;skip=True
        if is_gaia and not skip:
            if engine=='gaia-logical-inputs':
                logical_generation=decision_workers[engine].capture(decision['stamp'])
                variant=dict(logical_generation.files);edits={n:b for n,b in variant.items() if files.get(n)!=b}
                scan=dict(stat_calls=0,changed_file_reads=0,authoritative_generation=logical_generation.number)
            else:edits,scan=observed_delta(files,info['stats']);variant={**files,**edits}
            view_masks=logical_generation.masks if engine=='gaia-logical-inputs' else info['masks']
            plan=output/'commands.gcr';plan.write_bytes(project.encode_requests(cmds))
            if engine in ('gaia-shared-inputs','gaia-logical-inputs'):
                if engine not in input_sessions:input_sessions[engine]=Session(blake3)
                produced=input_sessions[engine].publish(variant,view_masks,len(cmds),output/'produced.gci',output/'produced.views')
                changed=sorted(edits)
            elif engine in ('gaia-inline','gaia-resident','gaia-fast-sha','gaia-blake3','gaia-linked','gaia-rebound','gaia-retained','gaia-native-verify','gaia-native-emit','gaia-shared-inputs','gaia-logical-inputs'):
                produced=inline_snapshot.publish(variant,info['masks'],len(cmds),output/'produced.gci',output/'produced.views',blake3=blake3 if engine in ('gaia-blake3','gaia-linked','gaia-rebound','gaia-retained','gaia-native-verify','gaia-native-emit','gaia-shared-inputs','gaia-logical-inputs') else None)
                changed=sorted(edits)
            else:
                patch,changed=dependency.delta_bytes(files,variant,info['masks'],base.sha(info['blob']),base.sha(info['views']))
                delta=output/'change.gdp';delta.write_bytes(patch)
                receipt=project.run_checked([str(a.producer),'delta',str(info['blob']),str(info['views']),str(delta),
                    str(output/'produced.gci'),str(output/'produced.views'),'-',str(len(cmds))],env=env)
                produced=json.loads(receipt.stdout)
                if receipt.stderr or produced['loose_reads']!=0:raise ValueError('producer contract violated')
            snapshot_end=time.perf_counter()
            cmd=[str(a.host),'memory',str(a.llvm/'bin/clang'),str(info['cwd']),str(output/'produced.gci'),produced['pin'],
                 str(output),str(plan),'8','internal',str(a.llvm/'bin/ld.lld'),str(info['linkplan']),'direct','journal' if engine=='gaia-journal' else 'journal-history-blake3' if engine in ('gaia-blake3','gaia-linked','gaia-rebound','gaia-retained','gaia-native-verify','gaia-native-emit','gaia-shared-inputs','gaia-logical-inputs') else 'journal-history-fast-hash' if engine in ('gaia-fast-sha','gaia-blake3','gaia-linked','gaia-rebound','gaia-retained','gaia-native-verify','gaia-native-emit','gaia-shared-inputs','gaia-logical-inputs') else 'journal-history-memo' if engine in ('gaia-memo','gaia-inline','gaia-resident','gaia-fast-sha','gaia-blake3','gaia-linked','gaia-rebound','gaia-retained','gaia-native-verify','gaia-native-emit','gaia-shared-inputs','gaia-logical-inputs') else 'journal-history-shared' if engine=='gaia-shared' else 'journal-history',str(store),
                 str(output/'produced.views'),info['context_id']]
            native_begin=time.perf_counter()
            if engine in ('gaia-resident','gaia-fast-sha','gaia-blake3','gaia-linked','gaia-rebound','gaia-retained','gaia-native-verify','gaia-native-emit','gaia-shared-inputs','gaia-logical-inputs'):
                if resident is None:
                    resident=ResidentHost(a.host,env);residents[engine]=resident
                result=resident.request(cmd);stderr=''
            else:
                p=project.run_checked(cmd,cwd=output,env=env);result=json.loads(p.stdout);stderr=p.stderr
            native_end=time.perf_counter()
            if stderr or not result['correct'] or result['cache_write_errors']:raise ValueError('Gaia build failed: '+stderr)
            extra=dict(native=result,scan=scan,changed_paths=changed,producer=produced,snapshot_seconds=snapshot_end-begin,native_launches=0 if engine in ('gaia-resident','gaia-fast-sha','gaia-blake3','gaia-linked','gaia-rebound','gaia-retained','gaia-native-verify','gaia-native-emit','gaia-shared-inputs','gaia-logical-inputs') else 1 if engine=='gaia-inline' else 2,native_process_seconds=native_end-native_begin)
            if history_stats is not None:extra['linked_results']=history_stats
            if fast:
                base.save(output/'last-result.json',result)
                supported=True
                if selective:
                    export_begin=time.perf_counter()
                    try:
                        if engine in ('gaia-retained','gaia-native-verify','gaia-native-emit','gaia-shared-inputs','gaia-logical-inputs'):
                            if engine not in producers:producers[engine]=retained_conditions.Producer(verifiers.get(engine))
                            encoded,index_stats=producers[engine].build(store,result,variant,view_masks,str(info['cwd']),output/'condition-fragments.gcf')
                        elif engine in ('gaia-incremental','gaia-shared','gaia-memo','gaia-inline','gaia-resident','gaia-fast-sha','gaia-blake3','gaia-linked','gaia-rebound','gaia-retained','gaia-native-verify','gaia-native-emit','gaia-shared-inputs','gaia-logical-inputs'):
                            encoded,index_stats=incremental_conditions.build_incremental(store,result,variant,info['masks'],str(info['cwd']),output/'condition-fragments.gcf')
                        else:
                            journals=condition_index.selected_journals(store,result)
                            builder=incremental_conditions.build_batched if engine=='gaia-batched' else condition_index.build_index
                            encoded,index_stats=builder(journals,variant,info['masks'],str(info['cwd']))
                        index.write_bytes(encoded)
                        extra['index']=index_stats
                    except (condition_index.UnsupportedIndex,OSError,UnicodeError) as error:
                        supported=False;extra['index']={'unsupported':str(error)}
                    extra['index_export_seconds']=time.perf_counter()-export_begin
                record_cmd=[str(a.decision),'selective-record' if selective else 'record',str(output/'receipt'),request,str(watch),str(outlist)]
                if selective:record_cmd += [str(namespace),str(index)]
                record_cmd += [decision['stamp']]
                receipt=decide(record_cmd) if supported else {'recorded':False,'inputs_unchanged':True}
                if not receipt['inputs_unchanged']:raise ValueError('inputs changed during build; receipt refused')
                extra.update(decision=decision,receipt=receipt)
                if engine in ('gaia-linked','gaia-rebound','gaia-retained','gaia-native-verify','gaia-native-emit','gaia-shared-inputs','gaia-logical-inputs') and receipt.get('recorded'):
                    history=LinkedResults(output/'linked-results',a.decision,env,runner=decide)
                    artifacts={name:output/name for name in ('libzstd.so','last-result.json','conditions.gcq','condition-fragments.gcf') if (output/name).exists()}
                    extra['linked_store']=history.store(request,artifacts,watch,namespace,index,decision['stamp'],source_receipt=output/'receipt' if engine in ('gaia-rebound','gaia-retained','gaia-native-verify','gaia-native-emit','gaia-shared-inputs','gaia-logical-inputs') else None)
                    if not extra['linked_store']['stored']:raise ValueError('benchmark linked-result publication failed: '+str(extra['linked_store']))
        elif not is_gaia:
            cmd=[str(a.ninja),'-f',str(output/'build.ninja'),'-j8']
            p=project.run_checked(cmd,cwd=info['cwd'],env=env)
            extra=dict(compile_edges=sum(line.startswith('[') and '] CC ' in line for line in p.stdout.splitlines()),
                       link_edges=sum(line.startswith('[') and '] LINK ' in line for line in p.stdout.splitlines()),stdout=p.stdout)
        end=time.perf_counter();after=resource.getrusage(resource.RUSAGE_CHILDREN)
        if logical_admission is not None:extra['logical_admission']=logical_admission
        sample=dict(seconds=end-begin,cpu_seconds=after.ru_utime-before.ru_utime+after.ru_stime-before.ru_stime,command=cmd,**extra)
        if engine in ('gaia-retained','gaia-native-verify','gaia-native-emit','gaia-shared-inputs','gaia-logical-inputs') and not sample['decision']['hit']:
            # Independent producer equivalence is parent verification, outside
            # timing like CLI object/library checks; no work moves out of build.
            reference,_=condition_index.build_index(condition_index.selected_journals(store,result),variant,view_masks,str(info['cwd']))
            if engine=='gaia-logical-inputs':reference=logical_projection(reference)
            if index.read_bytes()!=reference:raise ValueError('retained condition wire differs from reference')
            sample['condition_index_matches_reference']=True
        if engine in ('gaia-resident','gaia-fast-sha','gaia-blake3','gaia-linked','gaia-rebound','gaia-retained','gaia-native-verify','gaia-native-emit','gaia-shared-inputs','gaia-logical-inputs'):
            sample['resident_cpu_seconds']=resident.cpu_seconds()-resident_cpu
            sample['cpu_seconds']+=sample['resident_cpu_seconds']
        if engine in decision_workers:
            sample['decision_cpu_seconds']=decision_workers[engine].cpu_seconds()-decision_cpu
            sample['cpu_seconds']+=sample['decision_cpu_seconds']
        required={'unchanged':0,'unused-header':0,'implementation':1,'revert':1,
                  'shared-header':1,'generated-header':1,'high-fanout-header':info['high_readers'],
                  'flags':len(info['objects']),'clean':len(info['objects'])}[name]
        # Seeding is a clean build even when its scenario is called unchanged.
        # Timed observations below enforce the expected incremental work counts.
        if is_gaia:
            actual=dict(zip(info['objects'],extra['native']['object_sha256']));actual['libzstd.so']=base.sha(output/'libzstd.so')
        else:actual=hashes(output)
        if name in expected and actual!=expected[name]:raise ValueError('artifact mismatch: '+engine+' '+name)
        _,_,probe,version=info['scenarios'][name];cache.library_check(output/'libzstd.so',probe,version)
        sample['artifacts_match']=True
        if name=='revert' and engine in ('gaia-history','gaia-fast','gaia-selective','gaia-batched','gaia-incremental','gaia-shared','gaia-memo','gaia-inline','gaia-resident','gaia-fast-sha','gaia-blake3','gaia-linked','gaia-rebound','gaia-retained','gaia-native-verify','gaia-native-emit','gaia-shared-inputs','gaia-logical-inputs'):required=0
        sample['expected_incremental_compilers']=required
        if engine=='ninja-ccache':
            stats=project.run_checked([str(a.ccache),'--print-stats'],env=env)
            sample['ccache_stats']={parts[0]:int(parts[1]) for line in stats.stdout.splitlines() if len(parts:=line.split())==2 and parts[1].isdigit()}
        return sample
    def reset(path):
        if path.exists():shutil.rmtree(path)
        path.mkdir()
    seeds={};setup=[]
    for engine in a.engines:
        state('unchanged');reset(output);reset(store);reset(work/'ccache')
        s=build(engine,'unchanged');setup.append(dict(engine=engine,state='unchanged',sample=s))
        seed=work/('seed-'+engine);seed.mkdir()
        for path in (output,store,work/'ccache'):shutil.copytree(path,seed/path.name)
        seeds[(engine,'baseline')]=seed
        if engine in ('gaia-retained','gaia-native-verify','gaia-native-emit','gaia-shared-inputs','gaia-logical-inputs'):producer_seeds[(engine,'baseline')]=producers[engine].snapshot()
        if engine=='gaia-logical-inputs':logical_seeds[(engine,'baseline')]=logical_workspaces[engine].snapshot()
        if engine in ('gaia-shared-inputs','gaia-logical-inputs'):input_seeds[(engine,'baseline')]=(input_sessions[engine].snapshot(),s['producer']['pin'])
        if 'revert' in a.scenarios:
            state('implementation');s=build(engine,'implementation');setup.append(dict(engine=engine,state='implementation',sample=s))
            seed=work/('edited-'+engine);seed.mkdir()
            for path in (output,store,work/'ccache'):shutil.copytree(path,seed/path.name)
            seeds[(engine,'edited')]=seed
            if engine in ('gaia-retained','gaia-native-verify','gaia-native-emit','gaia-shared-inputs','gaia-logical-inputs'):producer_seeds[(engine,'edited')]=producers[engine].snapshot()
            if engine=='gaia-logical-inputs':logical_seeds[(engine,'edited')]=logical_workspaces[engine].snapshot()
            if engine in ('gaia-shared-inputs','gaia-logical-inputs'):input_seeds[(engine,'edited')]=(input_sessions[engine].snapshot(),s['producer']['pin'])
    versions={n:project.run_checked([str(p),'--version'],env=env).stdout for n,p in [('ninja',a.ninja),('ccache',a.ccache),('clang',a.llvm/'bin/clang')]}
    d=dict(run_id=run_id,status='running',trials=a.trials,work=str(work),versions=versions,
        environment=dict(uname=list(os.uname()),cpu_count=os.cpu_count(),cache='warm',
                         lscpu=project.run_checked(['lscpu']).stdout,
                         meminfo=Path('/proc/meminfo').read_text(),cpu_affinity=sorted(os.sched_getaffinity(0))),source_archive_sha256=PIN,
        high_fanout_readers=info['high_readers'],setup_seconds=info['setup_seconds'],context=info['context'],
        producer_sha256=base.sha(a.producer),tool_sha256={str(p):base.sha(p) for p in (a.ninja,a.ccache)},
        cases=[dict(engine=e,scenario=s,samples=[]) for s in a.scenarios for e in a.engines],setup=setup,
        adapter_source_sha256={p.name:base.sha(p) for p in HERE.glob('*') if p.suffix in ('.py','.odin','.cpp','.c','.h')})
    d['decision_sha256']=base.sha(a.decision) if any(e in a.engines for e in ('gaia-fast','gaia-selective','gaia-batched','gaia-incremental','gaia-shared','gaia-memo','gaia-inline','gaia-resident','gaia-fast-sha','gaia-blake3','gaia-linked','gaia-rebound','gaia-retained','gaia-native-verify','gaia-native-emit','gaia-shared-inputs','gaia-logical-inputs')) else None
    d['decision_libraries']=project.run_checked(['ldd',str(a.decision)]).stdout if any(e in a.engines for e in ('gaia-fast','gaia-selective','gaia-batched','gaia-incremental','gaia-shared','gaia-memo','gaia-inline','gaia-resident','gaia-fast-sha','gaia-blake3','gaia-linked','gaia-rebound','gaia-retained','gaia-native-verify','gaia-native-emit','gaia-shared-inputs','gaia-logical-inputs')) else None
    snapshots=work/'sources';snapshots.mkdir()
    for name,pin in d['adapter_source_sha256'].items():
        shutil.copy2(HERE/name,snapshots/name)
        if base.sha(snapshots/name)!=pin:raise ValueError('experiment source changed during setup')
    d['source_snapshots']=str(snapshots)
    def save():base.save(a.output/'results.json',d);report(d,a.output/'REPORT.md')
    save();rng=random.Random(20261110)
    for block in range(a.trials):
        order=d['cases'].copy();rng.shuffle(order)
        for case in order:
            name=case['scenario'];engine=case['engine'];state('unchanged')
            for path in (output,store,work/'ccache'):
                if path.exists():shutil.rmtree(path)
                if name=='clean':path.mkdir()
                else:shutil.copytree(seeds[(engine,'edited' if name=='revert' else 'baseline')]/path.name,path)
            state(name)
            if engine in ('gaia-retained','gaia-native-verify','gaia-native-emit','gaia-shared-inputs','gaia-logical-inputs'):producers[engine].restore(None if name=='clean' else producer_seeds[(engine,'edited' if name=='revert' else 'baseline')])
            if engine=='gaia-logical-inputs':
                if name=='clean':logical_workspaces.pop(engine,None)
                else:logical_workspaces[engine].restore(logical_seeds[(engine,'edited' if name=='revert' else 'baseline')])
            if engine in ('gaia-shared-inputs','gaia-logical-inputs'):
                session=input_sessions[engine]
                if name=='clean':
                    session.restore(None);control=residents[engine].request([str(a.host),'shared-reset',''])
                else:
                    seed_state,seed_pin=input_seeds[(engine,'edited' if name=='revert' else 'baseline')]
                    session.restore(seed_state)
                    control=residents[engine].request([str(a.host),'shared-prime',str(output/'produced.gci'),seed_pin,session.keep_pins()])
                if not control['correct']:raise ValueError('shared receiver seed restoration failed')
            if engine=='ninja-ccache':project.run_checked([str(a.ccache),'--zero-stats'],env=env)
            sample=build(engine,name)
            actual_work=sample['native']['compiler_executions'] if engine.startswith('gaia-') else sample['compile_edges']
            if actual_work!=sample['expected_incremental_compilers']:
                raise ValueError('unexpected incremental work: '+engine+' '+name+' '+str(actual_work))
            if engine.startswith('gaia-'):
                expected_links=0 if sample.get('decision',{}).get('hit') else 1
                if sample['native']['link_calls']!=expected_links:raise ValueError('unexpected Gaia link work')
                if engine in ('gaia-fast','gaia-selective','gaia-batched','gaia-incremental','gaia-shared','gaia-memo','gaia-inline','gaia-resident','gaia-fast-sha','gaia-blake3','gaia-linked','gaia-rebound','gaia-retained','gaia-native-verify','gaia-native-emit','gaia-shared-inputs','gaia-logical-inputs') and name=='unchanged' and (not sample['decision']['hit'] or sample['native_launches']!=0):
                    raise ValueError('unchanged fast build must skip producer, LLVM and link')
                if engine in ('gaia-selective','gaia-batched','gaia-incremental','gaia-shared','gaia-memo','gaia-inline','gaia-resident','gaia-fast-sha','gaia-blake3','gaia-linked','gaia-rebound','gaia-retained','gaia-native-verify','gaia-native-emit','gaia-shared-inputs','gaia-logical-inputs') and name=='unused-header' and (not sample['decision']['hit'] or sample['native_launches']!=0):
                    raise ValueError('irrelevant edit must skip producer, LLVM and link')
                if engine in ('gaia-history','gaia-fast','gaia-selective','gaia-batched','gaia-incremental','gaia-shared','gaia-memo','gaia-inline','gaia-resident','gaia-fast-sha','gaia-blake3','gaia-linked','gaia-rebound','gaia-retained','gaia-native-verify','gaia-native-emit','gaia-shared-inputs','gaia-logical-inputs') and name=='revert' and not sample.get('linked_results',{}).get('hit') and sample['native']['historical_hits']!=1:
                    raise ValueError('revert must reuse the historical source object')
            if engine in ('gaia-incremental','gaia-shared','gaia-memo','gaia-inline','gaia-resident','gaia-fast-sha','gaia-blake3','gaia-linked','gaia-rebound','gaia-retained','gaia-native-verify','gaia-native-emit','gaia-shared-inputs','gaia-logical-inputs') and not sample['decision']['hit']:
                expected_fragments=info['high_readers'] if name=='high-fanout-header' else len(info['objects']) if name in ('flags','clean') else 1
                stats=sample['index']
                if stats.get('fragment_misses')!=expected_fragments or stats.get('fragment_hits')!=len(info['objects'])-expected_fragments or not stats.get('fragment_cache_published'):
                    raise ValueError('unexpected incremental fragment reuse: '+name+' '+str(stats))
            if not engine.startswith('gaia-') and sample['link_edges']!=int(actual_work>0):
                raise ValueError('unexpected Ninja link work: '+name)
            case['samples'].append(sample)
            print('block',block+1,engine,name,f"{sample['seconds']*1000:.2f} ms",flush=True);save()
    if residents:
        d['residents']={engine:worker.statistics() for engine,worker in residents.items()}
        for worker in residents.values():worker.close()
    if decision_workers:
        d['decision_workers']={engine:worker.statistics() for engine,worker in decision_workers.items()}
        for worker in decision_workers.values():worker.close()
    state('unchanged');d['status']='complete';save()
    base.save(a.output/'validation.json',dict(run_id=run_id,passed=True,
        timed_builds=sum(len(c['samples']) for c in d['cases']),objects_per_build=len(info['objects']),
        all_objects_and_libraries_match=True,all_runtime_probes_pass=True,all_incremental_work_counts_match=True,
        high_fanout_readers=info['high_readers'],raw_sha256=base.sha(a.output/'results.json'),
        tools={n:v.splitlines()[0] for n,v in versions.items()},host_sha256=base.sha(a.host)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    base.toolchain_arguments(parser,headers=False)
    parser.add_argument('--archive',type=Path,default=HERE/'_work/downloads/zstd-1.5.7.tar.gz')
    parser.add_argument('--condition-verifier',type=Path,help='Pinned Odin batched condition verifier shared library')
    parser.add_argument('--blake3-helper',type=Path,help='Pinned caller BLAKE3 one-shot helper')
    parser.add_argument('--blake3-library',type=Path,help='Pin the BLAKE3 library used by the caller helper')
    parser.add_argument('--sha256-library',type=Path,help='Pin the optional linked OpenSSL crypto library in the execution context')
    parser.add_argument('--host',type=Path,required=True)
    parser.add_argument('--producer',type=Path,required=True)
    parser.add_argument('--decision',type=Path,help='Lightweight receipt validator (default beside producer)')
    parser.add_argument('--ninja',type=Path,default=shutil.which('ninja'),required=not shutil.which('ninja'))
    parser.add_argument('--ccache',type=Path,default=shutil.which('ccache'),required=not shutil.which('ccache'))
    parser.add_argument('--tool-library-path',type=Path,help='Optional runtime libraries for locally extracted comparison tools')
    parser.add_argument('--trials',type=int,default=7)
    parser.add_argument('--scenarios',nargs='+',choices=SCENARIOS,default=list(SCENARIOS))
    parser.add_argument('--engines',nargs='+',choices=ENGINES,default=[e for e in ENGINES if e not in ('gaia-fast-sha','gaia-blake3','gaia-linked','gaia-rebound','gaia-retained','gaia-native-verify','gaia-native-emit','gaia-shared-inputs','gaia-logical-inputs')])
    parser.add_argument('--output',type=Path,default=HERE/'_work/runs/ninja-comparison')
    args=parser.parse_args()
    if args.trials<1:parser.error('positive trials required')
    if len(set(args.engines))!=len(args.engines) or len(set(args.scenarios))!=len(args.scenarios):parser.error('duplicate cases')
    if any(e in args.engines for e in ('gaia-fast-sha','gaia-blake3','gaia-linked','gaia-rebound','gaia-retained','gaia-native-verify','gaia-native-emit','gaia-shared-inputs','gaia-logical-inputs')) and not args.sha256_library:parser.error('gaia-fast-sha requires --sha256-library for tool identity')
    if any(e in args.engines for e in ('gaia-blake3','gaia-linked','gaia-rebound','gaia-retained','gaia-native-verify','gaia-native-emit','gaia-shared-inputs','gaia-logical-inputs')) and (not args.blake3_library or not args.blake3_helper):parser.error('BLAKE3 engines require --blake3-library and --blake3-helper')
    if any(e in args.engines for e in ('gaia-native-verify','gaia-native-emit','gaia-shared-inputs','gaia-logical-inputs')) and not args.condition_verifier:parser.error('native condition engines require --condition-verifier')
    run(args)
