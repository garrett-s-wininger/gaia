#!/usr/bin/env python3
"""Fresh exec versus resident single-threaded CPython templates, full child life."""
import argparse
import compileall
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import py_compile
import random
import shutil
import statistics
import subprocess
import sys
import time
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BUNDLES=HERE.parent/'dependency_bundles'
MODES=('exec','minimal','imports','framework')
MODULES={'django':'django','asgiref':'asgiref','sqlparse':'sqlparse','djangorestframework':'rest_framework','django-filter':'django_filters'}

def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def prepare(args,work):
    begin=time.perf_counter();provenance=json.loads(args.provenance.read_text());latest={}
    for a in provenance['artifacts']:latest.setdefault(a['project'],a)
    deps=work/'dependencies';deps.mkdir();names=set();selected=[]
    for project,a in latest.items():
        wheel=args.wheels/a['filename']
        if sha(wheel)!=a['sha256']:raise ValueError('wheel hash mismatch')
        with zipfile.ZipFile(wheel) as archive:
            for info in archive.infolist():
                if info.is_dir():continue
                name=Path(info.filename)
                if name.is_absolute() or '..' in name.parts or str(name).casefold() in names:raise ValueError('unsafe/colliding input')
                names.add(str(name).casefold());target=deps/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(archive.read(info))
        selected.append({k:a[k] for k in ('project','version','filename','url','sha256')})
    fixture=work/'fixture';shutil.copytree(BUNDLES/'django_fixture',fixture/'django_fixture',ignore=shutil.ignore_patterns('__pycache__'))
    compileall.compile_dir(str(deps),quiet=2,force=True);compileall.compile_dir(str(fixture),quiet=2,force=True)
    compileall.compile_dir(str(HERE),quiet=2,force=True)
    runner=work/'runner.pyc';py_compile.compile(str(HERE/'runner.py'),cfile=str(runner),doraise=True)
    resources={}
    for n in ('contrib/admin/templates/admin/login.html','contrib/admin/static/admin/js/core.js','forms/templates/django/forms/widgets/text.html'):
        resources['django:'+n]=sha(deps/'django'/n)
    common=dict(adapter_root=str(HERE),fixture_parent=str(fixture),dependencies=str(deps),
                versions={MODULES[k]:v['version'] for k,v in latest.items()},resources=resources)
    for scenario in ('core','rest'):
        protected=dict(DJANGO_SETTINGS_MODULE='django_fixture.settings',GAIA_DJANGO_SCENARIO=scenario,GAIA_DJANGO_TEMPLATES='filesystem')
        write(work/(scenario+'.json'),dict(common,scenario=scenario,template_cwd=str(work),protected_environment=protected))
    return runner,selected,time.perf_counter()-begin

def call_for(work,scenario,token):
    env=dict(os.environ);env.update(DJANGO_SETTINGS_MODULE='django_fixture.settings',GAIA_DJANGO_SCENARIO=scenario,
                                   GAIA_DJANGO_TEMPLATES='filesystem',GAIA_REQUEST_TOKEN=token)
    return dict(cwd=str(work),argv=['snapshot-request',token],environment=env,token=token)

def command(runner,mode,stage,config,module='django_workload'):
    return [sys.executable,'-I','-S','-B',str(runner),mode,stage,module,str(config)]

