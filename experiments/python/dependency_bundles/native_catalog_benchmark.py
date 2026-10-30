"""Matched native arena catalog, reconstructed catalog and Python-table comparison."""
import os
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import random
import shutil
import statistics
import subprocess
import sys

import benchmark
from native_benchmark import compile_extension


def render(data,path):
    lines=['# Native bounded catalog experiment','',f"Run: `{data['run_id']}`. Status: **{data['status']}**.",'',
           'Reuses the exact admitted archive/index and precomputed-table inputs from the prior catalog '
           'run. Every case uses the same freshly compiled bridge and bytes+slice handoff. Django changes '
           'only its dependency catalog; its stdlib reader stays reconstructed. Warm filesystem cache, '
           f"{data['trials']} randomized fresh processes per case after correctness warmups.",'',
           '* rebuilt: export catalog and construct Python entry/module/package/child tables.',
           '* tables: read/hash/unmarshal pinned precomputed Python tables.',
           '* native: validate the existing binary index, retain mapped string views, and build native '
           'file/module/directory hash slots plus child links in one fixed-capacity mmap arena. '
           'Python uses lazy lookup/enumeration adapters; no full catalog export or deserialization.','',
           f"Arena capacity is **{data['budget_bytes']/1048576:.2f} MiB** per native mount. Mandatory "
           'tables must fit; exhaustion returns MemoryError without increasing capacity or changing '
           'repository data. Metadata allocation does not grow during lookups. Used bytes and fixed '
           'handle size are reported separately. Mapping page rounding, mapped input pages, temporary '
           'path/hash/OpenSSL work, the CPython shim and all Python allocations are outside the arena '
           'budget. This is a metadata-allocation bound, not a total process/RSS bound.','',
           '| Workload | Catalog | Setup median ms | Ready/workload median ms | Process median ms | Peak RSS MiB | Arena used MiB |',
           '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for case in data['cases']:
        samples=case['samples']
        if not samples:continue
        def med(key):return statistics.median(s[key] for s in samples)*1000
        key='ready_seconds' if case['workload']=='django' else 'workload_seconds'
        setup='—' if case['workload']=='django' else f"{med('setup_seconds'):.3f}"
        stats=samples[0]['catalog_stats'].get('native',{}) if case['workload']=='django' else samples[0]['native_catalog_stats']
        used=f"{stats['arena_used']/1048576:.3f}" if 'arena_used' in stats else '—'
        rss=statistics.median(s['peak_rss_bytes'] for s in samples)/1048576
        lines.append(f"| {case['workload']} | {case['mode']} | {setup} | {med(key):.3f} | {med('process_wall_seconds'):.3f} | {rss:.2f} | {used} |")
    lines+=['','Scaling cases still import the first 32 leaves plus initializer from the same expanding '
            'flat package. Native names/lookup-query counters are captured before scaling validation; '
            'large catalogs must not yield more Python names simply because more unused leaves exist. '
            'Resource/miss/discovery boundary validation happens after the workload, using membership '
            'instead of materializing every child. Full process/RSS include that validation. Actual '
            'enumeration emits Python objects for the requested children; importing a module does not '
            'enumerate its siblings. Native directory enumeration filters native views before decoding '
            'matching child names.','',
            'Index pin, format, range/UTF-8/duplicate-directory checks, archive identity/full-hash policy '
            'and per-read CRC remain. The native path additionally rejects duplicate canonical modules. '
            'Names stay views of the mapped index; all variable-size persistent native metadata is in '
            'the arena. Close releases the arena/index/archive, deferred while a native bytecode decode '
            'is active. Returned Python strings, bytes and code own their data.','',
            '| Workload | Mode | Native-open median ms | Catalog/adapters median ms | Primary min–max ms |',
            '| --- | --- | ---: | ---: | ---: |']
    for case in data['cases']:
        s=case['samples']
        if not s:continue
        key='ready_seconds' if case['workload']=='django' else 'setup_seconds'
        a=statistics.median(v['native_timings']['native_open_seconds'] for v in s)*1000
        b=statistics.median(v['native_timings']['catalog_seconds'] for v in s)*1000
        lines.append(f"| {case['workload']} | {case['mode']} | {a:.3f} | {b:.3f} | {min(v[key] for v in s)*1000:.3f}–{max(v[key] for v in s)*1000:.3f} |")
    if data['status']=='complete':
        lines+=['','| Workload | Native reduction vs rebuilt (setup/ready) | Native faster in blocks |', '| --- | ---: | ---: |']
        for w in dict.fromkeys(c['workload'] for c in data['cases']):
            c={a['mode']:a['samples'] for a in data['cases'] if a['workload']==w}
            key='ready_seconds' if w=='django' else 'setup_seconds'
            gain=100*(1-statistics.median(s[key] for s in c['native'])/statistics.median(s[key] for s in c['rebuilt']))
            wins=sum(n[key]<b[key] for b,n in zip(c['rebuilt'],c['native']))
            lines.append(f'| {w} | {gain:.2f}% | {wins}/{len(c["rebuilt"])} |')
    lines+=['','Native open still hashes and scans the entire index and builds bounded native hash/child '
            'tables: total setup is still linear in catalog size. Python metadata materialization '
            'follows requested lookups/enumerations. This prototype uses regular pure-Python packages; '
            'native extensions/unbundled fallbacks keep their prior paths. Rebuilt remains the default. '
            'Original artifact conversion costs/storage are retained in the parent catalog report; '
            'native mode needs no additional derived artifact. Compilation is outside consumer timing.','']
    path.write_text('\n'.join(lines))


def run(args):
    parent=json.loads(args.inputs.read_text())
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    work=benchmark.HERE/'_work'/('native-catalog-'+run_id);work.mkdir(parents=True)
    args.output.mkdir(parents=True,exist_ok=True)
    library,build=compile_extension(work,args.odin)
    data=dict(run_id=run_id,parent_run=parent['run_id'],status='running',trials=args.trials,
              budget_bytes=args.budget,environment=benchmark.environment(work),build=build,inputs=parent['inputs'],cases=[])
    references={}
    for original in parent['cases']:
        w=original['workload']
        if original['mode']!='rebuilt' or (args.workloads and w not in args.workloads):continue
        references[w]=original['samples'][0]
        for mode in ('rebuilt','tables','native'):
            source=next(c for c in parent['cases'] if c['workload']==w and c['mode']==('tables' if mode=='tables' else 'rebuilt'))
            cmd=source['command'][:]
            if w=='django':
                cmd[cmd.index('--library')+1]=str(library);cmd[cmd.index('--catalog-mode')+1]=mode
                cmd+=['--catalog-budget',str(args.budget)]
            else:
                cmd[cmd.index('--mode')+1]=mode;cmd+=['--library',str(library),'--budget',str(args.budget)]
            data['cases'].append(dict(workload=w,mode=mode,command=cmd,samples=[]))
    paths=('native_loader.py','native_catalog.py','precomputed_catalog.py','persistent_zip_loader.py','indexed_path_loader.py',
           'bundle_access.py','catalog_worker.py','django_worker.py','native/main.odin','native/python_api.odin',
           'native/live_catalog.odin','native/python_shim.c')
    data['implementation_sha256']={p:hashlib.sha256((benchmark.HERE/p).read_bytes()).hexdigest() for p in paths}
    def consume(case):
        try:s=benchmark.consume(case['command'])
        except subprocess.CalledProcessError as error:raise RuntimeError(error.stdout+error.stderr) from error
        if not s['correct']:raise ValueError('incorrect consumer')
        w,mode=case['workload'],case['mode'];expected=references[w]
        if w=='django':
            for key in ('module_origins','executed_files','api_result','resource_hashes','app_count','stdlib_stats','stdlib_origins','source_inspection'):
                if s[key]!=expected[key]:raise ValueError('application differs: '+key)
            if s['code_handoff_counts']!={'dependencies':460,'stdlib':118} or s['network_events']:raise ValueError('handoff/network differs')
            stats=s['catalog_stats'];native=stats.get('native',{})
            if stats['mode']!=mode:raise ValueError('catalog mode bypass')
            wrappers=stats['entry_wrappers']
        else:
            if s['imported']!=33 or s['modules']!=int(w):raise ValueError('fixed import count differs')
            native=s['native_catalog_stats'];wrappers=s['entry_wrappers']
            if mode=='native' and (native['names_returned']>200 or native['module_queries']>300):raise ValueError('native catalog materialized unused modules')
        if mode in ('tables','native') and wrappers:raise ValueError('entry wrappers materialized')
        if mode=='native' and not (native['arena_used']<=native['arena_capacity']==args.budget):raise ValueError('arena bound differs')
        return s
    for case in data['cases']:
        case['warmup']=consume(case);print('verified',case['workload'],case['mode'],flush=True)
    def checkpoint():
        for c in data['cases']:
            if c['samples']:c['summary']=benchmark.summarize(c['samples'])
        benchmark.write_json(args.output/'results.json',data);render(data,args.output/'REPORT.md')
    checkpoint();rng=random.Random(20261103)
    for trial in range(args.trials):
        cases=data['cases'].copy();rng.shuffle(cases)
        for c in cases:c['samples'].append(consume(c))
        checkpoint();print(f'native catalog trials {trial+1}/{args.trials}',flush=True)
    data['status']='complete';checkpoint()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,default=benchmark.HERE/'_work/runs/catalog/results.json')
    parser.add_argument('--output',type=Path,default=benchmark.HERE/'_work/runs/native-catalog')
    parser.add_argument('--trials',type=int,default=15)
    parser.add_argument('--budget',type=int,default=16*1048576)
    parser.add_argument('--workloads',nargs='+')
    parser.add_argument('--odin',default=shutil.which(os.environ.get("ODIN", "odin")) or os.environ.get("ODIN", "odin"))
    args=parser.parse_args()
    if args.trials<1 or args.budget<1:parser.error('positive trials/budget required')
    run(args)
