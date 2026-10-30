"""Untimed object-path syscall evidence for the completed direct-handoff run."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import benchmark as base

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--results',type=Path,default=base.HERE/'_work/runs/direct-handoff/results.json')
p.add_argument('--analyze-only',action='store_true',help='reclassify retained traces without rerunning tools')
a=p.parse_args();data=json.loads(a.results.read_text())
if data['status']!='complete':raise ValueError('finish timing before tracing')
rows=[]
for name in ('physical-8-file','physical-8-buffer-file','physical-8-direct'):
    case=next(c for c in data['cases'] if c['name']==name);out=Path(case['output'])
    if base.sha(Path(case['command'][0]))!=data['build']['host_sha256']:raise ValueError('host changed')
    trace=Path(data['work'])/(name+'.strace')
    if a.analyze_only:
        previous=json.loads(a.results.with_name('object-io-traces.json').read_text())
        sample=next(r for r in previous['rows'] if r['name']==name)['result']
    else:
        for n in [*data['inputs']['objects'],'libz.so']:(out/n).unlink(missing_ok=True)
        result=subprocess.run(['strace','-f','-qq','-yy','-e','trace=%file,read,pread64,mmap,write,pwrite64,close',
            '-o',str(trace),*case['command']],cwd=out,capture_output=True,text=True,timeout=180)
        if result.returncode:raise RuntimeError(result.stdout+result.stderr)
        sample=json.loads(result.stdout)
        if base.sha(out/'libz.so')!=case['warmup']['artifacts_sha256']['libz.so']:raise ValueError('traced ELF differs')
        if case['handoff']=='direct':
            if sample['buffer_hits']!=15 or sample['buffer_misses'] or any((out/n).exists() for n in data['inputs']['objects']):raise ValueError('direct path not proven')
            if dict(zip(data['inputs']['objects'],sample['object_sha256']))!={n:case['warmup']['artifacts_sha256'][n] for n in data['inputs']['objects']}:raise ValueError('traced objects differ')
        else:
            for n in data['inputs']['objects']:
                if base.sha(out/n)!=case['warmup']['artifacts_sha256'][n]:raise ValueError('traced file object differs')
    counts={};other={}
    for line in trace.read_text().splitlines():
        call=re.match(r'(?:\d+\s+)?([a-zA-Z0-9_]+)\(',line)
        if not call:continue
        paths=[x or y for x,y in re.findall(r'"([^"\n]+)"|<([^>\n]+)>',line)]
        generated=any((x in data['inputs']['objects']) or (x.startswith(str(out)+'/') and (x.endswith('.o') or x.endswith('.o.tmp'))) for x in paths)
        if generated:counts[call[1]]=counts.get(call[1],0)+1
        elif any(x.endswith('.o') for x in paths):other[call[1]]=other.get(call[1],0)+1
    if case['handoff']=='direct' and any(counts.get(k,0) for k in ('open','openat','openat2','read','pread64','mmap','write','pwrite64')):raise ValueError('direct object I/O found')
    rows.append(dict(name=name,generated_object_path_calls=counts,other_object_path_calls=other,trace=str(trace),result=sample))
    print(name,counts,flush=True)
base.save(a.results.with_name('object-io-traces.json'),dict(run_id=data['run_id'],timed=False,
    analyzer_sha256=base.sha(Path(__file__)),rows=rows))
