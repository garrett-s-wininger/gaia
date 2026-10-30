"""Verify a real high-fanout project header against independent CLI dependencies."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shlex
import subprocess
import benchmark as base
import project_benchmark as project
import object_cache_benchmark as cache
from check_object_cache import decode_inputs

HERE=base.HERE
if __name__=='__main__':
    out=HERE/'_work/runs/dependency-cache';d=json.loads((out/'results.json').read_text())
    if d['status']!='complete':raise ValueError('finish timing first')
    info=d['inputs'];s=info['scenarios']['unchanged'];work=Path(d['work'])/'fanout-check';work.mkdir();header=Path(info['cwd'])/'common/compiler.h';readers=[]
    for i,args in enumerate(s['commands']):
        cmd=args.copy();j=cmd.index('-o');del cmd[j:j+2];cmd.remove('-c');cmd+=['-M','-MT','gaia']
        p=project.run_checked(cmd,cwd=info['cwd'],env=cache.cache_env())
        paths=shlex.split(p.stdout.replace('\\\n',' ').split(':',1)[1]);paths=[os.path.normpath(p if p.startswith('/') else str(Path(info['cwd'])/p)) for p in paths]
        if str(header) in paths:readers.append(i)
    if not 1<len(readers)<info['jobs']:raise ValueError('expected genuinely shared, non-universal header')
    files=decode_inputs(info['baseline']);original=header.read_bytes()
    marker=b'\n#ifndef GAIA_DEP_FANOUT_ONCE\n#define GAIA_DEP_FANOUT_ONCE\n__attribute__((used)) static const unsigned gaia_dep_fanout_marker = 901;\n#endif\n'
    files[str(header)]+=marker;blob=work/'changed.gci';blob.write_bytes(project.encode_inputs(files));ref=work/'reference';ref.mkdir()
    try:
        header.write_bytes(files[str(header)])
        def compile_one(args):
            cmd=args.copy();i=cmd.index('-o')+1;cmd[i]=str(ref/cmd[i]);p=project.run_checked(cmd,cwd=info['cwd'],env=cache.cache_env())
            if p.stderr:raise ValueError(p.stderr)
        with ThreadPoolExecutor(max_workers=8) as executor:list(executor.map(compile_one,s['commands']))
        link=[str(base.admitted_tool(info,'ld.lld')),'-shared','--threads=1','--build-id=sha1','-soname','libzstd.so.1','-o','libzstd.so',*info['objects']]
        project.run_checked(link,cwd=ref,env=cache.cache_env())
    finally:header.write_bytes(original)
    expected={p:base.sha(ref/p) for p in [*info['objects'],'libzstd.so']}
    changed=[i for i,p in enumerate(info['objects']) if expected[p]!=s['expected'][p]]
    if changed!=readers:raise ValueError('marker did not independently change each reader object')
    native=work/'native';native.mkdir();store=work/'cache';store.mkdir()
    for p in Path(d['seeds']['journal']['cache']).iterdir():os.link(p,store/p.name)
    cmd=next(c for c in d['cases'] if c['name']=='unchanged-delta-journal')['command'].copy();cmd[4]=str(blob);cmd[5]=base.sha(blob);cmd[6]=str(native);cmd[14]=str(store)
    p=project.run_checked(cmd,cwd=native,env=cache.cache_env());r=json.loads(p.stdout)
    if p.stderr or not r['correct'] or r['compiler_executions']!=len(readers) or r['cache_hits']!=info['jobs']-len(readers) or r['cache_write_errors']:raise ValueError('high-fanout invalidation differs')
    actual=dict(zip(info['objects'],r['object_sha256']));actual['libzstd.so']=base.sha(native/'libzstd.so')
    if actual!=expected:raise ValueError('high-fanout cache artifact mismatch')
    cache.library_check(native/'libzstd.so',18,10507)
    base.save(out/'fanout-check.json',dict(run_id=d['run_id'],timed=False,passed=True,header=str(header),independent_cli_readers=readers,reader_objects=[info['objects'][i] for i in readers],changed_objects=changed,result=r,artifacts_sha256=actual,checker_sha256=base.sha(Path(__file__))))
    print('verified real shared-header fanout:',len(readers),'compilations,',r['cache_hits'],'hits')
