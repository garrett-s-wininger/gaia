#!/usr/bin/env python3
"""Small true disk-restore control; synthetic metadata, not a package ecosystem."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import random
import statistics
import subprocess
import time

HERE=Path(__file__).resolve().parent

def run(args):
    args.output.mkdir(parents=True,exist_ok=True);work=args.output/'blobs';work.mkdir(exist_ok=True)
    source=HERE/'node_graph.js';data=dict(run_id=datetime.now(timezone.utc).isoformat(),node=subprocess.check_output([args.node,'--version'],text=True).strip(),
        node_sha256=hashlib.sha256(Path(args.node).read_bytes()).hexdigest(),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        scope='Fresh Node processes; complete launch/output/normal exit. Warm page cache. Disk blobs rebuilt for the identical runtime. Synthetic object graph only.',
        trials=args.trials,setup=[],cases=[])
    for count in (0,100000):
        blob=work/(str(count)+'.blob');env=dict(os.environ,GAIA_GRAPH_COUNT=str(count));start=time.perf_counter()
        p=subprocess.run([args.node,'--snapshot-blob',str(blob),'--build-snapshot',str(source)],env=env,capture_output=True,text=True,check=True)
        data['setup'].append(dict(count=count,seconds=time.perf_counter()-start,blob_bytes=blob.stat().st_size,blob_sha256=hashlib.sha256(blob.read_bytes()).hexdigest(),stderr=p.stderr))
    samples={(c,m):[] for c in (0,100000) for m in ('exec','restore')};rng=random.Random(613)
    for block in range(-1,args.trials):
        order=list(samples);rng.shuffle(order)
        for count,mode in order:
            token=f'{block}-{count}-{mode}';env=dict(os.environ,GAIA_GRAPH_COUNT=str(count),GAIA_REQUEST_TOKEN=token)
            cmd=[args.node,str(source),token] if mode=='exec' else [args.node,'--snapshot-blob',str(work/(str(count)+'.blob')),'--',token]
            begin=time.perf_counter();p=subprocess.run(cmd,env=env,capture_output=True,text=True,check=True);end=time.perf_counter()
            result=json.loads(p.stdout)
            expected=sum(i%31+i%113 for i in range(0,count,997))
            if (result['count'],result['checksum'],result['token'],result['argvToken'])!=(count,expected,token,token):raise ValueError(str(result))
            if block>=0:samples[count,mode].append(dict(block=block,seconds=end-begin,**result))
    for (count,mode),ss in samples.items():
        data['cases'].append(dict(count=count,mode=mode,samples=ss,median_ms=statistics.median(s['seconds'] for s in ss)*1000))
    (args.output/'results.json').write_text(json.dumps(data,indent=2)+'\n')
    summary={k:v for k,v in data.items() if k!='cases'}
    summary['cases']=[{k:v for k,v in c.items() if k!='samples'}|{'paired_wins':sum(a['seconds']<b['seconds'] for a,b in zip(samples[c['count'],c['mode']],samples[c['count'],'exec']))} for c in data['cases']]
    summary['raw_sha256']=hashlib.sha256((args.output/'results.json').read_bytes()).hexdigest()
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (args.output/'validation.json').write_text(json.dumps(dict(passed=True,operations=args.trials*4,all_graphs_and_request_state_match=True,raw_sha256=summary['raw_sha256']),indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--node',default='/usr/bin/node');p.add_argument('--trials',type=int,default=7);p.add_argument('--output',type=Path,default=HERE/'_work/node')
    run(p.parse_args())
