"""Producer-built directly mapped native tables, with integrity timing kept visible."""
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
from mapped_catalog import build_mapped_catalog
from native_benchmark import compile_extension


def render(data,path):
    lines=['# Directly mapped lookup catalog experiment','',f"Run: `{data['run_id']}`. Status: **{data['status']}**.",'',
           'Same admitted archives/range indexes and newly compiled bridge across rebuilt Python catalogs, '
           'runtime-constructed native tables, and producer-built mapped native tables. Same bytes+slice '
           'bytecode handoff and reconstructed stdlib reader. Warm filesystem cache, '
           f"{data['trials']} randomized fresh processes per case after correctness warmups.",'',
           'The experimental v1 artifact has a 256-byte versioned header, original-index SHA-256 binding, '
           'offset/length directory records and aligned little-endian u64 name offsets, hash slots and '
           'child heads/counts/links. It contains no pointers, native strings or executable code. '
           'Current zero-copy integer-array views support Linux amd64; the on-disk scalars have explicit '
           'width/endianness. Module lookup semantics are certified once by the pinned producer. This '
           'local experiment is not yet an open standardized protocol.','',
           'Mapped consumers hash both index and lookup artifact, check binding/header/array bounds, '
           'validate table value domains/counts, and rescan original ranges/names for UTF-8 and '
           'offset agreement. Directory lookup binding is checked. They retain archive identity/full-hash '
           'policy and per-read payload CRC. They do not rebuild or re-prove every file/module hash '
           'placement; trusted immutable producer outputs are required, as with the earlier Python '
           'precomputed tables. Probing and child iteration are bounded against malformed inputs.','',
           '| Workload | Catalog | Setup median ms | Ready/workload median ms | Process median ms | Peak RSS MiB | Mutable arena bytes |',
           '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for c in data['cases']:
        samples=c['samples']
        if not samples:continue
        def med(k):return statistics.median(s[k] for s in samples)*1000
        key='ready_seconds' if c['workload']=='django' else 'workload_seconds'
        setup='—' if c['workload']=='django' else f"{med('setup_seconds'):.3f}"
        stats=samples[0]['catalog_stats'].get('native',{}) if c['workload']=='django' else samples[0]['native_catalog_stats']
        used=stats.get('arena_used','—');rss=statistics.median(s['peak_rss_bytes'] for s in samples)/1048576
        lines.append(f"| {c['workload']} | {c['mode']} | {setup} | {med(key):.3f} | {med('process_wall_seconds'):.3f} | {rss:.2f} | {used} |")
    lines+=['','Each scaling case imports the same 32 leaves plus initializer, independent of the '
            'available module count. Miss/resource/discovery checks follow the timed workload, using '
            'membership instead of materializing all children. Python lookup/name counters must stay '
            'small. Full process/RSS include common harness initialization, validation and exit. '
            'Django retains all application/output/origin/source-inspection/no-network checks.','',
            '| Workload | Catalog | Integrity median ms | Structure/setup median ms | Table construction median ms | Native open median ms |',
            '| --- | --- | ---: | ---: | ---: | ---: |']
    for c in data['cases']:
        s=c['samples']
        if not s or c['mode']=='rebuilt':continue
        def phases(v):return (v['catalog_stats']['native'] if c['workload']=='django' else v['native_catalog_stats'])['open_phases']
        values=[statistics.median(phases(v)[k] for v in s)*1000 for k in ('integrity_seconds','validation_seconds','construction_seconds')]
        opened=statistics.median(v['native_timings']['native_open_seconds'] for v in s)*1000
        lines.append(f"| {c['workload']} | {c['mode']} | "+' | '.join(f'{v:.3f}' for v in values)+f' | {opened:.3f} |')
    lines+=['','Integrity includes SHA-256 of the original index, additionally the lookup artifact for '
            'mapped mode, and archive identity/full-hash policy checks. Structure/setup includes '
            'format/range/UTF-8/table checks and directory-view setup; native mode also builds its '
            'directory hash in that phase. Construction covers native file/module/child table building '
            'and archive mapping; mapped mode performs no reconstruction. Native-open includes '
            'remaining mapping/glue. Independent medians do not add. All phases remain inside startup '
            'timing; no trust checks are timed away.','',
            '| Input | Lookup bytes | Production/certification ms |', '| --- | ---: | ---: |']
    for row in data['inputs']:
        m=row['mapped'];lines.append(f"| {row['label']} | {m['bytes']} | {m['producer_seconds']*1000:.3f} |")
    if data['status']=='complete':
        lines+=['','| Workload | Mapped vs native reduction (setup/ready) | Mapped faster in blocks | Primary mapped min–max ms |',
                '| --- | ---: | ---: | ---: |']
        for w in dict.fromkeys(c['workload'] for c in data['cases']):
            c={v['mode']:v['samples'] for v in data['cases'] if v['workload']==w};key='ready_seconds' if w=='django' else 'setup_seconds'
            reduction=100*(1-statistics.median(v[key] for v in c['mapped'])/statistics.median(v[key] for v in c['native']))
            wins=sum(m[key]<n[key] for m,n in zip(c['mapped'],c['native']))
            lines.append(f"| {w} | {reduction:.2f}% | {wins}/{len(c['native'])} | {min(s[key] for s in c['mapped'])*1000:.3f}–{max(s[key] for s in c['mapped'])*1000:.3f} |")
    lines+=['','The producer constructs the existing bounded native catalog, exhaustively checks every '
            'file-to-ordinal, module-to-member and directory binding against the admitted index, and '
            'writes its pointer-free tables with an external SHA pin. Production/storage are outside '
            'consumer timings and are not free. The consumer still scans and hashes inputs, so mount '
            'remains linear even though table reconstruction is removed. Mutable metadata stays within '
            f"the {data['budget']/1048576:.2f} MiB logical arena budget; read-only mapped lookup/index/archive "
            'pages and fixed handles are accounted through process RSS separately. Mapped file pages '
            'remain subject to OS paging. Close owns all three input mappings and defers release while '
            'native decoding is active. Rebuilt remains the default.','']
    path.write_text('\n'.join(lines))


def setarg(command,flag,value):
    if flag in command:command[command.index(flag)+1]=str(value)
    else:command.extend([flag,str(value)])


def run(args):
    parent=json.loads(args.inputs.read_text());run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    work=benchmark.HERE/'_work'/('mapped-catalog-'+run_id);work.mkdir(parents=True);args.output.mkdir(parents=True,exist_ok=True)
    library,build=compile_extension(work,args.odin)
    data=dict(run_id=run_id,parent_run=parent['run_id'],status='running',trials=args.trials,budget=args.budget,
              environment=benchmark.environment(work),build=build,inputs=[],cases=[])
    expected={}
    for item in parent['inputs']:
        w=item['label']
        if args.workloads and w not in args.workloads:continue
        row=copy.deepcopy(item);pin=row.get('pin',row.get('index_sha256'))
        row['mapped']=build_mapped_catalog(row['archive'],row['index'],pin,work/(w+'.lookup'),library,budget=args.budget)
        data['inputs'].append(row)
        original=next(c for c in parent['cases'] if c['workload']==w and c['mode']=='rebuilt')
        expected[w]=original['samples'][0]
        base=original['command'][:]
        if w!='django':
            plan=json.loads(Path(base[base.index('--plan')+1]).read_text());plan['catalogs']['mapped']=row['mapped']
            plan_path=work/(w+'-plan.json');benchmark.write_json(plan_path,plan);setarg(base,'--plan',plan_path)
        for mode in ('rebuilt','native','mapped'):
            command=base[:];setarg(command,'--library',library)
            setarg(command,'--catalog-mode' if w=='django' else '--mode',mode)
            setarg(command,'--catalog-budget' if w=='django' else '--budget',args.budget)
            if w=='django' and mode=='mapped':
                setarg(command,'--catalog',row['mapped']['path']);setarg(command,'--catalog-pin',row['mapped']['sha256'])
            data['cases'].append(dict(workload=w,mode=mode,command=command,samples=[]))
        print('produced',w,flush=True)
    sources=('native_loader.py','native_catalog.py','persistent_zip_loader.py','indexed_path_loader.py','bundle_access.py',
             'catalog_worker.py','django_worker.py','native/main.odin','native/python_api.odin','native/live_catalog.odin',
             'native/mapped_catalog.odin','native/python_shim.c')
    data['implementation_sha256']={n:hashlib.sha256((benchmark.HERE/n).read_bytes()).hexdigest() for n in sources}
    def consume(c):
        try:s=benchmark.consume(c['command'])
        except subprocess.CalledProcessError as e:raise RuntimeError(e.stdout+e.stderr) from e
        if not s['correct']:raise ValueError('incorrect consumer')
        w,mode=c['workload'],c['mode']
        if w=='django':
            for k in ('module_origins','executed_files','api_result','resource_hashes','app_count','stdlib_stats','stdlib_origins','source_inspection'):
                if s[k]!=expected[w][k]:raise ValueError('application differs: '+k)
            if s['network_events'] or s['code_handoff_counts']!={'dependencies':460,'stdlib':118}:raise ValueError('handoff/network differs')
            stats=s['catalog_stats'].get('native',{});wrappers=s['catalog_stats']['entry_wrappers']
            if s['catalog_stats']['mode']!=mode:raise ValueError('catalog mode bypass')
        else:
            stats=s['native_catalog_stats'];wrappers=s['entry_wrappers']
            if s['imported']!=33 or s['modules']!=int(w):raise ValueError('fixed import count differs')
            if mode!='rebuilt' and (stats['names_returned']>200 or stats['module_queries']>300):raise ValueError('Python catalog materialized')
        if mode!='rebuilt':
            if wrappers or not stats['arena_used']<=stats['arena_capacity']==args.budget:raise ValueError('catalog allocation differs')
            if mode=='mapped' and stats['open_phases']['construction_seconds']!=0:raise ValueError('mapped tables reconstructed')
        return s
    for c in data['cases']:
        c['warmup']=consume(c);print('verified',c['workload'],c['mode'],flush=True)
    def checkpoint():
        for c in data['cases']:
            if c['samples']:c['summary']=benchmark.summarize(c['samples'])
        benchmark.write_json(args.output/'results.json',data);render(data,args.output/'REPORT.md')
    checkpoint();rng=random.Random(20261104)
    for trial in range(args.trials):
        cases=data['cases'].copy();rng.shuffle(cases)
        for c in cases:c['samples'].append(consume(c))
        checkpoint();print(f'mapped catalog trials {trial+1}/{args.trials}',flush=True)
    data['status']='complete';checkpoint()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,default=benchmark.HERE/'_work/runs/native-catalog/results.json')
    parser.add_argument('--output',type=Path,default=benchmark.HERE/'_work/runs/mapped-catalog')
    parser.add_argument('--trials',type=int,default=15)
    parser.add_argument('--budget',type=int,default=16*1048576)
    parser.add_argument('--workloads',nargs='+')
    parser.add_argument('--odin',default=shutil.which(os.environ.get("ODIN", "odin")) or os.environ.get("ODIN", "odin"))
    args=parser.parse_args()
    if args.trials<1 or args.budget<1:parser.error('positive trials/budget required')
    run(args)
