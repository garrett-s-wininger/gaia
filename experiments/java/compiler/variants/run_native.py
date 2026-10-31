#!/usr/bin/env python3
"""Normal native/JVM endpoint lifecycles with identical materialized class delivery."""
import argparse
import json
import os
import random
import resource
import statistics
import subprocess
import time
from pathlib import Path
from run_variants import VM, write, AFFINITY, RUN_ENV


def process_cpu(pid):
    fields = Path('/proc/'+str(pid)+'/stat').read_text().rpartition(') ')[2].split()
    return (int(fields[11])+int(fields[12]))/os.sysconf('SC_CLK_TCK')


def run(command, requests):
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    begin = time.perf_counter()
    process = subprocess.Popen(command, text=True, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=RUN_ENV,
                               preexec_fn=lambda: os.sched_setaffinity(0, AFFINITY))
    ready = process.stdout.readline()
    at = time.perf_counter()
    if ready != 'READY\n':
        raise RuntimeError((ready, process.stderr.read()))
    rows = []
    for request in requests:
        cpu_before = process_cpu(process.pid)
        start = time.perf_counter()
        process.stdin.write(request+'\n')
        process.stdin.flush()
        line = process.stdout.readline()
        if not line:
            raise RuntimeError((process.returncode, process.stderr.read()))
        row = json.loads(line)
        row.update(request=request, wall_seconds=time.perf_counter()-start,process_cpu_seconds=process_cpu(process.pid)-cpu_before)
        for status in Path('/proc/'+str(process.pid)+'/status').read_text().splitlines():
            if status.startswith('VmRSS:'):
                row['rss_bytes'] = int(status.split()[1])*1024
        rows.append(row)
    process.stdin.write('stop\n')
    process.stdin.flush()
    _, stderr = process.communicate(timeout=30)
    end = time.perf_counter()
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    if process.returncode:
        raise RuntimeError((process.returncode, stderr))
    return dict(command=command, exit_code=process.returncode, cpu_affinity=AFFINITY, ready_seconds=at-begin,
                elapsed_seconds=end-begin,
                cpu_seconds=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
                requests=rows, stderr=stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', type=Path, required=True)
    parser.add_argument('--native', type=Path, required=True)
    parser.add_argument('--quick-native', type=Path)
    parser.add_argument('--references', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--trials', type=int, default=3)
    parser.add_argument('--warm-count', type=int, default=12)
    parser.add_argument('--modules', type=Path)
    args = parser.parse_args()
    if args.trials < 1 or not 3 <= args.warm_count <= 32:
        parser.error('positive trials and 3..32 warm requests required')
    prepared = json.loads(args.prepared.read_text())
    references = json.loads(args.references.read_text())
    work = args.output
    work.mkdir(parents=True, exist_ok=True)
    data = dict(status='running', schema_version=1, cases=[], references=references,
                prepared=prepared, warm_count=args.warm_count)
    rng = random.Random(7163)
    engines = ['jvm', 'jvm-modules', 'native'] if args.modules else ['jvm', 'native']
    if args.quick_native:
        engines.append('native-quick')
    for block in range(args.trials):
        order = list(engines)
        rng.shuffle(order)
        for engine in order:
            output = work / (engine+str(block))
            (output/'broken').mkdir(parents=True, exist_ok=True)
            (output/'broken/Broken.java').write_text('class Broken { this is invalid; }\n')
            executable = args.quick_native if engine == 'native-quick' else args.native
            prefix = ([str(executable), '-Xms32m', '-Xmx768m', '-Djava.home='+prepared['jdk']]
                      if engine.startswith('native') else
                      [str(Path(prepared['jdk'])/'bin/java'), *VM, '-cp', prepared['app'], 'NativeCompiler'])
            command = [*prefix, prepared['source'], prepared['second_source'], prepared['jdk'], str(output)]
            if args.modules and engine != 'jvm':
                command.append(str(args.modules))
            fresh = run(command, ['first'])
            resident = run(command, ['first', *['warm']*args.warm_count, 'edit', 'fail', 'warm'])
            for row in fresh['requests'] + resident['requests']:
                if row['request'] == 'fail':
                    if row['ok']:
                        raise ValueError('accepted invalid source')
                else:
                    reference = references['1' if row['request'] == 'edit' else '0']
                    if any(row.get(k) != reference[k] for k in ('classes', 'bytes', 'sha256')):
                        raise ValueError(('bytecode differs', engine, row, reference))
            data['cases'].append(dict(block=block, engine=engine, fresh=fresh, resident=resident))
            write(work/'results.json', data)
    data['summary'] = {}
    for engine in engines:
        rows = [r for r in data['cases'] if r['engine'] == engine]
        data['summary'][engine] = dict(
            fresh_ms=statistics.median(r['fresh']['elapsed_seconds']*1000 for r in rows),
            first_ms=statistics.median(r['resident']['requests'][0]['wall_seconds']*1000 for r in rows),
            late_warm_ms=statistics.median(r['resident']['requests'][i]['wall_seconds']*1000
                                          for r in rows for i in range(args.warm_count-2, args.warm_count+1)),
            cpu_seconds=statistics.median(r['resident']['cpu_seconds'] for r in rows),
            rss_bytes=statistics.median(r['resident']['requests'][args.warm_count]['rss_bytes'] for r in rows))
    data['status'] = 'complete'
    write(work/'results.json', data)
    print(json.dumps(data['summary'], indent=2))


if __name__ == '__main__':
    main()
