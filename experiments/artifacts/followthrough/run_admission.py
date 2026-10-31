"""Fresh Django starts through verified demand chunks or full admission."""
from dataclasses import asdict
from pathlib import Path
import argparse,hashlib,json,os,platform,random,resource,shutil,statistics,subprocess,sys,tempfile,threading,time,fcntl
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parents[1]/'storage'))
from admission import ChunkStore,RangeStore,Server,digest
from service import ModelIO,PROFILES,Sealed,checked_digest
from reader import validate_index
from run_python import install


def run(args):
    args.output.mkdir(parents=True,exist_ok=True)
    source_paths=list(HERE.glob('*.py'))+[HERE.parents[1]/'storage'/name for name in ('reader.py','service.py','run_python.py')]+list(HERE.parent.glob('*.py'))+list((HERE.parents[1]/'python/dependency_bundles').glob('*.py'))
    source_pins={str(p.relative_to(HERE.parents[2])):digest(p.read_bytes()) for p in source_paths}
    frozen=args.work/'source-snapshot';frozen.mkdir(parents=True,exist_ok=True)
    for path in source_paths:
        target=frozen/path.relative_to(HERE.parents[2]);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
    if (args.output/'results.json').exists():raise ValueError('fresh output required')
    summary=json.loads(args.descriptors.read_text());producer=summary['producer']['flat'];descriptors=dict(index=producer['index_descriptor'],payload=producer['payload_descriptor']);expected=dict(versions=summary['corpus']['versions'],resources=summary['corpus']['resources'])
    args.work.mkdir(parents=True,exist_ok=True);source=args.work/'producer';source.mkdir()
    for kind,path in [('index',args.index),('payload',args.payload)]:
        shutil.copyfile(path,source/kind);checked_digest((source/kind).read_bytes(),descriptors[kind])
    begin=time.perf_counter();payload=(source/'payload').read_bytes();hashes={size:[digest(payload[i:i+size]) for i in range(0,len(payload),size)] for size in (4096,65536)};prep=time.perf_counter()-begin;del payload
    expected_mem=Sealed(json.dumps(expected).encode());rows=[];signature=None
    cases=[(p,mode,block) for block in range(args.trials) for p in PROFILES if p.name in args.profiles for mode in args.modes];random.Random(2001).shuffle(cases)
    measurement=args.lock.open('a+') if args.lock else None
    for profile,mode,block in cases:
        if measurement:fcntl.flock(measurement,fcntl.LOCK_EX)
        folder=args.work/(profile.name+'-'+mode+'-'+str(block));folder.mkdir();model=ModelIO(args.work,profile);cache=folder/'cache'
        start=time.perf_counter();install(model,source,cache,descriptors);installed=time.perf_counter();install_stats=model.stats();model=ModelIO(args.work,profile)
        if mode=='range':store=RangeStore(cache/'payload',model)
        else:
            size=4096 if mode=='demand4k' else 65536
            store=ChunkStore(cache/'payload',size,descriptors['payload']['size'],model,hashes[size])
        if mode=='full':store.admit_all()
        admitted=time.perf_counter()
        # Socket transport is identical for every policy; server lifetime/setup is charged.
        sock=folder/'s';server=Server(sock,store);thread=threading.Thread(target=server.serve_forever,kwargs=dict(poll_interval=.01),daemon=True);thread.start();children=[]
        try:
            for child in range(args.consumers):
                job=dict(mode='range',socket=str(sock),root=str(cache),scope=str(args.work),profile=asdict(profile),index=descriptors['index'],payload=descriptors['payload'],index_path=str(cache/'index'),payload_path=str(cache/'payload'))
                command=[sys.executable,'-I','-S','-B',str(HERE/'worker.py'),'--root',str(cache),'--reader','python','--scenario','rest','--expected',f'/proc/self/fd/{expected_mem.fd}','--discovery','index']
                t0=time.perf_counter();process=subprocess.run(command,input=json.dumps(job),pass_fds=[expected_mem.fd],capture_output=True,text=True)
                if process.returncode:raise RuntimeError(process.stderr)
                result=json.loads(process.stdout);end=time.perf_counter();actual=[result[k] for k in ('module_origins','executed_files','api_result','resource_hashes','app_count')]
                if signature is None:signature=actual
                if actual!=signature or result['network_events'] or not result['correct']:raise ValueError('Django behavior changed')
                if result['native_timings']['integrity_policy']!='sha256+crc32-every-read':raise ValueError('verification bypass')
                children.append(dict(seconds=end-t0,result=result,server_after=store.stats()));print(profile.name,mode,block,child,round((end-t0)*1000,1),flush=True)
                if child==0:first=end-start
            rows.append(dict(profile=profile.name,mode=mode,block=block,install_seconds=installed-start,admission_seconds=admitted-installed,first_seconds=first,session_seconds=end-start,install_stats=install_stats,server=store.stats(),children=children,trace=store.trace))
        finally:
            server.shutdown();server.server_close();thread.join();store.close()
            if measurement:fcntl.flock(measurement,fcntl.LOCK_UN)
    expected_mem.close()
    if measurement:measurement.close()
    if any(digest((HERE.parents[2]/name).read_bytes())!=pin for name,pin in source_pins.items()):raise ValueError('source changed during measurement')
    data=dict(version=1,trials=args.trials,consumers=args.consumers,descriptors=descriptors,producer_chunk_manifest_seconds=prep,producer_chunk_hash_bytes=sum(len(v)*32 for v in hashes.values()),scope='application-service logical requests with warm host files; socket copies charged, no physical/network claim',python=sys.version,platform=platform.platform(),rows=rows,source_hashes=source_pins)
    raw=json.dumps(data,sort_keys=True).encode();(args.output/'results.json').write_bytes(raw)
    reduced=[]
    for profile in args.profiles:
        for mode in args.modes:
            selected=[r for r in rows if r['profile']==profile and r['mode']==mode]
            reduced.append(dict(profile=profile,mode=mode,first_ms=statistics.median(r['first_seconds']*1000 for r in selected),session_ms=statistics.median(r['session_seconds']*1000 for r in selected),payload_read_bytes=statistics.median(r['server']['storage']['read_bytes'] for r in selected),payload_read_calls=statistics.median(r['server']['storage']['read_calls'] for r in selected),peak_cache_bytes=statistics.median(r['server']['peak_cache_bytes'] for r in selected),execution_before_last_fetch=sum(r['children'][0]['result']['first_django_execution']<r['children'][0]['server_after']['last_fetch'] for r in selected)))
    (args.output/'summary.json').write_text(json.dumps(dict(rows=reduced,producer_chunk_manifest_seconds=prep,raw_identity=dict(bytes=len(raw),sha256=digest(raw))),indent=2)+'\n')
    (args.output/'validation.json').write_text(json.dumps(dict(passed=True,processes=len(rows)*args.consumers,same_application_behavior=True,sha_crc_every_read=True,verified_producer_chunks=True,raw_sha256=digest(raw)),indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--payload',type=Path,required=True);p.add_argument('--index',type=Path,required=True);p.add_argument('--descriptors',type=Path,default=HERE.parent/'results/preindexed-bundle/summary.json');p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--lock',type=Path);p.add_argument('--trials',type=int,default=3);p.add_argument('--consumers',type=int,default=3);p.add_argument('--profiles',nargs='+',default=['nominal','request-latency','bandwidth']);p.add_argument('--modes',nargs='+',default=['range','demand4k','demand64k','full']);run(p.parse_args())
