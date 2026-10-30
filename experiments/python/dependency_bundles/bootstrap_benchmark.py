"""Matched generic consumer-bootstrap experiments; no framework changes."""
import argparse
from datetime import datetime, timezone
import difflib
import hashlib
import json
import os
from pathlib import Path
import py_compile
import random
import statistics
import subprocess
import sys
import time

import benchmark
import process_characterization as lifecycle


def replace(source, old, new):
    if source.count(old) != 1:
        raise ValueError('transformation no longer matches: '+old[:100])
    return source.replace(old, new)


def thin_sources(sources):
    """Mechanical adapter separation; application/request/check code stays intact."""
    result = sources.copy()
    source = result['bundle_access.py']
    split = source.index('class BundlePath(Traversable):')
    result['bundle_resources.py'] = ('"""Reader-independent resource adapters."""\n'
        'from importlib.resources.abc import Traversable, TraversableResources\nimport io\n\n'+source[split:])
    result['bundle_access.py'] = replace(source[:split],
        'from importlib.resources.abc import Traversable, TraversableResources',
        'from bundle_resources import BundlePath, BundleResources')
    # The older all-layout worker executes adapters by filename before adding
    # their sibling directory. The extracted resource adapter is now a sibling.
    source = replace(result['worker.py'], 'sys.path.insert(0, str(Path(__file__).resolve().parent))\n', '')
    result['worker.py'] = replace(source, '_adapter_spec = importlib.util.spec_from_file_location(',
        'sys.path.insert(0, str(Path(__file__).resolve().parent))\n_adapter_spec = importlib.util.spec_from_file_location(')
    for name in ('django_worker.py', 'catalog_worker.py'):
        source = result[name]
        source = replace(source, 'import argparse\n', '')
        source = replace(source, "if __name__=='__main__':\n", "if __name__=='__main__':\n    import argparse\n")
        if name == 'django_worker.py':
            source = replace(source, 'from bundle_access import BundleReader, BundleResources',
                             'from bundle_resources import BundleResources')
            source = replace(source, 'from precomputed_index import IndexedBundleReader\n', '')
            source = replace(source, "if args.reader == 'zipfile':factory = lambda p: BundleReader(p,'zipfile')",
                "if args.reader == 'zipfile':\n            from bundle_access import BundleReader\n            factory = lambda p: BundleReader(p,'zipfile')")
            source = replace(source, "elif args.reader == 'python':\n", "elif args.reader == 'python':\n            from precomputed_index import IndexedBundleReader\n")
            source = replace(source, "elif args.stdlib_reader=='python':\n", "elif args.stdlib_reader=='python':\n            from precomputed_index import IndexedBundleReader\n")
        else:
            source = replace(source, 'from bundle_access import BundleResources', 'from bundle_resources import BundleResources')
        result[name] = source
    result['stdlib_snapshot.py'] = replace(result['stdlib_snapshot.py'],
        'from bundle_access import BundlePath', 'from bundle_resources import BundlePath')
    source = replace(result['native_loader.py'], 'from precomputed_catalog import LazyEntries,load_catalog\n', '')
    source = replace(source, 'import zipfile\n', '')
    source = replace(source, "                data=load_catalog(",
                     "                from precomputed_catalog import LazyEntries,load_catalog\n                data=load_catalog(")
    source = replace(source, '            raise zipfile.BadZipFile(str(error)) from error',
                     '            import zipfile\n            raise zipfile.BadZipFile(str(error)) from error')
    source = replace(source, "            if 'CRC' in str(error):raise zipfile.BadZipFile(str(error)) from error",
                     "            if 'CRC' in str(error):\n                import zipfile\n                raise zipfile.BadZipFile(str(error)) from error")
    result['native_loader.py'] = source
    source = replace(result['persistent_zip_loader.py'], 'import zipfile\n', '')
    source = replace(source, '        return zipfile.Path(', '        import zipfile\n        return zipfile.Path(')
    source = replace(source, 'archive_factory=zipfile.ZipFile', 'archive_factory=None')
    source = replace(source, '        self.archive_factory = archive_factory',
                     '        if archive_factory is None:\n            import zipfile\n            archive_factory = zipfile.ZipFile\n        self.archive_factory = archive_factory')
    result['persistent_zip_loader.py'] = source
    return result


