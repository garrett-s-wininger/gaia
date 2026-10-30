#!/usr/bin/env python3
"""Matched legacy/indexed discovery against exact retained Django inputs."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import benchmark


def render(data,path):
    lines=['# Index-backed package discovery','',f"Run: `{data['run_id']}`. Status: **{data['status']}**.", '',
           'Exact retained Django REST source/bytecode bundles, sidecars, native extension, app '
           'settings and templates from the parent run. No producer rebuild or dependency-source '
           'changes. Both controls execute the current worker; bundled cases differ only in discovery. '
           'The legacy provider remains available as a measured control.', '',
           'The indexed provider installs a path-entry finder for its owned bundle paths. It builds '
           'regular-package/direct-child tables once from the existing module map, handles misses '
           'without filesystem fallback, and supplies pkgutil iteration without reparsing ZIP. '
           'Unrelated paths retain normal import hooks. Close removes its hooks and restores prior '
           'importer-cache entries where possible. The archive format and payload readers are unchanged.', '',
           f"{data['trials']} randomized fresh processes per case after one correctness warmup. "
           'Warm filesystem cache. Indexed warmups additionally forbid stock ZIP-directory parsing; '
           'an untimed legacy negative control proves that guard detects the previous fallback. '
           'The guard is absent from timed observations. Medians, ms. Ready includes framework/WSGI '
           'initialization and checks; workload additionally includes the DB fixture and first API/admin '
           'responses. Full process includes common imports, validation and cleanup. Independent '
           'column medians need not add.', '',
           '| Input | Reader | Discovery | Samples | Ready ms | Workload ms | Process ms | Enumeration calls |',
           '| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for case in data['cases']:
        if not case['samples']:continue
        s=case['summary'];sample=case['samples'][0]
        lines.append(f"| {case['mode']} | {case['reader']} | {case['discovery']} | {len(case['samples'])} | "+
                     ' | '.join(f"{s[k]['median']*1000:.3f}" for k in ('ready_seconds','workload_seconds','process_wall_seconds'))+
                     f" | {sample['discovery_stats'].get('enumerations','—')} |")
    lines += ['', 'Every observation matches the parent module origins, executed-code sets, API output '
              'and resource hashes, with the same 455 dependency modules and 460 code reads for bundled '
              'cases. Payload CRC, one archive lifetime, package versions, admin rendering and zero '
              'network checks stay enabled. This app has pure-Python regular packages; namespace '
              'packages, native wheels and arbitrary mutable package paths remain outside the loader '
              'experiment. Host stdlib/native-extension loading, code-object reconstruction and '
              'framework initialization are unchanged. No timings from traces/profiles are substituted '
              'into this uninstrumented comparison.', '']
    path.write_text('\n'.join(lines))


def run(args):
    parent=json.loads(args.inputs.read_text())
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    work=benchmark.HERE/'_work'/('path-index-'+run_id);work.mkdir(parents=True)
    args.output.mkdir(parents=True,exist_ok=True)
    data=dict(run_id=run_id,status='running',parent_run=parent['run_id'],trials=args.trials,
              environment=benchmark.environment(work),native=parent['native'],inputs=[],cases=[])
    for mode in args.modes:
        input=next(i for i in parent['scenarios']['rest']['inputs'] if i['mode']==mode)
        if hashlib.sha256(Path(input['archive']).read_bytes()).hexdigest()!=input['archive_sha256']:
            raise ValueError('parent archive bytes changed')
        if hashlib.sha256(Path(input['index']).read_bytes()).hexdigest()!=input['index_sha256']:
            raise ValueError('parent index changed')
        data['inputs'].append(input)
        for reader in ('directory','python','odin'):
            original=next(c for c in parent['cases'] if c['scenario']=='rest' and c['mode']==mode and c['reader']==reader)
            for discovery in (('legacy',) if reader=='directory' else ('legacy','index')):
                command=original['command']+['--discovery',discovery]
                data['cases'].append(dict(mode=mode,reader=reader,discovery=discovery,command=command,samples=[]))
    if hashlib.sha256(Path(data['native']['path']).read_bytes()).hexdigest()!=data['native']['sha256']:
        raise ValueError('parent native extension changed')
    implementation=[benchmark.HERE/'django_worker.py',benchmark.HERE/'indexed_path_loader.py',benchmark.HERE/'persistent_zip_loader.py']
    data['consumer_implementation_sha256']={str(p.relative_to(benchmark.HERE.parent.parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in implementation}
    def consume(case,guard=False):
        command=case['command']+(['--forbid-zip-fallback'] if guard else [])
        try:sample=benchmark.consume(command)
        except subprocess.CalledProcessError as error:raise RuntimeError(error.stdout+error.stderr) from error
        original=next(c for c in parent['cases'] if c['scenario']=='rest' and c['mode']==case['mode'] and c['reader']==case['reader'])['samples'][0]
        for key in ('module_origins','executed_files','api_result','resource_hashes','app_count'):
            if sample[key]!=original[key]:raise ValueError('discovery changed '+key)
        return sample
    legacy=next(c for c in data['cases'] if c['reader']=='odin' and c['discovery']=='legacy')
    failure=subprocess.run(legacy['command']+['--forbid-zip-fallback'],capture_output=True,text=True,timeout=120)
    if not failure.returncode or 'stock zipimport reparsed the owned bundle' not in failure.stderr:
        raise ValueError('legacy negative control did not exercise ZIP fallback guard')
    data['legacy_guard_detected_fallback']=True
    for case in data['cases']:
        case['warmup']=consume(case,guard=case['discovery']=='index')
        print('verified',case['mode'],case['reader'],case['discovery'],flush=True)
    def checkpoint():
        for case in data['cases']:
            if case['samples']:case['summary']=benchmark.summarize(case['samples'])
        benchmark.write_json(args.output/'results.json',data);render(data,args.output/'REPORT.md')
    checkpoint();rng=random.Random(20261030)
    for trial in range(args.trials):
        cases=data['cases'].copy();rng.shuffle(cases)
        for case in cases:case['samples'].append(consume(case))
        checkpoint();print(f'path-index trials {trial+1}/{args.trials}',flush=True)
    data['status']='complete';checkpoint();print(args.output/'REPORT.md')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,default=benchmark.HERE/'_work/runs/django/results.json')
    parser.add_argument('--output',type=Path,default=benchmark.HERE/'_work/runs/path-index')
    parser.add_argument('--modes',nargs='+',choices=['source','bytecode'],default=['source','bytecode'])
    parser.add_argument('--trials',type=int,default=15)
    args=parser.parse_args()
    if args.trials<1 or len(args.modes)!=len(set(args.modes)):parser.error('positive trials and unique modes required')
    run(args)
