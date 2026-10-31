#!/usr/bin/env python3
"""Static framework class knowledge, without application training or native AOT."""
import argparse
from datetime import datetime,timezone
import hashlib,json,os,platform,random,re,shutil,statistics,subprocess,time,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
PINS={'groovy-6.0.0.jar':'6bcbec490ac1ade0dca6566dca9d02897cbb8fc31ee4008e950451aa83b1ac76',
      'picocli-4.7.7.jar':'f86e30fffd10d2b13b8caa8d4b237a7ee61f2ffccf5b1941de718b765d235bf8'}
MODES=('picocli','static','dynamic')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,indent=2)+'\n')
def checked(cmd,**kwargs):
    begin=time.perf_counter();p=subprocess.run([str(v) for v in cmd],capture_output=True,text=True,**kwargs);elapsed=time.perf_counter()-begin
    if p.returncode:raise RuntimeError(str(cmd)+'\n'+p.stdout+'\n'+p.stderr)
    return p,elapsed

def prepare(args,work):
    java=args.jdk/'bin/java';javac=args.jdk/'bin/javac';jar=args.jdk/'bin/jar'
    jars=[args.downloads/name for name in PINS]
    for p in jars:
        if sha(p)!=PINS[p.name]:raise ValueError('artifact hash mismatch: '+str(p))
    classpath=os.pathsep.join(str(p.resolve()) for p in jars)
    classes=work/'classes';classes.mkdir()
    _,groovyc_seconds=checked([java,'-cp',classpath,'org.codehaus.groovy.tools.FileSystemCompiler','-d',classes,HERE/'StaticLogic.groovy'])
    _,javac_seconds=checked([javac,'-cp',classpath+os.pathsep+str(classes),'-d',classes,HERE/'Command.java'])
    app=work/'app.jar';checked([jar,'--create','--file',app,'-C',classes,'.'])
    # Class knowledge comes directly from package artifacts, never a running app.
    names=set()
    for p in jars:
        with zipfile.ZipFile(p) as z:
            names.update(n[:-6] for n in z.namelist() if n.endswith('.class') and not n.startswith('META-INF/') and n!='module-info.class')
    classlist=work/'frameworks.classlist'
    classlist.write_text((args.jdk/'lib/classlist').read_text()+'\n'+'\n'.join(sorted(names))+'\n')
    archive=work/'frameworks.jsa'
    cmd=[java,'-Xshare:dump','-Xmixed','-XX:SharedClassListFile='+str(classlist),'-XX:SharedArchiveFile='+str(archive),'-cp',classpath]
    p,dump_seconds=checked(cmd)
    linked_setup=None;core_setup=None
    if args.linking:
        linked_cmd=[str(v) for v in cmd];linked_cmd.insert(1,'-XX:+AOTClassLinking');linked_cmd=[v.replace(str(archive),str(work/'linked.jsa')) for v in linked_cmd]
        lp,linked_seconds=checked(linked_cmd);(work/'linked-build.log').write_text(lp.stdout+lp.stderr)
        linked_setup=dict(seconds=linked_seconds,bytes=(work/'linked.jsa').stat().st_size,sha256=sha(work/'linked.jsa'),warning_lines=sum('warning' in line for line in (lp.stdout+lp.stderr).splitlines()),log_sha256=hashlib.sha256((lp.stdout+lp.stderr).encode()).hexdigest())
    if args.core:
        core_names={name for name in names if name.startswith('picocli/')}
        core_names.update(('groovy/lang/Binding','groovy/lang/Closure','groovy/lang/GroovyObject','groovy/lang/GroovySystem','groovy/lang/MetaClass','groovy/lang/MetaClassRegistry','groovy/lang/GroovyShell','groovy/lang/GroovyClassLoader','groovy/lang/Script','org/codehaus/groovy/runtime/InvokerHelper','org/codehaus/groovy/runtime/DefaultGroovyMethods','org/codehaus/groovy/reflection/ClassInfo','org/codehaus/groovy/runtime/metaclass/MetaClassRegistryImpl','org/codehaus/groovy/vmplugin/VMPluginFactory'))
        core_list=work/'core.classlist';core_list.write_text((args.jdk/'lib/classlist').read_text().rstrip()+'\n'+'\n'.join(sorted(core_names))+'\n')
        core_cmd=[str(v) for v in cmd];core_cmd.insert(1,'-XX:+AOTClassLinking');core_cmd=[v.replace(str(archive),str(work/'core-linked.jsa')).replace(str(classlist),str(core_list)) for v in core_cmd]
        cp,core_seconds=checked(core_cmd);(work/'core-build.log').write_text(cp.stdout+cp.stderr)
        core_setup=dict(seconds=core_seconds,bytes=(work/'core-linked.jsa').stat().st_size,sha256=sha(work/'core-linked.jsa'),declared_classes=sorted(core_names),warning_lines=sum('warning' in line for line in (cp.stdout+cp.stderr).splitlines()),log_sha256=hashlib.sha256((cp.stdout+cp.stderr).encode()).hexdigest())
    (work/'archive-build.log').write_text(p.stdout+p.stderr)
    return dict(java=java,classpath=classpath+os.pathsep+str(app),archive=archive,app=app,
        setup=dict(core=core_setup,linked=linked_setup,groovyc_seconds=groovyc_seconds,javac_seconds=javac_seconds,archive_seconds=dump_seconds,
                   archive_bytes=archive.stat().st_size,archive_sha256=sha(archive),explicit_framework_classes=len(names),
                   classlist_sha256=sha(classlist),archive_command=[str(v) for v in cmd],archive_log=p.stdout+p.stderr))

