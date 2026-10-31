"""Train-only 1D/3D embedding orders for a common real-trace evaluator."""
import argparse
from collections import defaultdict,deque,OrderedDict
import ctypes
import fcntl
import hashlib
import json
import math
from pathlib import Path
import random
import time


def digest(body):return hashlib.sha256(body).hexdigest()


def bfs_order(count,edges):
    adjacency=defaultdict(dict)
    for left,right,weight in edges:
        adjacency[left][right]=weight;adjacency[right][left]=weight
    remaining=set(range(count));result=[]
    while remaining:
        first=max(remaining,key=lambda n:(sum(adjacency[n].values()),-n));queue=deque([first]);remaining.remove(first)
        while queue:
            node=queue.popleft();result.append(node)
            for neighbor in sorted(adjacency[node],key=lambda n:(-adjacency[node][n],n)):
                if neighbor in remaining:remaining.remove(neighbor);queue.append(neighbor)
    return result


def morton_order(positions,count):
    lower=[min(positions[i*3+d] for i in range(count)) for d in range(3)]
    upper=[max(positions[i*3+d] for i in range(count)) for d in range(3)]
    def key(i):
        values=[int(1023*(positions[i*3+d]-lower[d])/max(1e-12,upper[d]-lower[d])) for d in range(3)];result=0
        for bit in range(10):
            for d in range(3):result|=((values[d]>>bit)&1)<<(bit*3+d)
        return result,i
    return sorted(range(count),key=key)


def model_reads(order,trace,sizes,group_size=8,budget=8*1024*1024):
    groups=[tuple(order[i:i+group_size]) for i in range(0,len(order),group_size)];locations={c:i for i,g in enumerate(groups) for c in g}
    lru=OrderedDict();retained=0;read_bytes=0;calls=0;evictions=0
    for chunk in trace:
        group=locations[chunk]
        if group in lru:lru.move_to_end(group);continue
        size=sum(sizes[c] for c in groups[group]);read_bytes+=size;calls+=1
        while retained+size>budget and lru:
            _,old=lru.popitem(last=False);retained-=old;evictions+=1
        if size<=budget:lru[group]=size;retained+=size
    return dict(read_bytes=read_bytes,group_reads=calls,evictions=evictions,retained_bytes=retained)


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--library',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--lock',type=Path,required=True);p.add_argument('--iterations',type=int,default=80);args=p.parse_args()
    body=args.input.read_bytes();data=json.loads(body);n=len(data['chunks']);edges=data['training_edges'];pins={p.name:digest(p.read_bytes()) for p in [Path(__file__),Path(__file__).with_name('embedding.odin')]};library_pin=digest(args.library.read_bytes())
    lib=ctypes.CDLL(str(args.library.resolve()));call=lib.gaia_embed;call.argtypes=[ctypes.c_uint32,ctypes.c_uint32,ctypes.c_uint32,ctypes.POINTER(ctypes.c_double),ctypes.POINTER(ctypes.c_double)];call.restype=ctypes.c_int32
    orders={};metadata={};coordinates={}
    for mode in ['lexical','bfs','force1d','force3d']:
        with args.lock.open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX);begin=time.perf_counter_ns();cpu=time.process_time_ns()
            if mode=='lexical':order=list(range(n))
            elif mode=='bfs':order=bfs_order(n,edges)
            else:
                dim=1 if mode=='force1d' else 3;weights=(ctypes.c_double*(n*n))();maximum=max(w for a,b,w in edges)
                for left,right,weight in edges:weights[left*n+right]=weights[right*n+left]=weight/maximum
                rng=random.Random(51);positions=(ctypes.c_double*(n*dim))(*(rng.uniform(-1,1) for _ in range(n*dim)))
                code=call(n,dim,args.iterations,weights,positions);assert code==0
                assert all(math.isfinite(x) for x in positions)
                coordinates[mode]=list(positions)
                order=sorted(range(n),key=lambda i:(positions[i],i)) if dim==1 else morton_order(positions,n)
            elapsed=time.perf_counter_ns()-begin;cpu=time.process_time_ns()-cpu
        assert sorted(order)==list(range(n));orders[mode]=order;metadata[mode]=dict(wall_ns=elapsed,cpu_ns=cpu)
    sizes=[row['size'] for row in data['chunks']]
    model={mode:{trace:model_reads(order,data[trace],sizes) for trace in ['training','heldout','reverse_synthetic']} for mode,order in orders.items()}
    assert pins=={p.name:digest(p.read_bytes()) for p in [Path(__file__),Path(__file__).with_name('embedding.odin')]};assert digest(args.library.read_bytes())==library_pin;assert digest(args.input.read_bytes())==digest(body)
    result=dict(schema='GAIA-GEOMETRY-ORDER-1',input_sha256=digest(body),source_sha256=pins,library_sha256=library_pin,nodes=n,training_edges=len(edges),iterations=args.iterations,orders=orders,construction=metadata,coordinates=coordinates,cache_model=model,
        scope='Native deterministic logical spring/repulsion embedding, training edges only, one seed.1Dsorted/3DMorton groups8;8MiBLRU modeledreadbytes. Heldout is another realfreshstart of sameDjangoworkload; reverse syntheticstress. Nothardware3Dplacement or measuredstoragethroughput; commondata-lane evaluator must charge actualrepacking andverifiedreads.')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(construction=metadata,cache_model=model),indent=2))


if __name__=='__main__':main()
