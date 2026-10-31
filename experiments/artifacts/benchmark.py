"""Protocol amplification over loopback HTTP, including verification/publication."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import shutil
import statistics
import sys
import time

import transfer as t

HERE=Path(__file__).resolve().parent
SCENARIOS=('metadata-only','cold-all','cached-all','cached-90','sparse-10','one-missing')


def synthetic(name):
    sizes={'small':[4096]*128,'mixed':[4096]*64+[32768]*48+[131072]*16,
           'large':[1048576]*8}[name]
    return [hashlib.shake_256(f'gaia-artifact-{name}-{i}'.encode()).digest(size) for i,size in enumerate(sizes)]


def input_payloads(directory):
    files=[]
    for p in sorted(directory.rglob('*')):
        if p.is_symlink():raise ValueError('input directory symlinks are outside this experiment')
        if p.is_file():
            if p.stat().st_size>t.MAX_PACK:raise ValueError('file exceeds collection bound')
            if len(files)>=t.MAX_OBJECTS or sum(map(len,files))+p.stat().st_size>t.MAX_PACK:raise ValueError('input collection exceeds experiment bounds')
            files.append(p.read_bytes())
    return files


def scenario(collection,name):
    keys=list(sorted(collection['objects']));rng=random.Random(12761);shuffled=keys.copy();rng.shuffle(shuffled)
    if name=='metadata-only':return [],[],False
    if name=='sparse-10':return shuffled[:max(1,len(keys)//10)],[],False
    if name=='cached-all':return keys,keys,True
    if name=='cached-90':return keys,shuffled[:len(keys)*9//10],True
    if name=='one-missing':return keys,[k for k in keys if k!=shuffled[0]],True
    return keys,[],False


def seed_cache(collection,cache,keys,metadata):
    cache.mkdir(parents=True);(cache/'objects'/'sha256').mkdir(parents=True)
    if metadata:(cache/('sha256-'+collection['manifest_id']+'.manifest')).write_bytes(collection['manifest'])
    for key in keys:(cache/'objects'/'sha256'/key).write_bytes(collection['objects'][key])


def validate(collection,cache,wanted):
    receipt=json.loads((cache/'ready.json').read_bytes())
    if receipt!={'version':1,'manifest':'sha256:'+collection['manifest_id'],'objects':['sha256:'+key for key in sorted(wanted)]}:raise ValueError('receipt mismatch')
    for key in wanted:
        if (cache/'objects'/'sha256'/key).read_bytes()!=collection['objects'][key]:raise ValueError('local artifact mismatch')


def summarize(data):
    rows=[]
    for corpus in dict.fromkeys(c['corpus'] for c in data['cases']):
        for delay in dict.fromkeys(c['delay_ms'] for c in data['cases'] if c['corpus']==corpus):
            for name in data['scenarios']:
                cases={c['mode']:c['samples'] for c in data['cases'] if c['corpus']==corpus and c['delay_ms']==delay and c['scenario']==name}
                if not cases or any(not ss for ss in cases.values()):continue
                modes={}
                for mode,ss in cases.items():
                    med=lambda key:statistics.median(s[key] for s in ss)
                    modes[mode]=dict(median_ms=med('seconds')*1000,min_ms=min(s['seconds'] for s in ss)*1000,
                        max_ms=max(s['seconds'] for s in ss)*1000,requests=med('requests'),transfer_bytes=med('transfer_bytes'),
                        manifest_bytes=med('manifest_bytes'),overfetch_bytes=med('overfetch_bytes'),cache_hits=med('cache_hits'),
                        published_objects=med('published_objects'),connections=med('connections'),hash_bytes=med('hash_bytes'),
                        median_metadata_ms=med('metadata_seconds')*1000,median_cache_validation_ms=med('cache_validation_seconds')*1000,
                        median_payload_verify_publish_ms=med('payload_verify_publish_seconds')*1000,median_receipt_ms=med('receipt_seconds')*1000)
                paired={}
                if 'pack-coalesced' in cases:
                    for control,ss in cases.items():
                        if control=='pack-coalesced':continue
                        deltas=[(a['seconds']-b['seconds'])*1000 for a,b in zip(cases['pack-coalesced'],ss)]
                        paired[control]=dict(median_delta_ms=statistics.median(deltas),wins=sum(x<0 for x in deltas),blocks=len(deltas))
                rows.append(dict(corpus=corpus,delay_ms=delay,scenario=name,modes=modes,coalesced_paired=paired))
    return dict(run_id=data['run_id'],status=data['status'],rows=rows,corpora=data['corpora'],
                trials=data['trials'],scenarios=data['scenarios'],modes=data['modes'],source_sha256=data['source_sha256'])


def report(data,path):
    summary=summarize(data)
    lines=['# Artifact-transfer amplification: first baseline','',f"Run `{data['run_id']}`; {data['status']}; {data['trials']} randomized blocks per case.",'',
           'Generated immutable bytes, separate manifest acquisition, a resident Python HTTP/1.1 server in another process, new client connections per fetch. Both sides disable Nagle. Complete request timing includes manifest lookup/verification, existing-cache verification, payload retrieval, requested-blob hashing, atomic cache publication, receipt publication and connection closure. Fixture generation, cache seeding and independent validation occur outside timing. Atomic publication does not include fsync or power-loss durability.','',
           'The delay field is an injected sleep before each server response. It is an application-delay model, not WAN RTT, packet loss, congestion, TLS, HTTP/2 or HTTP/3 evidence. A zero-delay run still uses loopback sockets and the Python implementation.','']
    for corpus in data['corpora']:
        for delay in sorted(set(c['delay_ms'] for c in data['cases'])):
            rows=[r for r in summary['rows'] if r['corpus']==corpus and r['delay_ms']==delay]
            if not rows:continue
            lines += [f"## {corpus}; injected response delay {delay:g} ms",'',
                      '| Scenario | '+' | '.join(data['modes'])+' |','| --- | '+' | '.join('---:' for _ in data['modes'])+' |']
            for row in rows:lines.append('| '+row['scenario']+' | '+' | '.join(f"{row['modes'][m]['median_ms']:.2f} ms" for m in data['modes'])+' |')
            lines += ['']
    lines += ['Full raw samples remain ignored in `results.json`. Compact counters/paired comparisons are in [summary.json](summary.json); independent validation and raw identity are in [validation.json](validation.json).','']
    path.write_text('\n'.join(lines))


def run(args):
    args.output.mkdir(parents=True,exist_ok=True)
    if (args.output/'results.json').exists():raise ValueError('choose fresh output directory')
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    work=HERE/'_work'/run_id;work.mkdir(parents=True)
    collections={name:t.build_collection(synthetic(name)) for name in args.corpora}
    if args.input_dir:collections['directory']=t.build_collection(input_payloads(args.input_dir))
    snapshots=work/'sources';snapshots.mkdir()
    pins={}
    for p in HERE.glob('*.py'):
        shutil.copy2(p,snapshots/p.name);pins[p.name]=t.digest(p.read_bytes())
    data=dict(run_id=run_id,status='running',trials=args.trials,modes=args.modes,scenarios=args.scenarios,
        corpora={name:dict(objects=len(c['objects']),payload_bytes=len(c['pack']),manifest_bytes=len(c['manifest']),
                    manifest_sha256=c['manifest_id'],pack_sha256=c['pack_id']) for name,c in collections.items()},
        environment=dict(python=sys.version,platform=platform.platform(),cpu_count=os.cpu_count(),
                         affinity=sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else None),
        source_sha256=pins,source_snapshots=str(snapshots),cases=[])
    def save():
        (args.output/'results.json').write_bytes(t.encode(data))
        (args.output/'summary.json').write_text(json.dumps(summarize(data),indent=2)+'\n');report(data,args.output/'REPORT.md')
    rng=random.Random(628017);verified=0
    for name,collection in collections.items():
        for delay in args.delays:
            cases={(scenario,mode):dict(corpus=name,delay_ms=delay,scenario=scenario,mode=mode,samples=[])
                   for scenario in args.scenarios for mode in args.modes}
            data['cases']+=list(cases.values())
            with t.local_server(collection,delay_ms=delay) as url:
                # Untimed correctness/warmup for every mode; all modes get the same treatment.
                for mode in args.modes:
                    cache=work/('warmup-'+mode)
                    if cache.exists():shutil.rmtree(cache)
                    seed_cache(collection,cache,[],False)
                    t.fetch(url,collection['manifest_id'],len(collection['manifest']),list(collection['objects']),cache,mode,
                            workers=args.workers,gap=args.gap,max_span=args.max_span)
                    validate(collection,cache,list(collection['objects']))
                for block in range(args.trials):
                    order=list(cases);rng.shuffle(order)
                    for scenario_name,mode in order:
                        wanted,seeded,metadata=scenario(collection,scenario_name)
                        cache=work/'cache'
                        if cache.exists():shutil.rmtree(cache)
                        seed_cache(collection,cache,seeded,metadata);t.control(url,'reset')
                        begin=time.perf_counter()
                        sample=t.fetch(url,collection['manifest_id'],len(collection['manifest']),wanted,cache,mode,
                                       workers=args.workers,gap=args.gap,max_span=args.max_span)
                        sample['function_seconds']=sample['seconds'];sample['seconds']=time.perf_counter()-begin
                        counts=t.control(url,'metrics')
                        if sample['requests']!=counts['requests'] or sample['response_payload_bytes']!=counts['response_payload_bytes']:
                            raise ValueError('client/server transfer counts differ')
                        if sample['published_objects']!=len(set(wanted)-set(seeded)) or sample['cache_hits']!=len(set(wanted)&set(seeded)):
                            raise ValueError('cache reuse/publication count mismatch')
                        if scenario_name=='cached-all' and (sample['requests'] or sample['response_payload_bytes']):raise ValueError('cached request made network traffic')
                        validate(collection,cache,wanted);verified+=len(wanted)
                        sample.update(block=block,verified=True,verified_objects=len(wanted),server=counts)
                        cases[(scenario_name,mode)]['samples'].append(sample)
                        print(name,delay,scenario_name,mode,'block',block+1,f"{sample['seconds']*1000:.2f} ms",flush=True);save()
    data['status']='complete';save()
    validation=dict(run_id=run_id,passed=True,timed_fetches=sum(len(c['samples']) for c in data['cases']),
                    independently_verified_objects=verified,all_receipts_and_payloads_match=True,
                    all_client_server_counts_match=True,all_cache_reuse_counts_match=True,
                    cached_all_has_zero_network_requests=True,raw_sha256=t.digest((args.output/'results.json').read_bytes()),
                    workers=args.workers,coalescing_gap_bytes=args.gap,max_span_bytes=args.max_span)
    (args.output/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=HERE/'_work/runs/initial')
    parser.add_argument('--corpora',nargs='+',choices=('small','mixed','large'),default=['small','mixed'])
    parser.add_argument('--input-dir',type=Path)
    parser.add_argument('--modes',nargs='+',choices=t.MODES,default=list(t.MODES[:5]))
    parser.add_argument('--scenarios',nargs='+',choices=SCENARIOS,default=list(SCENARIOS))
    parser.add_argument('--trials',type=int,default=7)
    parser.add_argument('--delays',nargs='+',type=float,default=[0,2])
    parser.add_argument('--workers',type=int,default=8)
    parser.add_argument('--gap',type=int,default=65536)
    parser.add_argument('--max-span',type=int,default=4*1024*1024)
    args=parser.parse_args()
    if args.trials<1 or not 1<=args.workers<=32 or args.gap<0 or args.max_span<1 or any(d<0 or d>1000 for d in args.delays):parser.error('invalid trial/budget/delay')
    if any(len(x)!=len(set(x)) for x in [args.corpora,args.modes,args.scenarios,args.delays]):parser.error('duplicate matrix value')
    run(args)
