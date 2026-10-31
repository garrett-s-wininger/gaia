#!/usr/bin/env python3
"""Real upstream TypeScript CLI project check+emit versus a module-init snapshot."""
import argparse
import base64
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import statistics
import subprocess
import tarfile
import time

import node_dependency_benchmark as previous

HERE=Path(__file__).resolve().parent
MODES=('tsc-cached','tsc-no-cache','api-require','api-bundle','snapshot')
CONFIG=dict(compilerOptions=dict(target='ES2020',module='CommonJS',lib=['ES2020','DOM'],strict=True,
    skipLibCheck=False,noEmitOnError=True,declaration=True,declarationMap=True,sourceMap=True,inlineSources=True,
    rootDir='src',outDir='dist'),include=['src/**/*.ts'],exclude=['src/**/*.spec.ts'])

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')

def extract_project(corpus,destination):
    provenance=json.loads((corpus/'provenance.json').read_text());archive=corpus/'exponential-backoff-3.1.3.tgz';body=archive.read_bytes()
    alg,pin=provenance['dist']['integrity'].split('-',1)
    if alg!='sha512' or base64.b64encode(hashlib.sha512(body).digest()).decode()!=pin or sha(archive)!=provenance['sha256']:
        raise ValueError('project archive integrity mismatch')
    destination.mkdir()
    with tarfile.open(archive) as tf:
        for member in tf.getmembers():
            name=Path(member.name)
            if name.is_absolute() or '..' in name.parts or member.issym() or member.islnk():raise ValueError('unsafe project archive')
            if member.isfile():
                path=destination/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(tf.extractfile(member).read())
    package=json.loads((destination/'package/package.json').read_text())
    if package['name']!='exponential-backoff' or package['version']!='3.1.3':raise ValueError('wrong project package')
    return provenance,destination/'package/src'

def prepare(args):
    args.output=args.output.resolve();args.compiler_corpus=args.compiler_corpus.resolve();args.project_corpus=args.project_corpus.resolve()
    args.output.mkdir(parents=True,exist_ok=True);work=args.output/'work';work.mkdir()
    compiler_provenance,compiler=previous.extract(args.compiler_corpus,work/'compiler')
    project_provenance,source=extract_project(args.project_corpus,work/'project-corpus')
    prefix=(HERE/'typescript_performance_bridge.js').read_text();suffix=(HERE/'typescript_cli_workload.js').read_text()
    compiler_source=compiler.read_text();bundle=prefix+'''\nconst ts = (() => { const module={exports:{}};
(function(module,exports,require,__filename,__dirname) {\n'''+compiler_source+'''\n})(module,module.exports,compilerRequire,'''+json.dumps(str(compiler))+','+json.dumps(str(compiler.parent))+'''); return module.exports; })();\n'''+suffix
    bundle_path=work/'bundle.cjs';bundle_path.write_text(bundle)
    api_path=work/'api.cjs';api_path.write_text(prefix+'\nconst ts=require('+json.dumps(str(compiler))+');\n'+suffix)
    blob=work/'compiler.blob';build_config=work/'snapshot-config.json';write(build_config,dict(builder=str(bundle_path),withoutCodeCache=False))
    env=environment();env['GAIA_INITIALIZATION_MARKER']='SNAPSHOT-BUILD';started=time.perf_counter()
    p=subprocess.run([args.node,'--snapshot-blob',str(blob),'--build-snapshot-config',str(build_config)],env=env,cwd=work,capture_output=True,text=True,check=True)
    if p.stderr:raise RuntimeError('snapshot builder warning/error: '+p.stderr)
    build=dict(seconds=time.perf_counter()-started,bytes=blob.stat().st_size,sha256=sha(blob),stderr=p.stderr)
    projects=[]
    for name in ('project-a','project-b'):
        project=work/name;shutil.copytree(source,project/'src');write(project/'tsconfig.json',CONFIG);projects.append(project)
    context=dict(compiler_provenance=compiler_provenance,compiler_source_sha256=sha(compiler),
      standard_libraries={p.name:sha(p) for p in sorted(compiler.parent.glob('lib*.d.ts'))},
      project_provenance=project_provenance,project_source_sha256={p.relative_to(source).as_posix():sha(p) for p in sorted(source.rglob('*.ts'))},
      config=CONFIG,bundle_sha256=sha(bundle_path),api_sha256=sha(api_path),snapshot=build)
    return work,compiler,bundle_path,api_path,blob,projects,context

def environment():
    env=dict(os.environ)
    for key in ['NODE_OPTIONS','NODE_COMPILE_CACHE','NODE_DISABLE_COMPILE_CACHE','NODE_V8_COVERAGE']:
        env.pop(key,None)
    env.update(NODE_ENV='production',GAIA_EXPECTED_TYPESCRIPT='5.9.3')
    return env

