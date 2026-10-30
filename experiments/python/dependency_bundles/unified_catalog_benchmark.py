"""Isolate unified-envelope and compact-reference effects against mapped v1."""
import os
import argparse
import copy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import random
import shutil
import statistics
import subprocess

import benchmark
from mapped_catalog_benchmark import setarg
from native_benchmark import compile_extension
from unified_catalog import build_unified_catalog


def render(data,path):
    lines=['# Unified and compact mapped metadata experiment','',f"Run: `{data['run_id']}`. Status: **{data['status']}**.",'',
           'Same archives and admitted range-index contents across all cases; same freshly compiled '
           'bridge, bytes+slice handoff and reconstructed stdlib reader. Warm filesystem cache, '
           f"{data['trials']} randomized fresh processes per case after correctness warmups.",'',
           '* mapped: original range index plus mapped 64-bit lookup artifact, two metadata hashes/maps.',
           '* unified: same embedded range index and sparse 64-bit tables in one authenticated envelope.',
           '* compact: unified envelope with eligible 32-bit offsets/ordinals/counts, independent file/module '
           'table sizing and a maximum 75% load factor. It falls back to the 64-bit layout if counts or '
           'embedded-index offsets do not fit. Names and payload range records are unchanged.','',
           'Experimental unified v1 has a 256-byte explicit-width/endianness header and embedded original '
           'range index, directory offset/length records, and mapped hash/child arrays. No pointers '
           'are serialized. The trusted SHA pin authenticates the entire envelope, including embedded '
           'index bytes. Its original-index SHA field is producer-certified lineage checked against '
           'the requested input; the embedded index is not separately rehashed. Thus one envelope '
           'hash replaces two independent metadata hashes without leaving embedded bytes unauthenticated. '
           'Trusted producer lookup semantics, range/UTF-8/table-domain/count checks, bounded probing '
           'and iteration, archive identity/full-hash policy and per-read CRC remain.','',
           '| Input | Mode | Metadata bytes | Producer ms |', '| --- | --- | ---: | ---: |']
    for row in data['inputs']:
        for mode,info in row['variants'].items():lines.append(f"| {row['label']} | {mode} | {info['total_metadata_bytes']} | {info.get('producer_seconds',0)*1000:.3f} |")
    lines+=['','Mapped production is inherited from the parent report; zero in this table means no '
            'new production in this run. Unified/compact production includes validation of retained '
            'inputs and transformation; the original mapped-artifact production cost remains separate. '
            'Every startup includes all metadata mapping, authentication and structural validation.','',
            '| Workload | Mode | Setup median ms | Ready/workload median ms | Process median ms | Peak RSS MiB |',
            '| --- | --- | ---: | ---: | ---: | ---: |']
    for c in data['cases']:
        s=c['samples']
        if not s:continue
        def med(k):return statistics.median(v[k] for v in s)*1000
        setup='—' if c['workload']=='django' else f"{med('setup_seconds'):.3f}"
        key='ready_seconds' if c['workload']=='django' else 'workload_seconds'
        lines.append(f"| {c['workload']} | {c['mode']} | {setup} | {med(key):.3f} | {med('process_wall_seconds'):.3f} | {statistics.median(v['peak_rss_bytes'] for v in s)/1048576:.2f} |")
    lines+=['','Scaling imports remain the same 32 leaves plus initializer. Validation happens afterward '
            'without materializing unused siblings; Python name/query counters must remain small. '
            'Full process/RSS include common harness and validation. Django preserves all application '
            'origins/executions, responses, resources, source inspection and no-network checks.','',
            '| Workload | Mode | Integrity ms | Structure/setup ms | Native open ms | Primary min–max ms |',
            '| --- | --- | ---: | ---: | ---: | ---: |']
    for c in data['cases']:
        s=c['samples']
        if not s:continue
        def stats(v):return (v['catalog_stats']['native'] if c['workload']=='django' else v['native_catalog_stats'])
        integrity=statistics.median(stats(v)['open_phases']['integrity_seconds'] for v in s)*1000
        structure=statistics.median(stats(v)['open_phases']['validation_seconds'] for v in s)*1000
        opened=statistics.median(v['native_timings']['native_open_seconds'] for v in s)*1000
        key='ready_seconds' if c['workload']=='django' else 'setup_seconds'
        lines.append(f"| {c['workload']} | {c['mode']} | {integrity:.3f} | {structure:.3f} | {opened:.3f} | {min(v[key] for v in s)*1000:.3f}–{max(v[key] for v in s)*1000:.3f} |")
    if data['status']=='complete':
        lines+=['','| Workload | Variant | Setup/ready reduction vs mapped | Faster in trial blocks |', '| --- | --- | ---: | ---: |']
        for w in dict.fromkeys(c['workload'] for c in data['cases']):
            cases={c['mode']:c['samples'] for c in data['cases'] if c['workload']==w}
            key='ready_seconds' if w=='django' else 'setup_seconds';base=cases['mapped']
            for mode in ('unified','compact'):
                s=cases[mode];gain=100*(1-statistics.median(v[key] for v in s)/statistics.median(v[key] for v in base))
                wins=sum(v[key]<b[key] for b,v in zip(base,s))
                lines.append(f'| {w} | {mode} | {gain:.2f}% | {wins}/{len(s)} |')
    lines+=['','All native tables stay mapped read-only; mutable arena data remains directory descriptors '
            'under the same logical budget. Extra file mappings/pointers are owned until close and '
            'release is deferred across native decoding. Compact tables trade denser probes and '
            '32-bit reads against fewer bytes authenticated/touched. Total setup is still linear in '
            'metadata bytes/entries. Current zero-copy views target Linux amd64. Rebuilt remains '
            'the default; this experimental format is not an open protocol standard.','']
    path.write_text('\n'.join(lines))


