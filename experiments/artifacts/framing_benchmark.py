"""Compare matched HTTP and binary envelopes separately from batching plans."""
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
import transfer as t

HERE=Path(__file__).resolve().parent
TRANSPORTS=('http','binary','binary-buffered')
MODES=t.MODES
SCENARIOS=baseline.SCENARIOS


def summarize(data):
    rows=[]
    for corpus in data['corpora']:
        for delay in data['delays']:
            for scenario in data['scenarios']:
                cases={(c['transport'],c['mode']):c['samples'] for c in data['cases']
                       if c['corpus']==corpus and c['delay_ms']==delay and c['scenario']==scenario}
                if not cases or any(not ss for ss in cases.values()):continue
                row=dict(corpus=corpus,delay_ms=delay,scenario=scenario,variants={},matched_binary_paired={},buffered_paired={})
                for (transport,mode),ss in cases.items():
                    med=lambda f:statistics.median(f(s) for s in ss)
                    row['variants'][transport+'/'+mode]=dict(median_ms=med(lambda s:s['seconds']*1000),
                        min_ms=min(s['seconds']*1000 for s in ss),max_ms=max(s['seconds']*1000 for s in ss),
                        requests=med(lambda s:s['requests']),transfer_bytes=med(lambda s:s['transfer_bytes']),
                        manifest_bytes=med(lambda s:s['manifest_bytes']),overfetch_bytes=med(lambda s:s['overfetch_bytes']),
                        batch_framing_bytes=med(lambda s:s['batch_framing_bytes']),
                        request_frame_bytes=med(lambda s:s['server']['request_frame_bytes']),
                        response_framing_bytes=med(lambda s:s['server']['response_framing_bytes']),
                        response_payload_bytes=med(lambda s:s['response_payload_bytes']),
                        application_wire_bytes=med(lambda s:s['server']['request_frame_bytes']+s['server']['response_framing_bytes']+s['response_payload_bytes']),
                        median_metadata_ms=med(lambda s:s['metadata_seconds']*1000),
                        median_cache_validation_ms=med(lambda s:s['cache_validation_seconds']*1000),
                        median_payload_verify_publish_ms=med(lambda s:s['payload_verify_publish_seconds']*1000),
                        median_receipt_ms=med(lambda s:s['receipt_seconds']*1000),
                        hash_bytes=med(lambda s:s['hash_bytes']))
                for mode in data['modes']:
                    if ('http',mode) not in cases or ('binary',mode) not in cases:continue
                    deltas=[(a['seconds']-b['seconds'])*1000 for a,b in zip(cases[('binary',mode)],cases[('http',mode)])]
                    row['matched_binary_paired'][mode]=dict(median_delta_ms=statistics.median(deltas),wins=sum(d<0 for d in deltas),blocks=len(deltas))
                for mode in data['modes']:
                    if ('binary-buffered',mode) not in cases:continue
                    row['buffered_paired'][mode]={}
                    for control in ('http','binary'):
                        if (control,mode) not in cases:continue
                        deltas=[(a['seconds']-b['seconds'])*1000 for a,b in zip(cases[('binary-buffered',mode)],cases[(control,mode)])]
                        row['buffered_paired'][mode][control]=dict(median_delta_ms=statistics.median(deltas),wins=sum(d<0 for d in deltas),blocks=len(deltas))
                rows.append(row)
    return dict(run_id=data['run_id'],status=data['status'],trials=data['trials'],corpora=data['corpora'],rows=rows,
                source_sha256=data['source_sha256'])


