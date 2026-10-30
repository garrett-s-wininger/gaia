"""Real Clang object generation: CLI, Odin/C++ physical inputs, mapped inputs."""
import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import re
import resource
import shutil
import statistics
import struct
import subprocess
import time

HERE=Path(__file__).resolve().parent
FLAGS=['--target=x86_64-unknown-linux-gnu','-x','c','-std=c11','-O2','-ffreestanding',
       '-nostdinc','-fno-ident','-fno-addrsig','-fno-stack-protector','-c']


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n')


def odin_executable():
    requested=os.environ.get('ODIN','odin')
    found=shutil.which(requested)
    if not found:raise RuntimeError('Odin unavailable: put odin on PATH or set ODIN to its executable')
    return found


def toolchain_arguments(parser,headers=True):
    """Require a caller-selected LLVM installation; never assume a host layout."""
    prefix=os.environ.get('GAIA_LLVM')
    parser.add_argument('--llvm',type=Path,default=Path(prefix) if prefix else None,
                        required=not prefix,help='LLVM 22 prefix (or set GAIA_LLVM)')
    if headers:
        include=os.environ.get('GAIA_LLVM_HEADERS') or (str(Path(prefix)/'include') if prefix else None)
        parser.add_argument('--llvm-headers',type=Path,default=Path(include) if include else None,
                            required=not include,help='Matching development include directory (or set GAIA_LLVM_HEADERS)')


def admitted_tool(info,name):
    """Use the exact tool selected by a freshly generated predecessor dataset."""
    matches=[Path(p) for p in info['toolchain_sha256'] if Path(p).name==name]
    if len(matches)!=1:raise ValueError('expected one admitted tool: '+name)
    path=matches[0]
    if not path.is_file() or sha(path)!=info['toolchain_sha256'][str(path)]:
        raise ValueError('admitted tool missing or changed; regenerate upstream inputs: '+str(path))
    return path


def bundle(files):
    result=bytearray(b'GAIACIN1'+struct.pack('<Q',len(files)))
    for name,body in files.items():
        name=name.encode();result+=struct.pack('<IQ',len(name),len(body))+name+b'\0'+body+b'\0'
    return result


def fixture(directory,headers):
    start=time.perf_counter();directory.mkdir();root=directory/'inputs';root.mkdir()
    files={}
    for i in range(headers):
        files[f'h{i:05}.h']=(f'#pragma once\ntypedef struct {{unsigned long v[4];}} GaType{i};\n'
            f'static inline unsigned long ga_fn{i}(unsigned long x){{return (x+{i*7%1000}UL)^{(i+17)*2654435761}UL;}}\n').encode()
    includes=''.join(f'#include "h{i:05}.h"\n' for i in range(headers))
    calls=''.join(f'x=ga_fn{i}(x);\n' for i in range(headers))
    for i in range(8):
        files[f'unit{i}.c']=(includes+f'unsigned long gaia_unit{i}(unsigned long x){{\n'+calls+f'return x^{i}UL;}}\n').encode()
    for name,body in files.items():(root/name).write_bytes(body)
    blob=directory/'inputs.gci';blob.write_bytes(bundle(files))
    return dict(headers=headers,root=str(root),bundle=str(blob),pin=sha(blob),
                files=len(files),payload_bytes=sum(map(len,files.values())),bundle_bytes=blob.stat().st_size,
                producer_seconds=time.perf_counter()-start,
                source_sha256={n:hashlib.sha256(v).hexdigest() for n,v in files.items()}),files


def build(args,work,bridge='bridge.cpp',odin_source='host.odin',extra_libraries=()):
    directory=work/'build';directory.mkdir()
    clang=args.llvm/'bin/clang';cpp=args.llvm/'bin/clang++'
    includes=args.llvm_headers
    if not (includes/'llvm/Support/VirtualFileSystem.h').is_file():
        raise RuntimeError('LLVM development headers missing; see README.md for workspace-local setup')
    odin=odin_executable()
    commands=[
        [str(cpp),'-std=c++17','-O2','-fPIC','-I'+str(args.llvm/'include'),'-I'+str(includes),
         '-c',str(HERE/bridge),'-o',str(directory/'bridge.o')],
        [odin,'build',str(HERE/odin_source),'-file','-o:speed','-build-mode:obj','-out:'+str(directory/'host.o')],
        [str(cpp),str(directory/'host.o'),str(directory/'bridge.o'),str(args.llvm/'lib/libclang-cpp.so'),
         str(args.llvm/'lib/libLLVM.so.22.1'),*map(str,extra_libraries),'-pthread',
         '-Wl,-rpath,'+str(args.llvm/'lib'),'-o',str(directory/'host')]]
    start=time.perf_counter()
    for command in commands:
        result=subprocess.run(command,capture_output=True,text=True)
        if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    metadata=dict(commands=commands,seconds=time.perf_counter()-start,host_sha256=sha(directory/'host'),
                  odin_version=subprocess.check_output([odin,'version'],text=True).strip())
    return directory/'host',metadata