def prepare(directory, sources, bytecode):
    directory.mkdir()
    for name in ('django_fixture','native'):
        (directory/name).symlink_to(benchmark.HERE/name,target_is_directory=True)
    for name, source in sources.items():
        path = directory/name
        if bytecode:
            # Compile in producer time. Consumers import ordinary sourceless pyc files.
            temporary = directory/(name+'.input')
            temporary.write_text(source)
            py_compile.compile(str(temporary), cfile=str(path)+'c', dfile=str(path), doraise=True,
                               invalidation_mode=py_compile.PycInvalidationMode.CHECKED_HASH)
            temporary.unlink()
        else:
            path.write_text(source)


def arguments(command, directory):
    """Use the unchanged CLI parser once to admit an exact programmatic launch."""
    index = next(i for i, v in enumerate(command) if v.endswith(('/django_worker.py', '/catalog_worker.py')))
    original = Path(command[index])
    source = replace(original.read_text(), '    main(parser.parse_args())',
                     "    print(json.dumps(vars(parser.parse_args()),default=lambda p:{'__path__':str(p)}))")
    extractor = directory/(original.stem+'-arguments.py')
    # Resolve imports from the original consumer directory.
    extractor.write_text('import sys\nsys.path.insert(0,'+repr(str(benchmark.HERE))+')\n'+source)
    parsed = subprocess.run([*command[:index],str(extractor),*command[index+1:]],
                            check=True,capture_output=True,text=True)
    values = json.loads(parsed.stdout)
    def literal(value):
        if isinstance(value,dict) and set(value)=={'__path__'}:return 'Path('+repr(value['__path__'])+')'
        return repr(value)
    return original.stem, ','.join(k+'='+literal(v) for k,v in values.items())


def validate(workload, sample, reference):
    if not sample['correct']:raise ValueError('incorrect result')
    if workload == 'django':
        for key in ('module_origins','executed_files','api_result','resource_hashes','source_inspection',
                    'module_count','app_count','template_loader','admin_validated','archive_opens','module_reads'):
            if sample[key] != reference[key]:raise ValueError('application differs: '+key)
        if sample['network_events']:raise ValueError('network attempted')
        if sample['code_handoff_counts']['dependencies'] != reference['code_handoff_counts']['dependencies']:
            raise ValueError('dependency decode count differs')
        # Narrower bootstrap changes which stdlib modules were already loaded. The
        # worker checks every newly loaded admitted stdlib origin and inspection.
    elif sample['imported'] != 33 or sample['modules'] != int(workload):
        raise ValueError('fixed-import workload differs')


