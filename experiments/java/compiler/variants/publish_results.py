#!/usr/bin/env python3
"""Publish compact reviewer evidence; full observations remain ignored."""
import argparse
import hashlib
import json
import os
import platform
import shutil
import statistics
from pathlib import Path
from run_variants import VM, AFFINITY, write

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    work, output = args.data, args.output
    output.mkdir(parents=True, exist_ok=True)
    summary, validation, sources = {}, {}, {}
    raw_files = []
    for name in ('flags', 'head', 'epsilon'):
        source = work/(name+'-main')/'results.json'
        data = json.loads(source.read_text())
        assert data['status'] == 'complete'
        target = output/name/'results.json'
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(source, target)
        raw_files.append(target)
        trace = {}
        key = 'engine'
        for engine in data['summary']:
            rows = [r for r in data['cases'] if r[key] == engine]
            trace[engine] = [statistics.median(r['resident']['requests'][i]['wall_seconds']*1000 for r in rows)
                             for i in range(data['warm_count']+1)]
        summary[name] = dict(cases=data['summary'], warm_trace_ms=trace,
                             blocks=len(set(r['block'] for r in data['cases'])),
                             raw_sha256=sha(target))
        good, bad, consumers = 0, 0, 0
        for row in data['cases']:
            requests = row['fresh']['requests'] + row['resident']['requests']
            for request in requests:
                if 'versions' in request:
                    assert request['versions'] == data['prepared']['target_versions']
                    consumers += 1
                elif request.get('ok') is False:
                    assert request.get('token', request.get('request')) == 'fail'
                    bad += 1
                else:
                    assert request['ok'] is True
                    good += request.get('targets',1)
        validation[name] = dict(cases=len(data['cases']), successful_complete_targets=good,
                                rejected_invalid_source=bad, paired_consumers=consumers,
                                normal_process_exit=True, cli_bytecode_guards=True)
        p = data['prepared']
        sources[name] = {k:p[k] for k in ('source_sha256','second_source_sha256','jdk_modules_sha256','target_sdk_modules_sha256','harness_sha256','native_endpoint_source_sha256','app_sha256') if k in p}
        sources[name]['compiled_app_sha256'] = sha(Path(p['app']))
    diagnostics = {}
    for relative in (
        'native/runtime-boundaries.json', 'native/build.json',
        'native-sdk/training.json', 'native-sdk/build.json',
        'native-sdk-o2/build.json', 'platform-sdk/manifest.json',
        'sdk-native-probes/probes.json', 'sdk-final-probes/probes.json', 'native-correctness-serial.json', 'native-correctness-epsilon.json', 'convergence32.json', 'endpoint-probes.json',
        'native-mutation/validation.json', 'native-consumers.json', 'gc-availability.json', 'effective-flags.json', 'epsilon-growth.json', 'instrumented-runtime-boundaries.json', 'instrumented-native-smoke.json', 'native-final-serial/build.json', 'native-final-epsilon/build.json',
        'leyden-cache/training.json', 'leyden-cache/code-setup.json',
        'leyden-cache/no-code-setup.json', 'leyden-cache/diagnostics.json'):
        path = work/relative
        if path.exists():
            diagnostics[relative] = json.loads(path.read_text())
    for relative in ('native/build.stdout','native-sdk/build.stdout','native-sdk-o2/build.stdout','native-final-serial/build.stdout','native-final-epsilon/build.stdout',
                     'leyden-cache/diagnostic-code.log','leyden-cache/diagnostic-no-code.log'):
        path = work/relative
        if path.exists():
            diagnostics[relative] = path.read_text()
    assert diagnostics['native-mutation/validation.json']['ok']
    assert all(r['returncode'] == 0 for r in diagnostics['native-consumers.json'])
    validation['head']['compiled_method_cache_used'] = diagnostics.get('leyden-cache/diagnostics.json',{}).get('code_usable',False)
    validation['head'].update(same_path_size_mtime_edit=True,
                                independent_jvm_consumers=len(diagnostics['native-consumers.json']),
                                module_readability_exports_probes=True)
    target = output/'diagnostics'/'results.json'
    target.parent.mkdir(exist_ok=True)
    write(target,diagnostics)
    raw_files.append(target)
    summary['convergence32']={k:v['summary'] for k,v in diagnostics['convergence32.json']['cases'].items()}
    growth=diagnostics['epsilon-growth.json'];summary['epsilon_growth']=dict(successful_compilations=growth['successful_compilations'],exit_code=growth['exit_code'],rss_bytes=[r.get('rss_bytes') for r in growth['requests']])
    write(output/'summary.json',summary)
    frozen=json.loads((work/'formal-sources/pins.json').read_text())
    checked_sources=('NativeCompiler.java','measure_endpoint.py','run_native.py','run_variants.py','prepare.py','configure_endpoint.py')
    for name in checked_sources:
        assert sha(HERE/name)==frozen[name],name
    validation['source_integrity']=dict(frozen_primary_sources_verified=True,files=list(checked_sources))
    write(output/'validation.json',validation)
    cpu = next((line.split(':',1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')), '')
    runtime_fixtures=json.loads((work/'runtime-fixtures.json').read_text())
    runtime_pins={k:{f:v[f] for f in ('jdk_modules_sha256','target_sdk_modules_sha256','app_sha256') if f in v} for k,v in runtime_fixtures.items()}
    provenance = dict(exploratory_quick_source_sha256=sha(work/'quick-build-sources/NativeCompiler.java') if (work/'quick-build-sources/NativeCompiler.java').exists() else None,runtime_pins=runtime_pins,measurement_source_pins=json.loads((work/'formal-sources/pins.json').read_text()),schema_version=1, platform=platform.platform(),cpu_model=cpu,
                      logical_cpus=os.cpu_count(),runtime_cpu_affinity=AFFINITY,vm_flags=VM,
                      source_pins={str(p.relative_to(REPO)):sha(p) for p in sorted(HERE.iterdir()) if p.suffix in ('.py','.java')},
                      toolchains=json.loads((HERE/'toolchains.json').read_text()),
                      inputs=sources,
                      scope='Fresh process with warm host page cache. All final runtimes use one instrumented JavaCompiler endpoint, identical file delivery and explicit SDK module representation. Cache/build/SDK setup and external JVM consumers are separate. Epsilon short epochs have exactly two full compilations per resident lifecycle under the same heap cap.')
    write(output/'provenance.json',provenance)
    manifest_path=REPO/'research/evidence.json'
    manifest=json.loads(manifest_path.read_text())
    for path in raw_files:
        relative=path.relative_to(REPO).as_posix()
        manifest['artifacts']=[x for x in manifest['artifacts'] if x['path']!=relative]
        manifest['artifacts'].append(dict(path=relative,bytes=path.stat().st_size,sha256=sha(path)))
    manifest['artifacts'].sort(key=lambda x:x['path'])
    write(manifest_path,manifest)
    index_path=REPO/'research/compiler/jvm/experiments.json'
    index=json.loads(index_path.read_text())
    for name in ('flags','head','epsilon'):
        identity='JVM-COMPILER-'+name.upper()
        index['experiments']=[x for x in index['experiments'] if x['id']!=identity]
        base=output.relative_to(REPO).as_posix()
        index['experiments'].append(dict(id=identity,status='measured-with-cli-output-and-lifecycle-guards',report=base+'/REPORT.md',raw=base+'/'+name+'/results.json',summary=base+'/summary.json',validation=base+'/validation.json',provenance=base+'/provenance.json',findings='research/compiler/jvm/findings.md'))
    write(index_path,index)
    print(json.dumps(validation,indent=2))


if __name__ == '__main__':
    main()
