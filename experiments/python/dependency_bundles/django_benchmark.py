#!/usr/bin/env python3
"""Pinned real Django core/REST app through directory/Python/Odin loading."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import random
import subprocess
import sys
import time
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parent))
import benchmark
from precomputed_index import build_index

HERE = Path(__file__).resolve().parent
MODULES = {'django':'django','asgiref':'asgiref','sqlparse':'sqlparse',
           'djangorestframework':'rest_framework','django-filter':'django_filters'}
READERS = ('directory-stock','directory','zipfile','python','odin')


def extract(artifacts, destination):
    destination.mkdir(parents=True)
    names = set()
    counts = []
    for artifact in artifacts:
        path = Path(artifact['path'])
        if hashlib.sha256(path.read_bytes()).hexdigest()!=artifact['sha256']:
            raise ValueError('wheel hash mismatch: '+str(path))
        files = code = logical = 0
        with zipfile.ZipFile(path) as wheel:
            for entry in wheel.infolist():
                if entry.is_dir():continue
                name = entry.filename;relative = PurePosixPath(name)
                if relative.is_absolute() or '..' in relative.parts or '\\' in name or name.casefold() in names:
                    raise ValueError('unsafe/colliding wheel path: '+name)
                if '.data' in relative.parts[0]:raise ValueError('wheel install relocation not implemented')
                names.add(name.casefold());payload = wheel.read(entry)
                target = destination/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(payload)
                files += 1;code += name.endswith('.py');logical += len(payload)
        counts.append(dict(project=artifact['project'],version=artifact['version'],files=files,
                           python_files=code,logical_bytes=logical,wheel_sha256=artifact['sha256']))
    return counts


def render(data, path):
    lines=['# Real Django loading experiment','',f"Run: `{data['run_id']}`. Status: **{data['status']}**.",'',
           'Published pure-Python wheels, pinned by URL/version/SHA-256. No dependency source edits. '
           'Core starts admin/auth/contenttypes/sessions/messages/staticfiles, forms and a tiny ORM app. '
           'REST adds Django REST framework and django-filter. Each process initializes WSGI, runs all '
           'Django system checks, seeds two rows in in-memory SQLite, serves a filtered JSON request '
           'and renders the admin login page through WSGI. No network listener, external service, '
           'dependency installation, migrations or production database. I18N is disabled; static '
           'assets are checksum-validated but not served.', '',
           '## Size and input preparation','',
           '| Scenario | Projects | Files | Python files available | Unpacked MiB |',
           '| --- | ---: | ---: | ---: | ---: |']
    for name,scenario in data['scenarios'].items():
        counts=scenario['inventory']
        lines.append(f"| {name} | {len(counts)} | {sum(c['files'] for c in counts)} | "
                     f"{sum(c['python_files'] for c in counts)} | {sum(c['logical_bytes'] for c in counts)/2**20:.2f} |")
    lines += ['', 'Producer extraction, bytecode compilation, stored-ZIP packing and binary index admission '
              'are outside consumer clocks and recorded separately. Source and bytecode are separate '
              'inputs; every reader within a mode sees equivalent dependency code/resources. Native '
              'extensions come only from the host interpreter/stdlib, including SQLite. The existing '
              'Odin extension is reused and its hash is checked.', '',
              '## Startup and first responses','',
              f"{data['trials']} randomized fresh `python -I -S -B` processes per case after one correctness "
              'warmup. Warm filesystem cache. Medians, ms. Ready includes dependency/provider open, '
              'framework/WSGI initialization and system checks. Workload additionally includes the '
              'separately reported test-database setup and first API/admin responses. Complete process '
              'includes common adapter imports, validation and cleanup; parent JSON decoding is excluded. '
              'Independent column medians need not add.', '',
              '| Scenario | Input | Reader | Ready | DB fixture | API | Admin | Workload | Process | Modules | RSS MiB |',
              '| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for case in data['cases']:
        if not case['samples']:continue
        s=case['summary'];sample=case['samples'][0]
        lines.append(f"| {case['scenario']} | {case['mode']} | {case['reader']} | "+
                     ' | '.join(f"{s[k]['median']*1000:.3f}" for k in
                                ('ready_seconds','fixture_db_seconds','first_api_seconds','first_admin_seconds','workload_seconds','process_wall_seconds'))+
                     f" | {sample['module_count']} | {s['peak_rss_bytes']['median']/2**20:.2f} |")
    lines += ['', '## Resource compatibility and controls','',
              '`directory-stock` uses the filesystem/app-directory template loaders. Every other case '
              'uses the same small Django template-loader adapter over `importlib.resources`; '
              '`directory` measures that adapter over ordinary files. Thus byte-reader comparisons '
              'hold template loading fixed and the stock-directory row exposes adapter effects. '
              'Form rendering uses Django’s TemplatesSetting renderer and the installed forms app '
              'in every case. Bundled cases do not silently extract dependency templates or code.', '',
              '`zipfile` uses the common Python reader with ZIP metadata validation on open; `python` '
              'uses a pinned binary sidecar/mmap reader; `odin` supplies sidecar/mapped reads through '
              'the existing in-process extension. Python still builds module lookup objects and executes '
              'the loader, compiler and framework. Sidecar cases use trusted immutable local-admission '
              'identity checks, not whole-bundle SHA-256 on every open; reads retain CRC checks. '
              'Input byte hashes and all index admission costs are retained. Discovery/enumeration '
              'through Python/pkgutil is not replaced by the Odin byte provider.', '',
              'All dependency module origins/loaders, API output, admin form markers, '
              'selected versions, three resource hashes, one provider open, matching code-read counts '
              'and zero network attempts are checked. Code/import sets must match across byte-reader '
              'controls; the stock-template baseline loads different template-loader code intentionally. '
              'Admin HTML contains random CSRF tokens, so '
              'semantic markers are checked rather than asserting byte-identical HTML. Detailed '
              'per-phase CPU/wall observations, imports, code executions and commands are retained.', '',
              'The project model, in-memory database, two routes and chosen add-ons are a specified '
              'application fixture, not a claim about typical Django deployments. Template resource '
              'access is adapted explicitly; arbitrary filesystem consumers, localization, migration '
              'discovery, static-file collection/serving, autoreload, namespace packages, native wheels '
              'and remote storage are not established by this test. Dependency solving is measured '
              'separately; a large framework source tree need not imply a large dependency graph.', '']
    path.write_text('\n'.join(lines))


def run(args):
    provenance=json.loads(args.provenance.read_text())
    latest={}
    for artifact in provenance['artifacts']:
        latest.setdefault(artifact['project'],artifact)
    if set(latest)!=set(MODULES):raise ValueError('expected the pinned five-project corpus')
    previous=None
    if args.library is None:
        previous=json.loads((HERE/'_work/runs/python-native/results.json').read_text())
        command=next(c['command'] for c in previous['cases'] if c['workload']=='pip' and c['reader']=='odin-local')
        library=Path(command[command.index('--library')+1])
    else:
        library=args.library.resolve()
    extension_hash=hashlib.sha256(library.read_bytes()).hexdigest()
    if previous is not None and extension_hash!=previous['build']['extension_sha256']:
        raise ValueError('generated Odin extension changed; rebuild predecessor inputs')
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    work=HERE/'_work'/('django-'+run_id);work.mkdir(parents=True)
    args.output.mkdir(parents=True,exist_ok=True)
    benchmark.write_json(args.output/'provenance.json',provenance)
    data=dict(run_id=run_id,status='running',trials=args.trials,environment=benchmark.environment(work),
              provenance=provenance,native=dict(path=str(library),sha256=extension_hash,parent_run=previous['run_id'] if previous else None),
              scenarios={},cases=[])
    consumer_files=[HERE/n for n in ('django_worker.py','persistent_zip_loader.py','indexed_path_loader.py',
                                     'native_loader.py','precomputed_index.py','bundle_access.py')]
    consumer_files += sorted((HERE/'django_fixture').glob('*.py'))
    data['consumer_implementation_sha256']={str(p.relative_to(HERE.parent.parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in consumer_files}
    for scenario in ('core','rest'):
        selected=[a for n,a in latest.items() if scenario=='rest' or n in ('django','asgiref','sqlparse')]
        source=work/(scenario+'-source');started=time.perf_counter();counts=extract(selected,source)
        extracted=time.perf_counter()-started
        versions={MODULES[a['project']]:a['version'] for a in selected}
        resources={}
        for name in ('contrib/admin/templates/admin/login.html','contrib/admin/static/admin/js/core.js','forms/templates/django/forms/widgets/text.html'):
            resources['django:'+name]=hashlib.sha256((source/'django'/name).read_bytes()).hexdigest()
        expected=work/(scenario+'-expected.json');benchmark.write_json(expected,dict(versions=versions,resources=resources))
        bytecode=work/(scenario+'-bytecode');compiled=benchmark.precompile(source,bytecode)
        data['scenarios'][scenario]=dict(inventory=counts,extract_seconds=extracted,compile_seconds=compiled,inputs=[])
        for mode,directory in (('source',source),('bytecode',bytecode)):
            archive=work/(scenario+'-'+mode+'.zip');packed=benchmark.pack(directory,archive,zipfile.ZIP_STORED)
            index=archive.with_suffix('.index');admitted=build_index(archive,index,encoding='binary')
            data['scenarios'][scenario]['inputs'].append(dict(mode=mode,directory=str(directory),archive=str(archive),
                                                            pack_seconds=packed,index=str(index),**admitted))
            for reader in READERS:
                root=directory if reader.startswith('directory') else archive
                command=[sys.executable,'-I','-S','-B',str(HERE/'django_worker.py'),'--root',str(root),
                         '--reader',reader,'--scenario',scenario,'--expected',str(expected)]
                if reader in ('python','odin'):command+=['--index',str(index),'--pin',admitted['index_sha256']]
                if reader=='odin':command+=['--library',str(library)]
                data['cases'].append(dict(scenario=scenario,mode=mode,reader=reader,command=command,samples=[]))
    signatures={}
    def consume(case):
        try:sample=benchmark.consume(case['command'])
        except subprocess.CalledProcessError as error:raise RuntimeError(error.stdout+error.stderr) from error
        signature=(sample['module_origins'],sample['executed_files'],sample['app_count'],sample['api_result'])
        # Origins normalize .pyc; co_filenames normalize to source paths.
        key=(case['scenario'],'stock' if case['reader']=='directory-stock' else 'resource')
        previous=signatures.setdefault(key,signature)
        if signature!=previous:raise RuntimeError('reader/layout changed imports, execution or app output')
        return sample
    def checkpoint():
        for case in data['cases']:
            if case['samples']:case['summary']=benchmark.summarize(case['samples'])
        benchmark.write_json(args.output/'results.json',data);render(data,args.output/'REPORT.md')
    for case in data['cases']:
        consume(case);print('verified',case['scenario'],case['mode'],case['reader'],flush=True)
    checkpoint()
    rng=random.Random(20261029)
    for trial in range(args.trials):
        cases=data['cases'].copy();rng.shuffle(cases)
        for case in cases:case['samples'].append(consume(case))
        checkpoint()
        print(f'Django trials {trial+1}/{args.trials}',flush=True)
    data['status']='complete';checkpoint();print(args.output/'REPORT.md')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provenance',type=Path,default=HERE/'_work/django-corpus/provenance.json')
    parser.add_argument('--library',type=Path)
    parser.add_argument('--trials',type=int,default=15)
    parser.add_argument('--output',type=Path,default=HERE/'_work/runs/django')
    args=parser.parse_args()
    if args.trials<1:parser.error('positive trials required')
    run(args)
