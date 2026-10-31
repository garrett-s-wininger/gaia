"""Bounded first passes for repository queries, schema sharing and checkpoints."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import shutil
import statistics
import subprocess
import sys
import time

import schema_pipeline as schema
from test_checkpoint import bundle

PATTERNS = ['Copyright', 'MIT License', 'TODO', 'FIXME', 'SPDX-License-Identifier', 'password']


def timed(function):
    start=time.perf_counter_ns();value=function()
    return {'wall_ns':time.perf_counter_ns()-start,'value':value}


def command(args):
    result=subprocess.run(list(map(str,args)),capture_output=True,check=True)
    return json.loads(result.stdout)


def digest(data):return hashlib.sha256(data).hexdigest()


def repository(args):
    corpus=args.work/'repository';corpus.mkdir(exist_ok=True)
    start=time.perf_counter_ns();identity=[]
    # Real source corpus from the installed Odin toolchain, selected explicitly.
    # Copy once into a private generation; no hidden filesystem-watching claim.
    source=args.corpus.resolve()
    for path in sorted(source.rglob('*')):
        if path.suffix not in {'.odin','.md','.h','.c','.cpp','.py'} or path.is_symlink() or not path.is_file():continue
        relative=path.relative_to(source);data=path.read_bytes()
        target=corpus/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        identity.append({'path':relative.as_posix(),'bytes':len(data),'sha256':digest(data)})
    manifest=args.work/'paths.txt';paths=[corpus/entry['path'] for entry in identity]
    assert all('\n' not in str(p) for p in paths)
    manifest.write_text(''.join(str(path)+'\n' for path in paths))
    admission_ns=time.perf_counter_ns()-start
    oracle=[sum(path.read_bytes().count(pattern.encode()) for path in paths) for pattern in PATTERNS]
    def native(mode,index=0):return command([args.scan_host,manifest,mode,index])
    def single(index):return native('single',index)['counts'][index]
    def rg(index):
        result=subprocess.run([args.rg,'--no-config','-uuu','-a','-F','--count-matches','--no-heading','--color','never',PATTERNS[index],str(corpus)],capture_output=True)
        if result.returncode not in (0,1):raise RuntimeError(result.stderr)
        return sum(int(line.rsplit(b':',1)[1]) for line in result.stdout.splitlines())
    def parallel(function):
        with ThreadPoolExecutor(max_workers=6) as pool:return list(pool.map(function,range(6)))
    def rg_combined():
        args_list=[args.rg,'--no-config','-uuu','-a','-F','-o','--no-filename','--no-line-number','--color','never']
        for pattern in PATTERNS:args_list.extend(['-e',pattern])
        result=subprocess.run([*args_list,str(corpus)],capture_output=True)
        if result.returncode not in (0,1):raise RuntimeError(result.stderr)
        counts=dict.fromkeys(PATTERNS,0)
        for match in result.stdout.splitlines():counts[match.decode()]+=1
        return [counts[p] for p in PATTERNS]
    operations={
        'odin_independent_sequential':lambda:[single(i) for i in range(6)],
        'odin_independent_parallel':lambda:parallel(single),
        'odin_shared_reads':lambda:native('shared')['counts'],
        'odin_fused_automaton':lambda:native('fused')['counts'],
        'rg_independent_sequential':lambda:[rg(i) for i in range(6)],
        'rg_independent_parallel':lambda:parallel(rg),
        'rg_combined_scan':rg_combined,
    }
    # Correctness warms pages for all modes before the measured paired blocks.
    for name,operation in operations.items():assert operation()==oracle,name
    rows=[]
    for block in range(args.trials):
        order=list(operations);random.Random(block).shuffle(order)
        for name in order:
            sample=timed(operations[name]);assert sample['value']==oracle
            rows.append({'block':block,'mode':name,**sample})
    return {'admission_ns':admission_ns,'files':identity,'total_bytes':sum(x['bytes'] for x in identity),'patterns':PATTERNS,'oracle':oracle,'rows':rows,
            'scope':'warm-page private immutable source corpus; exact fixed-string counts, not full license/secret tools; common enumerated namespace; process and output costs included'}


def schema_experiment(args):
    payload=schema.fixture(args.records,12)
    oracle=schema.generate(payload,False)
    operations={
        'independent_sequential':lambda:schema.generate(payload,False,False),
        'independent_threads':lambda:schema.generate(payload,False,True),
        'shared_sequential':lambda:schema.generate(payload,True,False),
        'shared_threads':lambda:schema.generate(payload,True,True),
    }
    rows=[]
    for block in range(args.trials):
        order=list(operations);random.Random(block).shuffle(order)
        for name in order:
            sample=timed(operations[name]);assert sample['value']==oracle
            rows.append({'block':block,'mode':name,'wall_ns':sample['wall_ns'],'outputs':{k:digest(v) for k,v in sample['value'].items()}})
    base=schema.operation(payload)
    edits={}
    data=json.loads(payload);edits['reorder']=json.dumps(data,sort_keys=True).encode()
    data['records']['Record00000']['description']+=' documentation edit';edits['description']=json.dumps(data).encode()
    data['records']['Record00000']['fields']['field00']['type']='integer';edits['field_type']=json.dumps(data).encode()
    propagation=[]
    for block in range(args.trials):
        for edit,value in edits.items():
            order=[False,True];random.Random(block).shuffle(order)
            expected=None
            for cutoff in order:
                sample=timed(lambda:schema.operation(value,base,cutoff))
                observed={k:(v[0].hex(),v[1]) for k,v in sample['value'].items()}
                if expected is None:expected=observed
                assert observed==expected
                propagation.append({'block':block,'edit':edit,'cutoff':cutoff,'wall_ns':sample['wall_ns'],
                                    'executed':[k for k,v in sample['value'].items() if v[2]],'outputs':observed})
    return {'records':args.records,'input_bytes':len(payload),'input_sha256':digest(payload),'rows':rows,'propagation':propagation,
            'scope':'synthetic declared schema subset; same Python emitters with immutable shared records; threads remain subject to Python runtime; downstream SQL execution and Python compilation charged in propagation'}


def checkpoint(args):
    store=args.work/'checkpoint-store';store.mkdir(exist_ok=True)
    if any(store.iterdir()):raise ValueError('checkpoint measurement requires fresh private store')
    path=args.work/'checkpoint-input.bundle'
    entries={f'src/file{n:05}.txt':((f'content {n}\n'*100).encode(),n%2) for n in range(500)}
    entries['large.bin']=(b'0123456789abcdef'*(1024*256),0)
    head='empty';rows=[]
    def run_capture():
        result=subprocess.run([str(args.checkpoint_host),'capture',str(store),str(path),head,'none'],capture_output=True,check=True)
        return result.stdout.decode().strip()
    for operation in ['initial','unchanged','small_edit','large_edit']:
        if operation=='small_edit':entries['src/file00000.txt']=(b'changed\n',0)
        if operation=='large_edit':entries['large.bin']=(b'X'+entries['large.bin'][0][1:],0)
        before={p.name:p.stat().st_size for p in store.iterdir()};start=time.perf_counter_ns()
        admission_start=time.perf_counter_ns();payload=bundle(entries);path.write_bytes(payload);admission_ns=time.perf_counter_ns()-admission_start
        sample=timed(run_capture);head=sample['value'];total_ns=time.perf_counter_ns()-start
        after={p.name:p.stat().st_size for p in store.iterdir()}
        read=timed(lambda:subprocess.run([str(args.checkpoint_host),'read',str(store),head,'large.bin'],capture_output=True,check=True).stdout)
        assert read['value']==entries['large.bin'][0]
        rows.append({'operation':operation,'admission_ns':admission_ns,'native_process_ns':sample['wall_ns'],'total_ns':total_ns,
                     'new_stored_bytes':sum(size for name,size in after.items() if name not in before),'objects':len(after)-1,
                     'historical_read_ns':read['wall_ns'],'snapshot':head,'input_bytes':len(payload)})
    return {'rows':rows,'scope':'single private caller, admitted regular-file bytes/executable flags; source discovery/ignores/symlinks/stacks/restores absent; typed immutable objects and file/directory fsync before HEAD acknowledgement; no Git performance comparison'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--work',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--corpus',type=Path,required=True);parser.add_argument('--scan-host',type=Path,required=True);parser.add_argument('--checkpoint-host',type=Path,required=True)
    parser.add_argument('--rg',default=shutil.which('rg'));parser.add_argument('--records',type=int,default=250);parser.add_argument('--trials',type=int,default=7)
    args=parser.parse_args();args.work.mkdir(parents=True,exist_ok=True)
    result={'schema_version':1,'python':sys.version,'platform':platform.platform(),'trials':args.trials,
            'tools':{str(p.name):{'bytes':p.stat().st_size,'sha256':digest(p.read_bytes())} for p in [args.scan_host,args.checkpoint_host,Path(args.rg)]}}
    result['repository']=repository(args);result['schema']=schema_experiment(args);result['checkpoint']=checkpoint(args)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
    for group in ['repository','schema']:
        for mode in sorted({row['mode'] for row in result[group]['rows']}):
            values=[r['wall_ns']/1e6 for r in result[group]['rows'] if r['mode']==mode]
            print(group,mode,round(statistics.median(values),3),'ms')


if __name__=='__main__':main()
