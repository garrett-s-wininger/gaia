"""Measured small task durations feed a scheduler MODEL, not a real task queue."""
import argparse
from dataclasses import replace
import fcntl
import hashlib
import json
import math
from pathlib import Path
import shutil
import statistics
import subprocess
import time

from scheduling import fixture, simulate


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--clang',type=Path,required=True)
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--lock',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();args.work.mkdir(parents=True,exist_ok=False)
    rg=shutil.which('rg');assert rg
    source=args.work/'unit.c'
    source.write_text('int value(int n) { return n * n; }\nint main(void) { return value(3) != 9; }\n')
    executable=args.work/'test'
    subprocess.run([str(args.clang),str(source),'-o',str(executable)],check=True,capture_output=True)
    pin=lambda q:hashlib.sha256(Path(q).read_bytes()).hexdigest()
    sources=[Path(__file__),Path(__file__).with_name('scheduling.py'),source]
    tools=[args.clang,Path(rg),executable]
    before={str(q):pin(q) for q in sources+tools}
    commands={
        'parse':[str(args.clang),'-fsyntax-only',str(source)],
        'diagnostic':[str(args.clang),'-fsyntax-only','-Wall','-Wextra',str(source)],
        'compile':[str(args.clang),'-O2','-c',str(source),'-o',str(args.work/'unit.o')],
        'test':[str(executable)],
        'search':[rg,'value',str(source)],
    }
    rows=[]
    for block in range(3):
        for name,command in commands.items():
            with args.lock.open('a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX);begin=time.perf_counter_ns()
                result=subprocess.run(command,capture_output=True)
                elapsed=time.perf_counter_ns()-begin
            assert result.returncode==0,(name,result.stderr)
            rows.append(dict(block=block,task=name,wall_ns=elapsed,stdout_sha256=hashlib.sha256(result.stdout).hexdigest()))
    durations={name:max(1,math.ceil(statistics.median(r['wall_ns'] for r in rows if r['task']==name)/100000)) for name in commands}
    period=max(1,durations['compile']//2)
    tasks=[replace(t,work=durations.get(t.name.rsplit(':',1)[-1],durations['compile'])) for t in fixture(period=period)]
    results=[simulate(tasks,policy,quantum=10,cold_cost=0) for policy in ('fifo','critical','fair','work-stealing','foraging')]
    results.append(simulate(tasks,'fifo',cancellation=False,quantum=10,cold_cost=0))
    assert before=={str(q):pin(q) for q in sources+tools}
    output=dict(schema='GAIA-SCHEDULER-CALIBRATION-1',status='complete',source_tools_verified_after=True,pins=before,rows=rows,duration_100us_units=durations,period_100us_units=period,results=results,
        scope='Actual separate-process small C syntax/diagnostics/compile/test/search wall durations, including spawn, calibrate a model only. Parse and diagnostics are standalone full syntax passes, not separable compiler phases. No measured concurrent scheduler, real cancellation, cache locality, or service latency. Cancellation quantum 1ms is hypothetical; no compiler safe callback exists.')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(output,indent=2)+'\n')


if __name__=='__main__':main()