def run(args):
    parent=json.loads(args.inputs.read_text());run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    work=benchmark.HERE/'_work'/('unified-catalog-'+run_id);work.mkdir(parents=True);args.output.mkdir(parents=True,exist_ok=True)
    library,build=compile_extension(work,args.odin)
    data=dict(run_id=run_id,parent_run=parent['run_id'],status='running',trials=args.trials,budget=args.budget,
              environment=benchmark.environment(work),build=build,inputs=[],cases=[])
    expected={}
    for item in parent['inputs']:
        w=item['label']
        if args.workloads and w not in args.workloads:continue
        row=copy.deepcopy(item);pin=row.get('pin',row.get('index_sha256'))
        row['variants']={'mapped':dict(row['mapped'],total_metadata_bytes=Path(row['index']).stat().st_size+row['mapped']['bytes'],producer_seconds=0)}
        for mode in ('unified','compact'):
            info=build_unified_catalog(row['archive'],row['index'],pin,row['mapped'],work/(w+'.'+mode),library,compact=mode=='compact',budget=args.budget)
            info['total_metadata_bytes']=info['bytes'];row['variants'][mode]=info
        data['inputs'].append(row)
        original=next(c for c in parent['cases'] if c['workload']==w and c['mode']=='mapped');expected[w]=original['samples'][0];base=original['command'][:]
        if w!='django':
            plan=json.loads(Path(base[base.index('--plan')+1]).read_text());plan['catalogs'].update(row['variants'])
            target=work/(w+'-plan.json');benchmark.write_json(target,plan);setarg(base,'--plan',target)
        for mode in ('mapped','unified','compact'):
            command=base[:];setarg(command,'--library',library);setarg(command,'--catalog-mode' if w=='django' else '--mode',mode)
            setarg(command,'--catalog-budget' if w=='django' else '--budget',args.budget)
            if w=='django':
                setarg(command,'--catalog',row['variants'][mode]['path']);setarg(command,'--catalog-pin',row['variants'][mode]['sha256'])
            data['cases'].append(dict(workload=w,mode=mode,command=command,samples=[]))
        print('produced',w,flush=True)
    names=('native_loader.py','native_catalog.py','catalog_worker.py','django_worker.py','persistent_zip_loader.py','indexed_path_loader.py','bundle_access.py',
           'native/main.odin','native/python_api.odin','native/live_catalog.odin','native/mapped_catalog.odin','native/unified_catalog.odin','native/python_shim.c')
    data['implementation_sha256']={n:hashlib.sha256((benchmark.HERE/n).read_bytes()).hexdigest() for n in names}
    def consume(c):
        try:s=benchmark.consume(c['command'])
        except subprocess.CalledProcessError as e:raise RuntimeError(e.stdout+e.stderr) from e
        if not s['correct']:raise ValueError('incorrect consumer')
        w=c['workload']
        if w=='django':
            for k in ('module_origins','executed_files','api_result','resource_hashes','app_count','stdlib_stats','stdlib_origins','source_inspection'):
                if s[k]!=expected[w][k]:raise ValueError('application differs: '+k)
            if s['network_events'] or s['code_handoff_counts']!={'dependencies':460,'stdlib':118}:raise ValueError('handoff/network differs')
            stats=s['catalog_stats']['native'];wrappers=s['catalog_stats']['entry_wrappers']
            if s['catalog_stats']['mode']!=c['mode']:raise ValueError('mode bypass')
        else:
            stats=s['native_catalog_stats'];wrappers=s['entry_wrappers']
            if s['imported']!=33 or s['modules']!=int(w):raise ValueError('fixed import count differs')
            if stats['names_returned']>200 or stats['module_queries']>300:raise ValueError('unused names materialized')
        if wrappers or not stats['arena_used']<=stats['arena_capacity']==args.budget or stats['open_phases']['construction_seconds']:
            raise ValueError('lookup tables reconstructed/budget changed')
        return s
    for c in data['cases']:
        c['warmup']=consume(c);print('verified',c['workload'],c['mode'],flush=True)
    def checkpoint():
        for c in data['cases']:
            if c['samples']:c['summary']=benchmark.summarize(c['samples'])
        benchmark.write_json(args.output/'results.json',data);render(data,args.output/'REPORT.md')
    checkpoint();rng=random.Random(20261105)
    for trial in range(args.trials):
        cases=data['cases'].copy();rng.shuffle(cases)
        for c in cases:c['samples'].append(consume(c))
        checkpoint();print(f'unified catalog trials {trial+1}/{args.trials}',flush=True)
    data['status']='complete';checkpoint()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,default=benchmark.HERE/'_work/runs/mapped-catalog/results.json')
    parser.add_argument('--output',type=Path,default=benchmark.HERE/'_work/runs/unified-catalog')
    parser.add_argument('--trials',type=int,default=15);parser.add_argument('--budget',type=int,default=16*1048576)
    parser.add_argument('--workloads',nargs='+');parser.add_argument('--odin',default=shutil.which(os.environ.get("ODIN", "odin")) or os.environ.get("ODIN", "odin"))
    args=parser.parse_args()
    if args.trials<1 or args.budget<1:parser.error('positive trials/budget required')
    run(args)
