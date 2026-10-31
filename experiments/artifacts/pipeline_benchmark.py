"""First bounded one-connection/request-list proof; complete consumer costs."""
import argparse
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

import admission_benchmark as admission
import benchmark as baseline
import cache_store
import pipeline_transport as p
import transfer as t

HERE=Path(__file__).resolve().parent
PATHS={'serial':'objects-serial','windowed':'objects-windowed','batch-buffered':'selected-batch','batch-streamed':'stream-batch'}
PROFILES=('pinned-established-all','pinned-established-partial','pinned-fresh-all','cold-index','offline')


def summarize(data):
    rows=[]
    for corpus in data['corpora']:
        for delay in data['delays']:
            for profile in data['profiles']:
                for layout in data['layouts']:
                    cases={c['path']:c['samples'] for c in data['cases'] if c['corpus']==corpus and c['delay_ms']==delay and c['profile']==profile and c['layout']==layout}
                    if not cases or any(not ss for ss in cases.values()):continue
                    row=dict(corpus=corpus,delay_ms=delay,profile=profile,layout=layout,paths={},paired={})
                    for path,ss in cases.items():
                        med=lambda f:statistics.median(f(s) for s in ss)
                        first=[s['first_new_verified_seconds']*1000 for s in ss if s['first_new_verified_seconds'] is not None]
                        row['paths'][path]=dict(median_ms=med(lambda s:s['seconds']*1000),first_new_verified_ms=statistics.median(first) if first else None,
                            median_materialization_ms=med(lambda s:s['materialization_seconds']*1000),with_ordinary_files_ms=med(lambda s:s['with_ordinary_files_seconds']*1000),
                            requests=med(lambda s:s['acquisition']['requests']),connections=med(lambda s:s['acquisition']['connections']),
                            manifest_requests=med(lambda s:s['server']['manifest_requests']),payload_bytes=med(lambda s:s['acquisition']['transfer_bytes']),
                            response_framing_bytes=med(lambda s:s['server']['response_framing_bytes']),request_wire_bytes=med(lambda s:s['server']['request_frame_bytes']),
                            peak_pending=med(lambda s:s['peak_pending']),reordered_completions=med(lambda s:s['reordered_completions']),
                            median_access_ms=med(lambda s:s['access_seconds']*1000),atomic_publications=med(lambda s:s['acquisition']['atomic_publications']))
                    for path in cases:
                        if path=='batch-buffered' or 'batch-buffered' not in cases:continue
                        diff=[(a['seconds']-b['seconds'])*1000 for a,b in zip(cases[path],cases['batch-buffered'])]
                        row['paired'][path]=dict(median_delta_ms=statistics.median(diff),wins=sum(x<0 for x in diff),blocks=len(diff))
                    rows.append(row)
    return dict(run_id=data['run_id'],status=data['status'],trials=data['trials'],rows=rows,connection_setup=data['connection_setup'],source_sha256=data['source_sha256'])


def report(data,path):
    lines=['# One-connection windowing and missing-list streaming','',f"Run `{data['run_id']}`; {data['status']}; {data['trials']} blocks.",'',
      'All paths retain selected SHA-256 identities, verified cache admission, a fresh logical consumer reopen and separately timed file materialization. The readiness delay is independently scheduled once per request on eight server workers. Stream records do not each sleep. This is an application-readiness model, not a WAN RTT or bandwidth simulation.','',
      '| Corpus / profile / layout / readiness delay | Serial | Windowed | Buffered list | Streamed list |','| --- | ---: | ---: | ---: | ---: |']
    for row in summarize(data)['rows']:
        lines.append('| '+row['corpus']+' / '+row['profile']+' / '+row['layout']+' / '+str(row['delay_ms'])+' ms | '+' | '.join(f"{row['paths'][path]['median_ms']:.2f} ms" for path in PATHS if path in row['paths'])+' |')
    lines+=['','[Summary](summary.json) retains first-new-verified readiness, complete/materalized endpoints, counters and paired values. [Validation](validation.json) binds ignored raw evidence.','']
    path.write_text('\n'.join(lines))