class Template:
    def __init__(self,runner,stage,config,module='django_workload'):
        started=time.perf_counter();self.process=subprocess.Popen(command(runner,'server',stage,config,module),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        line=self.process.stdout.readline()
        if not line:raise RuntimeError('template failed: '+self.process.stderr.read())
        self.ready=json.loads(line);self.start_seconds=time.perf_counter()-started
    def call(self,call):
        started=time.perf_counter();self.process.stdin.write(json.dumps(call)+'\n');self.process.stdin.flush();line=self.process.stdout.readline()
        ended=time.perf_counter()
        if not line:raise RuntimeError('template terminated: '+self.process.stderr.read())
        value=json.loads(line);value['wall_seconds']=ended-started;return value
    def close(self):
        started=time.perf_counter();self.process.stdin.write('{"stop":true}\n');self.process.stdin.flush()
        _,err=self.process.communicate(timeout=30)
        if self.process.returncode or err:raise RuntimeError('template shutdown: '+err)
        return time.perf_counter()-started

def validate(reply,token,work,expected=None):
    if not reply['ok'] or reply.get('wait_status',0):raise ValueError(str(reply))
    result=reply['result']
    if result['cwd']!=str(work) or result['token']!=token or result['rows']!=2:raise ValueError('bound request differs')
    semantic={k:v for k,v in result.items() if k not in ('cwd','token')}
    if expected is not None and semantic!=expected:raise ValueError('semantic result differs')
    return semantic

def run(args):
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');work=HERE/'_work'/run_id;work.mkdir(parents=True)
    args.output.mkdir(parents=True,exist_ok=True);runner,provenance,prepare_seconds=prepare(args,work)
    sources={str(p.relative_to(ROOT)):sha(p) for p in sorted(HERE.glob('*.py'))+sorted(HERE.glob('*.js'))}
    sources.update({str(p.relative_to(ROOT)):sha(p) for p in sorted((BUNDLES/'django_fixture').glob('*.py'))})
    data=dict(run_id=run_id,status='running',trials=args.trials,python=sys.version,executable_sha256=sha(sys.executable),
              uname=list(os.uname()),cpu_count=os.cpu_count(),page_cache='warm; no drop_caches',
              source_sha256=sources,provenance=provenance,input_preparation_seconds=prepare_seconds,
              scope='Fresh exec or resident-template IPC+fork+work+normal child finalization+wait; parent JSON decoding/verification excluded.',
              work=str(work),setup={},cases=[],criu=shutil.which('criu'))
    frozen=work/'sources'
    for name in sources:
        target=frozen/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    data['source_snapshots']=str(frozen)
    rng=random.Random(157);nonces=set();expected={};templates={};samples={(s,m):[] for s in ('core','rest') for m in MODES}
    try:
        for scenario in ('core','rest'):
            config=work/(scenario+'.json')
            for mode in MODES[1:]:
                t=Template(runner,mode,config);templates[scenario,mode]=t
                data['setup'][scenario+'-'+mode]=dict(start_seconds=t.start_seconds,**t.ready)
            # One complete validated warmup per case; includes no retained DB.
            for mode in MODES:
                token='warmup-'+scenario+'-'+mode;call=call_for(work,scenario,token)
                if mode=='exec':
                    p=subprocess.run(command(runner,'once','minimal',config),input=json.dumps(call)+'\n',capture_output=True,text=True,check=True)
                    reply=json.loads(p.stdout)
                else:reply=templates[scenario,mode].call(call)
                expected[scenario]=validate(reply,token,work,expected.get(scenario))
        for block in range(args.trials):
            order=list(samples);rng.shuffle(order)
            for scenario,mode in order:
                token=f'{block}-{scenario}-{mode}';call=call_for(work,scenario,token)
                if mode=='exec':
                    begin=time.perf_counter();p=subprocess.run(command(runner,'once','minimal',work/(scenario+'.json')),input=json.dumps(call)+'\n',capture_output=True,text=True,check=True);end=time.perf_counter()
                    if p.stderr:raise RuntimeError(p.stderr)
                    reply=json.loads(p.stdout);reply['wall_seconds']=end-begin
                else:reply=templates[scenario,mode].call(call)
                validate(reply,token,work,expected[scenario])
                if reply['nonce'] in nonces:raise ValueError('random nonce repeated')
                nonces.add(reply['nonce']);reply['block']=block;reply['validated']=True
                samples[scenario,mode].append(reply)
                print(block,scenario,mode,f"{reply['wall_seconds']*1000:.2f} ms",flush=True)
        data['status']='complete'
    finally:
        for (scenario,mode),template in templates.items():data['setup'][scenario+'-'+mode]['shutdown_seconds']=template.close()
        data['cases']=[dict(scenario=s,mode=m,samples=ss) for (s,m),ss in samples.items()]
        write(args.output/'results.json',data)
    summary=dict(run_id=run_id,raw_sha256=sha(args.output/'results.json'),cases=[],setup=data['setup'])
    for scenario in ('core','rest'):
        base=samples[scenario,'exec'];medbase=statistics.median(x['wall_seconds'] for x in base)
        for mode in MODES:
            ss=samples[scenario,mode];median=statistics.median(x['wall_seconds'] for x in ss)
            item=dict(scenario=scenario,mode=mode,median_ms=median*1000,min_ms=min(x['wall_seconds'] for x in ss)*1000,max_ms=max(x['wall_seconds'] for x in ss)*1000,
                      memory_median={k:statistics.median(x['memory'][k] for x in ss) for k in ss[0]['memory']},
                      paired_wins_vs_exec=sum(a['wall_seconds']<b['wall_seconds'] for a,b in zip(ss,base)),blocks=len(ss))
            if mode!='exec':
                setup=data['setup'][scenario+'-'+mode];item['amortized_ms']={str(n):(setup['start_seconds']+median*n+setup['shutdown_seconds'])/n*1000 for n in (1,2,5,10,100)}
                item['break_even_requests']=__import__('math').ceil((setup['start_seconds']+setup['shutdown_seconds'])/(medbase-median)) if medbase>median else None
            summary['cases'].append(item)
    write(args.output/'summary.json',summary)
    write(args.output/'validation.json',dict(passed=True,operations=args.trials*8,all_semantics_match=True,nonces_unique=True,raw_sha256=summary['raw_sha256'],source_sha256=sources))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provenance',type=Path,default=BUNDLES/'results/django/provenance.json')
    parser.add_argument('--wheels',type=Path,default=BUNDLES/'_work/django-corpus/wheels')
    parser.add_argument('--trials',type=int,default=15)
    parser.add_argument('--output',type=Path,default=HERE/'_work/results')
    args=parser.parse_args()
    if args.trials<1:parser.error('trials must be positive')
    run(args)
