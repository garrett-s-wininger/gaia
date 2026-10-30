#!/usr/bin/env python3
"""One offline Django application startup and two in-process WSGI requests."""
import time
import sys
_entered = time.perf_counter()
_entered_cpu = time.process_time()
_observer = None
if sys._xoptions.get('gaia_phases'):
    sys.path.insert(0,sys.argv[0].rsplit('/',1)[0])
    from process_phases import Observer
    _observer = Observer(_entered,_entered_cpu)


def phase(name,stamp=None):
    if _observer is not None:_observer.mark(name,stamp)
import argparse
import hashlib
import importlib.resources
import io
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bundle_access import BundleReader, BundleResources
from native_loader import NativeBundleReader
from persistent_zip_loader import PersistentZipProvider, ModuleLoader
from precomputed_index import IndexedBundleReader
from indexed_path_loader import IndexedPathProvider
from stdlib_snapshot import DirectorySnapshot,SnapshotLoader,StdlibSnapshotProvider
_prepared = time.perf_counter()
phase("common_prepared",_prepared)

PREFIXES = ('django', 'asgiref', 'sqlparse', 'rest_framework', 'django_filters')


def controlled(name):
    return any(name == p or name.startswith(p+'.') for p in PREFIXES)


def request(application, path, query='', accept='application/json'):
    response = {}
    environ = {'REQUEST_METHOD':'GET', 'SCRIPT_NAME':'', 'PATH_INFO':path,
               'QUERY_STRING':query, 'SERVER_NAME':'testserver', 'SERVER_PORT':'80',
               'SERVER_PROTOCOL':'HTTP/1.1', 'HTTP_HOST':'testserver', 'HTTP_ACCEPT':accept,
               'REMOTE_ADDR':'127.0.0.1', 'wsgi.version':(1,0), 'wsgi.url_scheme':'http',
               'wsgi.input':io.BytesIO(), 'wsgi.errors':io.StringIO(),
               'wsgi.multithread':False, 'wsgi.multiprocess':False, 'wsgi.run_once':True}
    def start_response(status, headers, exc_info=None):
        response.update(status=status, headers=headers)
    result = application(environ, start_response)
    try:body = b''.join(result)
    finally:
        if hasattr(result, 'close'):result.close()
    if not response['status'].startswith('200 '):
        raise RuntimeError(f"{path}: {response['status']} {environ['wsgi.errors'].getvalue()} {body[:200]!r}")
    return body


