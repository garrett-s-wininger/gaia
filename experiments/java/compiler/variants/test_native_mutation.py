#!/usr/bin/env python3
"""Regression: a retained native file manager must reread same-path/size/mtime edits."""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from run_variants import VM, AFFINITY, RUN_ENV, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', type=Path, required=True)
    parser.add_argument('--modules', type=Path, required=True)
    parser.add_argument('--native', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    prepared = json.loads(args.prepared.read_text())
    work = args.output
    work.mkdir(parents=True, exist_ok=True)
    source = work/'source'
    if source.exists():
        raise ValueError('use a fresh test output directory')
    shutil.copytree(prepared['source'], source)
    target = source/'picocli/CommandLine.java'
    initial = target.read_bytes()
    changed = initial.replace(b'String VERSION = "4.7.7"', b'String VERSION = "9.9.9"')
    assert len(initial) == len(changed) and initial != changed
    metadata = target.stat()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import benchmark
    fixture = dict(prepared, source=str(source))
    expected_a = benchmark.cli(fixture, 'mutation-before', True, output=work/'reference-a')
    target.write_bytes(changed)
    expected_b = benchmark.cli(fixture, 'mutation-after', True, output=work/'reference-b')
    target.write_bytes(initial)
    os.utime(target, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
    output = work/'native-output'
    output.mkdir()
    command = [str(args.native), '-Xms32m', '-Xmx768m', '-Djava.home='+prepared['jdk'],
               str(source), str(source), prepared['jdk'], str(output), str(args.modules)]
    proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, env=RUN_ENV,
                            preexec_fn=lambda:os.sched_setaffinity(0,AFFINITY))
    if proc.stdout.readline() != 'READY\n':
        raise RuntimeError(proc.stderr.read())
    results = []
    for index, expected in enumerate((expected_a, expected_b)):
        if index:
            target.write_bytes(changed)
            os.utime(target, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
            assert target.stat().st_size == metadata.st_size
            assert target.stat().st_mtime_ns == metadata.st_mtime_ns
        proc.stdin.write(('first' if not index else 'warm')+'\n')
        proc.stdin.flush()
        result = json.loads(proc.stdout.readline())
        if any(result.get(k) != expected[k] for k in ('classes','bytes','sha256')):
            raise AssertionError((result,expected))
        results.append(result)
    proc.stdin.write('stop\n')
    proc.stdin.flush()
    _, stderr = proc.communicate(timeout=30)
    if proc.returncode:
        raise RuntimeError(stderr)
    assert results[0]['sha256'] != results[1]['sha256']
    write(work/'validation.json',dict(ok=True,command=command,exit_code=proc.returncode,
                                    unchanged_path_size_mtime=True,results=results,stderr=stderr))
    print('same-path/size/mtime native source mutation passed')


if __name__ == '__main__':
    main()
