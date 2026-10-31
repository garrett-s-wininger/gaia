"""Producer-preindexed two-artifact flat bundle vs stored ZIP; matched readers."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import random
import shutil
import statistics
import subprocess
import sys
import time
import zipfile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'python/dependency_bundles'))
from precomputed_index import build_index
import cache_store
import compact_python as compact
import generic_lock as generic
import locked_python as python
import preindexed_bundle as bundle
import pipeline_transport as transport
import transfer as t


def produce(directory,logical_body,payloads,kind):
    directory=directory.resolve();begin=time.perf_counter();directory.mkdir();logical=json.loads(logical_body);pin=t.digest(logical_body);source=directory/'source';source.mkdir()
    if kind=='flat':
        unique={t.digest(body):body for body in payloads};store=cache_store.Packed(source)
        try:
            objects=[dict(sha256=key,size=len(body)) for key,body in sorted(unique.items())];store.prepare(objects)
            for obj in objects:store.put_verified(obj,unique[obj['sha256']])
            store.finish();data_path=store.data_dir/(next(iter(store.packs))+'.gap')
        finally:store.close()
        compact.build(source,logical_body,pin,directory/'local.gpi','pack')
    else:
        data_path=source/'dependencies.zip'
        with zipfile.ZipFile(data_path,'w',compression=zipfile.ZIP_STORED,allowZip64=False) as archive:
            for row,body in zip(logical['files'],payloads):
                info=zipfile.ZipInfo(row['name'],date_time=(2026,1,1,0,0,0));info.external_attr=0o100644<<16;archive.writestr(info,body)
        index=directory/'stored.index';desc=build_index(data_path,index,encoding='binary');compact.build(source,logical_body,pin,directory/'local.gpi','zip',data_path,index,desc['index_sha256'])
    payload=data_path.read_bytes();payload_desc=dict(algorithm='sha256',digest=t.digest(payload),size=len(payload));index_desc=bundle.portable_index(directory/'local.gpi',directory/'portable.gpi');index_body=(directory/'portable.gpi').read_bytes()
    artifacts=sorted([payload_desc,index_desc],key=lambda r:r['digest']);ids={r['digest']:i for i,r in enumerate(artifacts)}
    names={'rest_framework':'djangorestframework','django_filters':'django-filter'}
    packages=[dict(ecosystem='pypi',name=names.get(name,name),version=version) for name,version in sorted(logical['versions'].items())]
    associations=[dict(package=i,artifact=ids[desc['digest']],role=role,label='python-inputs') for i in range(len(packages)) for role,desc in (('payload',payload_desc),('index',index_desc))]
    lock=generic.encode_binary(dict(version=1,packages=packages,artifacts=artifacts,associations=associations,metadata=[dict(ecosystem='python',role='consumer-index',artifact=ids[index_desc['digest']])]))
    return dict(kind=kind,lock=lock,lock_pin=t.digest(lock),payload=payload,index=index_body,payload_descriptor=payload_desc,index_descriptor=index_desc,producer_seconds=time.perf_counter()-begin)


def run(args):
    args.output.mkdir(parents=True,exist_ok=True)
    if (args.output/'results.json').exists():raise ValueError('fresh output required')
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');work=HERE/'_work/preindexed'/run_id;work.mkdir(parents=True)
    expected=json.loads((args.fixture/'rest-expected.json').read_text());logical,payloads=python.make_lock(args.fixture/'rest-bytecode',expected);expected_path=work/'expected.json';expected_path.write_bytes(t.encode(expected))
    produced={kind:produce(work/kind,logical,payloads,kind) for kind in ('flat','zip')};collection=t.build_collection([p[k] for p in produced.values() for k in ('payload','index')])
    data=dict(run_id=run_id,status='running',trials=args.trials,producer={kind:{k:v for k,v in p.items() if k not in ('lock','payload','index')} for kind,p in produced.items()},corpus=dict(files=len(json.loads(logical)['files']),versions=expected['versions'],resources=expected['resources'],logical_pin=t.digest(logical)),samples=[],sources={str(p.relative_to(HERE.parents[1])):t.digest(p.read_bytes()) for base in (HERE,HERE.parent/'python/dependency_bundles',HERE.parent/'python/dependency_bundles/django_fixture') for p in base.glob('*.py')})
    sources=work/'sources';sources.mkdir();data['source_snapshots']=str(sources)
    for relative in data['sources']:
        dest=sources/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(HERE.parents[1]/relative,dest)
    signature=None
    def consume(kind,profile,block,url):
        nonlocal signature
        p=produced[kind];root=work/(kind+'-'+str(block));root.mkdir(exist_ok=True);cas=root/'cache';binding=root/'binding.json';receipt=root/'installed.json'
        begin=time.perf_counter();view,acquired=bundle.acquire(url,p['lock'],p['lock_pin'],cas);fetched=time.perf_counter()
        if profile=='cold' or acquired['requests'] or not receipt.exists():
            admission=bundle.admit(cas,p['index_descriptor'],p['payload_descriptor'],binding);t.atomic_write(receipt,t.encode(admission))
        else:admission=json.loads(receipt.read_text())
        installed=time.perf_counter();env=os.environ.copy();env.update(GAIA_READER_KIND='compact-pack',GAIA_COMPACT_INDEX=str(cas/'objects/sha256'/p['index_descriptor']['digest']),GAIA_COMPACT_PIN=p['index_descriptor']['digest'],GAIA_PY_LOCK_PIN=admission['logical_pin'],GAIA_BINDING=str(binding),GAIA_BINDING_PIN=admission['binding_pin']);env.pop('GAIA_PY_LOCK',None)
        command=[sys.executable,'-I','-S','-B',str(HERE/'preindexed_bundle_worker.py'),'--root',str(cas),'--reader','python','--scenario','rest','--expected',str(expected_path),'--discovery','index']
        child_begin=time.perf_counter();child=subprocess.run(command,env=env,capture_output=True,text=True,check=True);child_end=time.perf_counter();result=json.loads(child.stdout)
        actual=(result['module_origins'],result['executed_files'],result['api_result'],result['resource_hashes'],result['app_count'])
        if signature is None:signature=actual
        elif signature!=actual:raise ValueError('portable representations changed consumer behavior')
        if result['network_events'] or not result['correct'] or result['native_timings']['integrity_policy']!='sha256+crc32-every-read':raise ValueError('consumer validity/integrity policy')
        if acquired['objects']!=2 or acquired['requests']!=int(profile=='cold'):raise ValueError('artifact operation contract')
        if profile=='reuse' and acquired['transfer_bytes']:raise ValueError('offline reuse fetched bytes')
        row=dict(kind=kind,profile=profile,block=block,acquisition=acquired,acquisition_seconds=fetched-begin,admission_seconds=installed-fetched,install_seconds=installed-begin,process_seconds=child_end-child_begin,total_seconds=child_end-begin,admission=admission,worker=result)
        data['samples'].append(row);print(kind,profile,block,round(row['install_seconds']*1000,2),round(row['process_seconds']*1000,2),flush=True)
    with transport.local_server(collection) as url:
        for block in range(-1,args.trials):
            order=list(produced);random.Random(827+block).shuffle(order)
            for kind in order:consume(kind,'cold',block,url);consume(kind,'reuse',block,'gaia-mux://127.0.0.1:1')
            for profile in ('cold','reuse'):
                rows=[r for r in data['samples'] if r['block']==block and r['profile']==profile]
                if len({(r['worker']['native_timings']['read_bytes'],r['worker']['native_timings']['reads']) for r in rows})!=1:raise ValueError('logical byte/read work differs')
    data['status']='complete';(args.output/'results.json').write_bytes(t.encode(data));summary=[];paired=[]
    for profile in ('cold','reuse'):
        for kind in produced:
            ss=[s for s in data['samples'] if s['block']>=0 and s['profile']==profile and s['kind']==kind]
            summary.append(dict(kind=kind,profile=profile,**{k.replace('_seconds','_ms'):statistics.median(s[k]*1000 for s in ss) for k in ('acquisition_seconds','admission_seconds','install_seconds','process_seconds','total_seconds')},reader_setup_ms=statistics.median(s['worker']['native_timings']['setup_seconds']*1000 for s in ss),reader_read_ms=statistics.median(s['worker']['native_timings']['read_seconds']*1000 for s in ss),reader_hash_ms=statistics.median(s['worker']['native_timings']['hash_seconds']*1000 for s in ss),process_spread_ratio=max(s['process_seconds'] for s in ss)/min(s['process_seconds'] for s in ss),requests=ss[0]['acquisition']['requests'],transfer_bytes=ss[0]['acquisition']['transfer_bytes']))
        differences=[]
        for block in range(args.trials):
            a=next(s for s in data['samples'] if s['block']==block and s['kind']=='flat' and s['profile']==profile);b=next(s for s in data['samples'] if s['block']==block and s['kind']=='zip' and s['profile']==profile)
            differences.append(dict(block=block,**{k.replace('_seconds','_delta_ms'):(a[k]-b[k])*1000 for k in ('acquisition_seconds','install_seconds','process_seconds','total_seconds')}))
        paired.append(dict(profile=profile,blocks=differences,total_wins=sum(d['total_delta_ms']<0 for d in differences),process_wins=sum(d['process_delta_ms']<0 for d in differences)))
    (args.output/'summary.json').write_text(json.dumps(dict(run_id=run_id,producer=data['producer'],corpus=data['corpus'],rows=summary,paired=paired),indent=2)+'\n')
    (args.output/'validation.json').write_text(json.dumps(dict(passed=True,operations=len(data['samples']),timed_operations=sum(s['block']>=0 for s in data['samples']),same_consumer_behavior=True,same_logical_read_bytes_and_sha_crc_policy=True,two_cas_artifacts_both=True,reuse_offline=True,raw_sha256=t.digest((args.output/'results.json').read_bytes())),indent=2)+'\n')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--fixture',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--trials',type=int,default=5);run(parser.parse_args())
