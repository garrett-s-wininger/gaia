"""Compare reconstructed versus pinned derived catalogs, including scaling."""
import os
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import marshal
from pathlib import Path
import random
import shutil
import statistics
import subprocess
import sys
import time
import zipfile

import benchmark
from native_benchmark import compile_extension
from precomputed_catalog import write_catalog
from precomputed_index import build_index


def catalogs(archive,index,pin,root):
    result={}
    for mode in ('rows','tables'):
        start=time.perf_counter();result[mode]=write_catalog(archive,index,pin,root/(mode+'.catalog'),mode=mode)
        result[mode]['producer_seconds']=time.perf_counter()-start
    return result


def render(data,path):
    lines=['# Precomputed catalog experiment','',f"Run: `{data['run_id']}`. Status: **{data['status']}**.",'',
           'Same freshly compiled native bridge, archive bytes, binary range index, local immutable '
           'admission and per-read CRC in every mode. Bytecode handoff stays bytes+slice. Only the '
           'dependency catalog changes in Django; its admitted stdlib reader remains reconstructed.','',
           '* rebuilt: export/decode native names, allocate every Python entry wrapper, derive module/package/child tables.',
           '* rows: read/hash/unmarshal a producer-built name-to-native-row map; entry wrappers are lazy; derive provider tables normally.',
           '* tables: read/hash/unmarshal rows plus producer-built module/package/child tables; adopt those tables and bind package paths to the mount.', '',
           'Derived metadata is experimental v1, SHA-pinned, bound to the exact binary-index digest '
           'and interpreter identity. It uses Python marshal as a local acceleration artifact, not '
           'an open portable protocol. Consumers still deserialize Python dictionaries/strings, and '
           'Odin still validates the original index and constructs its native name/directory buffers. '
           'This avoids Python reconstruction; it is not direct in-place table lookup.','',
           f"{data['trials']} randomized fresh processes per case after correctness warmups; warm filesystem cache. "
           'Input generation, catalog production and bridge compilation are outside consumer timing. '
           'Catalog file reading, hashing, unmarshalling and table adoption are inside setup/application '
           'timing. All cases share common harness imports.','',
           '| Workload | Catalog | Samples | Setup median ms | Ready/workload median ms | Process median ms | Peak RSS MiB | Entry wrappers |',
           '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for case in data['cases']:
        samples=case['samples']
        if not samples:continue
        def median(k):return statistics.median(s[k] for s in samples)*1000
        key='ready_seconds' if case['workload']=='django' else 'workload_seconds'
        setup='—' if case['workload']=='django' else f"{median('setup_seconds'):.3f}"
        wrappers=samples[0]['catalog_stats']['entry_wrappers'] if case['workload']=='django' else samples[0]['entry_wrappers']
        rss=statistics.median(s['peak_rss_bytes'] for s in samples)/1048576
        lines.append(f"| {case['workload']} | {case['mode']} | {len(samples)} | {setup} | {median(key):.3f} | {median('process_wall_seconds'):.3f} | {rss:.2f} | {wrappers} |")
    lines+=['','Django readiness includes initialization/system checks and the same actual REST/admin/SQLite '
            'workload follows; full process includes unchanged validation/source inspection. The scaling '
            'cases contain an expanding flat package with one initializer and N trivial bytecode leaves '
            'plus one resource. Each imports the same first 32 leaves (33 modules total). Timed setup '
            'includes mount, native reader open and complete provider indexing. Miss/resource/discovery '
            'validation runs afterward without importing additional leaves. This isolates catalog '
            'scaling rather than asserting these module counts are typical Python applications.','',
            '| Input | Mode | Catalog bytes | Producer ms |', '| --- | --- | ---: | ---: |']
    for fixture in data['inputs']:
        for mode,row in fixture['catalogs'].items():lines.append(
            f"| {fixture['label']} | {mode} | {row['bytes']} | {row['producer_seconds']*1000:.3f} |")
    lines+=['','The producer validates the pinned binary index and admitted local archive before deriving '
            'metadata. Existing module ambiguity rejection is preserved. Trusted immutable producer '
            'outputs are required, as with the existing sidecar. Catalogs add storage and an additional '
            'input read; smaller application runs may not recover that cost. Timing ranges and '
            'per-phase native timings remain in raw JSON.','']
    if data['status']=='complete':
        lines+=['## Setup phases and variability','',
                '| Workload | Mode | Native open ms | Export or load catalog ms | Provider/install remainder ms | Primary min–max ms |',
                '| --- | --- | ---: | ---: | ---: | ---: |']
        for case in data['cases']:
            samples=case['samples']
            native_open=statistics.median(s['native_timings']['native_open_seconds'] for s in samples)*1000
            catalog=statistics.median(s['native_timings']['catalog_seconds'] for s in samples)*1000
            if case['workload']=='django':remainder='—';key='ready_seconds'
            else:
                remainder=f"{statistics.median(s['setup_seconds']-sum(s['native_timings'].values()) for s in samples)*1000:.3f}"
                key='setup_seconds'
            lines.append(f"| {case['workload']} | {case['mode']} | {native_open:.3f} | {catalog:.3f} | {remainder} | "
                         f"{min(s[key] for s in samples)*1000:.3f}–{max(s[key] for s in samples)*1000:.3f} |")
        lines+=['','Native open includes original range-index verification and name/directory buffer construction. '
                'Catalog time includes export/decode/wrapper creation for rebuilt, or file read/hash/unmarshal '
                'and lazy-map setup for precomputed modes. The scaling remainder includes provider table '
                'derivation or adoption plus mounting/glue. It is a per-observation subtraction, not a '
                'sum/subtraction of independent medians. Django primary ranges show readiness; scaling '
                'ranges show setup. Interpreter/common harness initialization is outside setup and remains '
                'in full process; native extension load is separately retained in raw JSON.','']
        lines+=['## Interpretation','',
                '| Workload | Tables setup/ready reduction of medians | Tables faster in blocks |',
                '| --- | ---: | ---: |']
        for workload in dict.fromkeys(c['workload'] for c in data['cases']):
            cases={c['mode']:c['samples'] for c in data['cases'] if c['workload']==workload}
            key='ready_seconds' if workload=='django' else 'setup_seconds'
            baseline=cases['rebuilt'];tables=cases['tables']
            reduction=100*(1-statistics.median(s[key] for s in tables)/statistics.median(s[key] for s in baseline))
            wins=sum(t[key]<b[key] for b,t in zip(baseline,tables))
            lines.append(f'| {workload} | {reduction:.2f}% | {wins}/{len(baseline)} |')
        lines+=['','The precomputed table path has a clear benefit in the largest scaling fixture, '
                'but no Django startup win. Rows-only does not avoid wrapper construction overall: '
                'the unchanged provider calls infolist and materializes all wrappers while deriving '
                'tables. The table path avoids that pass, at the cost of a larger derived artifact '
                'and Python dictionary/string deserialization. Large-archive setup is still linear '
                'in available catalog size. This supports testing direct/lazy indexed lookup next, '
                'rather than treating deserialized precomputed tables as the final interface. '
                'Rebuilt remains the default.','']
    path.write_text('\n'.join(lines))


def run(args):
    parent=json.loads(args.inputs.read_text());original=next(c for c in parent['cases'] if c['variant']=='odin')
    expected=original['samples'][0];command=original['command'][:]
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    work=benchmark.HERE/'_work'/('catalog-'+run_id);work.mkdir(parents=True)
    args.output.mkdir(parents=True,exist_ok=True)
    library,build=compile_extension(work,args.odin);command[command.index('--library')+1]=str(library)
    def value(flag):return command[command.index(flag)+1]
    data=dict(run_id=run_id,parent_run=parent['run_id'],status='running',trials=args.trials,
              environment=benchmark.environment(work),build=build,inputs=[],cases=[])
    root=work/'django';root.mkdir();derived=catalogs(value('--root'),value('--index'),value('--pin'),root)
    data['inputs'].append(dict(label='django',archive=value('--root'),index=value('--index'),pin=value('--pin'),catalogs=derived))
    for mode in ('rebuilt','rows','tables'):
        cmd=command+['--catalog-mode',mode]
        if mode!='rebuilt':cmd+=['--catalog',derived[mode]['path'],'--catalog-pin',derived[mode]['sha256']]
        data['cases'].append(dict(workload='django',mode=mode,command=cmd,samples=[]))
    for count in args.modules:
        root=work/str(count);root.mkdir();archive=root/'scale.zip';index=root/'scale.index'
        start=time.perf_counter()
        header=importlib.util.MAGIC_NUMBER+b'\0'*12
        with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_STORED) as bundle:
            bundle.writestr('gaia_catalog_scale/__init__.pyc',header+marshal.dumps(compile('','gaia-scale:///__init__.py','exec')))
            for i in range(count):
                name=f'gaia_catalog_scale/module{i:06}'
                bundle.writestr(name+'.pyc',header+marshal.dumps(compile(f'VALUE={i}',name+'.py','exec')))
            bundle.writestr('gaia_catalog_scale/data.txt',b'resource')
        admitted=build_index(archive,index,encoding='binary');generation=time.perf_counter()-start
        derived=catalogs(archive,index,admitted['index_sha256'],root)
        plan=dict(library=str(library),archive=str(archive),index=str(index),pin=admitted['index_sha256'],modules=count,catalogs=derived)
        plan_path=root/'plan.json';benchmark.write_json(plan_path,plan)
        data['inputs'].append(dict(label=str(count),archive=str(archive),archive_bytes=archive.stat().st_size,
                                   index=str(index),index_bytes=index.stat().st_size,index_sha256=admitted['index_sha256'],
                                   generation_seconds=generation,catalogs=derived))
        for mode in ('rebuilt','rows','tables'):
            cmd=[sys.executable,'-I','-S','-B',str(benchmark.HERE/'catalog_worker.py'),'--plan',str(plan_path),'--mode',mode]
            data['cases'].append(dict(workload=str(count),mode=mode,command=cmd,samples=[]))
        print('prepared',count,flush=True)
    source_names=('native_loader.py','precomputed_catalog.py','persistent_zip_loader.py','indexed_path_loader.py',
                  'stdlib_snapshot.py','django_worker.py','catalog_worker.py','native/python_shim.c','native/python_api.odin')
    data['implementation_sha256']={n:hashlib.sha256((benchmark.HERE/n).read_bytes()).hexdigest() for n in source_names}
    def consume(case):
        try:sample=benchmark.consume(case['command'])
        except subprocess.CalledProcessError as error:raise RuntimeError(error.stdout+error.stderr) from error
        if not sample['correct']:raise ValueError('incorrect application')
        if case['workload']=='django':
            for key in ('module_origins','executed_files','api_result','resource_hashes','app_count','stdlib_stats',
                        'stdlib_origins','source_inspection'):
                if sample[key]!=expected[key]:raise ValueError('application differs: '+key)
            if sample['network_events'] or sample['code_handoff_counts']!={'dependencies':460,'stdlib':118}:
                raise ValueError('network/handoff differs')
            stats=sample['catalog_stats']
            if stats['mode']!=case['mode'] or stats['precomputed_tables']!=(case['mode']=='tables'):
                raise ValueError('catalog adoption bypass')
            if case['mode']=='tables' and stats['entry_wrappers']:raise ValueError('entry catalog reconstructed')
        else:
            if sample['imported']!=33 or sample['modules']!=int(case['workload']):raise ValueError('scale import count differs')
            if sample['precomputed_tables']!=(case['mode']=='tables'):raise ValueError('scale table bypass')
            if case['mode']=='tables' and sample['entry_wrappers']:raise ValueError('scale catalog reconstructed')
        return sample
    for case in data['cases']:
        case['warmup']=consume(case);print('verified',case['workload'],case['mode'],flush=True)
    def checkpoint():
        for case in data['cases']:
            if case['samples']:case['summary']=benchmark.summarize(case['samples'])
        benchmark.write_json(args.output/'results.json',data);render(data,args.output/'REPORT.md')
    checkpoint();rng=random.Random(20261102)
    for trial in range(args.trials):
        cases=data['cases'].copy();rng.shuffle(cases)
        for case in cases:case['samples'].append(consume(case))
        checkpoint();print(f'catalog trials {trial+1}/{args.trials}',flush=True)
    data['status']='complete';checkpoint()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,default=benchmark.HERE/'_work/runs/stdlib/results.json')
    parser.add_argument('--output',type=Path,default=benchmark.HERE/'_work/runs/catalog')
    parser.add_argument('--trials',type=int,default=15)
    parser.add_argument('--modules',type=int,nargs='+',default=[1024,16384,131072])
    parser.add_argument('--odin',default=shutil.which(os.environ.get("ODIN", "odin")) or os.environ.get("ODIN", "odin"))
    args=parser.parse_args()
    if args.trials<1 or any(n<32 for n in args.modules):parser.error('positive trials and at least 32 modules required')
    run(args)