def input_project(project,sequence,error=False):
    (project/'src/consumer.ts').write_text('''import {backOff} from './backoff';
export const sequence: number = '''+str(sequence)+''';
export async function run(): Promise<number> {
  return backOff(() => Promise.resolve(sequence), {startingDelay:0, jitter:'none'});
}
'''+('const broken: number = "semantic failure";\n' if error else ''))

def outputs(project):
    dist=project/'dist'
    return {p.relative_to(dist).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(dist.rglob('*')) if p.is_file()} if dist.exists() else {}

def clean_outputs(project):
    if (project/'dist').exists():shutil.rmtree(project/'dist')

def invocation(args,mode,compiler,bundle,api,blob,project,token,extra=None,environment_changes=None):
    metadata=project/(token+'.metadata.json');env=environment();env.update(GAIA_METADATA_PATH=str(metadata),GAIA_REQUEST_TOKEN=token,GAIA_INITIALIZATION_MARKER='LIVE-'+token)
    if environment_changes:env.update(environment_changes)
    cmd=[args.node,'--require',str(HERE/'typescript_cli_probe.cjs')]
    if mode=='tsc-cached':
        cmd+=[str(compiler.parent/'tsc.js')];env['NODE_COMPILE_CACHE']=str(args.output/'work/compile-cache')
    elif mode=='tsc-no-cache':
        cmd+=[str(compiler.parent/'_tsc.js')];env['NODE_DISABLE_COMPILE_CACHE']='1'
    elif mode=='api-require':cmd+=[str(api)];env['NODE_DISABLE_COMPILE_CACHE']='1'
    elif mode=='api-bundle':cmd+=[str(bundle)];env['NODE_DISABLE_COMPILE_CACHE']='1'
    else:cmd+=['--snapshot-blob',str(blob),'--'];env['NODE_DISABLE_COMPILE_CACHE']='1'
    cmd+=['--project','tsconfig.json','--pretty','false']+(extra or [])
    start=time.perf_counter();p=subprocess.run(cmd,cwd=project,env=env,capture_output=True,text=True,timeout=30);elapsed=time.perf_counter()-start
    if not metadata.exists():
        if environment_changes and p.returncode!=0:
            return dict(seconds=elapsed,status=p.returncode,stdout=p.stdout,stderr=p.stderr,metadata=None,early_rejection=True)
        raise RuntimeError('exit metadata absent: '+p.stderr)
    record=json.loads(metadata.read_text())
    if record['token']!=token or record['cwd']!=str(project) or record['status']!=p.returncode:raise ValueError('exit identity/status differs')
    return dict(seconds=elapsed,status=p.returncode,stdout=p.stdout,stderr=p.stderr,metadata=record)

def validate(sample,expected_status,project,expected=None):
    if sample['status']!=expected_status or sample['stderr']:raise ValueError(str(sample))
    files=outputs(project)
    if expected is not None and (sample['stdout'],files)!=expected:raise ValueError('CLI diagnostics or emitted files differ')
    meta=sample['metadata'];compiler=meta.get('compiler')
    if compiler:
        if compiler['state']['version']!='5.9.3' or compiler['state']['exports']!=2244:raise ValueError('wrong initialized compiler')
        if sample['status']==0 and (compiler['program']['libraryFiles']<40 or compiler['program']['projectFiles']<10):raise ValueError('standard libraries/project were not loaded')
        if 'snapshot' in sample.get('mode','') and compiler['state']['marker']!='SNAPSHOT-BUILD':raise ValueError('compiler initialized again')
    if sample['status']==0:
        # Independent emitted-program runtime check, outside the compiler clock.
        cmd=[os.environ.get('GAIA_NODE','/usr/bin/node'),'-e',"require('./dist/consumer.js').run().then(x=>console.log(x))"]
        p=subprocess.run(cmd,cwd=project,capture_output=True,text=True,check=True)
        sequence=json.loads((project/'expected.json').read_text())['sequence']
        if p.stdout.strip()!=str(sequence) or p.stderr:raise ValueError('emitted program behaves differently')
    sample['emitted']=files;sample['validated']=True
    return sample['stdout'],files

def diagnostic_counts(stdout,process_seconds):
    counts={}
    for line in stdout.splitlines():
        key,value=line.rsplit(':',1);key=key.strip();value=value.strip()
        if key=='Memory used':
            if not value.endswith('K') or not value[:-1].isdigit():raise ValueError('bad memory statistic')
        elif key.endswith('time'):
            if not value.endswith('s') or not 0<=float(value[:-1])<=process_seconds+0.1:raise ValueError('stale/out-of-range compiler timing')
        else:
            if not value.isdigit():raise ValueError('bad compiler count')
            counts[key]=int(value)
    return counts

