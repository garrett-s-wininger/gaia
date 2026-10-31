"""Verified local pack/index admission and logical access, with file controls."""
import argparse
from contextlib import ExitStack
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import platform
import random
import shutil
import statistics
import sys
import time

import benchmark as baseline
import binary_transport
import cache_store
import transfer as t

HERE=Path(__file__).resolve().parent
TRANSPORTS=('http','binary-buffered')
LAYOUTS=('files','packed')
SCENARIOS=baseline.SCENARIOS
MODES=('pack-coalesced','selected-batch')


def seed(collection,path,keys,metadata,layout):
    store=cache_store.make(path,layout)
    try:
        objects={obj['sha256']:obj for obj in t.parse_manifest(collection['manifest'])['objects']}
        store.prepare([objects[key] for key in keys])
        for key in keys:
            body=collection['objects'][key]
            if t.digest(body)!=key:raise ValueError('invalid cache seed')
            store.put_verified(objects[key],body)
        store.finish()
    finally:store.close()
    if metadata:(path/('sha256-'+collection['manifest_id']+'.manifest')).write_bytes(collection['manifest'])


def validate(collection,path,wanted,views,ordinary):
    receipt=json.loads((path/'ready.json').read_bytes())
    if receipt!={'version':1,'manifest':'sha256:'+collection['manifest_id'],'objects':['sha256:'+key for key in sorted(wanted)]}:
        raise ValueError('receipt mismatch')
    if set(views)!=set(wanted) or set(ordinary)!=set(wanted):raise ValueError('logical/ordinary selection mismatch')
    for key in wanted:
        if not views[key].readonly or bytes(views[key])!=collection['objects'][key] or ordinary[key].read_bytes()!=collection['objects'][key]:
            raise ValueError('logical or materialized payload mismatch')


def summarize(data):
    result=[]
    for corpus in data['corpora']:
        for delay in data['delays']:
            for scenario in data['scenarios']:
                for mode in data['modes']:
                    cases={(c['transport'],c['layout']):c['samples'] for c in data['cases']
                           if c['corpus']==corpus and c['delay_ms']==delay and c['scenario']==scenario and c['mode']==mode}
                    if not cases or any(not values for values in cases.values()):continue
                    row=dict(corpus=corpus,delay_ms=delay,scenario=scenario,mode=mode,variants={},packed_paired={})
                    for (transport,layout),samples in cases.items():
                        med=lambda f:statistics.median(f(s) for s in samples)
                        row['variants'][transport+'/'+layout]=dict(median_ms=med(lambda s:s['seconds']*1000),
                            min_ms=min(s['seconds']*1000 for s in samples),max_ms=max(s['seconds']*1000 for s in samples),
                            median_acquisition_ms=med(lambda s:s['acquisition_seconds']*1000),median_access_ms=med(lambda s:s['access_seconds']*1000),
                            median_materialization_ms=med(lambda s:s['materialization_seconds']*1000),
                            median_with_ordinary_files_ms=med(lambda s:s['with_ordinary_files_seconds']*1000),
                            atomic_publications=med(lambda s:s['acquisition']['atomic_publications']),
                            extra_materialization_publications=med(lambda s:s['materialization']['publications']),
                            requests=med(lambda s:s['acquisition']['requests']),transfer_bytes=med(lambda s:s['acquisition']['transfer_bytes']),
                            overfetch_bytes=med(lambda s:s['acquisition']['overfetch_bytes']),logical_hash_bytes=med(lambda s:s['logical_hash_bytes']),
                            representation_hash_bytes=med(lambda s:s['representation_hash_bytes']),
                            data_opens=med(lambda s:s['acquisition']['store']['data_opens']+s['access']['store']['data_opens']),
                            data_reads=med(lambda s:s['acquisition']['store']['data_reads']+s['access']['store']['data_reads']),
                            data_read_bytes=med(lambda s:s['acquisition']['store']['data_read_bytes']+s['access']['store']['data_read_bytes']),
                            cache_write_bytes=med(lambda s:s['acquisition']['publication_bytes']),
                            packs=med(lambda s:s['access']['store']['packs']))
                    for transport in data['transports']:
                        a=cases[(transport,'packed')];b=cases[(transport,'files')]
                        delta=[(x['seconds']-y['seconds'])*1000 for x,y in zip(a,b)]
                        ordinary=[(x['with_ordinary_files_seconds']-y['with_ordinary_files_seconds'])*1000 for x,y in zip(a,b)]
                        row['packed_paired'][transport]=dict(median_delta_ms=statistics.median(delta),wins=sum(x<0 for x in delta),blocks=len(delta),
                            ordinary_files_median_delta_ms=statistics.median(ordinary),ordinary_files_wins=sum(x<0 for x in ordinary))
                    result.append(row)
    return dict(run_id=data['run_id'],status=data['status'],trials=data['trials'],corpora=data['corpora'],rows=result,source_sha256=data['source_sha256'])


