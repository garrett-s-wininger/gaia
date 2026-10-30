#!/usr/bin/env python3
"""Admit the observed stdlib closure, then compare fresh Django processes."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parent))
import benchmark
from build_stdlib_snapshot import build_snapshot


def render(data,path):
    lines=['# Admitted stdlib snapshot experiment','',f"Run: `{data['run_id']}`. Status: **{data['status']}**.", '',
           'Same retained Django REST bytecode/dependency bundle, indexed discovery and native reader. '
           'The host control uses the installed stdlib. Other cases load the observed 118 pure-Python '
           'stdlib modules from an admitted code/source snapshot, using known-path files, Python mmap '
           'or the existing Odin reader. Native extensions and names outside this closure keep normal '
           'host loaders. No global hash-validation flag is changed.', '',
           '## Admission and identity','',
           'The producer reads each source and checked-hash pyc, verifies interpreter magic, flags and '
           'source hash, and records input SHA-256 identities. It preserves bytecode instructions and '
           'line tables while replacing nested code filenames with a stable snapshot URI, retaining '
           'source for loader-based inspection. The manifest binds exact interpreter/build/platform/'
           'optimization identity. Consumers validate that manifest and the admitted pyc headers; '
           'payload reads retain CRC. This is an experimental v1 format.', '',
           f"Producer admission/pack/index cost: **{data['producer_seconds']*1000:.3f} ms**, outside consumer timings. "
           f"Snapshot: `{data['snapshot']['snapshot']}`; {data['snapshot']['modules']} modules. "
           'The directory control uses the same relocated code, source, manifest and CRC checks, '
           'separating snapshot-loader/admission policy from mapped-bundle access. Source and code are '
           'both retained. Bytecode still creates Python code objects at import.', '',
           '## Startup comparison','',
           f"{data['trials']} randomized fresh `python -I -S -B` processes per case after one correctness warmup. "
           'Warm filesystem cache. Snapshot descriptor read, reader open, interpreter checks and mounting '
           'occur inside the application workload. Interpreter/common worker preparation still precedes '
           'that workload and remains in full-process timing. This is an application-phase closure, '
           'not a replacement for the interpreter’s own earliest bootstrap.', '',
           '| Stdlib provider | Samples | Ready ms | Workload ms | Process ms | Snapshot code reads | Startup source reads |',
           '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for case in data['cases']:
        if not case['samples']:continue
        s=case['summary'];sample=case['samples'][0];b=sample['stdlib_stats']
        lines.append(f"| {case['variant']} | {len(case['samples'])} | "+
                     ' | '.join(f"{s[k]['median']*1000:.3f}" for k in ('ready_seconds','workload_seconds','process_wall_seconds'))+
                     f" | {b.get('code_reads','—')} | {b.get('source_reads','—')} |")
    lines += ['', 'Ready includes WSGI/framework initialization and system checks. Workload additionally '
              'includes the two-row SQLite fixture and first API/admin responses. Full process also '
              'includes common imports, identical module/function/class source-inspection checks for '
              'every provider, cleanup and output. '
              'Source-inspection validation occurs after the workload and intentionally reads snapshot '
              'source; the source-read column is captured before that validation. Independent medians '
              'need not add. Timings are variable: the readiness min–max ranges below show the '
              'spread; small differences between medians are not evidence of a stable ranking.', '',
              '| Provider | Readiness min–max ms |', '| --- | ---: |',
              *[f"| {c['variant']} | {min(s['ready_seconds'] for s in c['samples'])*1000:.3f}–"
                f"{max(s['ready_seconds'] for s in c['samples'])*1000:.3f} |" for c in data['cases'] if c['samples']], '',
              '## Compatibility and scope','',
              'Every observation must preserve dependency module origins/execution sets, API results, '
              'resources, app count and zero network events. Snapshot-loaded stdlib origins deliberately '
              'use stable URIs; names remain standard. Module/function/class source inspection is tested, '
              'including unit tests with changed host source files. Packages retain a host fallback path '
              'for unbundled children/data, and native extensions retain their host loader. These fallback '
              'paths mean the limited snapshot is not a fully hermetic Python installation.', '',
              'The source/bytecode relationship is checked at admission against immutable inputs, '
              'rather than rereading loose source during each import. This policy is tied to the exact '
              'admitted snapshot and interpreter. It is not disabling checked caches globally or asserting '
              'arbitrary changed host files remain part of the same environment. Concurrent mutation of '
              'mapped/admitted files is unsupported, as in the existing reader experiments. Broader '
              'stdlib resource/process-spawn/debugger behavior needs its own compatibility coverage.', '']
    path.write_text('\n'.join(lines))


def run(args):
    parent=json.loads(args.inputs.read_text());observed=json.loads(args.host_io.read_text())
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    work=benchmark.HERE/'_work'/('stdlib-'+run_id);work.mkdir(parents=True)
    args.output.mkdir(parents=True,exist_ok=True)
    host_root=Path(sys._stdlib_dir)
    pairs=[(Path(p).parent.parent/(Path(p).name.split('.cpython-')[0]+'.py'),Path(p)) for p in observed['paths']['bytecode']]
    begin=time.perf_counter();snapshot=build_snapshot(pairs,work/'snapshot',host_root);producer=time.perf_counter()-begin
    descriptor=work/'snapshot-input.json';benchmark.write_json(descriptor,snapshot)
    original=next(c for c in parent['cases'] if c['mode']=='bytecode' and c['reader']=='odin' and c['discovery']=='index')
    data=dict(run_id=run_id,status='running',trials=args.trials,parent_run=parent['run_id'],
              environment=benchmark.environment(work),native=parent['native'],snapshot=snapshot,
              producer_seconds=producer,snapshot_descriptor=str(descriptor),cases=[])
    for variant in ('host','directory','python','odin'):
        command=original['command'][:]+['--inspect-stdlib']
        if variant!='host':command+=['--stdlib-bundle',str(descriptor),'--stdlib-reader',variant]
        data['cases'].append(dict(variant=variant,command=command,samples=[]))
    source_files=[benchmark.HERE/n for n in ('django_worker.py','stdlib_snapshot.py','indexed_path_loader.py','persistent_zip_loader.py','native_loader.py','precomputed_index.py')]
    data['consumer_implementation_sha256']={str(p.relative_to(benchmark.HERE.parent.parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}
    def consume(case):
        try:sample=benchmark.consume(case['command'])
        except subprocess.CalledProcessError as error:raise RuntimeError(error.stdout+error.stderr) from error
        expected=original['samples'][0]
        for key in ('module_origins','executed_files','api_result','resource_hashes','app_count'):
            if sample[key]!=expected[key]:raise ValueError('snapshot changed application '+key)
        if sample['source_inspection']!={'module':True,'function':True,'class':True}:
            raise ValueError('stdlib source compatibility failed')
        if case['variant']!='host':
            if (sample['stdlib_stats']['code_reads']!=snapshot['modules'] or sample['stdlib_stats']['source_reads'] or
                    sample['stdlib_stats']['preloaded'] or len(sample['stdlib_origins'])!=snapshot['modules']):
                raise ValueError('snapshot closure was preloaded, bypassed or read sources during startup')
        return sample
    for case in data['cases']:
        case['warmup']=consume(case);print('verified stdlib',case['variant'],flush=True)
    def checkpoint():
        for case in data['cases']:
            if case['samples']:case['summary']=benchmark.summarize(case['samples'])
        benchmark.write_json(args.output/'results.json',data);render(data,args.output/'REPORT.md')
    checkpoint();rng=random.Random(20261031)
    for trial in range(args.trials):
        cases=data['cases'].copy();rng.shuffle(cases)
        for case in cases:case['samples'].append(consume(case))
        checkpoint();print(f'stdlib trials {trial+1}/{args.trials}',flush=True)
    data['status']='complete';checkpoint();print(args.output/'REPORT.md')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,default=benchmark.HERE/'_work/runs/path-index/results.json')
    parser.add_argument('--host-io',type=Path,default=benchmark.HERE/'_work/runs/path-index/diagnostics/host-io.json')
    parser.add_argument('--output',type=Path,default=benchmark.HERE/'_work/runs/stdlib')
    parser.add_argument('--trials',type=int,default=15)
    args=parser.parse_args()
    if args.trials<1:parser.error('positive trials required')
    run(args)
