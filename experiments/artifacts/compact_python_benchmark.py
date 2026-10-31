"""Hash lock -> stream -> retained representation -> real Django lifecycle."""
import argparse
from datetime import datetime,timezone
import hashlib
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
LOADERS=HERE.parent/'python/dependency_bundles'
sys.path.insert(0,str(LOADERS))
import binary_index
from precomputed_index import file_identity,IndexedBundleReader
import locked_python as lp
import compact_python as compact
import pipeline_transport as transport
import transfer as t


def run(args):
    args.output.mkdir(parents=True,exist_ok=True)
    if (args.output/'results.json').exists():raise ValueError('fresh output required')
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');work=HERE/'_work'/('compact-python-'+run_id);work.mkdir()
    fixture=args.fixture.resolve();source=fixture/'rest-bytecode';archive=fixture/'rest-bytecode.zip';index=fixture/'rest-bytecode.index'
    expected=json.loads((fixture/'rest-expected.json').read_text());expected_path=work/'expected.json';expected_path.write_bytes(t.encode(expected))
    started=time.perf_counter();logical_lock,payloads=lp.make_lock(source,expected);logical_pin=t.digest(logical_lock)
    zip_body=archive.read_bytes();index_body=index.read_bytes();zip_key=t.digest(zip_body);index_key=t.digest(index_body)
    package_lock=t.encode(dict(version=1,algorithm='sha256',files=[dict(name='dependencies.zip',sha256=t.digest(zip_body),size=len(zip_body)),dict(name='dependencies.index',sha256=t.digest(index_body),size=len(index_body))],versions=expected['versions'],resources=expected['resources']))
    package_pin=t.digest(package_lock);lp.parse_lock(package_lock,package_pin)
    logical_path=work/'dependencies.pylock';logical_path.write_bytes(logical_lock)
    package_path=work/'archive.pylock';package_path.write_bytes(package_lock)
    collection=t.build_collection(payloads+[zip_body,index_body]);producer=time.perf_counter()-started
    data=dict(run_id=run_id,status='running',trials=args.trials,producer_seconds=producer,
      corpus=dict(versions=expected['versions'],resources=expected['resources'],files=len(json.loads(logical_lock)['files']),logical_unique_objects=len(set(t.digest(p) for p in payloads)),logical_bytes=sum(map(len,payloads)),zip_bytes=len(zip_body),index_bytes=len(index_body),logical_lock_sha256=logical_pin,package_lock_sha256=package_pin),
      sources={str(p.relative_to(HERE.parents[1])):t.digest(p.read_bytes()) for base in (HERE,LOADERS) for p in base.glob('*.py')},cases=[],samples=[])
    frozen=work/'sources';frozen.mkdir()
    for relative,pin in data['sources'].items():
        dest=frozen/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(HERE.parents[1]/relative,dest)
    data['source_snapshots']=str(frozen)
    signature=None
    def sample(mode,profile,block,url):
        nonlocal signature
        root=work/(mode+'-'+str(block));root.mkdir(exist_ok=True);cas=root/'cas';installed=root/'installed'
        lock,pin=(logical_lock,logical_pin) if mode.endswith('pack') else (package_lock,package_pin)
        started=time.perf_counter();acq=lp.acquire(url,lock,pin,cas,'packed' if mode.endswith('pack') else 'files');fetched=time.perf_counter()
        if mode.endswith('pack'):consumer_root=cas;consumer_index=None;index_pin=None
        else:
            objects=cas/'objects/sha256';zip_path=objects/zip_key;producer_index=objects/index_key
            if mode=='directory':
                if not installed.exists():
                    installed.mkdir()
                    with zipfile.ZipFile(zip_path) as z:
                        # Only exact pinned logical names are permitted; bounded source set.
                        names={row['name']:row for row in json.loads(logical_lock)['files']}
                        if set(z.namelist())!=set(names):raise ValueError('zip logical set mismatch')
                        for name,row in names.items():
                            body=z.read(name)
                            if len(body)!=row['size'] or t.digest(body)!=row['sha256']:raise ValueError('extracted logical digest')
                            target=installed/name;target.parent.mkdir(parents=True,exist_ok=True);t.atomic_write(target,body)
                    t.atomic_write(root/'install-ready.json',t.encode(dict(version=1,lock=logical_pin)))
                consumer_root=installed;consumer_index=None;index_pin=None
            else:
                consumer_root=zip_path;consumer_index=root/'admitted.index'
                if not consumer_index.exists():
                    document=binary_index.decode(producer_index.read_bytes());document['entries']=list(document['entries'])
                    if document['archive_sha256']!=zip_key or document['archive_size']!=len(zip_body):raise ValueError('index/archive binding')
                    document['local_identity']=file_identity(zip_path.stat());encoded=binary_index.encode(document);t.atomic_write(consumer_index,encoded)
                    check=IndexedBundleReader(zip_path,consumer_index,index_sha256=t.digest(encoded),verify='local');check.close()
                    t.atomic_write(root/'install-ready.json',t.encode(dict(version=1,lock=package_pin)))
                index_pin=t.digest(consumer_index.read_bytes())
        compact_descriptor=None
        if mode.startswith('compact-'):
            compact_path=root/'consumer.gpi'
            receipt=root/'consumer-pin.json'
            if not receipt.exists():
                compact_descriptor=compact.build(cas,logical_lock,logical_pin,compact_path,'pack' if mode.endswith('pack') else 'zip',consumer_root,consumer_index,index_pin)
                t.atomic_write(receipt,t.encode(compact_descriptor))
            else:compact_descriptor=json.loads(receipt.read_text())
            consumer_root=cas
        installed_end=time.perf_counter()
        cmd=[sys.executable,'-I','-S','-B',str(HERE/'compact_python_worker.py'),'--root',str(consumer_root),'--reader','directory' if mode=='directory' else 'python','--scenario','rest','--expected',str(expected_path),'--discovery','index']
        if consumer_index:cmd+=['--index',str(consumer_index),'--pin',index_pin]
        env=os.environ.copy();env.pop('GAIA_PY_LOCK',None);env.pop('GAIA_PY_LOCK_PIN',None)
        env['GAIA_READER_KIND']=mode
        if mode.endswith('pack'):env.update(GAIA_PY_LOCK=str(logical_path),GAIA_PY_LOCK_PIN=logical_pin)
        if compact_descriptor:env.update(GAIA_COMPACT_INDEX=str(compact_path),GAIA_COMPACT_PIN=compact_descriptor['pin'],GAIA_PY_LOCK_PIN=logical_pin)
        child_start=time.perf_counter();child=subprocess.run(cmd,env=env,capture_output=True,text=True,check=True);child_end=time.perf_counter();result=json.loads(child.stdout)
        sig=(result['module_origins'],result['executed_files'],result['api_result'],result['resource_hashes'],result['app_count'])
        if signature is None:signature=sig
        elif signature!=sig:raise ValueError('consumer behavior differs')
        if not result['correct'] or result['network_events']:raise ValueError('consumer validation')
        if mode.endswith('pack') and any(p.suffix in ('.py','.pyc','.html') for p in cas.rglob('*') if p.is_file()):raise ValueError('loose files materialized')
        row=dict(compact_descriptor=compact_descriptor,mode=mode,profile=profile,block=block,acquisition=acq,acquisition_seconds=fetched-started,install_seconds=installed_end-started,process_seconds=child_end-child_start,total_seconds=child_end-started,worker=result)
        data['samples'].append(row);print(mode,profile,block,round(row['install_seconds']*1000,2),round(row['process_seconds']*1000,2),flush=True)
        if profile=='reuse' and acq['requests']:raise ValueError('reuse accessed network')
    with transport.local_server(collection) as url:
        for block in range(-1,args.trials):
            modes=['old-zip','old-pack','compact-zip','compact-pack'];random.Random(917+block).shuffle(modes)
            for mode in modes:
                sample(mode,'cold',block,url);sample(mode,'reuse',block,'gaia-mux://127.0.0.1:1')
    data['status']='complete'
    (args.output/'results.json').write_bytes(t.encode(data))
    summary=[]
    for profile in ('cold','reuse'):
        for mode in ('old-zip','old-pack','compact-zip','compact-pack'):
            ss=[s for s in data['samples'] if s['profile']==profile and s['mode']==mode and s['block']>=0]
            summary.append(dict(mode=mode,profile=profile,samples=len(ss),**{k.replace('_seconds','_ms'):statistics.median(s[k]*1000 for s in ss) for k in ('acquisition_seconds','install_seconds','process_seconds','total_seconds')},ready_ms=statistics.median(s['worker']['ready_seconds']*1000 for s in ss),modules=ss[0]['worker']['module_count'],requests=ss[0]['acquisition']['requests'],transfer_bytes=ss[0]['acquisition']['transfer_bytes'],reader_setup_ms=statistics.median(s['worker']['native_timings']['setup_seconds']*1000 for s in ss),reader_integrity=ss[0]['worker']['native_timings']['integrity_policy'],reader_read_ms=None if 'read_seconds' not in ss[0]['worker']['native_timings'] else statistics.median(s['worker']['native_timings']['read_seconds']*1000 for s in ss),reader_hash_ms=None if 'hash_seconds' not in ss[0]['worker']['native_timings'] else statistics.median(s['worker']['native_timings']['hash_seconds']*1000 for s in ss),process_spread_ratio=max(s['process_seconds'] for s in ss)/min(s['process_seconds'] for s in ss)))
    paired=[]
    for profile in ('cold','reuse'):
        for left,right in (('compact-pack','compact-zip'),('compact-pack','old-pack'),('compact-zip','old-zip')):
            pairs=[]
            for block in range(args.trials):
                a=next(s for s in data['samples'] if s['mode']==left and s['profile']==profile and s['block']==block);b=next(s for s in data['samples'] if s['mode']==right and s['profile']==profile and s['block']==block)
                pairs.append(dict(block=block,total_delta_ms=(a['total_seconds']-b['total_seconds'])*1000,process_delta_ms=(a['process_seconds']-b['process_seconds'])*1000,install_delta_ms=(a['install_seconds']-b['install_seconds'])*1000))
            paired.append(dict(profile=profile,left=left,right=right,blocks=pairs,total_wins=sum(p['total_delta_ms']<0 for p in pairs),process_wins=sum(p['process_delta_ms']<0 for p in pairs)))
    (args.output/'summary.json').write_text(json.dumps(dict(run_id=run_id,corpus=data['corpus'],rows=summary,paired=paired),indent=2)+'\n')
    (args.output/'validation.json').write_text(json.dumps(dict(passed=True,operations=len(data['samples']),timed_operations=sum(s['block']>=0 for s in data['samples']),consumer_signatures_match=True,no_dependency_materialization_packed=True,reuse_offline=True,raw_sha256=t.digest((args.output/'results.json').read_bytes())),indent=2)+'\n')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--fixture',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--trials',type=int,default=5)
    args=parser.parse_args();run(args)
