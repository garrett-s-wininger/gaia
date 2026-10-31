"""Real fmt sources plus a labelled four-target integration DAG; shared host adapter."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import time
import threading

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import benchmark as common
import project_benchmark as project
import object_cache_benchmark as environment
import shared_inputs
from resident_host import ResidentHost
from blake3_digest import Blake3

SOURCE_SHA='8b852bb5aa6e7d8564f9e81394055395dd1d1936d38dfd3a17792a02bebd7af0'
SOURCE_URL='https://codeload.github.com/fmtlib/fmt/tar.gz/refs/tags/12.2.0'


def sha(body):return hashlib.sha256(body).hexdigest()
def run(args,**kw):return project.run_checked(list(map(str,args)),**kw)
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()


def ninja_path(value):return str(value).replace('$','$$').replace(' ','$ ').replace(':','$:')
def ninja_command(args):return shlex.join(map(str,args)).replace('$','$$')


def sdk_search(cpp,env):
    p=run([cpp,'--no-default-config','-E','-x','c++','-','-v'],input='',env=env);active=False;roots=[]
    for line in p.stderr.splitlines():
        if '#include <...> search starts here:' in line:active=True;continue
        if 'End of search list.' in line:active=False
        if active:roots.append(str(Path(line.strip()).resolve()))
    if not roots:raise ValueError('missing C++ SDK search')
    return roots


def driver_link(cpp,lld,output,target,objects,dependencies,env):
    options=['--no-default-config','--driver-mode=g++','-fuse-ld='+str(lld),'-Wl,--threads=1,--build-id=sha1','-Wl,-rpath,$ORIGIN']
    if target['shared']:options+=['-shared','-Wl,-soname,'+target['output']]
    for name in [*objects,*dependencies]:(output/name).touch(exist_ok=True)
    p=run([cpp,*options,'-o',output/target['output'],*map(lambda n:output/n,objects),*map(lambda n:output/n,dependencies),'-###'],env=env)
    candidates=[shlex.split(line) for line in p.stderr.splitlines() if line.lstrip().startswith('"')]
    link=next((c for c in reversed(candidates) if Path(c[0]).name.startswith('ld.lld')),None)
    if link is None:raise ValueError('no captured LLD invocation: '+p.stderr)
    return [arg.replace('\\$','$') for arg in link]


def resolve_libraries(args):
    roots=[Path(v[2:]) for v in args if v.startswith('-L') and len(v)>2];result=[]
    for arg in args:
        if arg.startswith('-l'):
            name=arg[2:];candidates=[root/file for root in roots for file in (('lib'+name+'.so'),('lib'+name+'.a'))]
            found=next((p for p in candidates if p.is_file()),None)
            if found is None:raise ValueError('unresolved implicit library '+arg)
            result.append(str(found))
        else:result.append(arg)
    return result


def prepare(args,work):
    if sha(args.archive.read_bytes())!=SOURCE_SHA:raise ValueError('fmt archive pin')
    source=work/'source';source.mkdir()
    with tarfile.open(args.archive) as archive:archive.extractall(source,filter='data')
    fmt=source/'fmt-12.2.0';fixture=source/'integration';shutil.copytree(HERE/'fixture',fixture)
    env=environment.cache_env()
    if args.tool_library_path:env['LD_LIBRARY_PATH']=str(args.tool_library_path)
    cpp=args.llvm/'bin/clang++';lld=args.llvm/'bin/ld.lld';roots=sdk_search(cpp,env);triple=run([cpp,'--no-default-config','-dumpmachine'],env=env).stdout.strip()
    flags=['--no-default-config','--driver-mode=g++','--target='+triple,'-std=c++17','-O2','-DNDEBUG','-fPIC','-fno-ident','-fno-addrsig','-Werror=date-time','-fdebug-compilation-dir='+str(source),'-nostdinc','-nostdinc++','-I'+str(fmt/'include'),'-I'+str(fixture)]
    for root in roots:flags+=['-isystem',root]
    targets=[dict(name='fmt',sources=[str(fmt/'src/format.cc'),str(fmt/'src/os.cc')],objects=['fmt-format.o','fmt-os.o'],shared=True,output='libfmt_graph.so',deps=[],defines=['-DFMT_LIB_EXPORT']),
             dict(name='integration',sources=[str(fixture/'report.cpp'),str(fixture/'sum.cpp')],objects=['report.o','sum.o'],shared=True,output='libintegration.so',deps=['fmt'],defines=['-DFMT_SHARED']),
             dict(name='app',sources=[str(fixture/'app.cpp')],objects=['app.o'],shared=False,output='report-cli',deps=['integration','fmt'],defines=['-DFMT_SHARED']),
             dict(name='test',sources=[str(fixture/'test.cpp')],objects=['test.o'],shared=False,output='graph-test',deps=['integration','fmt'],defines=['-DFMT_SHARED'])]
    files={str(p.resolve()):p.read_bytes() for root in (fmt/'include',fixture) for p in root.rglob('*') if p.is_file()}
    # Admit complete C++/Clang header roots, plus all positive C SDK dependencies.
    for root in map(Path,roots):
        if root==Path('/usr/include') or not root.exists():continue
        for p in root.rglob('*'):
            if p.is_file():files[str(p.resolve())]=p.read_bytes()
    by_name={t['name']:t for t in targets};aliases={};plans={};sdk_inputs=set()
    plan_output=work/'capture';plan_output.mkdir();alias_dir=work/'sdk-link-inputs';alias_dir.mkdir()
    for target in targets:
        target['commands']=[[str(cpp),*flags,*target['defines'],'-c',src,'-o',obj] for src,obj in zip(target['sources'],target['objects'])];dependencies=set()
        for command in target['commands']:
            dep=command.copy();i=dep.index('-o');del dep[i:i+2];dep.remove('-c');dep+=['-M','-MT','graph']
            found=run(dep,cwd=source,env=env).stdout.replace('\\\n',' ');paths=shlex.split(found.split(':',1)[1])
            for name in paths:
                p=Path(name).resolve();dependencies.add(str(p));files[str(p)]=p.read_bytes()
        target['positive_inputs']=sorted(dependencies)
        dependency_outputs=[by_name[n]['output'] for n in target['deps']]
        original=resolve_libraries(driver_link(cpp,lld,plan_output,target,target['objects'],dependency_outputs,env));aliased=[]
        for value in original:
            p=Path(value)
            if p.is_file() and p.suffix=='.o' and not str(p.resolve()).startswith(str(plan_output.resolve())+'/'):
                destination=alias_dir/(p.name+'.input');body=p.read_bytes()
                if destination.exists() and destination.read_bytes()!=body:raise ValueError('CRT alias basename collision')
                destination.write_bytes(body);aliases[str(p)]=str(destination);value=str(destination)
            aliased.append(value)
            if Path(value).is_file() and not str(Path(value).resolve()).startswith(str(plan_output.resolve())+'/'):sdk_inputs.add(value)
        target['original_link']=original;target['captured_link']=aliased
    tools=[args.host,cpp,lld,args.blake3_helper]
    tools += [args.llvm/'lib'/n for n in ('libclang-cpp.so','libLLVM.so.22.1','liblldELF.so','liblldCommon.so')]
    if args.blake3_library:tools.append(args.blake3_library)
    tools.extend([args.ccache,args.ninja]);sdk_inputs.update(map(str,tools));sdk_inputs.update(aliases)
    if sum(map(len,files.values()))>60*1024*1024:raise ValueError('admitted source/SDK bound')
    return dict(source=source,fmt=fmt,fixture=fixture,files=files,roots=roots,flags=flags,targets=targets,aliases=aliases,sdk_inputs=sdk_inputs,tools=tools,env=env,cpp=cpp,lld=lld,capture=plan_output)


def link_for(info,target,output,original=False):
    prefix=str(info['capture'])+'/'
    return [str(output/Path(value).name) if value.startswith(prefix) else value for value in target['original_link' if original else 'captured_link']]


class Watch:
    """Trusted local stat reuse, with content checks on every changed identity."""
    def __init__(self,paths,retain=()):
        self.records={};self.retain=set(retain);self.refresh(paths)
    def refresh(self,paths):
        changed=[];reads=0
        for name in sorted(set(map(str,paths))):
            p=Path(name);stat=p.stat();local=p.lstat();fingerprint=(stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns,local.st_ino,local.st_mtime_ns,local.st_ctime_ns)
            old=self.records.get(name)
            if old is None or old['stat']!=fingerprint:
                body=p.read_bytes();reads+=1;digest=sha(body)
                if old is None or old['digest']!=digest:changed.append(name)
                self.records[name]=dict(stat=fingerprint,digest=digest,body=body if name in self.retain else None)
        return dict(paths=len(set(paths)),reads=reads,changed=changed)
    def digests(self,paths):return {str(p):self.records[str(p)]['digest'] for p in paths}


def verify_runtime(output,scenario,env):
    bias=1 if scenario=='header' else 0;delta=1 if scenario=='source' else 0
    outputs={name:run([output/name],env=env).stdout for name in ('report-cli','graph-test')}
    expected={'report-cli':f'fmt=120200 value={42+bias+delta} sum={6+bias} bias={bias}\n','graph-test':f'ok:fmt=120200 value={7+bias+delta} sum={6+bias} bias={bias}\n'}
    if outputs!=expected:raise ValueError('runtime semantic mismatch: '+repr(outputs))
    return outputs


def cli_build(info,output,original=False,trace=False):
    output.mkdir(exist_ok=True)
    for target in info['targets']:
        def compile_one(command):
            command=command.copy();command[command.index('-o')+1]=str(output/command[command.index('-o')+1]);run(command,cwd=info['source'],env=info['env'])
        with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(compile_one,target['commands']))
        argv=link_for(info,target,output,original);run(argv,cwd=output,env=info['env'])
        if trace:
            observed=run([*argv,'--trace'],cwd=output,env=info['env'])
            for line in observed.stdout.splitlines():
                p=Path(line.split('(',1)[0])
                if p.is_file() and not str(p.resolve()).startswith(str(output.resolve())+'/'):info['sdk_inputs'].add(str(p))
    return {target['output']:sha((output/target['output']).read_bytes()) for target in info['targets']}


def alias_proof(info,output):
    checked=[]
    for target in info['targets']:
        argv=link_for(info,target,output,original=True);original=output/(target['output']+'.original');argv[argv.index('-o')+1]=str(original);run(argv,cwd=output,env=info['env'])
        same=sha(original.read_bytes())==sha((output/target['output']).read_bytes())
        if not same:raise ValueError('original CRT vs admitted alias changed artifact '+target['name'])
        checked.append(dict(target=target['name'],byte_identical=True))
    return checked


def write_ninja(info,output,path,ccache):
    lines=['builddir = '+ninja_path(output)]
    for target in info['targets']:
        for index,command in enumerate(target['commands']):
            rule=target['name']+str(index);obj=output/target['objects'][index];actual=command.copy();actual[actual.index('-o')+1]=str(obj);actual += ['-MD','-MF',str(obj)+'.d','-MT',str(obj)]
            lines += ['rule '+rule,'  command = cd '+ninja_command([info['source']])+' && '+ninja_command([ccache,*actual]),'  depfile = '+ninja_path(str(obj)+'.d'),'  deps = gcc','build '+ninja_path(obj)+': '+rule+' '+ninja_path(target['sources'][index])]
        rule=target['name']+'link';dependencies=[next(t for t in info['targets'] if t['name']==n)['output'] for n in target['deps']]
        lines += ['rule '+rule,'  command = '+ninja_command(link_for(info,target,output)), 'build '+ninja_path(output/target['output'])+': '+rule+' '+' '.join(ninja_path(output/name) for name in target['objects']+dependencies)+' | '+' '.join(ninja_path(p) for p in sorted(info['sdk_inputs']))]
    lines+=['default '+' '.join(ninja_path(output/n) for n in ('report-cli','graph-test'))];path.write_text('\n'.join(lines)+'\n')


class Engine:
    def __init__(self,name,info,args,work):
        self.name,self.info,self.args=name,info,args;self.output=work/name;self.output.mkdir();self.receipts={};self.residents={};self.targets={t['name']:t for t in info['targets']};self.env=info['env'].copy()
        self.ccache=work/'ccache';config=work/'ccache.conf';config.write_text('compiler_check = content\nmax_size = 1G\nremote_storage =\n');self.env.update(CCACHE_DIR=str(self.ccache),CCACHE_CONFIGPATH=str(config),CCACHE_TEMPDIR=str(work/'ccache-tmp'))
        self.publisher_lock=threading.Lock();self.watch=Watch([*info['files'],*info['sdk_inputs']],retain=info['files']);self.sdk_pins=self.watch.digests(info['sdk_inputs']);self.producer=shared_inputs.Session(Blake3(args.blake3_helper))
        self.context=sha(canonical(dict(tools=self.sdk_pins,flags=info['flags'],cwd=str(info['source']),contract='cpp-graph-compile-only-v1')))
        if name=='ninja-ccache':write_ninja(info,self.output,self.output/'build.ninja',args.ccache)
        else:
            for target in info['targets']:
                directory=self.output/target['name'];directory.mkdir();(directory/'store').mkdir();(directory/'commands.gcr').write_bytes(project.encode_requests(target['commands']));(directory/'link.gcr').write_bytes(project.encode_requests([link_for(info,target,self.output)]));self.residents[target['name']]=ResidentHost(args.host,self.env)
    def checked_inputs(self):
        observed=self.watch.refresh([*self.info['files'],*self.info['sdk_inputs']])
        if self.watch.digests(self.info['sdk_inputs'])!=self.sdk_pins:raise ValueError('pinned SDK/tool/link input changed')
        for original,alias in self.info['aliases'].items():
            if self.watch.records[original]['digest']!=self.watch.records[alias]['digest']:raise ValueError('CRT admitted copy diverged')
        return observed
    def output_digests(self):return {t['output']:sha((self.output/t['output']).read_bytes()) for t in self.info['targets']}
    def build(self):
        begin=time.perf_counter();pre=self.checked_inputs();generation=self.watch.digests(self.info['files']);native=[]
        if self.name=='ninja-ccache':
            result=run([self.args.ninja,'-f',self.output/'build.ninja','-j8'],cwd=self.output,env=self.env);messages=result.stdout
        else:
            variant={name:self.watch.records[name]['body'] for name in self.info['files']};namespace=sha(canonical(sorted(variant)))
            def target_build(target):
                directory=self.output/target['name'];deps=[self.targets[name]['output'] for name in target['deps']]
                dependent={name:sha((self.output/name).read_bytes()) for name in deps}
                signature=sha(canonical(dict(compile_inputs=self.watch.digests(target['positive_inputs']),namespace=namespace,commands=target['commands'],link=link_for(self.info,target,self.output),external=self.sdk_pins,dependent=dependent,compile_context=self.context)))
                artifact=self.output/target['output'];old=self.receipts.get(target['name'])
                if old and old['signature']==signature and artifact.exists() and sha(artifact.read_bytes())==old['output']:return dict(target=target['name'],skip=True,compiler_executions=0,link_calls=0)
                jobs=len(target['commands']);masks={name:(1<<jobs)-1 for name in variant}
                # Publish serially before parallel native work; Session owns sealed shared segments.
                with self.publisher_lock:produced=self.producer.publish(variant,masks,jobs,directory/'inputs.gci',directory/'inputs.views')
                external_before={str(p):sha(Path(p).read_bytes()) for p in [self.output/name for name in deps]}
                if any(dependent[name]!=external_before[str(self.output/name)] for name in deps):raise ValueError('dependent artifact changed before link')
                argv=[str(self.args.host),'memory',str(self.info['cpp']),str(self.info['source']),str(directory/'inputs.gci'),produced['pin'],str(self.output),str(directory/'commands.gcr'),'4','internal',str(self.info['lld']),str(directory/'link.gcr'),'direct','journal-history-blake3',str(directory/'store'),str(directory/'inputs.views'),self.context]
                result=self.residents[target['name']].request(argv)
                if not result['correct'] or result['errors']:raise ValueError('native target failed')
                if external_before!={str(p):sha(Path(p).read_bytes()) for p in [self.output/name for name in deps]}:raise ValueError('dependent linker artifact changed during target request')
                digest=sha(artifact.read_bytes());self.receipts[target['name']]=dict(signature=signature,output=digest)
                return dict(target=target['name'],skip=False,producer=produced,**result)
            # Topological stages; targets have private processes/contexts. At most
            # four native workers per node and eight across the independent leaves.
            for name in ('fmt','integration'):native.append(target_build(self.targets[name]))
            # Each leaf owns its compiler/linker process. Publisher mutation is
            # serialized, then the independent requests overlap within 8 workers.
            with ThreadPoolExecutor(max_workers=2) as pool:native.extend(pool.map(target_build,[self.targets[n] for n in ('app','test')]))
            messages=''
        post=self.checked_inputs()
        if self.watch.digests(self.info['files'])!=generation:raise ValueError('source/SDK generation changed during graph operation')
        artifacts=self.output_digests();finished=time.perf_counter()
        return dict(seconds=finished-begin,precheck=pre,postcheck=post,targets=native,messages=messages,artifacts=artifacts)
    def close(self):
        for resident in self.residents.values():resident.close()
