"""Actual admitted source generations and artifact chunks; soft budget companion."""
from pathlib import Path
import argparse,fcntl,json,os,signal,sys,threading,time
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));from admission import ChunkStore,digest
from service import ModelIO,Profile


def run(args):
    start=time.perf_counter();bodies={};generations=[]
    for path in sorted(args.workspace.rglob('*.py')):
        if '_work' in path.parts or path.is_symlink() or path.stat().st_size>1024*1024:continue
        body=path.read_bytes();bodies[digest(body)]=body
    if not bodies:raise ValueError('no real workspace source bytes')
    base=dict(bodies)
    largest=max(base.values(),key=len)
    for generation in range(args.generations):
        changed=largest+b'\n# admitted generation '+str(generation).encode()+b'\n';key=digest(changed);bodies[key]=changed;generations.append(key)
    workspace_bytes=sum(map(len,bodies.values()))
    if workspace_bytes>=args.budget:raise ValueError('workspace alone exceeds logical admission budget')
    # Producer-side pinned chunk manifest preparation is charged in companion readiness.
    data=json.loads(args.trace.read_text());raw=args.payload.read_bytes();descriptor=data['descriptors']['payload']
    if len(raw)!=descriptor['size'] or digest(raw)!=descriptor['digest']:raise ValueError('companion payload/trace identity')
    hashes=[digest(raw[i:i+65536]) for i in range(0,len(raw),65536)];del raw
    trace=data['rows'][0]['trace']
    model=ModelIO(args.payload.parent,Profile('nominal'));store=ChunkStore(args.payload,65536,args.budget-workspace_bytes,model,hashes)
    for offset,size in trace:store.read(offset,size)
    stop=threading.Event()
    def input_stop():
        for line in sys.stdin:
            if line.strip()=='STOP':stop.set();return
    threading.Thread(target=input_stop,daemon=True).start()
    signal.signal(signal.SIGTERM,lambda *_:stop.set());signal.signal(signal.SIGINT,lambda *_:stop.set())
    ready=dict(event='READY',pid=os.getpid(),workspace_bytes=workspace_bytes,generations=args.generations,unique_source_bodies=len(bodies),source_set_sha256=digest(''.join(sorted(bodies)).encode()),logical_budget=args.budget,admitted_chunk_bytes=store.bytes,readiness_seconds=time.perf_counter()-start,scope='logical admitted bytes; process RSS is additional and externally sampled')
    print(json.dumps(ready),flush=True);loops=0;until=time.monotonic()+args.hold_seconds
    try:
        while not stop.is_set() and time.monotonic()<until:
            if args.replay:
                for offset,size in trace:
                    if stop.is_set():break
                    store.read(offset,size)
                loops+=1;stop.wait(.02)
            else:stop.wait(.05)
        result=dict(ready=ready,loops=loops,elapsed_seconds=time.perf_counter()-start,cache=store.stats(),admitted_bytes=workspace_bytes+store.bytes)
        if result['admitted_bytes']>args.budget:raise ValueError('budget exceeded')
        if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(dict(event='STOPPED',loops=loops,admitted_bytes=result['admitted_bytes'])),flush=True)
    finally:store.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--payload',type=Path,required=True);p.add_argument('--trace',type=Path,required=True);p.add_argument('--budget',type=int,default=16*1024*1024);p.add_argument('--generations',type=int,default=4);p.add_argument('--hold-seconds',type=float,default=600);p.add_argument('--replay',action='store_true');p.add_argument('--output',type=Path);run(p.parse_args())