def report(data,path):
    rows=summarize(data)['rows'];lines=['# Verified local pack/index admission and access','',
        f"Run `{data['run_id']}`; {data['status']}; {data['trials']} randomized blocks per case.",'',
        'Complete operation timing includes acquisition (metadata, cache verification, transfer, logical digest validation and publication/receipt), followed by a fresh verified logical-byte access. The latter reopens the store and returns read-only views backed by owned immutable buffers. File and pack layouts perform the same requested logical verification. Pack/index representation checks and sealing hashes are extra work, recorded separately.','',
        'Ordinary-file materialization is timed afterward and reported separately and as a combined operation. File controls reuse their existing per-blob paths; packed views must pay to create requested ordinary files. Source/server/cache-seed initialization and parent validation are excluded. Injected delay is a per-response application sleep, not a WAN model.','']
    for corpus in data['corpora']:
        for delay in data['delays']:
            lines += [f'## {corpus}; injected response delay {delay:g} ms','',
                '| Scenario / transfer mode | HTTP files | HTTP packed | Buffered binary files | Buffered binary packed |','| --- | ---: | ---: | ---: | ---: |']
            for row in rows:
                if row['corpus']!=corpus or row['delay_ms']!=delay:continue
                lines.append('| '+row['scenario']+' / '+row['mode']+' | '+' | '.join(f"{row['variants'][key]['median_ms']:.2f} ms" for key in ('http/files','http/packed','binary-buffered/files','binary-buffered/packed'))+' |')
            lines+=['']
    lines+=['[Summary](summary.json) includes paired results, access/materialization costs and storage counters; [validation](validation.json) binds ignored raw observations.','']
    path.write_text('\n'.join(lines))