def run(args):
    if args.resume_boundaries:
        args.output=args.output.resolve();data=json.loads((args.output/'results.json').read_text())
        if data['status']!='main-complete':raise ValueError('resume requires a completed main checkpoint')
        work=Path(data['source_snapshots']).parent;compiler=work/'compiler/package/lib/typescript.js'
        for name,pin in data['source_sha256'].items():
            if name!='node_project_benchmark.py' and sha(HERE/name)!=pin:raise ValueError('timed engine changed')
        data['boundary_harness_sha256']=sha(Path(__file__));data['correctness']=[];args.trials=data['trials']
        samples={c['mode']:c['samples'] for c in data['cases']}
        finish(args,data,work,compiler,work/'bundle.cjs',work/'api.cjs',work/'compiler.blob',
               [work/'project-a',work/'project-b'],samples,data['compilecache_first_operation'])
        return
    began=time.perf_counter();work,compiler,bundle,api,blob,projects,context=prepare(args)
    data=dict(run_id=datetime.now(timezone.utc).isoformat(),node=subprocess.check_output([args.node,'--version'],text=True).strip(),
      node_sha256=sha(args.node),context=context,prepare_seconds=time.perf_counter()-began,trials=args.trials,
      scope='Full fresh-process upstream CLI config+module/standardlib load+typecheck+JS/d.ts/maps filesystem emit+normal exit; warm pages. Output cleanup/input edits/parent validation are outside clock.',
      source_sha256={p.name:sha(p) for p in [Path(__file__),HERE/'typescript_performance_bridge.js',HERE/'typescript_cli_workload.js',HERE/'typescript_cli_probe.cjs']},
      cases=[],correctness=[],warmups=[])
    frozen=work/'sources';frozen.mkdir()
    for name in data['source_sha256']:shutil.copyfile(HERE/name,frozen/name)
    data['source_snapshots']=str(frozen);samples={m:[] for m in MODES};rng=random.Random(511)
    # First normal-shim use includes its actual Node compilecache publication.
    project=projects[0];input_project(project,-1);write(project/'expected.json',dict(sequence=-1));clean_outputs(project)
    cold=invocation(args,'tsc-cached',compiler,bundle,api,blob,project,'first-compilecache');cold['mode']='tsc-cached';validate(cold,0,project)
    data['compilecache_first_operation']=cold
    expected=None
    for mode in MODES:
        clean_outputs(project);sample=invocation(args,mode,compiler,bundle,api,blob,project,'warmup-'+mode);sample['mode']=mode
        expected=validate(sample,0,project,expected);data['warmups'].append(sample)
    for block in range(args.trials):
        project=projects[block%2];input_project(project,block);write(project/'expected.json',dict(sequence=block));expected=None;order=list(MODES);rng.shuffle(order)
        for mode in order:
            clean_outputs(project);sample=invocation(args,mode,compiler,bundle,api,blob,project,f'{block}-{mode}');sample.update(mode=mode,block=block)
            expected=validate(sample,0,project,expected);samples[mode].append(sample)
            print(block,mode,f"{sample['seconds']*1000:.2f} ms",flush=True)
        data['cases']=[dict(mode=m,samples=ss) for m,ss in samples.items()]
        data['status']='running'
        write(args.output/'results.json',data)
    data['cases']=[dict(mode=m,samples=ss) for m,ss in samples.items()]
    data['status']='main-complete'
    write(args.output/'results.json',data)
    finish(args,data,work,compiler,bundle,api,blob,projects,samples,cold)