def main(args):
    phase("main_entered")
    if not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError('requires -I -S -B')
    if any(controlled(n) for n in sys.modules):raise RuntimeError('dependency preloaded')
    expected = json.loads(args.expected.read_text())
    root = str(args.root.resolve(strict=True))
    provider = None
    if args.reader not in ('directory', 'directory-stock'):
        if args.reader == 'zipfile':factory = lambda p: BundleReader(p,'zipfile')
        elif args.reader == 'python':
            factory = lambda p: IndexedBundleReader(p,args.index,index_sha256=args.pin,verify='local')
        else:
            factory = lambda p: NativeBundleReader(p,args.index,index_sha256=args.pin,verify='local',library=args.library,bytecode_handoff=args.bytecode_handoff,
                                                  catalog_path=args.catalog,catalog_sha256=args.catalog_pin,catalog_mode=args.catalog_mode,catalog_budget=args.catalog_budget)
        provider_type = IndexedPathProvider if args.discovery=='index' else PersistentZipProvider
        provider = provider_type(root,archive_factory=factory,resource_factory=BundleResources)
    if args.forbid_zip_fallback:
        import zipimport
        original_read_directory = zipimport._read_directory
        def forbid_owned_archive(archive):
            if str(archive)==root:raise AssertionError('stock zipimport reparsed the owned bundle')
            return original_read_directory(archive)
        zipimport._read_directory = forbid_owned_archive
    network, executions = [], {}
    def audit(event, arguments):
        if event in ('socket.connect','socket.getaddrinfo','socket.bind'):
            network.append(event);raise RuntimeError('network attempted')
        if event == 'exec':
            code = arguments[0];name = code.co_filename
            if name.startswith(root+os.sep):name = name[len(root)+1:]
            elif name.startswith('gaia-fixture:///'):name = name[len('gaia-fixture:///'):]
            if code.co_name=='<module>' and name.split('/')[0] in PREFIXES:
                executions[name] = executions.get(name,0)+1
    sys.addaudithook(audit)
    os.environ['DJANGO_SETTINGS_MODULE'] = 'django_fixture.settings'
    os.environ['GAIA_DJANGO_SCENARIO'] = args.scenario
    os.environ['GAIA_DJANGO_TEMPLATES'] = 'filesystem' if args.reader=='directory-stock' else 'resource'
    bootstrap=None
    preloaded_stdlib=set(sys.modules)
    if provider is not None and provider.archive is not None:raise RuntimeError('provider opened early')
    begin = time.perf_counter();cpu_begin = time.process_time()
    phase("workload_begin",begin)
    sys.path.insert(0,root)
    if provider is not None:
        if args.discovery=='index':provider.install()
        else:sys.meta_path.insert(0,provider)
    if args.stdlib_bundle:
        descriptor=json.loads(args.stdlib_bundle.read_text())
        if args.stdlib_reader=='directory':
            bootstrap_root=descriptor['directory'];bootstrap_factory=DirectorySnapshot
        elif args.stdlib_reader=='python':
            bootstrap_root=descriptor['archive']
            bootstrap_factory=lambda p:IndexedBundleReader(p,descriptor['index'],index_sha256=descriptor['index_sha256'],verify='local')
        else:
            bootstrap_root=descriptor['archive']
            bootstrap_factory=lambda p:NativeBundleReader(p,descriptor['index'],index_sha256=descriptor['index_sha256'],verify='local',library=args.library,bytecode_handoff=args.bytecode_handoff)
        bootstrap=StdlibSnapshotProvider(bootstrap_root,archive_factory=bootstrap_factory,
                                        manifest_sha256=descriptor['manifest_sha256'],host_root=descriptor['host_root'])
        bootstrap.install()
    from django.core.wsgi import get_wsgi_application
    application = get_wsgi_application()
    initialized = time.perf_counter()
    phase("framework_initialized",initialized)
    from django.core.checks import run_checks
    issues = run_checks()
    if issues:raise RuntimeError('Django system checks: '+str(issues))
    checked = time.perf_counter()
    phase("checks_finished",checked)
    from django.db import connection
    from django_fixture.models import Widget
    with connection.schema_editor() as editor:editor.create_model(Widget)
    Widget.objects.bulk_create([Widget(name='alpha'),Widget(name='beta')])
    seeded = time.perf_counter()
    phase("fixture_finished",seeded)
    body = request(application,'/widgets/','name=alpha')
    responded = time.perf_counter()
    phase("api_finished",responded)
    page = request(application,'/admin/login/',accept='text/html')
    finished = time.perf_counter();cpu_finished = time.process_time()
    phase("workload_finished",finished)
    bootstrap_stats=({'snapshot':bootstrap.snapshot,'modules':len(bootstrap.records),
                      'code_reads':bootstrap.module_reads,'source_reads':bootstrap.source_reads,
                      'preloaded':sorted(set(bootstrap.records)&preloaded_stdlib)} if bootstrap else {})
    if json.loads(body)!=[{'id':1,'name':'alpha'}]:raise RuntimeError('filtered ORM/API result differs')
    if not all(s in page for s in (b'Django administration',b'name="username"',b'name="password"')):
        raise RuntimeError('admin login template/widget output differs')
    import django
    from django.apps import apps
    if django.get_version()!=expected['versions']['django']:raise RuntimeError('wrong Django version')
    for package,version in expected['versions'].items():
        if args.scenario=='core' and package in ('rest_framework','django_filters'):continue
        module = __import__(package)
        actual = getattr(module,'__version__',None)
        if actual!=version:raise RuntimeError(f'version mismatch: {package} {actual} != {version}')
    modules = {n:m for n,m in sys.modules.items() if controlled(n)}
    origins = {}
    for name,module in modules.items():
        spec = module.__spec__
        if spec is None or not spec.origin or not spec.origin.startswith(root+os.sep):
            raise RuntimeError(f'dependency escaped input: {name}')
        if provider is not None and not isinstance(spec.loader,ModuleLoader):
            raise RuntimeError(f'dependency bypassed provider: {name}')
        origin = spec.origin[len(root)+1:]
        origins[name] = origin[:-1] if origin.endswith('.pyc') else origin
    for resource,digest in expected['resources'].items():
        package,relative = resource.split(':',1)
        data = importlib.resources.files(package).joinpath(*relative.split('/')).read_bytes()
        if hashlib.sha256(data).hexdigest()!=digest:raise RuntimeError('resource hash differs')
    if not executions or network:raise RuntimeError('missing execution audit or network attempted')
    native_timings = getattr(provider.archive,'native_timings',None) if provider else None
    opens = provider.archive_opens if provider else None
    reads = provider.module_reads if provider else None
    if provider and (opens!=1 or reads!=sum(executions.values())):
        raise RuntimeError('provider reopened or code read/execution counts differ')
    from django.template import engines
    template_loader = type(engines['django'].engine.template_loaders[0].loaders[0]).__module__
    app_count = len(apps.get_app_configs())
    bootstrap_origins={};inspection={}
    if bootstrap:
        for name,row in bootstrap.records.items():
            if name in sys.modules and name not in preloaded_stdlib:
                module=sys.modules[name]
                if not isinstance(module.__loader__,SnapshotLoader) or module.__spec__.origin!=row['origin']:
                    raise RuntimeError('stdlib snapshot bypassed: '+name)
                bootstrap_origins[name]=row['origin']
    if bootstrap or args.inspect_stdlib:
        import inspect
        import subprocess
        import email.message
        if bootstrap and not isinstance(subprocess.__loader__,SnapshotLoader):raise RuntimeError('subprocess was preloaded')
        if 'def run(' not in inspect.getsource(subprocess.run):raise RuntimeError('function source inspection failed')
        if 'class EmailMessage' not in inspect.getsource(email.message.EmailMessage):raise RuntimeError('class source inspection failed')
        inspected=inspect.getsource(subprocess)
        if inspected!=subprocess.__loader__.get_source('subprocess'):raise RuntimeError('module source inspection differs')
        inspection={'module':True,'function':True,'class':True}
        for name in ('_ssl','_sqlite3','_asyncio'):
            module=sys.modules.get(name)
            if module is not None and isinstance(module.__loader__,SnapshotLoader):raise RuntimeError('native extension loader replaced')
    connection.close()
    discovery_stats = ({'enumerations':provider.enumerations,'path_lookups':provider.path_lookups,
                        'path_misses':provider.path_misses} if isinstance(provider,IndexedPathProvider) else {})
    catalog_stats={'mode':getattr(provider.archive,'catalog_mode',None) if provider else None,
                   'entry_wrappers':getattr(provider.archive.entries,'created',len(provider.archive.entries)) if provider else 0,
                   'precomputed_tables':hasattr(provider.archive,'precomputed_modules') if provider else False}
    if provider and getattr(provider.archive,'native_provider',False):
        catalog_stats['native']=dict(zip(('entries','directories','modules','arena_used','arena_capacity','handle_bytes'),provider.archive.live_counts))
        catalog_stats['native'].update(module_queries=provider.archive.module_queries,names_returned=provider.archive.names_returned)
        catalog_stats['native']['open_phases']=provider.archive.native_open_phases
    handoff_counts={'dependencies':getattr(provider.archive,'code_loads',0) if provider else 0,
                    'stdlib':getattr(bootstrap.archive,'code_loads',0) if bootstrap else 0}
    phase("validation_finished")
    if provider:provider.close()
    if bootstrap:bootstrap.close()
    phase("providers_closed")
    rss = next(int(line.split()[1])*1024 for line in Path('/proc/self/status').read_text().splitlines()
               if line.startswith('VmHWM:'))
    result = dict(correct=True,bootstrap_seconds=_prepared-_entered,
                          initialization_seconds=initialized-begin,checks_seconds=checked-initialized,
                          ready_seconds=checked-begin,fixture_db_seconds=seeded-checked,
                          first_api_seconds=responded-seeded,first_admin_seconds=finished-responded,
                          workload_seconds=finished-begin,workload_cpu_seconds=cpu_finished-cpu_begin,
                          validation_seconds=time.perf_counter()-finished,peak_rss_bytes=rss,
                          module_count=len(origins),module_origins=origins,executed_files=executions,
                          app_count=app_count,template_loader=template_loader,api_result=json.loads(body),
                          admin_validated=True,resource_hashes=expected['resources'],network_events=network,
                          archive_opens=opens,module_reads=reads,native_timings=native_timings,
                          discovery=args.discovery,discovery_stats=discovery_stats,
                          stdlib_reader=args.stdlib_reader if bootstrap else 'host',stdlib_stats=bootstrap_stats,
                          stdlib_origins=bootstrap_origins,source_inspection=inspection,
                          bytecode_handoff=args.bytecode_handoff,code_handoff_counts=handoff_counts,
                          catalog_stats=catalog_stats)
    phase("result_built")
    output=json.dumps(result)
    phase("result_encoded")
    print(output,flush=_observer is not None)
    phase("result_flushed")


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--reader',choices=['directory-stock','directory','zipfile','python','odin'],required=True)
    parser.add_argument('--scenario',choices=['core','rest'],required=True)
    parser.add_argument('--expected',type=Path,required=True)
    parser.add_argument('--index',type=Path);parser.add_argument('--pin');parser.add_argument('--library',type=Path)
    parser.add_argument('--discovery',choices=['legacy','index'],default='legacy')
    parser.add_argument('--forbid-zip-fallback',action='store_true',help='untimed diagnostic guard')
    parser.add_argument('--stdlib-bundle',type=Path)
    parser.add_argument('--bytecode-handoff',choices=['bytes','view','native'],default='bytes')
    parser.add_argument('--catalog',type=Path)
    parser.add_argument('--catalog-pin')
    parser.add_argument('--catalog-mode',choices=['rebuilt','rows','tables','native','mapped','unified','compact'],default='rebuilt')
    parser.add_argument('--catalog-budget',type=int,default=16*1048576)
    parser.add_argument('--inspect-stdlib',action='store_true',help='equal post-workload source-inspection validation')
    parser.add_argument('--stdlib-reader',choices=['directory','python','odin'],default='odin')
    main(parser.parse_args())
    if _observer is not None:_observer.finish()