def report(data,path):
    summary=summarize(data);transports=data['transports']
    lines=['# Matched artifact transport implementations','',
        f"Run `{data['run_id']}`; {data['status']}; {data['trials']} randomized blocks per case.",'',
        'All variants retain the trusted JSON manifest, object digests, selected sets, cache seeds, planning, hashing, atomic publication and receipt. The buffered binary variant uses the same versioned frames and wire lengths as the original. No planning or integrity work moves outside the clock.','',
        'Complete fetch timing includes connection setup/closure, metadata acquisition/local verification, cached-content verification, transfer, requested-blob verification and publication. Process/server startup, initial source admission, fixture/cache preparation and parent validation are excluded. Injected response delay is an application sleep, not a WAN/TLS/loss/HTTP2 model.','']
    for corpus in data['corpora']:
        for delay in data['delays']:
            lines += [f'## {corpus}; injected response delay {delay:g} ms','',
                '| Scenario / mode | '+' | '.join(transport+' ms' for transport in transports)+' |',
                '| --- | '+' | '.join('---:' for _ in transports)+' |']
            for row in summary['rows']:
                if row['corpus']!=corpus or row['delay_ms']!=delay:continue
                for mode in data['modes']:
                    values=[row['variants'].get(transport+'/'+mode) for transport in transports]
                    if any(value is None for value in values):continue
                    lines.append('| '+row['scenario']+' / '+mode+' | '+' | '.join(f"{value['median_ms']:.2f}" for value in values)+' |')
            lines+=['']
    lines+=['[Summary](summary.json) retains phase clocks, counters and paired comparisons; [validation](validation.json) binds ignored raw observations.','']
    path.write_text('\n'.join(lines))