def run(args):
    args.output.mkdir(parents=True,exist_ok=True)
    if (args.output/'results.json').exists():raise ValueError('fresh output required')
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');work=HERE/'_work'/('pipeline-'+run_id);work.mkdir(parents=True)
    sources=work/'sources';sources.mkdir();pins={}
    for file in HERE.glob('*.py'):shutil.copy2(file,sources/file.name);pins[file.name]=t.digest(file.read_bytes())
    data=dict(run_id=run_id,status='running',trials=args.trials,profiles=args.profiles,layouts=['files','packed'],paths=args.paths,delays=args.delays,
              corpora={},connection_setup=[],source_sha256=pins,source_snapshots=str(sources),cases=[],
              environment=dict(python=sys.version,platform=platform.platform(),cpu_count=os.cpu_count()))
    def save():
        (args.output/'results.json').write_bytes(t.encode(data));(args.output/'summary.json').write_text(json.dumps(summarize(data),indent=2)+'\n');report(data,args.output/'REPORT.md')
    rng=random.Random(82703);checked=0
    for corpus in args.corpora:
        collection=t.build_collection(baseline.synthetic(corpus));data['corpora'][corpus]=dict(objects=len(collection['objects']),payload_bytes=len(collection['pack']),manifest_sha256=collection['manifest_id'])
        for delay in args.delays:
            cases={(profile,layout,path):dict(corpus=corpus,delay_ms=delay,profile=profile,layout=layout,path=path,samples=[])
                   for profile in args.profiles for layout in data['layouts'] for path in args.paths};data['cases']+=list(cases.values())
            with p.local_server(collection,delay_ms=delay) as url:
                clients={}
                try:
                    for layout in data['layouts']:
                        for path in args.paths:
                            client=p.Client(url);begin=time.perf_counter();client.connect();connected=time.perf_counter()
                            client.get('/control/metrics',t.MAX_MANIFEST);primed=time.perf_counter();client.reset_counts();clients[(layout,path)]=client
                            data['connection_setup'].append(dict(corpus=corpus,delay_ms=delay,layout=layout,path=path,connect_seconds=connected-begin,prime_seconds=primed-connected))
                    for block in range(args.trials):
                        order=list(cases);rng.shuffle(order)
                        for profile,layout,path in order:
                            scenario='cached-90' if profile.endswith('partial') else 'cached-all' if profile=='offline' else 'cold-all'
                            wanted,seeded,_=baseline.scenario(collection,scenario);metadata=profile!='cold-index';cache=work/'cache';ordinary=work/'ordinary'
                            for directory in (cache,ordinary):
                                if directory.exists():shutil.rmtree(directory)
                            admission.seed(collection,cache,seeded,metadata,layout);t.control(url,'reset')
                            client=clients[(layout,path)] if profile.startswith('pinned-established') else None
                            if client is not None:client.reset_counts()
                            target='gaia-mux://127.0.0.1:1' if profile=='offline' else url
                            begin=time.perf_counter();acquired=t.fetch(target,collection['manifest_id'],len(collection['manifest']),wanted,cache,PATHS[path],storage=layout,client=client)
                            acquired_end=time.perf_counter();views,access=cache_store.access(cache,collection['manifest_id'],len(collection['manifest']),wanted,layout);access_end=time.perf_counter()
                            files,material=cache_store.materialize(cache,views,layout,ordinary);material_end=time.perf_counter();server=t.control(url,'metrics')
                            admission.validate(collection,cache,wanted,views,files);checked+=len(wanted)
                            if acquired['requests']!=server['requests'] or acquired['response_payload_bytes']!=server['response_payload_bytes']:raise ValueError('server counts differ')
                            missing=len(set(wanted)-set(seeded));expected=(missing if path in ('serial','windowed') else int(missing>0))+int(not metadata)
                            if acquired['requests']!=expected or server['manifest_requests']!=int(not metadata):raise ValueError('operation/discovery count')
                            sample=dict(seconds=access_end-begin,acquisition=acquired,access_seconds=access_end-acquired_end,
                                materialization_seconds=material_end-access_end,with_ordinary_files_seconds=material_end-begin,
                                first_new_verified_seconds=acquired['first_new_verified_seconds'],server=server,block=block,
                                logical_hash_bytes=acquired['hash_bytes']+access['logical_hash_bytes']+access['metadata_hash_bytes'],
                                peak_pending=client.peak_pending if client else None,reordered_completions=client.reordered_completions if client else None)
                            # Fresh-owned clients are closed inside fetch; only persistent clients expose their window counters here.
                            if client is None:sample['peak_pending']=0;sample['reordered_completions']=0
                            if acquired['transfer_bytes']!=sum(len(collection['objects'][key]) for key in set(wanted)-set(seeded)):raise ValueError('unexpected overfetch')
                            cases[(profile,layout,path)]['samples'].append(sample)
                            print(corpus,delay,profile,layout,path,'block',block+1,f"{sample['seconds']*1000:.2f} ms",flush=True)
                        for profile in args.profiles:
                            reference=cases[(profile,'files',args.paths[0])]['samples'][-1]
                            for layout in data['layouts']:
                                for path in args.paths:
                                    sample=cases[(profile,layout,path)]['samples'][-1]
                                    if sample['logical_hash_bytes']!=reference['logical_hash_bytes'] or sample['acquisition']['transfer_bytes']!=reference['acquisition']['transfer_bytes'] or sample['acquisition']['published_objects']!=reference['acquisition']['published_objects']:
                                        raise ValueError('logical work mismatch')
                        save()
                finally:
                    for client in clients.values():client.close()
    data['status']='complete';save()
    validation=dict(run_id=run_id,passed=True,timed_operations=sum(len(c['samples']) for c in data['cases']),independently_verified_objects=checked,
        all_views_files_and_receipts_match=True,all_server_counts_and_discovery_counts_match=True,all_selected_bytes_logical_hashes_and_publications_match=True,
        raw_sha256=t.digest((args.output/'results.json').read_bytes()))
    (args.output/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=HERE/'_work/runs/pipeline')
    parser.add_argument('--corpora',nargs='+',choices=('small','mixed'),default=['mixed']);parser.add_argument('--delays',nargs='+',type=float,default=[0,2])
    parser.add_argument('--profiles',nargs='+',choices=PROFILES,default=list(PROFILES[:3]));parser.add_argument('--paths',nargs='+',choices=PATHS,default=list(PATHS))
    parser.add_argument('--trials',type=int,default=3);args=parser.parse_args()
    if args.trials<1 or any(d<0 or d>1000 for d in args.delays):parser.error('invalid trial/delay')
    run(args)
