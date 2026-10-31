"""Diagnostic fresh-process cost with no build inputs; not a build benchmark."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import statistics
import subprocess
import time


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('host','decision','clang','linker','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--trials',type=int,default=15);args=parser.parse_args()
    if args.trials<1:parser.error('positive trials required')
    cases={'native-invalid-argc':([str(args.host.resolve())],2),
           'decision-invalid-argc':([str(args.decision.resolve())],2),
           'clang-version':([str(args.clang.resolve()),'--version'],0),
           'linker-version':([str(args.linker.resolve()),'--version'],0)}
    rng=random.Random(7203);samples={name:[] for name in cases}
    for _ in range(args.trials):
        order=list(cases);rng.shuffle(order)
        for name in order:
            command,expected=cases[name];begin=time.perf_counter_ns()
            result=subprocess.run(command,capture_output=True)
            elapsed=time.perf_counter_ns()-begin
            if result.returncode!=expected:raise RuntimeError(name+' unexpected exit '+str(result.returncode))
            samples[name].append(elapsed/1e6)
    data=dict(scope='fresh process; invalid argc or version only; no valid request or input admission',
              trials=args.trials,cases={name:dict(command=command,exit_code=expected,samples_ms=samples[name],
              median_ms=statistics.median(samples[name]),sha256=hashlib.sha256(Path(command[0]).read_bytes()).hexdigest())
              for name,(command,expected) in cases.items()})
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(data,indent=2)+'\n')


if __name__=='__main__':main()