def run(args):
    args.output.mkdir(parents=True,exist_ok=True)
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');work=HERE/'_work'/run_id;work.mkdir(parents=True)
    prepared=prepare(args,work)
    data=dict(run_id=run_id,status='running',scope='Fresh JVMs with normal exit and warm filesystem pages. Explicit static framework list; no application training.',
        java=checked([prepared['java'],'-version'])[0].stderr,environment=dict(platform=platform.platform(),cpu_count=os.cpu_count()),
        jars={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in (args.downloads/name for name in PINS)},
        source_sha256={p.name:sha(p) for p in HERE.iterdir() if p.suffix in ('.java','.groovy','.py')},
        setup=prepared['setup'],trials=args.trials,cases=[],diagnostics=[],work=str(work))
    frozen=work/'sources';frozen.mkdir()
    for name in data['source_sha256']:shutil.copyfile(HERE/name,frozen/name)
    variants={'off':['-Xshare:off'],'default':[],'explicit':['-Xshare:on','-XX:SharedArchiveFile='+str(prepared['archive'])]}
    if args.linking:
        variants.pop('off');variants['linked']=['-Xshare:on','-XX:SharedArchiveFile='+str(work/'linked.jsa')]
    if args.core:
        variants.pop('off',None);variants['core-linked']=['-Xshare:on','-XX:SharedArchiveFile='+str(work/'core-linked.jsa')]
    samples={(m,v):[] for m in MODES for v in variants};rng=random.Random(7729)
    def command(mode,variant,token,extra=()):return [prepared['java'],*variants[variant],*extra,'-cp',prepared['classpath'],'Command','--mode',mode,'--count','5','--token',token]
    def validate(p,mode,token):
        value=json.loads(p.stdout)
        if value!=dict(mode=mode,count=5,sum=15,token=token,groovy='unused' if mode=='picocli' else '6.0.0'):raise ValueError(str(value))
    for block in range(-1,args.trials):
        order=list(samples);rng.shuffle(order)
        for mode,variant in order:
            token=f'b{block+1}-{mode}-{variant}';env=dict(os.environ,GAIA_REQUEST_TOKEN=token)
            p,seconds=checked(command(mode,variant,token),env=env);validate(p,mode,token)
            if block>=0:samples[mode,variant].append(dict(block=block,seconds=seconds,validated=True))
            print(block,mode,variant,f'{seconds*1000:.2f} ms',flush=True)
    # Intrusive diagnostics outside benchmark latency observations.
    for mode in MODES:
        for variant in variants:
            token='diagnostic-'+mode+'-'+variant;log=work/(token+'.log')
            p,_=checked(command(mode,variant,token,['-Xlog:class+load=info,class+init=info:file='+str(log)]),env=dict(os.environ,GAIA_REQUEST_TOKEN=token));validate(p,mode,token)
            text=log.read_text();classes=[]
            for line in text.splitlines():
                hit=re.search(r'\[class,load\] ([^ ]+) source: (.+)$',line)
                if hit:classes.append((hit[1],hit[2]))
            frameworks=[x for x in classes if x[0].startswith(('groovy.','org.codehaus.groovy.','picocli.','org.apache.groovy.'))]
            data['diagnostics'].append(dict(mode=mode,variant=variant,loaded_classes=len(classes),shared_classes=sum('shared objects file' in s for _,s in classes),
                 framework_loaded=len(frameworks),framework_shared=sum('shared objects file' in s for _,s in frameworks),
                 framework_initializations=sum('[class,init]' in line and 'Initializing' in line and any(n in line for n in ('groovy/','groovy.','picocli/','picocli.')) for line in text.splitlines()),log_sha256=sha(log)))
    data['cases']=[dict(mode=m,variant=v,samples=ss) for (m,v),ss in samples.items()];data['status']='complete'
    write(args.output/'results.json',data)
    summary=dict(run_id=run_id,raw_sha256=sha(args.output/'results.json'),trials=args.trials,cases=[],setup=data['setup'],diagnostics=data['diagnostics'])
    for (mode,variant),ss in samples.items():
        times=[s['seconds']*1000 for s in ss];base=samples[mode,'default']
        summary['cases'].append(dict(mode=mode,variant=variant,median_ms=statistics.median(times),min_ms=min(times),max_ms=max(times),
            paired_wins_vs_default=sum(a['seconds']<b['seconds'] for a,b in zip(ss,base)),blocks=len(ss)))
    write(args.output/'summary.json',summary);write(args.output/'validation.json',dict(passed=True,timed_operations=args.trials*len(samples),all_outputs_and_current_tokens_match=True,raw_sha256=summary['raw_sha256'],source_sha256=data['source_sha256']))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--jdk',type=Path,default=HERE/'_work/toolchain/jdk-25.0.5.0.3');p.add_argument('--downloads',type=Path,default=HERE/'_work/downloads');p.add_argument('--core',action='store_true',help='Add declared Picocli plus Groovy public-core AOTClassLinking variant');p.add_argument('--linking',action='store_true',help='Compare default, explicit classic CDS and explicit AOTClassLinking');p.add_argument('--trials',type=int,default=7);p.add_argument('--output',type=Path,default=HERE/'_work/results');a=p.parse_args()
    if a.trials<1:p.error('trials must be positive')
    run(a)