def command(clang,host,case,mode,output):
    if mode=='cli':return [str(clang),*FLAGS,*[str(Path(case['root'])/f'unit{i}.c') for i in range(case['requests'])]]
    return [str(host),mode,str(clang),case['root'],case['bundle'],case['pin'],str(output),str(case['requests'])]


def consume(cmd,output,mode):
    before=resource.getrusage(resource.RUSAGE_CHILDREN);start=time.perf_counter()
    process=subprocess.run(cmd,cwd=output,capture_output=True,text=True,timeout=120)
    elapsed=time.perf_counter()-start;after=resource.getrusage(resource.RUSAGE_CHILDREN)
    if process.returncode:raise RuntimeError(process.stderr+'\n'+process.stdout)
    result={} if mode=='cli' else json.loads(process.stdout)
    if mode!='cli' and (not result['correct'] or result['errors'] or result['warnings']):
        raise ValueError('compiler result differs')
    if process.stderr:raise ValueError('unexpected diagnostics: '+process.stderr)
    result.update(wall_seconds=elapsed,user_seconds=after.ru_utime-before.ru_utime,
                  system_seconds=after.ru_stime-before.ru_stime,
                  cpu_seconds=after.ru_utime-before.ru_utime+after.ru_stime-before.ru_stime,
                  minor_faults=after.ru_minflt-before.ru_minflt,major_faults=after.ru_majflt-before.ru_majflt)
    return result


def objects(output,count):
    return {f'unit{i}.o':sha(output/f'unit{i}.o') for i in range(count)}


def execute_objects(clang,output,headers,count):
    library=output/'validation.so'
    subprocess.run([str(clang),'-shared',*[str(output/f'unit{i}.o') for i in range(count)],'-o',str(library)],
                   check=True,capture_output=True,text=True)
    module=ctypes.CDLL(str(library));value=7
    if ctypes.sizeof(ctypes.c_ulong)!=8:raise ValueError('fixture requires 64-bit unsigned long')
    for i in range(headers):value=((value+i*7%1000)^((i+17)*2654435761))&((1<<64)-1)
    for i in range(count):
        fn=getattr(module,'gaia_unit'+str(i));fn.argtypes=[ctypes.c_ulong];fn.restype=ctypes.c_ulong
        if fn(7)!=(value^i):raise ValueError('linked object execution differs')


