"""Separate ptrace diagnostics over already measured/validated compiler commands."""
import argparse
import json
from pathlib import Path
import benchmark

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--results',type=Path,default=benchmark.HERE/'_work/runs/initial/results.json')
args=parser.parse_args();data=json.loads(args.results.read_text())
if data['status']!='complete':raise ValueError('complete timing run required')
physical=next(c for c in data['cases'] if c['mode']=='physical')
host=Path(physical['command'][0]);clang=Path(physical['command'][2])
if benchmark.sha(host)!=data['build']['host_sha256']:raise ValueError('host changed')
traces=[]
for case in data['cases']:
    if case['requests']!=8:continue
    row=benchmark.trace(clang,host,case,case['mode'],Path(case['output']),Path(data['work']))
    if benchmark.objects(Path(case['output']),8)!=case['warmup']['objects_sha256']:
        raise ValueError('traced object hashes differ')
    traces.append(row);print('traced',case['headers'],case['mode'],flush=True)
data['traces']=traces
benchmark.save(args.results,data);benchmark.report(data,args.results.with_name('REPORT.md'))
