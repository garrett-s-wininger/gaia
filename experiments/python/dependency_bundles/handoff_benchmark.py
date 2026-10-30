"""Compare identical CRC/header policies with fewer bytecode handoff copies."""
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


def report(data,path):
    lines=['# Mapped bytecode handoff experiment','',f"Run: `{data['run_id']}`. Status: **{data['status']}**.",'',
           'All cases use the same newly compiled Odin/C bridge, admitted dependency and stdlib '
           'archives/indexes, local immutable admission, per-read CRC, magic/flags/source-hash checks '
           'and code-type/origin checks. No payload format or interpreter modification.','',
           '* bytes: copy mapped entry to owned Python bytes, then slice off the 16-byte header.',
           '* view: same entry copy, then use a memoryview to avoid the header-slice copy.',
           '* native: CRC/header validation and CPython unmarshalling directly from the mapped range; '
           'no intermediate whole-entry/body bytes without audit hooks. With hooks, an owned audit '
           'payload preserves marshal.loads notification and rejection (the app has a hook). '
           'Code objects still allocate. The GIL stays held, '
           'no borrowed mapped view escapes, and returned code survives reader close.','',
           f"{data['trials']} randomized fresh processes per mode and workload, after correctness warmups. "
           'Warm filesystem cache; micro and application runs are separate. Compilation is outside '
           'consumer timing. Full application clock includes mount/setup; full process includes common '
           'bootstrap and identical validation.','',
           '| Workload | Handoff | Samples | Decode/ready median ms | Workload median ms | Full process median ms | Primary min–max ms |',
           '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for case in data['cases']:
        s=case['samples']
        if not s:continue
        primary='decode_seconds' if case['workload']=='decode' else 'ready_seconds'
        def median(key):return statistics.median(v[key] for v in s)*1000
        workload=f"{median('workload_seconds'):.3f}" if case['workload']=='application' else '—'
        lines.append(f"| {case['workload']} | {case['mode']} | {len(s)} | {median(primary):.3f} | {workload} | "
                     f"{median('process_wall_seconds'):.3f} | {min(v[primary] for v in s)*1000:.3f}–{max(v[primary] for v in s)*1000:.3f} |")
    lines+=['','The decode diagnostic opens both readers before its decode clock, then loads and retains '
            '578 code objects without executing modules. It replays the application’s 460 dependency '
            'executions as a first-seen ordered multiset (repeats adjacent), followed by 118 stdlib '
            'modules in manifest order. It checks structural code equality and filenames against the '
            'bytes control after closing the timed readers. Its full process includes that reference '
            'decode; only decode time isolates the handoff. It is not an import/startup substitute.','',
            'Every application checks identical dependency origins/execution sets, resources, responses, '
            'stdlib snapshot identity/origins, source inspection and zero network events. Counters must '
            'confirm all 460 dependency and 118 stdlib code loads use the selected handoff. '
            'Native extensions and unbundled modules/data keep their existing loaders. Timing spread '
            'is retained; compare within this run rather than against earlier absolute timings.','']
    if data['status']=='complete':
        cases={(c['workload'],c['mode']):c['samples'] for c in data['cases']}
        lines+=['## Interpretation','',
                '| Workload/clock | Native reduction of medians | Native faster in trial blocks |',
                '| --- | ---: | ---: |']
        for workload,key in (('decode','decode_seconds'),('application','ready_seconds'),
                             ('application','workload_seconds'),('application','process_wall_seconds')):
            baseline=cases[workload,'bytes'];native=cases[workload,'native']
            reduction=100*(1-statistics.median(s[key] for s in native)/statistics.median(s[key] for s in baseline))
            wins=sum(b[key]<a[key] for a,b in zip(baseline,native))
            lines.append(f'| {workload}/{key} | {reduction:.2f}% | {wins}/{len(baseline)} |')
        lines+=['','Small differences with broad ranges and inconsistent block wins do not establish '
                'a stable startup improvement. The memoryview-only variant has worse medians here. '
                'The native variant remains opt-in; bytes stays the default. Native fusion changes '
                'both intermediate copying and Python header-validation overhead, so even a stable '
                'gain would not measure copying alone. The application audit hook also retains one '
                'owned payload copy inside CPython. No syscall reduction or bytecode-format change '
                'is expected from this handoff test.','']
    path.write_text('\n'.join(lines))


def run(args):
    parent=json.loads(args.inputs.read_text());original=next(c for c in parent['cases'] if c['variant']=='odin')
    expected=original['samples'][0];command=original['command'][:]
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    work=benchmark.HERE/'_work'/('handoff-'+run_id);work.mkdir(parents=True)
    args.output.mkdir(parents=True,exist_ok=True)
    library,build=compile_extension(work,args.odin)
    command[command.index('--library')+1]=str(library)
    def value(flag):return command[command.index(flag)+1]
    snapshot=json.loads(Path(value('--stdlib-bundle')).read_text())
    from stdlib_snapshot import MANIFEST
    manifest=json.loads((Path(snapshot['directory'])/MANIFEST).read_text())
    plan=dict(library=str(library),inputs=[
        dict(archive=value('--root'),index=value('--index'),pin=value('--pin'),
             requests=[(name[:-3]+'.pyc',None) for name,count in expected['executed_files'].items() for _ in range(count)]),
        dict(archive=snapshot['archive'],index=snapshot['index'],pin=snapshot['index_sha256'],
             requests=[(row['code'],row['source_hash']) for row in manifest['modules'].values()])])
    plan_path=work/'decode-plan.json';benchmark.write_json(plan_path,plan)
    data=dict(run_id=run_id,parent_run=parent['run_id'],status='running',trials=args.trials,
              environment=benchmark.environment(work),build=build,plan=str(plan_path),cases=[])
    sources=('handoff_worker.py','native_loader.py','persistent_zip_loader.py','stdlib_snapshot.py','django_worker.py',
             'native/python_shim.c','native/python_api.odin')
    data['implementation_sha256']={name:hashlib.sha256((benchmark.HERE/name).read_bytes()).hexdigest() for name in sources}
    for workload in ('decode','application'):
        for mode in ('bytes','view','native'):
            cmd=([sys.executable,'-I','-S','-B',str(benchmark.HERE/'handoff_worker.py'),'--plan',str(plan_path),'--mode',mode]
                 if workload=='decode' else command+['--bytecode-handoff',mode])
            data['cases'].append(dict(workload=workload,mode=mode,command=cmd,samples=[]))
    def consume(case):
        try:sample=benchmark.consume(case['command'])
        except subprocess.CalledProcessError as error:raise RuntimeError(error.stdout+error.stderr) from error
        if not sample['correct']:raise ValueError('incorrect consumer')
        if case['workload']=='application':
            for key in ('module_origins','executed_files','api_result','resource_hashes','app_count',
                        'stdlib_stats','stdlib_origins','source_inspection'):
                if sample[key]!=expected[key]:raise ValueError('application differs: '+key)
            if sample['code_handoff_counts']!={'dependencies':460,'stdlib':118}:raise ValueError('code handoff bypass')
            if sample['network_events']:raise ValueError('network attempted')
        elif sample['code_count']!=578:raise ValueError('decode count differs')
        return sample
    for case in data['cases']:
        case['warmup']=consume(case);print('verified',case['workload'],case['mode'],flush=True)
    def checkpoint():
        benchmark.write_json(args.output/'results.json',data);report(data,args.output/'REPORT.md')
    checkpoint();rng=random.Random(20261101)
    for trial in range(args.trials):
        cases=data['cases'].copy();rng.shuffle(cases)
        for case in cases:case['samples'].append(consume(case))
        checkpoint();print(f'handoff trials {trial+1}/{args.trials}',flush=True)
    data['status']='complete';checkpoint()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,default=benchmark.HERE/'_work/runs/stdlib/results.json')
    parser.add_argument('--output',type=Path,default=benchmark.HERE/'_work/runs/handoff')
    parser.add_argument('--trials',type=int,default=15)
    parser.add_argument('--odin',default=shutil.which(os.environ.get("ODIN", "odin")) or os.environ.get("ODIN", "odin"))
    args=parser.parse_args()
    if args.trials<1:parser.error('positive trials required')
    run(args)
