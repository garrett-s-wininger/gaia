"""Untimed negative-query, candidate publication and producer boundary checks."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import benchmark as base
import project_benchmark as project
import object_cache_benchmark as cache
import dependency_cache_benchmark as experiment
from check_object_cache import decode_inputs

HERE=base.HERE


def records(entry):
    data=entry.read_bytes();size=int.from_bytes(data[72:80],'little');wire=data[88:88+size]
    if wire[:8]!=b'GAIAJR01':raise ValueError('unexpected journal')
    offset=12;out=[]
    for _ in range(int.from_bytes(wire[8:12],'little')):
        op,outcome=wire[offset:offset+2];n=int.from_bytes(wire[offset+2:offset+6],'little');offset+=6
        path=wire[offset:offset+n].decode();offset+=n;digest=wire[offset:offset+32].hex();offset+=32
        out.append(dict(op=op,outcome=outcome,path=path,fingerprint=digest))
    if offset!=len(wire):raise ValueError('journal framing')
    return out


def run():
    path=HERE/'_work/runs/dependency-cache/results.json';d=json.loads(path.read_text())
    if d['status']!='complete':raise ValueError('finish timing before checks')
    info=d['inputs'];work=Path(d['work'])/'checks';work.mkdir();rows=[];n=info['jobs'];seed=Path(d['seeds']['journal']['cache'])
    template=next(c for c in d['cases'] if c['name']=='unchanged-delta-journal')['command'];base_s=info['scenarios']['unchanged'];files=decode_inputs(info['baseline'])
    def make(name,scenario='unchanged',store=None):
        out=work/name;out.mkdir()
        if store is None:
            store=work/(name+'-cache');store.mkdir()
            for p in seed.iterdir():os.link(p,store/p.name)
        s=info['scenarios'][scenario];cmd=template.copy();cmd[6]=str(out);cmd[14]=str(store);cmd[4]=s['bundle'];cmd[5]=s['pin'];cmd[7]=s['plan'];cmd[15]=s['masks']
        return cmd,out,Path(store)
    def call(cmd,out):return subprocess.run(cmd,cwd=out,capture_output=True,text=True,timeout=180,env=cache.cache_env())
    def verify(cmd,out,p,scenario='unchanged',misses=0,corrupt=0,warning=False):
        if p.returncode:raise ValueError(p.stdout+p.stderr)
        s=json.loads(p.stdout);expected=info['scenarios'][scenario]
        if not warning and p.stderr:raise ValueError(p.stderr)
        if not s['correct'] or s['errors'] or s['compiler_executions']!=misses or s['cache_hits']!=n-misses or s['cache_corrupt']!=corrupt or s['cache_write_errors'] or s['buffer_hits']!=n or s['buffer_misses'] or s['link_calls']!=1:
            raise ValueError('dependency outcome differs: '+str(s))
        if s['cache_writes']!=(0 if warning else misses):raise ValueError('unexpected publication')
        actual=dict(zip(info['objects'],s['object_sha256']));actual['libzstd.so']=base.sha(out/'libzstd.so')
        if actual!=expected['expected'] or any((out/p).exists() for p in info['objects']):raise ValueError('dependency artifact mismatch')
        cache.library_check(out/'libzstd.so',expected['probe'],expected['version']);return s
    # Independently inspect the seed's actual prior failed queries, not just hit counts.
    keys=d['seeds']['journal']['result']['cache_keys'];probe_records=records(seed/(keys[-1]+'.gdo'))
    def canonical(p):return os.path.normpath(p if p.startswith('/') else str(Path(info['cwd'])/p))
    negatives=[r for r in probe_records if r['outcome']]
    for name in ('optional','shadow'):
        if not any(canonical(r['path'])==info['special_paths'][name] for r in negatives):raise ValueError('required failed header query not captured')
    directory=str(Path(info['special_paths']['newdir']).parent)
    if not any(canonical(r['path']) in (directory,info['special_paths']['newdir']) for r in negatives):raise ValueError('failed directory/header lookup not captured')
    rows.append(dict(check='seed-retains-optional-shadow-and-directory-negatives',passed=True,probe_records=probe_records))
    for scenario in ('shared-header','generated-header','optional-header','shadow-header','new-directory'):
        cmd,out,store=make('query-'+scenario,scenario);s=verify(cmd,out,call(cmd,out),scenario,1)
        if s['dependency_invalidations']!=1 or not s['dependency_negatives']:raise ValueError('query revalidation was bypassed')
        rows.append(dict(check='observations-invalidate-only-reader-'+scenario,passed=True,result=s))
    cmd,out,store=make('unused','unused-header');s=verify(cmd,out,call(cmd,out),'unused-header',0)
    rows.append(dict(check='unused-visible-content-keeps-all-hits',passed=True,result=s))
    # Revert a newly shadowing header using the same latest-candidate store.
    cmd,out,store=make('shadow-install','shadow-header');verify(cmd,out,call(cmd,out),'shadow-header',1)
    cmd2,out2,_=make('shadow-revert',store=store);s=verify(cmd2,out2,call(cmd2,out2),'unchanged',1)
    rows.append(dict(check='positive-shadow-disappearance-invalidates',passed=True,result=s))
    # Corruption must cover both journal and object, and malformed operations are
    # rejected even if a locally constructed record has a consistent checksum.
    for kind in ('payload','journal','opcode'):
        cmd,out,store=make('corrupt-'+kind);entry=store/(keys[-1]+'.gdo');data=bytearray(entry.read_bytes());entry.unlink()
        if kind=='payload':data[-1]^=1
        elif kind=='journal':data[100]^=1
        else:
            data[100]=0  # first opcode follows 88-byte header + 12-byte journal header
            data[40:72]=hashlib.sha256(data[8:40]+data[72:]).digest()
        entry.write_bytes(data);s=verify(cmd,out,call(cmd,out),'unchanged',1,corrupt=1)
        verify(cmd,out,call(cmd,out),'unchanged',0)
        rows.append(dict(check='reject-and-repair-'+kind,passed=True,result=s))
    # Deleting a used header cannot hit an old successful result or publish failure.
    shared=str(Path(info['cwd'])/'_gaia_shared.h');deleted=dict(files);del deleted[shared]
    old_masks=dict(zip(sorted(files),map(int,Path(info['base_views']).read_text().split()[1:])))
    blob=work/'deleted.gci';blob.write_bytes(project.encode_inputs(deleted));views=work/'deleted.views';views.write_text('GAIACV1\n'+'\n'.join(str(old_masks[p]) for p in sorted(deleted))+'\n')
    cmd,out,store=make('deleted-header');cmd[4]=str(blob);cmd[5]=base.sha(blob);cmd[15]=str(views);sentinel=b'previous published library';(out/'libzstd.so').write_bytes(sentinel)
    before={p.name:base.sha(p) for p in store.iterdir()};p=call(cmd,out);s=json.loads(p.stdout)
    if not p.returncode or not s['errors'] or s['compiler_executions']!=1 or s['cache_hits']!=n-1 or s['link_calls'] or s['cache_writes'] or (out/'libzstd.so').read_bytes()!=sentinel:
        raise ValueError('deleted header reused/published stale result')
    if {p.name:base.sha(p) for p in store.iterdir()}!=before:raise ValueError('failed compile changed candidates')
    rows.append(dict(check='used-header-deletion-preserves-library-and-candidates',passed=True,result=s,stderr=p.stderr))
    # The two inputs share action IDs but require different object bytes. Atomic
    # journal+object publication must not mix their records.
    store=work/'concurrent-candidates';store.mkdir()
    for p in seed.iterdir():os.link(p,store/p.name)
    pairs=[(name,*make('concurrent-'+name,name,store=store)[:2]) for name in ('shared-header','generated-header')]
    with ThreadPoolExecutor(max_workers=2) as executor:responses=list(executor.map(lambda pair:call(pair[1],pair[2]),pairs))
    writers=[]
    for (name,cmd,out),p in zip(pairs,responses):writers.append(verify(cmd,out,p,name,1))
    readback=[]
    for name in ('shared-header','generated-header'):
        cmd,out,_=make('readback-'+name,name,store=store);p=call(cmd,out);r=json.loads(p.stdout);readback.append(verify(cmd,out,p,name,r['compiler_executions']))
    if len(list(store.glob('*.gdo')))!=n or list(store.glob('*.tmp.*')):raise ValueError('mixed/partial concurrent candidates')
    rows.append(dict(check='concurrent-different-input-same-action-publication',passed=True,writers=writers,readback=readback))
    # Action identities do not depend on job slots. Remap visibility bits and
    # reverse requests, retaining the original declared linker input order.
    reverse=work/'reverse.gcr';reverse.write_bytes(project.encode_requests(list(reversed(base_s['commands']))))
    reversed_masks=[]
    for mask in map(int,Path(info['base_views']).read_text().split()[1:]):
        remapped=sum(1<<(n-1-i) for i in range(n) if mask&(1<<i));reversed_masks.append(remapped)
    vm=work/'reverse.views';vm.write_text('GAIACV1\n'+'\n'.join(map(str,reversed_masks))+'\n')
    cmd,out,store=make('reordered');cmd[7]=str(reverse);cmd[15]=str(vm);p=call(cmd,out);s=json.loads(p.stdout)
    if p.returncode or p.stderr or s['compiler_executions'] or s['cache_hits']!=n or s['buffer_hits']!=n:raise ValueError('job slots entered cache identity')
    actual=dict(zip(reversed(info['objects']),s['object_sha256']));actual['libzstd.so']=base.sha(out/'libzstd.so')
    if actual!=base_s['expected']:raise ValueError('reordered requests changed link artifacts')
    rows.append(dict(check='reordered-requests-remapped-views-all-hit-fixed-link-order',passed=True,result=s))
    # Diagnostic-producing requests must repeat messages rather than get cached.
    warned=dict(files);warned[info['sources'][-1]]=b'#warning gaia_dependency_warning\n'+warned[info['sources'][-1]]
    wb=work/'warn.gci';wb.write_bytes(project.encode_inputs(warned));cmd,out,store=make('warnings');cmd[4]=str(wb);cmd[5]=base.sha(wb)
    before={p.name:base.sha(p) for p in store.iterdir()};runs=[]
    for _ in range(2):
        p=call(cmd,out);s=verify(cmd,out,p,'unchanged',1,warning=True)
        if s['warnings']!=1 or 'gaia_dependency_warning' not in p.stderr:raise ValueError('warning disappeared')
        runs.append(dict(result=s,stderr=p.stderr))
    if {p.name:base.sha(p) for p in store.iterdir()}!=before:raise ValueError('diagnostics were cached')
    rows.append(dict(check='warnings-repeat-without-candidate-publication',passed=True,runs=runs))
    # Failed producer admission must leave prior private outputs intact and not
    # emit a receipt. Different failures exercise framing/base/view/result binding.
    producer=d['producer'];good=Path(base_s['delta']).read_bytes();basefile=Path(info['baseline']);baseviews=Path(info['base_views'])
    pout=work/'preserved.gci';pv=work/'preserved.views';producer_checks=[]
    bad_base=bytearray(good);bad_base[8]^=1;bad_views=bytearray(good);bad_views[40]^=1
    unsafe_name=(str(Path(info['cwd'])/'..'/'escape.h')).encode();unsafe=good[:72]+struct.pack('<Q',1)+struct.pack('<IBQQ',len(unsafe_name),1,(1<<n)-1,1)+unsafe_name+b'\0x\0'
    for name,data,expected in [('base-pin',bad_base,'-'),('view-pin',bad_views,'-'),('truncated',good[:-1],'-'),('unsafe-name',unsafe,'-'),('result-pin',good,'0'*64)]:
        patch=work/(name+'.gdp');patch.write_bytes(data);pout.write_bytes(sentinel);pv.write_bytes(sentinel)
        cmd=[producer,'delta',str(basefile),str(baseviews),str(patch),str(pout),str(pv),expected,str(n)]
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
        if p.returncode!=3 or p.stdout or pout.read_bytes()!=sentinel or pv.read_bytes()!=sentinel:raise ValueError('invalid producer input published output: '+name)
        producer_checks.append(dict(case=name,passed=True,returncode=p.returncode,stderr=p.stderr))
    rows.append(dict(check='producer-rejects-invalid-events-before-publication',passed=True,cases=producer_checks))
    # Explicit removal and zero-byte updates produce the same canonical bytes.
    variant=dict(files);del variant[shared];variant[info['special_paths']['unused']]=b''
    newmasks={p:old_masks[p] for p in variant};expected_blob=project.encode_inputs(variant);expected_pin=hashlib.sha256(expected_blob).hexdigest()
    patch,changed=experiment.delta_bytes(files,variant,newmasks,info['baseline_pin'],info['base_view_pin']);pf=work/'remove-empty.gdp';pf.write_bytes(patch)
    sdesc=dict(changed_paths=changed,changes={p:variant[p].hex() for p in changed if p in variant});experiment.install_changes(files,sdesc)
    produced=[]
    try:
        for mode in ('full','delta'):
            cmd=[producer,mode,str(basefile),str(baseviews),str(pf),str(work/(mode+'-remove.gci')),str(work/(mode+'-remove.views')),expected_pin,str(n)]
            p=project.run_checked(cmd);r=json.loads(p.stdout)
            if Path(cmd[5]).read_bytes()!=expected_blob:raise ValueError('producer removal/empty content differs')
            produced.append(r)
    finally:experiment.restore_changes(files,sdesc)
    rows.append(dict(check='producer-removal-and-zero-byte-update-equivalent',passed=True,results=produced))
    for name,h in info['baseline_file_sha256'].items():
        if base.sha(Path(name))!=h:raise ValueError('checks changed baseline')
    result=dict(run_id=d['run_id'],timed=False,host_sha256=base.sha(Path(d['host'])),producer_sha256=base.sha(Path(producer)),
        rows=rows,checker_sha256=base.sha(Path(__file__)))
    base.save(path.with_name('checks.json'),result);print('verified',len(rows),'dependency/producer boundary groups',flush=True)

if __name__=='__main__':run()
