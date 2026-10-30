"""Untimed corruption, invalidation, failure, diagnostic and publication checks."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import benchmark as base
import project_benchmark as project
import object_cache_benchmark as bench

HERE=base.HERE


def decode_inputs(path):
    data=Path(path).read_bytes();offset=16;out={}
    for _ in range(int.from_bytes(data[8:16],'little')):
        n=int.from_bytes(data[offset:offset+4],'little');size=int.from_bytes(data[offset+4:offset+12],'little');offset+=12
        name=data[offset:offset+n].decode();offset+=n+1;out[name]=data[offset:offset+size];offset+=size+1
    if offset!=len(data):raise ValueError('unexpected fixture framing')
    return out


def run(a):
    d=json.loads(a.results.read_text())
    if d['status']!='complete':raise ValueError('finish timings before checks')
    info=d['inputs'];host=a.host.resolve();work=Path(d['work'])/'checks';work.mkdir();rows=[]
    descriptor={**info['context_descriptor'],'host_sha256':base.sha(host)}
    context_id=hashlib.sha256(json.dumps(descriptor,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    template=next(c for c in d['cases'] if c['name']=='unchanged-scoped')['command']
    n=info['jobs'];baseline=info['scenarios']['unchanged'];counter=0
    def command(name,cache=None,seed=None,context=context_id):
        nonlocal counter
        counter+=1;out=work/name;out.mkdir()
        if cache is None:
            cache=work/(name+'-cache');bench.reset_cache(seed,cache)
        cmd=template.copy();cmd[0]=str(host);cmd[6]=str(out);cmd[14]=str(cache);cmd[16]=context
        return cmd,out,Path(cache)
    def verify(cmd,out,p,expected,misses,writes=None,corrupt=0,allow_diagnostics=False,write_errors=0):
        if p.returncode:raise ValueError(p.stdout+p.stderr)
        s=json.loads(p.stdout)
        if p.stderr and not allow_diagnostics:raise ValueError(p.stderr)
        if not s['correct'] or s['errors'] or s['compiler_executions']!=misses or s['cache_hits']!=n-misses or s['ready_objects']!=n or s['link_calls']!=1 or s['buffer_hits']!=n or s['buffer_misses']:
            raise ValueError('cache result differs: '+str(s))
        if s['cache_corrupt']!=corrupt or s['cache_write_errors']!=write_errors or s['cache_writes']!=(misses if writes is None else writes):raise ValueError('cache disposition differs')
        artifacts=dict(zip(info['objects'],s['object_sha256']));artifacts['libzstd.so']=base.sha(out/'libzstd.so')
        if artifacts!=expected or any((out/x).exists() for x in info['objects']):raise ValueError('cache artifact mismatch')
        return s
    def call(cmd,out):return subprocess.run(cmd,cwd=out,capture_output=True,text=True,timeout=180,env=bench.cache_env())
    # New host identities receive a fresh receipt and independent baseline seed.
    cmd,out,seed=command('seed');p=call(cmd,out);s=verify(cmd,out,p,baseline['expected'],n)
    keys=s['cache_keys'];rows.append(dict(check='cold-populates-valid-baseline',passed=True,result=s))
    cmd,out,cache=command('warm',seed=seed);s=verify(cmd,out,call(cmd,out),baseline['expected'],0)
    rows.append(dict(check='warm-all-hit',passed=True,result=s))
    for kind in ('payload','truncated','entry-key'):
        cmd,out,cache=command('corrupt-'+kind,seed=seed);entry=cache/(keys[-1]+'.gco');body=bytearray(entry.read_bytes())
        entry.unlink()  # Break the seed hardlink before deliberately corrupting it.
        if kind=='payload':body[-1]^=1
        elif kind=='entry-key':body[8]^=1
        else:body=body[:10]
        entry.write_bytes(body);s=verify(cmd,out,call(cmd,out),baseline['expected'],1,corrupt=1)
        healed=verify(cmd,out,call(cmd,out),baseline['expected'],0)
        rows.append(dict(check='reject-and-repair-'+kind,passed=True,result=s,healed=healed))
    other=hashlib.sha256((context_id+'different-admitted-toolchain-identity').encode()).hexdigest()
    cmd,out,cache=command('context-changed',seed=seed,context=other);s=verify(cmd,out,call(cmd,out),baseline['expected'],n)
    if set(s['cache_keys'])&set(keys):raise ValueError('context identity did not affect keys')
    rows.append(dict(check='different-context-id-invalidates-all-same-binary',passed=True,result=s))
    cmd,out,cache=command('write-failure');shutil.rmtree(cache);cache.write_text('not a directory')
    s=verify(cmd,out,call(cmd,out),baseline['expected'],n,writes=0,write_errors=n)
    rows.append(dict(check='cache-write-failure-keeps-build-usable',passed=True,result=s))
    # A failed new source must neither link nor publish partial successful misses.
    files=decode_inputs(baseline['bundle']);probe=info['sources'][-1];bad=dict(files);bad[probe]+=b'\n#error gaia_cache_compile_failure\n'
    blob=work/'bad.gci';blob.write_bytes(project.encode_inputs(bad));cmd,out,cache=command('compile-failure',seed=seed)
    cmd[4]=str(blob);cmd[5]=base.sha(blob);sentinel=b'previous published library';(out/'libzstd.so').write_bytes(sentinel)
    before={p.name:base.sha(p) for p in cache.iterdir()};p=call(cmd,out);s=json.loads(p.stdout)
    if not p.returncode or s['correct'] or not s['errors'] or s['link_calls'] or s['cache_writes'] or s['cache_hits']!=n-1 or s['compiler_executions']!=1 or (out/'libzstd.so').read_bytes()!=sentinel:
        raise ValueError('failed compile published/reused invalid output')
    if {p.name:base.sha(p) for p in cache.iterdir()}!=before:raise ValueError('failed build changed cache')
    rows.append(dict(check='compile-failure-preserves-library-and-cache',passed=True,result=s,stderr=p.stderr))
    # Physical files outside the declared view must not affect either hits or misses.
    shadow=Path(info['logical_cwd'])/'_gaia_optional.h'
    if shadow.exists():raise ValueError('unexpected physical optional header')
    shadow.write_text('#define GAIA_OPTIONAL 1000\n')
    try:
        for mode in ('scoped','off'):
            cmd,out,cache=command('undeclared-host-header-'+mode,seed=seed);cmd[13]=mode
            s=verify(cmd,out,call(cmd,out),baseline['expected'],0 if mode=='scoped' else n,writes=0)
            bench.library_check(out/'libzstd.so',11,10507)
            rows.append(dict(check='undeclared-host-header-invisible-'+mode,passed=True,result=s))
    finally:shadow.unlink()
    # An admitted but invisible file changes the collection pin, not the view keys.
    extra=dict(files);extra[str(Path(info['logical_cwd'])/'_gaia_unexposed.txt')]=b'unexposed bytes'
    blob=work/'unexposed.gci';blob.write_bytes(project.encode_inputs(extra))
    masks=list(map(int,Path(baseline['masks']).read_text().split()[1:]));old_masks=dict(zip(sorted(files),masks))
    maskpath=work/'unexposed.views';maskpath.write_text('GAIACV1\n'+'\n'.join(str(old_masks.get(p,0)) for p in sorted(extra))+'\n')
    cmd,out,cache=command('invisible-admitted-file',seed=seed);cmd[4]=str(blob);cmd[5]=base.sha(blob);cmd[15]=str(maskpath)
    s=verify(cmd,out,call(cmd,out),baseline['expected'],0);rows.append(dict(check='invisible-input-does-not-invalidate-scoped-keys',passed=True,result=s))
    # Two independently compiling processes publish the same keys concurrently.
    shared=work/'concurrent-cache';shared.mkdir();pairs=[command('concurrent-'+str(i),cache=shared) for i in range(2)]
    with ThreadPoolExecutor(max_workers=2) as executor:results=list(executor.map(lambda pair:call(pair[0],pair[1]),pairs))
    concurrent=[]
    for (cmd,out,_),p in zip(pairs,results):
        raw=json.loads(p.stdout);concurrent.append(verify(cmd,out,p,baseline['expected'],n-raw['cache_hits']))
    if len(list(shared.glob('*.gco')))!=n or list(shared.glob('*.tmp.*')):raise ValueError('partial concurrent entries remain')
    cmd,out,_=command('concurrent-readback',cache=shared);s=verify(cmd,out,call(cmd,out),baseline['expected'],0)
    rows.append(dict(check='concurrent-publication-and-all-hit-readback',passed=True,writers=concurrent,readback=s))
    # Minimal real compiler request exercises diagnostic replay policy. Diagnostic
    # results are intentionally not cached; both calls must emit the warning.
    probe_cmd=baseline['commands'][-1];single_plan=work/'warning.gcr';single_plan.write_bytes(project.encode_requests([probe_cmd]))
    single_masks=work/'single.views';single_masks.write_text('GAIACV1\n'+'\n'.join('1' if m&(1<<(n-1)) else '0' for m in masks)+'\n')
    warning_files=dict(files);warning_files[probe]=b'#warning gaia_cache_warning\n'+warning_files[probe]
    warning_blob=work/'warning.gci';warning_blob.write_bytes(project.encode_inputs(warning_files))
    linker=[str(base.admitted_tool(info,'ld.lld')),'-shared','--threads=1','--build-id=sha1','-soname','libzstd.so.1','-o','libzstd.so',info['objects'][-1]]
    single_link=work/'single-link.gcr';single_link.write_bytes(project.encode_requests([linker]))
    ref=work/'warning-reference';ref.mkdir();physical=Path(probe);old=physical.read_bytes()
    try:
        physical.write_bytes(warning_files[probe]);cc=probe_cmd.copy();cc[cc.index('-o')+1]=str(ref/info['objects'][-1])
        project.run_checked(cc,cwd=info['logical_cwd'],env=bench.cache_env());project.run_checked(linker,cwd=ref,env=bench.cache_env())
    finally:physical.write_bytes(old)
    expected={info['objects'][-1]:base.sha(ref/info['objects'][-1]),'libzstd.so':base.sha(ref/'libzstd.so')}
    cmd,out,cache=command('diagnostic-bypass');cmd[4]=str(warning_blob);cmd[5]=base.sha(warning_blob);cmd[7]=str(single_plan);cmd[11]=str(single_link);cmd[15]=str(single_masks)
    warning_results=[]
    for _ in range(2):
        p=call(cmd,out);s=json.loads(p.stdout)
        if p.returncode or not s['correct'] or s['warnings']!=1 or s['compiler_executions']!=1 or s['cache_hits'] or s['cache_writes'] or 'gaia_cache_warning' not in p.stderr or list(cache.iterdir()):raise ValueError('warning was cached/suppressed')
        actual={info['objects'][-1]:s['object_sha256'][0],'libzstd.so':base.sha(out/'libzstd.so')}
        if actual!=expected:raise ValueError('warning bypass artifact changed')
        warning_results.append(dict(result=s,stderr=p.stderr))
    rows.append(dict(check='warnings-bypass-cache-and-repeat-diagnostics',passed=True,runs=warning_results))
    # Volatile macros fail instead of producing time-dependent cache entries.
    dated=dict(files);generated=str(Path(info['logical_cwd'])/'_gaia_generated.h');dated[generated]=b'#define GAIA_GENERATED (__TIME__[0])\n'
    db=work/'date.gci';db.write_bytes(project.encode_inputs(dated));cmd[4]=str(db);cmd[5]=base.sha(db);(out/'libzstd.so').write_bytes(sentinel)
    p=call(cmd,out);s=json.loads(p.stdout)
    if not p.returncode or not s['errors'] or s['link_calls'] or s['cache_writes'] or (out/'libzstd.so').read_bytes()!=sentinel:raise ValueError('volatile macro guard failed')
    rows.append(dict(check='volatile-date-macro-rejected',passed=True,result=s,stderr=p.stderr))
    for path,h in info['source_sha256'].items():
        if base.sha(Path(path))!=h:raise ValueError('checks modified baseline source')
    result=dict(run_id=d['run_id'],timed=False,host_sha256=base.sha(host),host=str(host),execution_context=descriptor,
        context_id=context_id,build=json.loads((host.parent.parent/'build.json').read_text()),rows=rows,
        checker_sha256=base.sha(Path(__file__)),source_sha256={name:base.sha(HERE/name) for name in ('cache_host.odin','cache_bridge.cpp','handoff_impl.h','pool_bridge.cpp')})
    base.save(a.results.with_name('checks.json'),result);print('verified',len(rows),'cache boundary/publication/diagnostic groups',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--results',type=Path,default=HERE/'_work/runs/object-cache/results.json');p.add_argument('--host',type=Path,required=True);run(p.parse_args())
