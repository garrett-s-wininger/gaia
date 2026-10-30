#!/usr/bin/env python3
"""Diagnostic wrapper; mark/profile the unchanged worker's six-clock workload.

Only diagnostic observations use this clock wrapper. Never use their timings as
benchmark samples. Shared stdlib imports can differ from the uninstrumented run.
"""
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import sys
import time


def main(args):
    command=json.loads(args.command.read_text())
    target=str(Path(__file__).resolve().parent/'django_worker.py')
    sys.argv=command[command.index(target):]
    profiler=None
    if args.profile:
        import cProfile
        profiler=cProfile.Profile()
    clock=time.perf_counter
    calls=0
    def marked_clock():
        nonlocal calls
        caller=sys._getframe(1)
        if caller.f_code.co_filename==target and caller.f_code.co_name=='main':
            calls+=1
            if calls==1:
                os.write(2,b'GAIA_WORKLOAD_BEGIN\n')
                if profiler:profiler.enable()
            elif calls==6:
                if profiler:profiler.disable()
                os.write(2,b'GAIA_WORKLOAD_END\n')
        return clock()
    time.perf_counter=marked_clock
    output=io.StringIO()
    try:
        with contextlib.redirect_stdout(output):runpy.run_path(target,run_name='__main__')
    finally:
        time.perf_counter=clock
        if profiler:
            profiler.disable();profiler.dump_stats(str(args.profile))
    if calls!=7:raise RuntimeError(f'worker clock layout changed: expected 7 main calls, got {calls}')
    result=json.loads(output.getvalue())
    if args.result:args.result.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(correct=result['correct'],module_count=result['module_count'],
                          clock_layout_validated=True)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--command',type=Path,required=True)
    parser.add_argument('--profile',type=Path)
    parser.add_argument('--result',type=Path)
    main(parser.parse_args())
