"""Real Django dependency reads under an explicit synchronous storage-service model."""
import argparse
from dataclasses import asdict
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

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'artifacts'))
from service import ModelIO,PROFILES,Sealed,checked_digest
from reader import validate_index


def encoded(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()
def digest(body):return hashlib.sha256(body).hexdigest()
def difference(after,before):return {key:after[key]-before[key] for key in after}


def install(model,source,cache,descriptors):
    for kind in ('index','payload'):
        body=model.read(source/kind,descriptors[kind]['size']);checked_digest(body,descriptors[kind])
        if kind=='index':validate_index(body,descriptors['payload'])
        model.write(cache/kind,body)
    model.write(cache/'ready.json',encoded(dict(version=1,artifacts=descriptors)))
    # Input buffers intentionally end with the persistent-store service call;
    # the separate consumer service must import its own admitted input.


def calibration(root,profile):
    model=ModelIO(root,profile);begin=time.perf_counter()
    for size in (65536,1048576):
        body=b'x'*size;path=root/str(size);model.write(path,body)
        if model.read(path,size)!=body:raise ValueError('calibration bytes')
    elapsed=time.perf_counter()-begin;stats=model.stats()
    if stats['slept_seconds']+1e-6<stats['requested_seconds']:raise ValueError('injected delay fell below requested budget')
    return dict(profile=asdict(profile),elapsed_seconds=elapsed,**stats)


def run(args):
    args.output.mkdir(parents=True,exist_ok=True)
    if (args.output/'results.json').exists():raise ValueError('fresh output required')
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');work=(HERE/'_work'/run_id).resolve();work.mkdir()
    summary=json.loads(args.descriptors.read_text());producer=summary['producer']['flat'];descriptors=dict(index=producer['index_descriptor'],payload=producer['payload_descriptor']);expected=dict(versions=summary['corpus']['versions'],resources=summary['corpus']['resources'])
    source=work/'producer';source.mkdir();shutil.copy2(args.index,source/'index');shutil.copy2(args.payload,source/'payload')
    for kind in descriptors:checked_digest((source/kind).read_bytes(),descriptors[kind])
    expected_input=Sealed(encoded(expected));data=dict(run_id=run_id,status='running',trials=args.trials,consumers=args.consumers,scope='synchronous application artifact-storage service, not degraded physical/block I/O',descriptors=descriptors,versions=expected['versions'],resources=expected['resources'],profiles=[asdict(p) for p in PROFILES if p.name in args.profiles],sessions=[],calibrations=[],sources={})
    tracked=list(HERE.glob('*.py'))+list((HERE.parent/'artifacts').glob('*.py'))+list((HERE.parent/'python/dependency_bundles').glob('*.py'))+list((HERE.parent/'python/dependency_bundles/django_fixture').glob('*.py'))
    frozen=work/'sources';frozen.mkdir()
    for path in tracked:
        relative=path.relative_to(HERE.parents[1]);data['sources'][str(relative)]=digest(path.read_bytes());dest=frozen/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
    data['source_snapshots']=str(frozen)
    signature=None
    def session(profile,mode,block):
        nonlocal signature
        root=work/(profile.name+'-'+mode+'-'+str(block));root.mkdir();cache=root/'cache';model=ModelIO(work,profile)
        begin=time.perf_counter();install(model,source,cache,descriptors);installed=time.perf_counter();install_stats=model.stats();snapshots=[]
        if install_stats['read_calls']!=2 or install_stats['write_calls']!=3 or install_stats['read_bytes']!=sum(d['size'] for d in descriptors.values()):raise ValueError('persistent installation call/byte audit')
        try:
            if mode=='memory':
                for kind in ('index','payload'):
                    body=model.read(cache/kind,descriptors[kind]['size']);checked_digest(body,descriptors[kind]);snapshots.append(Sealed(body))
            admitted=time.perf_counter();admit_stats=difference(model.stats(),install_stats);children=[]
            if admit_stats['read_calls']!=(2 if mode=='memory' else 0) or admit_stats['write_calls']:raise ValueError('input admission audit')
            for consumer in range(args.consumers):
                job=dict(mode=mode,root=str(cache),scope=str(work),profile=asdict(profile),index=descriptors['index'],payload=descriptors['payload'],index_path=str(cache/'index'),payload_path=str(cache/'payload'))
                fds=[expected_input.fd]
                if mode=='memory':job.update(index_fd=snapshots[0].fd,payload_fd=snapshots[1].fd);fds += [s.fd for s in snapshots]
                command=[sys.executable,'-I','-S','-B',str(HERE/'python_worker.py'),'--root',str(cache),'--reader','python','--scenario','rest','--expected',f'/proc/self/fd/{expected_input.fd}','--discovery','index']
                child_begin=time.perf_counter();child=subprocess.run(command,input=json.dumps(job),pass_fds=fds,capture_output=True,text=True,check=True);finished=time.perf_counter();result=json.loads(child.stdout)
                actual=(result['module_origins'],result['executed_files'],result['api_result'],result['resource_hashes'],result['app_count'],result['native_timings']['reads'],result['native_timings']['read_bytes'])
                if signature is None:signature=actual
                elif actual!=signature:raise ValueError('reader changed actual Django behavior')
                reads=result['native_timings']['reads'];read_bytes=result['native_timings']['read_bytes'];stats=result['storage_model']
                if result['network_events'] or not result['correct'] or result['native_timings']['integrity_policy']!='sha256+crc32-every-read':raise ValueError('consumer correctness/integrity')
                if mode=='range' and (stats['read_calls']!=reads+1 or stats['read_bytes']!=read_bytes+descriptors['index']['size']):raise ValueError('range byte/call audit')
                if mode=='memory' and (stats['read_calls'] or stats['write_calls']):raise ValueError('sealed consumer accessed modeled storage')
                children.append(dict(seconds=finished-child_begin,reader=result,consumer=consumer));print(profile.name,mode,block,consumer,round((finished-child_begin)*1000,2),flush=True)
                if consumer==0:first_consumer=finished-begin
            row=dict(profile=profile.name,mode=mode,block=block,install_seconds=installed-begin,admission_seconds=admitted-installed,first_total_seconds=first_consumer,session_seconds=finished-begin,install_stats=install_stats,admission_stats=admit_stats,children=children)
            data['sessions'].append(row)
        finally:
            for snapshot in snapshots:snapshot.close()
    try:
        for profile in PROFILES:
            if profile.name not in args.profiles:continue
            data['calibrations'].append(calibration(work/('calibration-'+profile.name),profile))
        rng=random.Random(912)
        for block in range(args.trials):
            order=[(p,mode) for p in PROFILES if p.name in args.profiles for mode in ('range','memory')];rng.shuffle(order)
            for profile,mode in order:session(profile,mode,block)
        data['status']='complete';(args.output/'results.json').write_bytes(encoded(data))
    finally:expected_input.close()
    rows=[];paired=[]
    for profile in args.profiles:
        for mode in ('range','memory'):
            ss=[s for s in data['sessions'] if s['profile']==profile and s['mode']==mode]
            rows.append(dict(profile=profile,mode=mode,sessions=len(ss),**{key.replace('_seconds','_ms'):statistics.median(s[key]*1000 for s in ss) for key in ('install_seconds','admission_seconds','first_total_seconds','session_seconds')},consumer_ms=statistics.median(c['seconds']*1000 for s in ss for c in s['children']),requested_model_wait_ms=statistics.median((s['install_stats']['requested_seconds']+s['admission_stats']['requested_seconds']+sum(c['reader']['storage_model']['requested_seconds'] for c in s['children']))*1000 for s in ss)))
        blocks=[]
        for block in range(args.trials):
            memory=next(s for s in data['sessions'] if s['profile']==profile and s['mode']=='memory' and s['block']==block);ranges=next(s for s in data['sessions'] if s['profile']==profile and s['mode']=='range' and s['block']==block)
            blocks.append(dict(block=block,first_delta_ms=(memory['first_total_seconds']-ranges['first_total_seconds'])*1000,session_delta_ms=(memory['session_seconds']-ranges['session_seconds'])*1000))
        paired.append(dict(profile=profile,blocks=blocks,memory_first_wins=sum(b['first_delta_ms']<0 for b in blocks),memory_session_wins=sum(b['session_delta_ms']<0 for b in blocks)))
    (args.output/'summary.json').write_text(json.dumps(dict(run_id=run_id,consumers=args.consumers,rows=rows,paired=paired,calibrations=data['calibrations']),indent=2)+'\n')
    (args.output/'validation.json').write_text(json.dumps(dict(passed=True,sessions=len(data['sessions']),consumer_processes=sum(len(s['children']) for s in data['sessions']),same_consumer_behavior_and_sha_crc=True,exact_modeled_range_calls_and_bytes=True,no_modeled_storage_access_from_sealed_consumers=True,calibration_waits_meet_requested_budget=True,raw_sha256=digest((args.output/'results.json').read_bytes())),indent=2)+'\n')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--payload',type=Path,required=True);parser.add_argument('--index',type=Path,required=True);parser.add_argument('--descriptors',type=Path,default=HERE.parent/'artifacts/results/preindexed-bundle/summary.json');parser.add_argument('--output',type=Path,required=True);parser.add_argument('--trials',type=int,default=3);parser.add_argument('--consumers',type=int,default=3);parser.add_argument('--profiles',nargs='+',choices=tuple(p.name for p in PROFILES),default=[p.name for p in PROFILES]);run(parser.parse_args())