def boundary_checks(clang,host,case,files,work,expected):
    directory=work/'boundary';directory.mkdir();out=directory/'out';out.mkdir()
    outcomes=[]
    def check(label,content=None,pin=None,expected_code=None,diagnostic=False):
        blob=directory/(label+'.gci')
        blob.write_bytes(content if content is not None else bundle(files))
        c={**case,'requests':1,'bundle':str(blob),'pin':pin or sha(blob)}
        p=subprocess.run(command(clang,host,c,'memory',out),cwd=out,capture_output=True,text=True,timeout=120)
        if expected_code is not None and p.returncode!=expected_code:raise ValueError(label+' did not fail as expected: '+p.stderr)
        if diagnostic and (not p.returncode or not json.loads(p.stdout)['errors'] or not p.stderr):
            raise ValueError(label+' did not return compiler diagnostics')
        outcomes.append(dict(check=label,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
    check('wrong-pin',pin='0'*64,expected_code=3)
    check('truncated',content=bundle(files)[:-1],expected_code=3)
    bad=dict(files);bad['../outside.h']=b'bad';check('unsafe-name',bundle(bad),expected_code=3)
    missing=dict(files);del missing['h00000.h'];check('missing-header',bundle(missing),diagnostic=True)
    invalid=dict(files);invalid['unit0.c']=b'int broken( {\n';check('syntax-error',bundle(invalid),diagnostic=True)
    original=Path(case['root']);hidden=original.with_name('inputs-hidden');original.rename(hidden)
    try:
        sample=consume(command(clang,host,{**case,'requests':1},'memory',out),out,'memory')
        if objects(out,1)['unit0.o']!=expected['unit0.o']:raise ValueError('hidden-input object differs')
        outcomes.append(dict(check='loose-inputs-unavailable',correct=True,result=sample))
    finally:hidden.rename(original)
    return outcomes


def trace_counts(case,path):
    counts={};bundle_counts={}
    process_execs=frontend_execs=0
    for line in path.read_text().splitlines():
        match=re.match(r'(?:\d+\s+)?([a-zA-Z0-9_]+)\(',line)
        if match and match[1]=='execve':
            process_execs+=1;frontend_execs+='"-cc1"' in line
        if not match or match[1] not in ('openat','openat2','newfstatat','statx','access','read','pread64','mmap'):continue
        # inputs.gci shares the 'inputs' basename; it is not inside inputs/.
        root=case['root']
        owned=(root+'/' in line or '"'+root+'"' in line or '<'+root+'>' in line)
        if owned:counts[match[1]]=counts.get(match[1],0)+1
        if case['bundle'] in line:bundle_counts[match[1]]=bundle_counts.get(match[1],0)+1
    return dict(headers=case['headers'],requests=case['requests'],mode=case['mode'],path=str(path),
                input_path_calls=counts,bundle_path_calls=bundle_counts,
                process_execs=process_execs,frontend_execs=frontend_execs)


def trace(clang,host,case,mode,output,work):
    path=work/(str(case['headers'])+'-'+mode+'.strace')
    cmd=command(clang,host,case,mode,output)
    p=subprocess.run(['strace','-f','-yy','-e','trace=%file,read,pread64,mmap,close','-o',str(path),*cmd],
                     cwd=output,capture_output=True,text=True,timeout=120)
    if p.returncode:raise RuntimeError(p.stderr)
    return trace_counts(case,path)


def report(data,path):
    lines=['# Programmatic compiler invocation: Clang 22 / Odin host','',
           f"Run `{data['run_id']}`; **{data['status']}**. {data['trials']} randomized fresh processes per case; warm filesystem cache.",'',
           'Actual C object generation at -O2, same compiler/target/flags and input bytes. CLI is one '
           'ordinary Clang command accepting all requested source files, not one artificial wrapper '
           'process per file. Physical and memory modes use Odin + Clang ToolInvocation/EmitObjAction '
           'in process. Memory mode hashes/validates one mapped collection and uses a VFS with no '
           'host input fallback. Each request creates/disposes its compiler/FileManager state; no '
           'PCH, saved AST, completed result or incremental parse state is reused.','',
           '| Headers per TU | TUs per process | Mode | Process median ms | Range ms | Child CPU ms | Compile ms | Input mount ms |',
           '| ---: | ---: | --- | ---: | --- | ---: | ---: | ---: |']
    for c in data['cases']:
        s=c['samples']
        if not s:continue
        wall=[v['wall_seconds']*1000 for v in s]
        med=lambda k:statistics.median(v[k] for v in s)
        compile_ms=f"{med('compile_ns')/1e6:.3f}" if c['mode']!='cli' else '—'
        mount=f"{(med('map_ns')+med('setup_ns'))/1e6:.3f}" if c['mode']!='cli' else '—'
        lines.append(f"| {c['headers']} | {c['requests']} | {c['mode']} | {statistics.median(wall):.3f} | "
                     f"{min(wall):.2f}–{max(wall):.2f} | {med('cpu_seconds')*1000:.3f} | {compile_ms} | {mount} |")
    lines+=['','## Paired full-process comparisons','',
            '| Headers | TUs | Comparison | Median paired change ms | Wins / trials |',
            '| ---: | ---: | --- | ---: | ---: |']
    for headers in sorted({c['headers'] for c in data['cases']}):
        for requests in (1,8):
            cases={c['mode']:c for c in data['cases'] if c['headers']==headers and c['requests']==requests}
            for mode,base in [('physical','cli'),('memory','cli'),('memory','physical')]:
                if mode not in cases or not cases[mode]['samples']:continue
                delta=[(a['wall_seconds']-b['wall_seconds'])*1000 for a,b in zip(cases[mode]['samples'],cases[base]['samples'])]
                if not delta:continue
                lines.append(f"| {headers} | {requests} | {base} → {mode} | {statistics.median(delta):+.3f} | {sum(v<0 for v in delta)}/{len(delta)} |")
    lines+=['','All timed object hashes match CLI controls. Each mode/case warmup is linked and '
            'executed against independently computed results; linking/validation are outside '
            'compile timing. Timing includes compiler startup, mapped input authentication/setup, '
            'code generation/object writes, compiler-state disposal and process exit. Native phase '
            'clocks exclude startup; do not subtract independent medians. Native registration '
            'is included in setup, and compilation includes per-request setup/destruction. '
            'Programmatic mode disables Clang DisableFree to reclaim each request; CLI defaults '
            'may use process-exit reclamation. Both use normal process exit.','',
            'This is a synthetic flat C input fixture with repeated headers and eight generated '
            'source files, not a representative project or a standard protocol. In-memory VFS '
            'still uses path lookups and mutable per-file metadata; only payloads borrow the '
            'immutable mapping. Output and runtime-library activity remain filesystem based. '
            'Producer fixture generation, toolchain/header acquisition and adapter compilation '
            'are separate recorded costs. Current target: Linux x86-64, Clang/LLVM 22.1.8.','']
    if data.get('boundary_checks'):
        lines+=['Boundary checks: '+', '.join(v['check'] for v in data['boundary_checks'])+'.','']
    if data.get('traces'):
        lines+=['## Separate syscall observations','',
                '| Headers | TUs | Mode | Loose-input path syscalls | Bundle path syscalls | Process execs / cc1 execs |',
                '| ---: | ---: | --- | --- | --- | ---: |']
        for row in data['traces']:
            lines.append(f"| {row['headers']} | {row['requests']} | {row['mode']} | {row['input_path_calls']} | {row['bundle_path_calls']} | {row['process_execs']} / {row['frontend_execs']} |")
        lines+=['','Traces are separate runs and not benchmark samples. Counts match absolute input '
                'paths in file/read/mmap syscalls; failed probes are included. They are not whole '
                'process syscall totals or physical disk reads. Raw paths/traces are local artifacts.','']
    path.write_text('\n'.join(lines))


def run(args):
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    work=HERE/'_work'/run_id;work.mkdir(parents=True);args.output.mkdir(parents=True,exist_ok=True)
    clang=args.llvm/'bin/clang'
    if args.host:host=args.host.resolve();build_info=dict(external_host=str(host),host_sha256=sha(host))
    else:host,build_info=build(args,work)
    data=dict(run_id=run_id,status='running',trials=args.trials,work=str(work),build=build_info,
              environment=dict(uname=list(platform.uname()),cpu_count=os.cpu_count(),cache='warm/reused; no eviction',
                 clang_version=subprocess.check_output([str(clang),'--version'],text=True).strip()),
              source_sha256={n:sha(HERE/n) for n in ('bridge.cpp','host.odin','benchmark.py')},
              toolchain_sha256={str(p):sha(p) for p in (clang,args.llvm/'lib/libclang-cpp.so',args.llvm/'lib/libLLVM.so.22.1')},
              fixtures=[],cases=[])
    all_files={}
    for headers in args.headers:
        source,files=fixture(work/('headers-'+str(headers)),headers);data['fixtures'].append(source);all_files[headers]=files
        for requests in (1,8):
            for mode in ('cli','physical','memory'):
                output=work/(f'{headers}-{requests}-{mode}');output.mkdir()
                case={**source,'requests':requests,'mode':mode,'output':str(output),'samples':[]}
                case['command']=command(clang,host,case,mode,output);data['cases'].append(case)
    references={}
    def take(case):
        sample=consume(case['command'],Path(case['output']),case['mode'])
        if case['mode']!='cli' and sample['compiled']!=case['requests']:raise ValueError('compiled request count differs')
        hashes=objects(Path(case['output']),case['requests']);key=(case['headers'],case['requests'])
        if key in references and hashes!=references[key]:raise ValueError('object bytes differ: '+str(key)+' '+case['mode'])
        references.setdefault(key,hashes);sample['objects_sha256']=hashes;return sample
    for case in data['cases']:
        case['warmup']=take(case)
        execute_objects(clang,Path(case['output']),case['headers'],case['requests'])
        print('verified objects/execution',case['headers'],case['requests'],case['mode'],flush=True)
    small=next(c for c in data['cases'] if c['headers']==args.headers[0] and c['requests']==1)
    data['boundary_checks']=boundary_checks(clang,host,small,all_files[args.headers[0]],work,references[(args.headers[0],1)])
    def checkpoint():save(args.output/'results.json',data);report(data,args.output/'REPORT.md')
    checkpoint();rng=random.Random(20261101)
    for trial in range(args.trials):
        shuffled=data['cases'].copy();rng.shuffle(shuffled)
        for case in shuffled:case['samples'].append(take(case))
        checkpoint();print(f'compiler trials {trial+1}/{args.trials}',flush=True)
    data['traces']=[]
    for f in data['fixtures']:
        if sha(Path(f['bundle']))!=f['pin']:raise ValueError('fixture changed')
        for n,pin in f['source_sha256'].items():
            if sha(Path(f['root'])/n)!=pin:raise ValueError('loose input changed')
    if sha(host)!=build_info['host_sha256']:raise ValueError('native host changed')
    data['status']='complete';checkpoint()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    toolchain_arguments(parser)
    parser.add_argument('--host',type=Path,help='reuse a previously built adapter')
    parser.add_argument('--headers',type=int,nargs='+',default=[32,512])
    parser.add_argument('--trials',type=int,default=15)
    parser.add_argument('--output',type=Path,default=HERE/'_work/runs/initial')
    args=parser.parse_args()
    if args.trials<1 or any(n<1 or n>4096 for n in args.headers):parser.error('positive trials; headers between 1 and 4096')
    if len(set(args.headers))!=len(args.headers):parser.error('duplicate header counts')
    args.llvm=args.llvm.resolve();args.llvm_headers=args.llvm_headers.resolve()
    run(args)