def report(data, path):
    lines = ['# Generic bootstrap experiments','',f"Run: `{data['run_id']}`; **{data['status']}**.",'',
        'Warm filesystem cache, fresh isolated Python process, identical compact artifacts/native '
        'binary, bytes+slice handoff and normal interpreter exit. No dependency/framework code '
        'changes. Build/compilation is separate producer work. All samples validate application '
        'results, dependency execution/origins, resources and source inspection. Narrow imports '
        'change the preloaded stdlib set; the worker validates every newly loaded snapshot origin.','',
        '| Workload | Mode | Process wall ms | Child CPU ms | Bootstrap ms | Workload ms | RSS MiB |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for case in data['cases']:
        if not case['samples']:continue
        def med(key):return statistics.median(s[key] for s in case['samples'])
        bootstrap = f"{med('bootstrap_seconds')*1000:.3f}" if 'bootstrap_seconds' in case['samples'][0] else '—'
        lines.append(f"| {case['workload']} | {case['mode']} | {med('process_wall_seconds')*1000:.3f} | "
                     f"{med('child_cpu_seconds')*1000:.3f} | {bootstrap} | {med('workload_seconds')*1000:.3f} | {med('peak_rss_bytes')/1048576:.2f} |")
    lines += ['', '## Paired whole-process comparisons','',
              '| Workload | Mode vs source control | Median change ms | Wins / trials |',
              '| --- | --- | ---: | ---: |']
    for case in data['cases']:
        if case['mode']=='source' or not case['samples']:continue
        base=next(c for c in data['cases'] if c['workload']==case['workload'] and c['mode']=='source')
        pairs=list(zip(case['samples'],base['samples']))
        delta=[(a['process_wall_seconds']-b['process_wall_seconds'])*1000 for a,b in pairs]
        lines.append(f"| {case['workload']} | {case['mode']} | {statistics.median(delta):+.3f} | {sum(v<0 for v in delta)}/{len(delta)} |")
    lines += ['', '## Incremental whole-process comparisons','',
              '| Workload | Change | Median paired change ms | Wins / trials |',
              '| --- | --- | ---: | ---: |']
    for workload in sorted({c['workload'] for c in data['cases']}):
        cases={c['mode']:c for c in data['cases'] if c['workload']==workload}
        for mode,base in [('pyc','source'),('thin-pyc','pyc'),('thin-pyc','source'),
                          ('programmatic','thin-pyc'),('gc4','programmatic'),('gc16','programmatic')]:
            if mode not in cases or base not in cases:continue
            delta=[(a['process_wall_seconds']-b['process_wall_seconds'])*1000
                   for a,b in zip(cases[mode]['samples'],cases[base]['samples'])]
            if not delta:continue
            lines.append(f"| {workload} | {base} → {mode} | {statistics.median(delta):+.3f} | {sum(v<0 for v in delta)}/{len(delta)} |")
    lines += ['', 'Modes: source = unchanged consumer snapshot; pyc = same code, producer-compiled; '
              'thin-source/thin-pyc = independent resource adapter plus on-demand comparison/ZIP '
              'imports; programmatic = thin-pyc with exact CLI arguments admitted once and supplied '
              'as typed parameters, avoiding argparse; gc4 = programmatic with the generation-zero '
              'GC threshold multiplied by four, other thresholds unchanged; gc16 = programmatic '
              'with the generation-zero GC threshold multiplied by sixteen. GC remains enabled and normal shutdown runs in every mode. '
              'Programmatic compilation/configuration must be invalidated on argument/code/runtime '
              'changes; its producer cost is recorded, not hidden as consumer work. No warm worker '
              'or interpreter-state sharing is used.', '',
              'Uninstrumented samples supply this table. Separate observed runs/profiles are '
              'diagnostics only. Source snapshots, exact thin.patch, source/bytecode hashes, commands '
              'and launch parameter source remain under the recorded work directory. Process time '
              'includes launch, all work/validation/output/close and normal finalization. Bootstrap '
              'and workload are worker clocks and exclude portions of CLI/programmatic launch. '
              'Do not compare absolute times with previous runs as speedups.', '']
    path.write_text('\n'.join(lines))


def verify_artifacts(data):
    work=Path(data['work'])
    for name,pin in data['bytecode_sha256'].items():
        if hashlib.sha256((work/name).read_bytes()).hexdigest()!=pin:raise ValueError('bytecode changed: '+name)
    for mode,key in [('source','sources_sha256'),('thin-source','thin_sources_sha256')]:
        for name,pin in data[key].items():
            if hashlib.sha256((work/mode/name).read_bytes()).hexdigest()!=pin:raise ValueError('source changed: '+name)
    for name,pin in data['fixture_sources_sha256'].items():
        if hashlib.sha256((benchmark.HERE/name).read_bytes()).hexdigest()!=pin:raise ValueError('fixture changed: '+name)
    case=next(c for c in data['cases'] if c['workload']=='django' and c['mode']=='source')
    command=case['command'];library=Path(command[command.index('--library')+1])
    if hashlib.sha256(library.read_bytes()).hexdigest()!=data['native_extension_sha256']:raise ValueError('native pin changed')


def run(args):
    parent=json.loads(args.inputs.read_text())
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    work=benchmark.HERE/'_work'/('bootstrap-'+run_id);work.mkdir(parents=True)
    args.output.mkdir(parents=True,exist_ok=True)
    sources={p.name:p.read_text() for p in benchmark.HERE.glob('*.py')}
    thin=thin_sources(sources)
    patch=''.join(''.join(difflib.unified_diff(sources.get(n,'').splitlines(True),s.splitlines(True),
              fromfile='original/'+n,tofile='thin/'+n)) for n,s in thin.items() if s!=sources.get(n))
    (work/'thin.patch').write_text(patch)
    start=time.perf_counter()
    for name,content,bytecode in [('source',sources,False),('pyc',sources,True),
                                  ('thin-source',thin,False),('thin-pyc',thin,True)]:
        prepare(work/name,content,bytecode)
    data=dict(run_id=run_id,status='running',trials=args.trials,parent_run=parent['run_id'],
              work=str(work),environment=benchmark.environment(work),cases=[],
              snapshot_production_seconds=time.perf_counter()-start,
              native_extension_sha256=parent['build']['extension_sha256'],
              sources_sha256={n:hashlib.sha256(s.encode()).hexdigest() for n,s in sources.items()},
              thin_sources_sha256={n:hashlib.sha256(s.encode()).hexdigest() for n,s in thin.items()},profiles=[])
    data['fixture_sources_sha256']={str(p.relative_to(benchmark.HERE)):hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in (benchmark.HERE/'django_fixture').glob('*.py')}
    for workload in ('1024','131072','django'):
        reference=next(c for c in parent['cases'] if c['workload']==workload and c['mode']=='compact')
        command=reference['command'];index=next(i for i,v in enumerate(command) if v.endswith(('/django_worker.py','/catalog_worker.py')))
        if workload=='django':
            library=Path(command[command.index('--library')+1])
            if hashlib.sha256(library.read_bytes()).hexdigest()!=data['native_extension_sha256']:raise ValueError('native pin changed')
        admission=time.perf_counter();module,values=arguments(command,work)
        launch=('from pathlib import Path\nfrom types import SimpleNamespace\nimport sys\n'
                'sys.path.insert(0,'+repr(str(work/'thin-pyc'))+')\n'
                "if sys._xoptions.get('gaia_gc_scale'):\n import gc\n t=gc.get_threshold();gc.set_threshold(t[0]*int(sys._xoptions['gaia_gc_scale']),*t[1:])\n"
                'import '+module+' as worker\nworker.main(SimpleNamespace('+values+'))\n'
                'if worker._observer is not None:worker._observer.finish()\n')
        launchpath=work/'thin-pyc'/(workload+'-launch.pyc')
        temporary=work/(workload+'-launch.py');temporary.write_text(launch)
        py_compile.compile(str(temporary),cfile=str(launchpath),doraise=True)
        data.setdefault('launch_admission_seconds',{})[workload]=time.perf_counter()-admission
        for mode in ('source','pyc','thin-source','thin-pyc','programmatic','gc4','gc16'):
            cmd=command.copy();environment={}
            if mode in ('programmatic','gc4','gc16'):
                cmd=[*command[:index],str(launchpath)]
                if mode in ('gc4','gc16'):cmd[1:1]=['-X','gaia_gc_scale='+('4' if mode=='gc4' else '16')]
            else:cmd[index]=str(work/mode/(Path(command[index]).name+('c' if mode.endswith('pyc') else '')))
            data['cases'].append(dict(workload=workload,mode=mode,command=cmd,environment=environment,samples=[],reference=reference['samples'][0]))
    data['bytecode_sha256']={str(p.relative_to(work)):hashlib.sha256(p.read_bytes()).hexdigest()
                             for mode in ('pyc','thin-pyc') for p in (work/mode).glob('*.pyc')}
    def take(case,log=None,profile=None):
        previous={k:os.environ.get(k) for k in case['environment']}
        try:
            os.environ.update(case['environment'])
            sample=lifecycle.consume(case['command'],log,profile=profile)
        finally:
            for k,v in previous.items():
                if v is None:os.environ.pop(k,None)
                else:os.environ[k]=v
        validate(case['workload'],sample,case['reference'])
        return sample
    for case in data['cases']:
        case['warmup']=take(case);print('verified',case['workload'],case['mode'],flush=True)
    def save():
        benchmark.write_json(args.output/'results.json',data);report(data,args.output/'REPORT.md')
    save();rng=random.Random(20261030)
    for trial in range(args.trials):
        shuffled=data['cases'].copy();rng.shuffle(shuffled)
        for case in shuffled:case['samples'].append(take(case))
        save();print(f'bootstrap trials {trial+1}/{args.trials}',flush=True)
    for case in data['cases']:
        if case['workload']!='django' or case['mode'] not in ('source','thin-pyc','programmatic','gc4'):continue
        prefix=work/(case['mode']+'-profile');log=work/(case['mode']+'-profile.phases')
        sample=take(case,log,profile=prefix)
        data['profiles'].append(dict(mode=case['mode'],observation=sample,phases=lifecycle.profiles(prefix)))
        print('profiled',case['mode'],flush=True)
    benchmark.write_json(args.output/'profiles.json',data['profiles'])
    for row in data['profiles']:
        for phase in row['phases']:phase.pop('functions',None)
    data['diagnostics']=[]
    for case in data['cases']:
        if case['workload']!='django' or case['mode'] not in ('source','pyc','thin-pyc','programmatic'):continue
        mode=case['mode'];plan=work/(mode+'-command.json');events=work/(mode+'-compiles.json')
        benchmark.write_json(plan,case['command'])
        audited=subprocess.run([sys.executable,'-I','-S','-B',str(benchmark.HERE/'compile_probe.py'),str(plan),str(events)],
                               check=True,capture_output=True,text=True)
        validate('django',json.loads(audited.stdout),case['reference'])
        imported=subprocess.run([case['command'][0],'-X','importtime',*case['command'][1:]],
                                check=True,capture_output=True,text=True)
        validate('django',json.loads(imported.stdout),case['reference'])
        graph=work/(mode+'-importtime.txt');graph.write_text(imported.stderr)
        compiled=json.loads(events.read_text())
        root=work/('thin-pyc' if mode=='programmatic' else mode)
        data['diagnostics'].append(dict(mode=mode,compile_events=compiled,
            consumer_source_compiles=[e for e in compiled if Path(e['filename']).parent==root],
            import_graph_path=str(graph)))
    benchmark.write_json(args.output/'diagnostics.json',data['diagnostics'])
    verify_artifacts(data)
    data['status']='complete';save()


def confirm(args):
    """Reuse admitted commands for a tighter, independently randomized comparison."""
    parent=json.loads(args.confirm.read_text())
    verify_artifacts(parent)
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    args.output.mkdir(parents=True,exist_ok=True)
    data=dict(run_id=run_id,status='running',trials=args.trials,parent_run=parent['run_id'],
              work=parent['work'],environment=benchmark.environment(Path(parent['work'])),cases=[],
              native_extension_sha256=parent['native_extension_sha256'])
    for original in parent['cases']:
        if original['workload']=='django' and original['mode'] in ('source','thin-pyc','programmatic'):
            case={k:v for k,v in original.items() if k not in ('samples','warmup')}
            case['samples']=[];data['cases'].append(case)
    if len(data['cases'])!=3:raise ValueError('confirmation requires the three Django launch controls')
    def take(case):
        sample=lifecycle.consume(case['command'])
        validate(case['workload'],sample,case['reference']);return sample
    for case in data['cases']:case['warmup']=take(case)
    rng=random.Random(20261031)
    for trial in range(args.trials):
        shuffled=data['cases'].copy();rng.shuffle(shuffled)
        for case in shuffled:case['samples'].append(take(case))
        benchmark.write_json(args.output/'results.json',data);report(data,args.output/'REPORT.md')
        print(f'confirmation trials {trial+1}/{args.trials}',flush=True)
    data['status']='complete'
    benchmark.write_json(args.output/'results.json',data);report(data,args.output/'REPORT.md')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,default=benchmark.HERE/'_work/runs/unified-catalog/results.json')
    parser.add_argument('--output',type=Path,default=benchmark.HERE/'_work/runs/bootstrap')
    parser.add_argument('--trials',type=int,default=15)
    parser.add_argument('--confirm',type=Path,help='reuse saved commands for focused Django launch confirmation')
    args=parser.parse_args()
    if args.trials<1:parser.error('positive trials required')
    if args.confirm:confirm(args)
    else:run(args)
