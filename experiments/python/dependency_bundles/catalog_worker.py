"""Mount a catalog, then import a fixed 32 leaves from an expanding archive."""
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
import importlib
import importlib.resources
import json
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parent))
from bundle_access import BundleResources
from indexed_path_loader import IndexedPathProvider
from native_loader import NativeBundleReader
_prepared=time.perf_counter()
phase("common_prepared",_prepared)


def main(args):
    phase("main_entered")
    plan=json.loads(args.plan.read_text());options={}
    if args.mode not in ('rebuilt','native'):
        catalog=plan['catalogs'][args.mode]
        options=dict(catalog_path=catalog['path'],catalog_sha256=catalog['sha256'])
    provider=IndexedPathProvider(plan['archive'],archive_factory=lambda p:NativeBundleReader(
        p,plan['index'],index_sha256=plan['pin'],library=args.library or plan['library'],verify='local',
        catalog_mode=args.mode,catalog_budget=args.budget,bytecode_handoff='bytes',**options),resource_factory=BundleResources)
    start=time.perf_counter();cpu=time.process_time()
    phase("workload_begin",start)
    provider.install();reader=provider.open_archive();opened=time.perf_counter()
    phase("catalog_opened",opened)
    values=[importlib.import_module(f'gaia_catalog_scale.module{i:06}').VALUE for i in range(32)]
    finished=time.perf_counter();cpu_finished=time.process_time()
    phase("workload_finished",finished)
    wrappers=getattr(reader.entries,'created',len(reader.entries))
    native_stats=dict(zip(('entries','directories','modules','arena_used','arena_capacity','handle_bytes'),reader.live_counts)) if args.mode in ('native','mapped','unified','compact') else {}
    if args.mode in ('native','mapped','unified','compact'):native_stats['open_phases']=reader.native_open_phases
    native_stats.update(module_queries=reader.module_queries,names_returned=reader.names_returned)
    try:
        if values!=list(range(32)):raise ValueError('module results differ')
        if provider.module_reads!=33 or reader.code_loads!=33:raise ValueError('code load count differs')
        if len(provider.modules)!=plan['modules']+1:raise ValueError('module table differs')
        if provider.find_spec('gaia_catalog_scale.missing') is not None:raise ValueError('owned miss differs')
        package=importlib.import_module('gaia_catalog_scale')
        if importlib.resources.files(package).joinpath('data.txt').read_bytes()!=b'resource':raise ValueError('resource differs')
        children=provider.children[provider.archive_path+'/gaia_catalog_scale']
        if len(children)!=plan['modules'] or ('module000000',False) not in children:raise ValueError('discovery differs')
        if (f"module{plan['modules']-1:06}",False) not in children:raise ValueError('discovery boundary differs')
        phase("validation_finished")
        result=dict(correct=True,mode=args.mode,modules=plan['modules'],imported=33,
                              setup_seconds=opened-start,imports_seconds=finished-opened,
                              workload_seconds=finished-start,workload_cpu_seconds=cpu_finished-cpu,
                              native_timings=reader.native_timings,entry_wrappers=wrappers,
                              native_catalog_stats=native_stats,
                              peak_rss_bytes=next(int(line.split()[1])*1024 for line in Path('/proc/self/status').read_text().splitlines() if line.startswith('VmHWM:')),
                              precomputed_tables=hasattr(reader,'precomputed_modules'))
        phase("result_built")
        output=json.dumps(result)
        phase("result_encoded")
        print(output,flush=_observer is not None)
        phase("result_flushed")
    finally:
        provider.close()
        phase("providers_closed")


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--mode',choices=['rebuilt','rows','tables','native','mapped','unified','compact'],required=True)
    parser.add_argument('--library',type=Path)
    parser.add_argument('--budget',type=int,default=16*1048576)
    main(parser.parse_args())
    if _observer is not None:_observer.finish()
