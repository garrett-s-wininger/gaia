#!/usr/bin/env python3
"""Fresh-process naive/trail scaling and the original offline pip startup case.

Reuses admitted artifacts and existing loader inputs. No network or installation.
Startup workers solve once; scale workers solve twice. Outputs are checkpointed
after each observation so long uncached runs remain inspectable and recoverable.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import benchmark


HERE = Path(__file__).resolve().parent


def request_for(data, name):
    case = next(c for c in data['cases'] if c['dataset'] == name)
    return json.loads(Path(case['command'][case['command'].index('--request')+1]).read_text())


def consume(command, timeout):
    begin = time.perf_counter()
    child = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if child.returncode:
        raise RuntimeError(child.stdout + child.stderr)
    result = json.loads(child.stdout)
    # Invocation boundary includes decoding the returned validation JSON. Keep
    # the historical metric name, but disclose this parent-side work in reports.
    result['process_wall_seconds'] = time.perf_counter()-begin
    if not result['correct']:
        raise RuntimeError('worker validation failed')
    return result


def validate_pair(cases):
    signatures = {}
    pip_reports = set()
    pip_executions = {}
    for case in cases:
        for sample in case['samples']:
            if case['kind'] == 'solver':
                if not sample['complete'] or sample['status'] != 'solved':
                    raise RuntimeError('incomplete or unsolved comparison')
                selected = sample['passes'][0]['selected']
                names = sorted([row[0], row[1]] for row in selected)
                signature = (sample['snapshot'], sample['target'], sample['selection_sha256'])
                key = ('artifacts', case['dataset'])
                previous = signatures.setdefault(key, signature)
                if previous != signature:
                    raise RuntimeError('solver snapshot/target/selection changed')
                for solve in sample['passes']:
                    if solve['status'] != 'solved' or benchmark.solver.digest(solve['selected']) != sample['selection_sha256']:
                        raise RuntimeError('repeated solve changed result')
            else:
                names = sample['selected']
                if sample['network_events'] or not sample['backtracked']:
                    raise RuntimeError('pip offline/backtracking check failed')
                pip_reports.add(sample['report_sha256'])
                if len(pip_reports) > 1:
                    raise RuntimeError('pip reports differ')
                execution = sorted(sample['executed_files'].items())
                previous = pip_executions.setdefault(case['mode'], execution)
                if execution != previous:
                    raise RuntimeError('pip executed different code')
            key = ('versions', case['dataset'])
            previous = signatures.setdefault(key, names)
            if previous != names:
                raise RuntimeError('selected versions differ between pip and solver')


def render(data, path):
    lines = ['# Naive baseline and original startup comparison', '',
             f"Run: `{data['run_id']}`. Status: **{data['status']}**.", '',
             'Warm filesystem cache; each observation starts a fresh isolated Python process. '
             'Existing artifact snapshots, exact queries and pip source/bytecode/native loader inputs '
             'are reused. No network, installation, new admission or native rebuild. '
             'The solver controls have identical lexical policy and artifact selection. '
             'The uncached reference is our deliberately cache-free provider, not pip behavior.', '',
             '## Larger graph: uncached reference versus trail', '',
             f"{data['scaling_trials']} randomized trials per case; two fresh solves per process, "
             'with session reuse only on the second. No extra untimed solver warmup. '
             'Medians, ms. First use is the per-observation sum of source open and first solve. '
             'Parsing/library imports precede the solve clock; complete process wall includes both '
             'solves, validation, output, shutdown and parent result decoding, so it is not a '
             'one-shot startup metric.', '',
             '| Leaves | Variant | Samples | Open | First solve | Open + first | Second solve |',
             '| ---: | --- | ---: | ---: | ---: | ---: | ---: |']
    for case in data['scaling']:
        if not case['samples']:continue
        s = benchmark.measurements.summarize(case['samples'])
        lines.append(f"| {case['dataset'].split('-')[1]} | {case['variant']} | {len(case['samples'])} | " +
                     ' | '.join(f"{s[k]['median']*1000:.3f}" for k in
                                ('open_seconds','first_solve_seconds','first_use_seconds','reused_solve_seconds')) + ' |')
    lines += ['', '## Original startup: identical 22-wheel / 12-package case', '',
              f"{data['startup_trials']} randomized trials per case. Each solver process solves exactly once. "
              'Each real pip process executes the original offline dry-run CLI once, using the corrected '
              'worker that opens its input provider after the workload timer starts. '
              'Pip source and bytecode execute the same implementation. The Odin reader accelerates '
              'code-byte access; the interpreter and pip remain Python. Medians, ms.', '',
              '| Consumer | Code input | Reader / variant | Samples | Complete invocation | Command / open + solve | Harness/library preparation |',
              '| --- | --- | --- | ---: | ---: | ---: | ---: |']
    for case in data['startup']:
        if not case['samples']:continue
        s = benchmark.measurements.summarize(case['samples'])
        solver = case['kind'] == 'solver'
        workload = 'first_use_seconds' if solver else 'workload_seconds'
        setup = 'bootstrap_seconds' if solver else 'setup_seconds'
        lines.append(f"| {'Reference solver' if solver else 'Real pip dry-run'} | {case.get('mode','host imports')} | "
                     f"{case['variant']} | {len(case['samples'])} | " +
                     ' | '.join(f"{s[k]['median']*1000:.3f}" for k in ('process_wall_seconds',workload,setup)) + ' |')
    lines += ['', 'The two last columns have different scopes: the pip command includes importing its '
              'implementation, configuration, discovery/preparation, resolution and report generation; '
              'solver open + solve starts after importing its smaller dependency set. Complete process '
              'wall includes interpreter startup, setup, validation, serialization, cleanup and parent '
              'JSON result decoding in both harnesses. Validation/reporting work differs, so ratios compare these specific '
              'commands, not equivalent pip replacements. Independent column medians need not add.', '',
              'The reference worker imports benchmark/fixture helpers as well as packaging/resolvelib. '
              'Its preparation time is not pure interpreter startup or a minimal-runtime floor. '
              'The earlier approximately 298 ms result was a separate synthetic 2,072-module loading '
              'process, not a dependency solve; see the [persistent-loader report]'
              '(../../../dependency_bundles/results/persistent/REPORT.md). '
              'The fresh real-pip rows above revisit the later representative startup experiment.', '',
              'All consumers must select the same versions on the original case. The two solver controls '
              'also match immutable artifact IDs, snapshot and target. The original wheels are hashed '
              'outside timing to verify that pip and the solver use identical bytes. Pip checks origins, '
              'code/resource reads, report hash, backtracking and zero network events. Solver closures '
              'are independently validated outside solve timing but inside complete process wall.', '',
              'Admission/catalog creation is a producer cost carried forward from prior runs, excluded '
              'from all consumer times here. Real pip is measured only on its original small graph. '
              'The larger-graph speedups must not be presented as pip speedups or pure startup wins. '
              'There is no native solver, installer replacement or cold-cache claim.', '']
    path.write_text('\n'.join(lines))


def run(args):
    original = json.loads(args.original.read_text())
    scaling = json.loads(args.scaling.read_text())
    pip = json.loads(args.pip.read_text())
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    work = HERE/'_work'/('startup-'+run_id)
    work.mkdir(parents=True)
    args.output.mkdir(parents=True, exist_ok=True)
    data = dict(run_id=run_id, status='running', scaling_trials=args.scaling_trials,
                startup_trials=args.startup_trials, worker_timeout_seconds=args.timeout,
                environment=benchmark.measurements.environment(work),
                parent_runs=dict(original=original['run_id'], scaling=scaling['run_id'], pip=pip['run_id']),
                libraries=original['libraries'], scaling=[], startup=[], input_checks={},
                invocation_includes_parent_json_decode=True)
    if scaling['target'] != original['target']:
        raise ValueError('original/scaling targets differ')
    def solver_case(source, name, variant, passes):
        request = request_for(source, name)
        request['variant'] = variant
        path = work/f'{name}-{variant}-{passes}.json'
        benchmark.measurements.write_json(path, request)
        return dict(kind='solver',dataset=name,variant=variant,passes=passes,samples=[],
                    command=[sys.executable,'-I','-S','-B',str(HERE/'benchmark.py'),'--worker',
                             '--request',str(path),'--passes',str(passes)])
    for width in args.widths:
        for variant in ('wheel-uncached','catalog-trail'):
            data['scaling'].append(solver_case(scaling,f'wide-{width}',variant,2))
    for variant in ('wheel-uncached','catalog-trail'):
        data['startup'].append(solver_case(original,'original-22',variant,1))
    for old in pip['cases']:
        if old['workload'] != 'pip' or old['reader'] not in ('directory','python-local','odin-local'):
            continue
        data['startup'].append(dict(kind='pip', dataset='original-22',mode=old['mode'],
                                    variant=old['reader'],command=old['command'],samples=[]))
    request = request_for(original,'original-22')
    inventory = json.loads(Path(request['admission']['inputs']['inventory']['path']).read_text())
    # Compare physical wheel bytes, not just package/version labels.
    pip_case = next(c for c in data['startup'] if c['kind']=='pip')
    command = pip_case['command']
    wheelhouse = Path(command[command.index('--wheelhouse')+1])
    pip_bytes = sorted(hashlib.sha256(p.read_bytes()).hexdigest() for p in wheelhouse.glob('*.whl'))
    solver_bytes = sorted(row['id'] for row in inventory['artifacts'])
    if pip_bytes != solver_bytes:
        raise RuntimeError('original pip and solver wheel bytes differ')
    data['input_checks'] = dict(original_artifact_ids=solver_bytes, original_wheel_bytes_identical=True,
                                original_snapshot=request['admission']['snapshot'], target=original['target'],
                                pip_setup_timing_corrected=True)
    def checkpoint():
        for group in ('startup','scaling'):
            for case in data[group]:
                if case['samples']:case['summary']=benchmark.measurements.summarize(case['samples'])
        benchmark.measurements.write_json(args.output/'results.json',data)
        render(data,args.output/'REPORT.md')
    checkpoint()
    rng = random.Random(20261029)
    # Startup observations finish before the long uncached scaling trials.
    for group, trials in (('startup',args.startup_trials),('scaling',args.scaling_trials)):
        for trial in range(trials):
            cases = data[group].copy();rng.shuffle(cases)
            for case in cases:
                sample = consume(case['command'],args.timeout)
                case['samples'].append(sample)
                validate_pair(data['startup']+data['scaling'])
                checkpoint()
                print(f"{group} {trial+1}/{trials}: {case['dataset']} / {case.get('mode','')} / "
                      f"{case['variant']} ({sample['process_wall_seconds']:.3f}s process)",flush=True)
    data['status']='complete';checkpoint()
    print(args.output/'REPORT.md')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original',type=Path,default=HERE/'_work/runs/initial/results.json')
    parser.add_argument('--scaling',type=Path,default=HERE/'_work/runs/trail-scaling/results.json')
    parser.add_argument('--pip',type=Path,default=HERE.parent/'dependency_bundles/_work/runs/python-native/results.json')
    parser.add_argument('--widths',type=int,nargs='+',default=[250,1000,4000])
    parser.add_argument('--scaling-trials',type=int,default=3)
    parser.add_argument('--startup-trials',type=int,default=15)
    parser.add_argument('--timeout',type=float,default=900)
    parser.add_argument('--output',type=Path,default=HERE/'_work/runs/naive-startup')
    args=parser.parse_args()
    if min(args.scaling_trials,args.startup_trials)<1 or args.timeout<=0:
        parser.error('positive trials and timeout required')
    if len(set(args.widths))!=len(args.widths) or min(args.widths)<1:
        parser.error('unique positive widths required')
    run(args)