def run(args):
    args.output.mkdir(parents=True,exist_ok=True)
    if (args.output/'results.json').exists():raise ValueError('choose fresh output directory')
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');work=HERE/'_work'/('admission-'+run_id);work.mkdir(parents=True)
    collections={name:t.build_collection(baseline.synthetic(name)) for name in args.corpora}
    if args.input_dir:collections['directory']=t.build_collection(baseline.input_payloads(args.input_dir))
    sources=work/'sources';sources.mkdir();pins={}
    for source in HERE.glob('*.py'):shutil.copy2(source,sources/source.name);pins[source.name]=t.digest(source.read_bytes())
    data=dict(run_id=run_id,status='running',trials=args.trials,transports=list(TRANSPORTS),layouts=list(LAYOUTS),modes=args.modes,
        scenarios=args.scenarios,delays=args.delays,corpora={name:dict(objects=len(c['objects']),payload_bytes=len(c['pack']),manifest_bytes=len(c['manifest']),manifest_sha256=c['manifest_id']) for name,c in collections.items()},
        environment=dict(python=sys.version,platform=platform.platform(),cpu_count=os.cpu_count(),affinity=sorted(os.sched_getaffinity(0))),
        source_sha256=pins,source_snapshots=str(sources),cases=[])
    def save():
        (args.output/'results.json').write_bytes(t.encode(data));(args.output/'summary.json').write_text(json.dumps(summarize(data),indent=2)+'\n');report(data,args.output/'REPORT.md')
    rng=random.Random(4628022);checked=0
    work_fields=('requests','response_payload_bytes','manifest_bytes','transfer_bytes','missing_bytes','overfetch_bytes','cache_hits','published_objects','hash_bytes','batch_framing_bytes')
    for name,collection in collections.items():
        for delay in args.delays:
            cases={(scenario,mode,transport,layout):dict(corpus=name,delay_ms=delay,scenario=scenario,mode=mode,transport=transport,layout=layout,samples=[])
                   for scenario in args.scenarios for mode in args.modes for transport in TRANSPORTS for layout in LAYOUTS}
            data['cases']+=list(cases.values())
            with ExitStack() as stack:
                urls=dict(http=stack.enter_context(t.local_server(collection,delay_ms=delay)),
                          **{'binary-buffered':stack.enter_context(binary_transport.local_server(collection,delay_ms=delay,buffered=True))})
                for transport in TRANSPORTS:
                    for layout in LAYOUTS:
                        cache=work/'warmup'
                        if cache.exists():shutil.rmtree(cache)
                        seed(collection,cache,[],False,layout)
                        t.fetch(urls[transport],collection['manifest_id'],len(collection['manifest']),list(collection['objects']),cache,args.modes[0],storage=layout)
                        views,_=cache_store.access(cache,collection['manifest_id'],len(collection['manifest']),list(collection['objects']),layout)
                        if any(bytes(views[key])!=body for key,body in collection['objects'].items()):raise ValueError('warmup access mismatch')
                for block in range(args.trials):
                    order=list(cases);rng.shuffle(order)
                    for scenario,mode,transport,layout in order:
                        wanted,seeded,metadata=baseline.scenario(collection,scenario);cache=work/'cache';ordinary_root=work/'ordinary'
                        for directory in (cache,ordinary_root):
                            if directory.exists():shutil.rmtree(directory)
                        seed(collection,cache,seeded,metadata,layout);t.control(urls[transport],'reset')
                        plan=t.digest(t.encode(dict(manifest=collection['manifest_id'],wanted=wanted,seeded=seeded,mode=mode,gap=args.gap,max_span=args.max_span)))
                        begin=time.perf_counter()
                        acquired=t.fetch(urls[transport],collection['manifest_id'],len(collection['manifest']),wanted,cache,mode,gap=args.gap,max_span=args.max_span,storage=layout)
                        acquired_end=time.perf_counter();views,access=cache_store.access(cache,collection['manifest_id'],len(collection['manifest']),wanted,layout);access_end=time.perf_counter()
                        paths,materialized=cache_store.materialize(cache,views,layout,ordinary_root);materialized_end=time.perf_counter()
                        server=t.control(urls[transport],'metrics')
                        validate(collection,cache,wanted,views,paths);checked+=len(wanted)
                        if any(acquired[field]!=server[field] for field in ('requests','response_payload_bytes','batch_framing_bytes')):raise ValueError('server counter mismatch')
                        if acquired['cache_hits']!=len(set(wanted)&set(seeded)) or acquired['published_objects']!=len(set(wanted)-set(seeded)):raise ValueError('cache reuse mismatch')
                        if access['logical_hash_bytes']!=sum(len(collection['objects'][key]) for key in wanted):raise ValueError('access verification missing')
                        if acquired['atomic_publications']!=(acquired['published_objects'] if layout=='files' else 3*int(acquired['published_objects']>0))+int(not metadata)+1:
                            raise ValueError('publication count mismatch')
                        if materialized['publications']!=(len(wanted) if layout=='packed' else 0):raise ValueError('materialization count mismatch')
                        if scenario=='cached-all' and acquired['requests']:raise ValueError('offline cached operation contacted server')
                        sample=dict(seconds=access_end-begin,acquisition_seconds=acquired_end-begin,access_seconds=access_end-acquired_end,
                            materialization_seconds=materialized_end-access_end,with_ordinary_files_seconds=materialized_end-begin,
                            acquisition=acquired,access=access,materialization=materialized,server=server,plan_sha256=plan,block=block,verified_objects=len(wanted),verified=True,
                            logical_hash_bytes=acquired['hash_bytes']+access['logical_hash_bytes']+access['metadata_hash_bytes'],
                            representation_hash_bytes=acquired['store']['representation_hash_bytes']+access['store']['representation_hash_bytes'])
                        cases[(scenario,mode,transport,layout)]['samples'].append(sample)
                        print(name,delay,scenario,mode,transport,layout,'block',block+1,f"{sample['seconds']*1000:.2f} ms; files +{sample['materialization_seconds']*1000:.2f}",flush=True)
                    for scenario in args.scenarios:
                        for mode in args.modes:
                            control=cases[(scenario,mode,'http','files')]['samples'][-1]
                            for transport in TRANSPORTS:
                                for layout in LAYOUTS:
                                    sample=cases[(scenario,mode,transport,layout)]['samples'][-1]
                                    if control['plan_sha256']!=sample['plan_sha256'] or control['logical_hash_bytes']!=sample['logical_hash_bytes'] or any(control['acquisition'][field]!=sample['acquisition'][field] for field in work_fields):
                                        raise ValueError('matched transfer/logical verification differs')
                    save()
    data['status']='complete';save()
    validation=dict(run_id=run_id,passed=True,timed_operations=sum(len(c['samples']) for c in data['cases']),independently_verified_objects=checked,
        all_logical_views_and_materialized_files_match=True,all_receipts_match=True,matched_transfer_plans_counts_and_logical_hash_work=True,
        all_server_counters_match=True,all_publication_and_materialization_counts_match=True,cached_all_zero_network=True,
        raw_sha256=t.digest((args.output/'results.json').read_bytes()))
    (args.output/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=HERE/'_work/runs/admission')
    parser.add_argument('--corpora',nargs='+',choices=('small','mixed','large'),default=['small','mixed']);parser.add_argument('--input-dir',type=Path)
    parser.add_argument('--scenarios',nargs='+',choices=SCENARIOS,default=list(SCENARIOS));parser.add_argument('--modes',nargs='+',choices=t.MODES,default=list(MODES))
    parser.add_argument('--delays',nargs='+',type=float,default=[0,2]);parser.add_argument('--trials',type=int,default=7)
    parser.add_argument('--gap',type=int,default=65536);parser.add_argument('--max-span',type=int,default=4*1024*1024);args=parser.parse_args()
    if args.trials<1 or args.gap<0 or args.max_span<1 or any(d<0 or d>1000 for d in args.delays):parser.error('invalid trial/budget/delay')
    if any(len(x)!=len(set(x)) for x in (args.corpora,args.scenarios,args.modes,args.delays)):parser.error('duplicate matrix value')
    run(args)
