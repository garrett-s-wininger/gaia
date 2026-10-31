"""Matched generic JSON/binary resolved manifests with the same packed consumer."""
import argparse
from datetime import datetime,timezone
import gc
import json
import os
from pathlib import Path
import random
import shutil
import statistics
import subprocess
import sys
import time
import tracemalloc

import compact_python as compact
import generic_lock as lock
import locked_python as python
import pipeline_transport as transport
import transfer as t

HERE=Path(__file__).resolve().parent
ENCODERS={'json':lock.encode_json,'binary':lock.encode_binary}


def resolved(directory,expected):
    logical,payloads=python.make_lock(directory,expected);logical=json.loads(logical);context=t.encode(expected);payloads.append(context)
    unique={t.digest(body):body for body in payloads};artifacts=[dict(algorithm='sha256',digest=key,size=len(unique[key])) for key in sorted(unique)];ids={r['digest']:i for i,r in enumerate(artifacts)}
    module_names=sorted(expected['versions']);project_names={'rest_framework':'djangorestframework','django_filters':'django-filter'}
    packages=[dict(ecosystem='pypi',name=project_names.get(name,name),version=expected['versions'][name]) for name in module_names];packages_by_module={name:i for i,name in enumerate(module_names)}
    associations=[dict(package=packages_by_module.get(r['name'].split('/')[0],lock.NONE),artifact=ids[r['sha256']],role='python-file',label=r['name']) for r in logical['files']]
    doc=dict(version=1,packages=packages,artifacts=artifacts,associations=associations,metadata=[dict(ecosystem='python',role='context',artifact=ids[t.digest(context)])])
    return doc,list(unique.values())


def diagnostic(doc,trials):
    bodies={kind:encoder(doc) for kind,encoder in ENCODERS.items()};pins={kind:t.digest(body) for kind,body in bodies.items()};samples={kind:[] for kind in bodies};rng=random.Random(552)
    for block in range(trials):
        order=list(bodies);rng.shuffle(order)
        for kind in order:
            gc.collect();begin=time.perf_counter();cpu=time.process_time();view=lock.parse(bodies[kind],pins[kind],kind);cpu_end=time.process_time();end=time.perf_counter()
            samples[kind].append(dict(block=block,wall_ms=(end-begin)*1000,cpu_ms=(cpu_end-cpu)*1000));del view
    allocations={}
    for kind,body in bodies.items():
        gc.collect();tracemalloc.start();view=lock.parse(body,pins[kind],kind);current,peak=tracemalloc.get_traced_memory();tracemalloc.stop();allocations[kind]=dict(retained_traced_bytes=current,peak_traced_bytes=peak);del view
    return dict(scope='Standalone full pin/structure validation; provided input bytes excluded from allocations. Allocation tracing is separate from latency samples.',trials=trials,samples=samples,allocations=allocations,bytes={kind:len(body) for kind,body in bodies.items()})


