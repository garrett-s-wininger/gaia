#!/usr/bin/env python3
"""Complete-target JVM variants with separately charged setup and normal shutdown."""
import argparse
import hashlib
import json
import os
import random
import resource
import statistics
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
AFFINITY = sorted(os.sched_getaffinity(0))[:4]
RUN_ENV = {k:v for k,v in os.environ.items() if k not in ('JAVA_TOOL_OPTIONS','JDK_JAVA_OPTIONS','_JAVA_OPTIONS','CLASSPATH')}
VM = ['-XX:-UsePerfData', '-Xms32m', '-Xmx768m', '-XX:ActiveProcessorCount=4']


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def pins(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*.java'))}


def session(java, app, prepared, flags, requests, output):
    cmd = [str(java), *VM, *flags, '-cp', str(app), 'CompilerHarness', 'batch', '1',
           prepared['source'], prepared['compilation_classpath'], prepared.get('target_sdk',prepared['jdk']),
           str(output), 'false', prepared['second_source']]
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter()
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, env=RUN_ENV,
                            preexec_fn=lambda: os.sched_setaffinity(0, AFFINITY))
    ready = proc.stdout.readline()
    ready_at = time.perf_counter()
    if not ready.startswith('READY '):
        raise RuntimeError((cmd, ready, proc.stderr.read()))
    rows = []
    for request in requests:
        begin = time.perf_counter()
        proc.stdin.write(request + '\n')
        proc.stdin.flush()
        line = proc.stdout.readline()
        end = time.perf_counter()
        try:
            row = json.loads(line)
        except Exception:
            raise RuntimeError((line, proc.stderr.read()))
        row['wall_seconds'] = end - begin
        rows.append(row)
    proc.stdin.write('stop\n')
    proc.stdin.flush()
    _, stderr = proc.communicate(timeout=30)
    end = time.perf_counter()
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    if proc.returncode:
        raise RuntimeError((proc.returncode, stderr))
    return dict(command=cmd, exit_code=proc.returncode, cpu_affinity=AFFINITY, ready_seconds=ready_at-start,
                elapsed_seconds=end-start,
                cpu_seconds=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
                ready=json.loads(ready[6:]), requests=rows, stderr=stderr)


def cli_reference(prepared, target, output):
    sys.path.insert(0,str(BASE))
    import benchmark
    output.mkdir(parents=True, exist_ok=True)
    source = Path(prepared['second_source'] if target else prepared['source'])
    files = sorted((source/n for n in prepared['source_files']), key=lambda p:-p.stat().st_size)
    flags = ['-encoding','UTF-8','-g:none','-proc:none','-implicit:none','-source','25','-target','25',
             '--system',prepared.get('target_sdk',prepared['jdk']),'-classpath',prepared['compilation_classpath'],
             '-sourcepath',str(Path(prepared['source'])/'empty-sourcepath'),'-d',str(output)]
    command = [str(Path(prepared['jdk'])/'bin/javac'), *['-J'+v for v in VM], *flags, *map(str,files)]
    result = subprocess.run(command,capture_output=True,text=True,env=RUN_ENV)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return dict(command=command,diagnostics=result.stderr,**benchmark.hashes(output))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--trials', type=int, default=3)
    parser.add_argument('--warm-count', type=int, default=8)
    parser.add_argument('--java', type=Path)
    parser.add_argument('--extra', action='append', default=[])
    parser.add_argument('--single', action='store_true')
    parser.add_argument('--config', type=Path)
    args = parser.parse_args()
    if args.trials < 1 or not 2 <= args.warm_count <= 32:
        parser.error('positive trials and 2..32 warm requests required')
    prepared = json.loads(args.prepared.read_text())
    args.output.mkdir(parents=True, exist_ok=True)
    java = args.java or Path(prepared['jdk']) / 'bin/java'
    variants = {'default': [], 'serial': ['-XX:+UseSerialGC'],
                'parallel': ['-XX:+UseParallelGC'], 'tier1': ['-XX:TieredStopAtLevel=1']}
    if args.single:
        variants = {'configured': args.extra}
    if args.config:
        variants = json.loads(args.config.read_text())
    data = dict(status='running', schema_version=1, prepared=prepared,
                java_version=subprocess.run([java, '-version'], capture_output=True, text=True).stderr,
                source_pins=pins(Path(prepared['source'])), warm_count=args.warm_count, cases=[])
    sys.path.insert(0, str(BASE))
    import benchmark
    references = [cli_reference(prepared, i, args.output / 'reference-pair' / ('target'+str(i)))
                  for i in (0, 1)]
    expected = {k: references[0][k] for k in ('classes', 'bytes', 'sha256')}
    pair_expected = benchmark.hashes(args.output / 'reference-pair')
    data['references'] = references
    data['pair_reference'] = pair_expected
    requests = ['first', *['warm'+str(i) for i in range(args.warm_count)],
                'pair-edit', 'check', 'fail', 'recovery']
    rng = random.Random(8741)
    for block in range(args.trials):
        names = list(variants)
        rng.shuffle(names)
        for name in names:
            fresh = session(java, prepared['app'], prepared, variants[name], ['first'],
                            args.output / (name+'-fresh'))
            row = session(java, prepared['app'], prepared, variants[name], requests,
                          args.output / name)
            for item in fresh['requests'] + row['requests']:
                if item.get('token') == 'fail':
                    if item.get('ok') is not False:
                        raise ValueError('accepted invalid source')
                elif 'versions' in item:
                    if item['versions'] != prepared['target_versions']:
                        raise ValueError('constant edit/consumer differs')
                else:
                    reference = pair_expected if item.get('targets') == 2 else expected
                    if any(item.get(k) != reference[k] for k in ('classes', 'bytes', 'sha256')):
                        raise ValueError((name, item, reference))
            data['cases'].append(dict(block=block, variant=name, fresh=fresh, **row))
            write(args.output / 'results.json', data)
    summaries = {}
    for name in variants:
        rows = [r for r in data['cases'] if r['variant'] == name]
        summaries[name] = {k: statistics.median(r[k] for r in rows)
                           for k in ('ready_seconds', 'elapsed_seconds', 'cpu_seconds')}
        summaries[name].update(
            fresh_ms=statistics.median(r['fresh']['elapsed_seconds']*1000 for r in rows),
            first_ms=statistics.median(r['requests'][0]['wall_seconds']*1000 for r in rows),
            late_warm_ms=statistics.median(r['requests'][i]['wall_seconds']*1000
                                          for r in rows for i in range(max(1, args.warm_count-2), args.warm_count+1)),
            rss_bytes=statistics.median(r['requests'][args.warm_count]['rss_bytes'] for r in rows))
    data['status'] = 'complete'
    data['summary'] = summaries
    write(args.output / 'results.json', data)
    print(json.dumps(summaries, indent=2))


if __name__ == '__main__':
    main()