def run(args):
    args.output.mkdir(parents=True,exist_ok=True)
    if (args.output/'results.json').exists():raise ValueError('choose fresh output directory')
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    work=HERE/'_work'/('framing-'+run_id);work.mkdir(parents=True)
    collections={name:t.build_collection(baseline.synthetic(name)) for name in args.corpora}
    if args.input_dir:collections['directory']=t.build_collection(baseline.input_payloads(args.input_dir))
    snapshots=work/'sources';snapshots.mkdir();pins={}
    for p in HERE.glob('*.py'):
        shutil.copy2(p,snapshots/p.name);pins[p.name]=t.digest(p.read_bytes())
    data=dict(run_id=run_id,status='running',trials=args.trials,transports=args.transports,modes=args.modes,
        scenarios=args.scenarios,delays=args.delays,
        corpora={name:dict(objects=len(c['objects']),payload_bytes=len(c['pack']),manifest_bytes=len(c['manifest']),
                        manifest_sha256=c['manifest_id'],pack_sha256=c['pack_id']) for name,c in collections.items()},
        environment=dict(python=sys.version,platform=platform.platform(),cpu_count=os.cpu_count(),
                        affinity=sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else None),
        source_sha256=pins,source_snapshots=str(snapshots),cases=[])
    def save():
        (args.output/'results.json').write_bytes(t.encode(data))
        (args.output/'summary.json').write_text(json.dumps(summarize(data),indent=2)+'\n');report(data,args.output/'REPORT.md')
    rng=random.Random(2628017);verified=0
    matched_fields=('requests','response_payload_bytes','manifest_bytes','transfer_bytes','missing_bytes','overfetch_bytes',
                    'cache_hits','published_objects','hash_bytes','batch_framing_bytes')
    for name,collection in collections.items():
        for delay in args.delays:
            cases={(scenario,transport,mode):dict(corpus=name,delay_ms=delay,scenario=scenario,transport=transport,mode=mode,samples=[])
                   for scenario in args.scenarios for transport in args.transports for mode in args.modes}
            data['cases']+=list(cases.values())
            with ExitStack() as stack:
                urls={transport:stack.enter_context(t.local_server(collection,delay_ms=delay) if transport=='http' else
                      binary_transport.local_server(collection,delay_ms=delay,buffered=transport=='binary-buffered')) for transport in args.transports}
                for transport in args.transports:
                    for mode in args.modes:
                        cache=work/'warmup'
                        if cache.exists():shutil.rmtree(cache)
                        baseline.seed_cache(collection,cache,[],False)
                        t.fetch(urls[transport],collection['manifest_id'],len(collection['manifest']),list(collection['objects']),cache,mode,
                                workers=args.workers,gap=args.gap,max_span=args.max_span)
                        baseline.validate(collection,cache,list(collection['objects']))
                for block in range(args.trials):
                    order=list(cases);rng.shuffle(order)
                    for scenario,transport,mode in order:
                        wanted,seeded,metadata=baseline.scenario(collection,scenario);cache=work/'cache'
                        if cache.exists():shutil.rmtree(cache)
                        baseline.seed_cache(collection,cache,seeded,metadata);t.control(urls[transport],'reset')
                        plan=t.digest(t.encode(dict(manifest=collection['manifest_id'],wanted=wanted,seeded=seeded,mode=mode,
                                                    workers=args.workers,gap=args.gap,max_span=args.max_span)))
                        begin=time.perf_counter()
                        sample=t.fetch(urls[transport],collection['manifest_id'],len(collection['manifest']),wanted,cache,mode,
                                       workers=args.workers,gap=args.gap,max_span=args.max_span)
                        sample['function_seconds']=sample['seconds'];sample['seconds']=time.perf_counter()-begin
                        counts=t.control(urls[transport],'metrics')
                        if sample['requests']!=counts['requests'] or sample['response_payload_bytes']!=counts['response_payload_bytes'] or sample['batch_framing_bytes']!=counts['batch_framing_bytes']:
                            raise ValueError('independent server counters differ')
                        if sample['published_objects']!=len(set(wanted)-set(seeded)) or sample['cache_hits']!=len(set(wanted)&set(seeded)):
                            raise ValueError('reuse/publication count')
                        if scenario=='cached-all' and sample['requests']:raise ValueError('offline request contacted server')
                        baseline.validate(collection,cache,wanted);verified+=len(wanted)
                        sample.update(block=block,plan_sha256=plan,verified=True,verified_objects=len(wanted),server=counts)
                        cases[(scenario,transport,mode)]['samples'].append(sample)
                        print(name,delay,scenario,transport,mode,'block',block+1,f"{sample['seconds']*1000:.2f} ms",flush=True)
                    for scenario in args.scenarios:
                        for mode in args.modes:
                            if 'http' not in args.transports:continue
                            a=cases[(scenario,'http',mode)]['samples'][-1]
                            for transport in args.transports:
                                if transport=='http':continue
                                b=cases[(scenario,transport,mode)]['samples'][-1]
                                if a['plan_sha256']!=b['plan_sha256'] or any(a[field]!=b[field] for field in matched_fields):
                                    raise ValueError('matched transport plan/work differs: '+scenario+' '+mode+' '+transport)
                            if 'binary' in args.transports and 'binary-buffered' in args.transports:
                                a=cases[(scenario,'binary',mode)]['samples'][-1]['server'];b=cases[(scenario,'binary-buffered',mode)]['samples'][-1]['server']
                                if any(a[field]!=b[field] for field in ('request_frame_bytes','response_framing_bytes')):
                                    raise ValueError('binary implementations changed wire lengths')
                    save()
    data['status']='complete';save()
    validation=dict(run_id=run_id,passed=True,timed_fetches=sum(len(c['samples']) for c in data['cases']),
        independently_verified_objects=verified,all_receipts_and_payloads_match=True,all_client_server_counts_match=True,
        matched_transport_requests_payloads_hash_work_and_publication_identical=True,cached_all_zero_network=True,
        raw_sha256=t.digest((args.output/'results.json').read_bytes()),workers=args.workers,
        coalescing_gap_bytes=args.gap,max_span_bytes=args.max_span)
    (args.output/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=HERE/'_work/runs/framing')
    parser.add_argument('--corpora',nargs='+',choices=('small','mixed','large'),default=['small','mixed'])
    parser.add_argument('--input-dir',type=Path)
    parser.add_argument('--transports',nargs='+',choices=TRANSPORTS,default=['http','binary'])
    parser.add_argument('--modes',nargs='+',choices=MODES,default=list(MODES))
    parser.add_argument('--scenarios',nargs='+',choices=SCENARIOS,default=list(SCENARIOS))
    parser.add_argument('--trials',type=int,default=7);parser.add_argument('--delays',nargs='+',type=float,default=[0,2])
    parser.add_argument('--workers',type=int,default=8);parser.add_argument('--gap',type=int,default=65536)
    parser.add_argument('--max-span',type=int,default=4*1024*1024);args=parser.parse_args()
    if args.trials<1 or not 1<=args.workers<=32 or args.gap<0 or args.max_span<1 or any(d<0 or d>1000 for d in args.delays):parser.error('invalid budget/trial/delay')
    if any(len(x)!=len(set(x)) for x in [args.corpora,args.transports,args.modes,args.scenarios,args.delays]):parser.error('duplicate matrix value')
    run(args)