def run(args):
    args.output.mkdir(parents=True,exist_ok=True)
    if (args.output/'results.json').exists():raise ValueError('fresh output required')
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');work=HERE/'_work'/('generic-lock-'+run_id);work.mkdir()
    fixture=args.fixture.resolve();expected=json.loads((fixture/'rest-expected.json').read_text());expected_path=work/'expected.json';expected_path.write_bytes(t.encode(expected))
    prepared=time.perf_counter();doc,payloads=resolved(fixture/'rest-bytecode',expected);collection=t.build_collection(payloads);prepared=time.perf_counter()-prepared
    data=dict(run_id=run_id,status='running',trials=args.trials,producer_fixture_seconds=prepared,
        corpus=dict(packages=len(doc['packages']),artifacts=len(doc['artifacts']),associations=len(doc['associations']),metadata=len(doc['metadata']),versions=expected['versions'],resources=expected['resources'],payload_bytes=sum(len(p) for p in payloads)),samples=[],
        sources={str(p.relative_to(HERE.parents[1])):t.digest(p.read_bytes()) for base in (HERE,HERE.parent/'python/dependency_bundles') for p in base.glob('*.py')})
    sources=work/'sources';sources.mkdir();data['source_snapshots']=str(sources)
    for name in data['sources']:
        target=sources/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(HERE.parents[1]/name,target)
    signature=None;logical_signature=None;encoded={}
    def consume(kind,profile,block,url):
        nonlocal signature,logical_signature
        root=work/(kind+'-'+str(block));root.mkdir(exist_ok=True);cache=root/'cache'
        begin=time.perf_counter();produce_begin=time.perf_counter()
        if profile=='cold':
            body=ENCODERS[kind](doc);pin=t.digest(body);encoded[(kind,block)]=(body,pin)
        else:body,pin=encoded[(kind,block)]
        produce_end=time.perf_counter();view,acquired=lock.acquire(url,body,pin,cache,kind);acquired_end=time.perf_counter();receipt=root/'consumer.json';index=root/'consumer.gpi';adapter_seconds=0
        if not receipt.exists():
            adapter_begin=time.perf_counter();logical=lock.python_adapter(view,cache);adapter_seconds=time.perf_counter()-adapter_begin;logical_pin=t.digest(logical)
            if logical_signature is None:logical_signature=logical_pin
            elif logical_pin!=logical_signature:raise ValueError('formats changed logical Python lock')
            descriptor=compact.build(cache,logical,logical_pin,index,'pack');descriptor['logical_pin']=logical_pin;t.atomic_write(receipt,t.encode(descriptor))
        else:descriptor=json.loads(receipt.read_text())
        installed=time.perf_counter();env=os.environ.copy();env.update(GAIA_READER_KIND='compact-pack',GAIA_COMPACT_INDEX=str(index),GAIA_COMPACT_PIN=descriptor['pin'],GAIA_PY_LOCK_PIN=descriptor['logical_pin'])
        env.pop('GAIA_PY_LOCK',None)
        command=[sys.executable,'-I','-S','-B',str(HERE/'compact_python_worker.py'),'--root',str(cache),'--reader','python','--scenario','rest','--expected',str(expected_path),'--discovery','index']
        child_begin=time.perf_counter();child=subprocess.run(command,env=env,capture_output=True,text=True,check=True);child_end=time.perf_counter();result=json.loads(child.stdout)
        actual=(result['module_origins'],result['executed_files'],result['api_result'],result['resource_hashes'],result['app_count'])
        if signature is None:signature=actual
        elif actual!=signature:raise ValueError('generic format changes consumer result')
        if not result['correct'] or result['network_events'] or result['native_timings']['integrity_policy']!='sha256+crc32-every-read':raise ValueError('consumer/integrity mismatch')
        if profile=='reuse' and acquired['requests']:raise ValueError('reuse used network')
        if acquired['manifest_requests'] or acquired['requests']!=int(profile=='cold'):raise ValueError('unexpected discovery/request count')
        sample=dict(kind=kind,profile=profile,block=block,format_production_seconds=produce_end-produce_begin,acquisition=acquired,acquisition_seconds=acquired_end-produce_end,adapter_seconds=adapter_seconds,install_seconds=installed-begin,process_seconds=child_end-child_begin,total_seconds=child_end-begin,lock_bytes=len(body),descriptor=descriptor,worker=result)
        data['samples'].append(sample);print(kind,profile,block,round(sample['install_seconds']*1000,2),round(sample['process_seconds']*1000,2),flush=True)
    with transport.local_server(collection) as url:
        for block in range(-1,args.trials):
            kinds=list(ENCODERS);random.Random(924+block).shuffle(kinds)
            for kind in kinds:consume(kind,'cold',block,url);consume(kind,'reuse',block,'gaia-mux://127.0.0.1:1')
            a=[s for s in data['samples'] if s['block']==block and s['kind']=='json'];b=[s for s in data['samples'] if s['block']==block and s['kind']=='binary']
            for x,y in zip(a,b):
                if x['acquisition']['transfer_bytes']!=y['acquisition']['transfer_bytes'] or x['acquisition']['hash_bytes']-x['lock_bytes']!=y['acquisition']['hash_bytes']-y['lock_bytes'] or x['worker']['native_timings']['read_bytes']!=y['worker']['native_timings']['read_bytes']:raise ValueError('logical transfer/hash/read work mismatch')
    data['status']='complete';(args.output/'results.json').write_bytes(t.encode(data))
    rows=[];paired=[]
    for profile in ('cold','reuse'):
        for kind in ENCODERS:
            ss=[s for s in data['samples'] if s['block']>=0 and s['profile']==profile and s['kind']==kind]
            fields=('format_production_seconds','acquisition_seconds','adapter_seconds','install_seconds','process_seconds','total_seconds')
            rows.append(dict(kind=kind,profile=profile,**{k.replace('_seconds','_ms'):statistics.median(s[k]*1000 for s in ss) for k in fields},lock_parse_ms=statistics.median(s['acquisition']['lock_parse_seconds']*1000 for s in ss),lock_bytes=ss[0]['lock_bytes'],reader_setup_ms=statistics.median(s['worker']['native_timings']['setup_seconds']*1000 for s in ss),process_spread_ratio=max(s['process_seconds'] for s in ss)/min(s['process_seconds'] for s in ss)))
        differences=[]
        for block in range(args.trials):
            a=next(s for s in data['samples'] if s['block']==block and s['profile']==profile and s['kind']=='binary');b=next(s for s in data['samples'] if s['block']==block and s['profile']==profile and s['kind']=='json')
            differences.append(dict(block=block,**{k.replace('_seconds','_delta_ms'):(a[k]-b[k])*1000 for k in ('acquisition_seconds','install_seconds','process_seconds','total_seconds')}))
        paired.append(dict(profile=profile,blocks=differences,total_wins=sum(x['total_delta_ms']<0 for x in differences),acquisition_wins=sum(x['acquisition_delta_ms']<0 for x in differences)))
    (args.output/'summary.json').write_text(json.dumps(dict(run_id=run_id,corpus=data['corpus'],rows=rows,paired=paired),indent=2)+'\n')
    (args.output/'parse-profile.json').write_text(json.dumps(diagnostic(doc,max(5,args.trials)),indent=2)+'\n')
    (args.output/'validation.json').write_text(json.dumps(dict(passed=True,operations=len(data['samples']),timed_operations=sum(s['block']>=0 for s in data['samples']),same_logical_python_lock=True,same_logical_transfer_hash_and_read_bytes=True,same_consumer_behavior_and_sha_crc_policy=True,reuse_offline=True,raw_sha256=t.digest((args.output/'results.json').read_bytes())),indent=2)+'\n')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--fixture',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--trials',type=int,default=5);run(parser.parse_args())
