"""Untimed real-project input traces over saved, validated build commands."""
import argparse
import json
from pathlib import Path
import re
import subprocess

import benchmark as base
import project_benchmark as project


def summarize(lines,inputs):
    categories={}
    for name in inputs['source_sha256']:
        category='project' if name.startswith(inputs['root']+'/') else 'system'
        categories[name]=category;categories[str(Path(name).resolve())]=category
    counts={'project':{},'system':{},'bundle':{}};execs=cc1=0
    calls={'openat','openat2','newfstatat','statx','access','read','pread64','mmap'}
    for line in lines:
        match=re.match(r'(?:\d+\s+)?([a-zA-Z0-9_]+)\(',line)
        if not match:continue
        call=match[1]
        if call=='execve':execs+=1;cc1+='"-cc1"' in line
        if call not in calls:continue
        found=set()
        for quoted,annotated in re.findall(r'"([^"\n]+)"|<([^>\n]+)>',line):
            name=quoted or annotated
            if name in categories:found.add(categories[name])
            if name==inputs['bundle']:found.add('bundle')
        for category in found:counts[category][call]=counts[category].get(call,0)+1
    return dict(input_path_calls=counts,process_execs=execs,frontend_execs=cc1)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results',type=Path,default=base.HERE/'_work/runs/zlib/results.json')
    args=parser.parse_args();data=json.loads(args.results.read_text());inputs=data['inputs'];rows=[]
    if data['status']!='complete':raise ValueError('complete timed run required')
    native=next(c for c in data['cases'] if c['mode']=='physical')
    if base.sha(Path(native['command'][0]))!=data['build']['host_sha256']:raise ValueError('native host changed')
    for name,pin in inputs['source_sha256'].items():
        if base.sha(Path(name))!=pin:raise ValueError('input changed: '+name)
    for case in data['cases']:
        if case['mode'] not in ('cli-batch','physical','memory'):continue
        path=Path(data['work'])/(case['mode']+'-project.strace')
        p=subprocess.run(['strace','-f','-yy','-e','trace=%file,read,pread64,mmap,close','-o',str(path),*case['command']],
                         cwd=case['output'],capture_output=True,text=True,timeout=180)
        if p.returncode:raise RuntimeError(p.stdout+p.stderr)
        if project.artifact_hashes(Path(case['output']),inputs)!=case['warmup']['artifacts_sha256']:
            raise ValueError('traced artifacts differ')
        row=dict(mode=case['mode'],path=str(path),**summarize(path.read_text().splitlines(),inputs))
        if case['mode']=='memory' and (row['input_path_calls']['project'] or row['input_path_calls']['system']):
            raise ValueError('memory compiler read loose admitted inputs')
        rows.append(row);print('traced real project:',case['mode'],flush=True)
    data['traces']=rows;data['trace_analysis_sha256']=base.sha(Path(__file__))
    base.save(args.results,data);project.report(data,args.results.with_name('REPORT.md'))
