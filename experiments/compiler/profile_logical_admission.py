"""Charge strict physical import separately from explicit logical edit admission.

Diagnostic only: import reads every member of an already known namespace. It
does not measure directory discovery or claim to replace a filesystem watcher.
Run against a completed ninja_benchmark.py result whose work directory remains.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import statistics
import struct

from logical_workspace import Workspace, import_physical


def decode_snapshot(body):
    if len(body)<16 or body[:8]!=b'GAIACIN2':raise ValueError('snapshot version')
    count=struct.unpack_from('<Q',body,8)[0];at=16;files={}
    if not 0<count<=100000:raise ValueError('snapshot count')
    for _ in range(count):
        if at+12>len(body):raise ValueError('snapshot row')
        namesize,size=struct.unpack_from('<IQ',body,at);at+=12
        if not 0<namesize<=4096 or size>64*1048576 or at+namesize+size+2>len(body):raise ValueError('snapshot bound')
        name=body[at:at+namesize].decode();at+=namesize
        if body[at]!=0 or body[at+size+1]!=0 or name in files:raise ValueError('snapshot framing')
        at+=1;files[name]=body[at:at+size];at+=size+1
    if at!=len(body):raise ValueError('snapshot tail')
    return files


def run(args):
    source=args.run.read_bytes();run=json.loads(source);work=Path(run['work'])
    files=decode_snapshot((work/'baseline.gci').read_bytes())
    views=(work/'baseline.views').read_text().splitlines()
    if views[0]!='GAIACV1' or len(views)!=len(files)+1:raise ValueError('visibility framing')
    masks=dict(zip(sorted(files),map(int,views[1:])))
    jobs=max(masks.values()).bit_length();workspace=Workspace(files,masks,jobs)
    baseline=workspace.snapshot();name=next(n for n in files if n.endswith('/common/zstd_common.c'))
    changed=files[name].replace(b'return ZSTD_VERSION_NUMBER;',b'return ZSTD_VERSION_NUMBER+1;')
    if changed==files[name]:raise ValueError('expected generic source-edit fixture')
    # Refuse to profile a different physical mirror; never rewrite source files.
    if any(Path(n).read_bytes()!=b for n,b in files.items()):raise ValueError('physical mirror differs from baseline')
    rows=[];rng=random.Random(217)
    for block in range(args.trials):
        order=['strict-known-namespace-import','explicit-changed-body','explicit-no-op'];rng.shuffle(order)
        for kind in order:
            workspace.restore(baseline)
            if kind=='strict-known-namespace-import':
                _,stats=import_physical(workspace,files,masks)
            else:
                _,stats=workspace.apply({name:changed} if kind=='explicit-changed-body' else {})
                stats=dict(seconds=stats['admission_ns']/1e9,admission=stats,physical_reads=0,physical_bytes=0,stat_calls=0)
            rows.append(dict(block=block,kind=kind,**stats))
    summary={k:dict(median_ms=statistics.median(r['seconds']*1000 for r in rows if r['kind']==k),samples=args.trials) for k in order}
    result=dict(status='complete',diagnostic=True,run_sha256=hashlib.sha256(source).hexdigest(),files=len(files),bytes=sum(map(len,files.values())),jobs=jobs,edit_bytes=len(changed),initial_admission=workspace.initial_admission,limitations=['Warm page cache; known namespace only; no directory discovery.','Strict import is a correctness adapter, not an optimized filesystem watcher.','Explicit packet body already exists; admission hashing/copying is charged.'],summary=summary,observations=rows)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--trials',type=int,default=21)
    args=parser.parse_args()
    if args.trials<1:parser.error('positive trials required')
    run(args)