def finish(args,data,work,compiler,bundle,api,blob,projects,samples,cold):
    if not args.skip_boundaries:
        project=projects[0]
        for kind in ('semantic-error','invalid-config','changed-config','extended-diagnostics'):
            input_project(project,99,error=kind=='semantic-error');write(project/'expected.json',dict(sequence=99))
            config=json.loads(json.dumps(CONFIG))
            if kind=='invalid-config':config['compilerOptions']['module']='NOT-A-MODULE'
            if kind=='changed-config':config['compilerOptions']['target']='ES5'
            write(project/'tsconfig.json',config);expected=None
            for mode in MODES:
                clean_outputs(project);sample=invocation(args,mode,compiler,bundle,api,blob,project,kind+'-'+mode,
                    extra=['--extendedDiagnostics'] if kind=='extended-diagnostics' else None);sample.update(mode=mode,boundary=kind)
                if kind=='extended-diagnostics':
                    validate(sample,0,project)
                    # Counts remain exact; time/memory diagnostics are per-process observations.
                    static=diagnostic_counts(sample['stdout'],sample['seconds'])
                    observed=(static,sample['emitted'])
                    if expected is not None and observed!=expected:raise ValueError('extended diagnostic counts differ')
                    expected=observed
                else:expected=validate(sample,1 if kind=='semantic-error' else 2 if kind=='invalid-config' else 0,project,expected)
                data['correctness'].append(sample)
                write(args.output/'results.json',data)
        write(project/'tsconfig.json',CONFIG)
        for mode in ('api-require','api-bundle','snapshot'):
            for kind,env in [('version-context',{'GAIA_EXPECTED_TYPESCRIPT':'0.0.0'}),('environment-context',{'NODE_ENV':'development'})]:
                clean_outputs(project);sample=invocation(args,mode,compiler,bundle,api,blob,project,kind+'-'+mode,environment_changes=env)
                expected_error='compiler version context mismatch' if kind=='version-context' else 'unsupported mutable compiler environment'
                if sample['status']==0 or outputs(project) or expected_error not in sample['stderr']:raise ValueError('unsupported context admitted or wrong rejection')
                data['correctness'].append(dict(mode=mode,boundary=kind,rejected=True,stderr=sample['stderr'],early_rejection=sample.get('early_rejection',False)))
            sample=invocation(args,mode,compiler,bundle,api,blob,project,'persistent-mode-'+mode,extra=['--watch'])
            if sample['status']==0 or 'unsupported persistent/resource CLI mode' not in sample['stderr']:raise ValueError('watch mode admitted')
            data['correctness'].append(dict(mode=mode,boundary='watch-mode',rejected=True))
    rebuild=work/'compiler-rebuilt.blob';started=time.perf_counter()
    p=subprocess.run([args.node,'--snapshot-blob',str(rebuild),'--build-snapshot-config',str(work/'snapshot-config.json')],
        env=dict(environment(),GAIA_INITIALIZATION_MARKER='SNAPSHOT-REBUILD'),cwd=work,capture_output=True,text=True,check=True)
    if p.stderr:raise RuntimeError('snapshot rebuild warning/error: '+p.stderr)
    data['rebuild']=dict(seconds=time.perf_counter()-started,bytes=rebuild.stat().st_size,sha256=sha(rebuild),stderr=p.stderr)
    data['cases']=[dict(mode=m,samples=ss) for m,ss in samples.items()]
    data['status']='complete'
    cache=work/'compile-cache';data['compilecache_payload_bytes']=sum(p.stat().st_size for p in cache.rglob('*') if p.is_file())
    write(args.output/'results.json',data)
    summary={k:v for k,v in data.items() if k not in ('cases','warmups','correctness','source_snapshots','compilecache_first_operation')}
    summary['compilecache_first_operation_ms']=cold['seconds']*1000;summary['raw_sha256']=sha(args.output/'results.json');summary['cases']=[]
    for mode,ss in samples.items():
        summary['cases'].append(dict(mode=mode,median_ms=statistics.median(s['seconds'] for s in ss)*1000,
          min_ms=min(s['seconds'] for s in ss)*1000,max_ms=max(s['seconds'] for s in ss)*1000,
          memory_median_bytes={key:statistics.median(s['metadata']['memory'][key] for s in ss) for key in ss[0]['metadata']['memory']},
          paired_wins_vs_stock_cached=sum(a['seconds']<b['seconds'] for a,b in zip(ss,samples['tsc-cached'])),
          paired_wins_vs_bundle=sum(a['seconds']<b['seconds'] for a,b in zip(ss,samples['api-bundle'])),blocks=len(ss)))
    write(args.output/'summary.json',summary);write(args.output/'validation.json',dict(passed=True,operations=args.trials*len(MODES),
      warmups=len(data['warmups']),boundary_operations=len(data['correctness']),all_stdout_and_emission_and_runtime_checks_match=True,
      performance_binding_warning_free=True,raw_sha256=summary['raw_sha256']))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--node',default='/usr/bin/node');p.add_argument('--trials',type=int,default=7)
    p.add_argument('--compiler-corpus',type=Path,default=HERE/'_work/typescript-corpus');p.add_argument('--project-corpus',type=Path,default=HERE/'_work/backoff-corpus')
    p.add_argument('--output',type=Path,default=HERE/'_work/typescript-project');p.add_argument('--skip-boundaries',action='store_true');p.add_argument('--resume-boundaries',action='store_true')
    a=p.parse_args()
    if a.trials<1:p.error('trials must be positive')
    run(a)
