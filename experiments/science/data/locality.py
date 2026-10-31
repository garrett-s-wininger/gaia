"""Trace-derived pack grouping with charged construction and real verified reads."""
from collections import Counter,OrderedDict
import argparse,hashlib,json,os,random,statistics,time
from pathlib import Path
from common import HERE,digest,measured,pins,publish

def cluster(count,edges,width=8):
    adjacency={i:{} for i in range(count)}
    for a,b,weight in edges:
        adjacency[a][b]=weight;adjacency[b][a]=weight
    remaining=set(range(count));order=[]
    while remaining:
        seed=max(remaining,key=lambda k:(sum(adjacency[k].values()),-k));group=[seed];remaining.remove(seed)
        while remaining and len(group)<width:
            selected=max(remaining,key=lambda k:(sum(adjacency[a].get(k,0) for a in group),-k));group.append(selected);remaining.remove(selected)
        order.extend(group)
    return order

def reinforced(sequence,count,decay=.98):
    weights={}
    for i,node in enumerate(sequence):
        weights={key:value*decay for key,value in weights.items() if value*decay>=.01}
        for previous in sequence[max(0,i-3):i]:
            if previous!=node:
                key=tuple(sorted((previous,node)));weights[key]=weights.get(key,0)+1
        if len(weights)>4096:
            keep=sorted(weights,key=lambda key:(weights[key],key),reverse=True)[:4096];weights={key:weights[key] for key in keep}
    return [[a,b,w] for (a,b),w in sorted(weights.items())]

def build_layout(payload,order,width,path):
    started=time.perf_counter_ns();groups=[];locations={};at=0
    with path.open('wb') as output:
        for start in range(0,len(order),width):
            members=order[start:start+width];size=0
            for node in members:
                body=payload[node*65536:(node+1)*65536];output.write(body);size+=len(body)
            group=(at,size,members);groups.append(group)
            for node in members:locations[node]=group
            at+=size
    return locations,time.perf_counter_ns()-started,at

def evaluate(path,locations,meta,sequence,budget,cost_size=False):
    cache=OrderedDict();frequency=Counter();resident=peak=transient=reads=read_bytes=evictions=hits=0;result=hashlib.sha256();start=time.perf_counter_ns()
    with path.open('rb') as stream:
        for node in sequence:
            frequency[node]+=1
            if node in cache:hits+=1;cache.move_to_end(node)
            else:
                offset,size,members=locations[node];stream.seek(offset);body=stream.read(size)
                if len(body)!=size:raise ValueError('truncated pack')
                reads+=1;read_bytes+=size;transient=max(transient,size);at=0
                for member in members:
                    n=meta[member]['size'];part=body[at:at+n];at+=n
                    if digest(part)!=meta[member]['sha256']:raise ValueError('bad relocated chunk')
                    if member in cache:continue
                    if n>budget:raise ValueError('cache cannot admit one chunk')
                    while resident+n>budget:
                        victim=min(cache,key=lambda k:(frequency[k]/len(cache[k]),k)) if cost_size else next(iter(cache))
                        resident-=len(cache.pop(victim));evictions+=1
                    cache[member]=part;resident+=n;peak=max(peak,resident)
            # The demanded chunk is more recent than speculative siblings.
            cache.move_to_end(node);value=cache[node]
            result.update(node.to_bytes(4,'big'));result.update(hashlib.sha256(value).digest())
    return {'wall_ns':time.perf_counter_ns()-start,'reads':reads,'read_bytes':read_bytes,'hits':hits,'evictions':evictions,'peak_cache_bytes':peak,'max_transient_group_bytes':transient,'budget':budget,'result_sha256':result.hexdigest()}

def model(sequence,meta,width,budget):
    cache=OrderedDict();resident=reads=read_bytes=peak=0
    for node in sequence:
        if node in cache:cache.move_to_end(node);continue
        group=range((node//width)*width,min(len(meta),(node//width+1)*width));reads+=1
        for member in group:
            size=meta[member]['size'];read_bytes+=size
            if member in cache:continue
            while resident+size>budget:
                _,old=cache.popitem(last=False);resident-=old
            cache[member]=size;resident+=size;peak=max(peak,resident)
        cache.move_to_end(node)
    return {'reads':reads,'read_bytes':read_bytes,'peak_cache_bytes':peak}

def run(args):
    sources=[Path(__file__),HERE/'common.py'];before=pins(sources);input_body=args.input.read_bytes();data=json.loads(input_body);payload=args.payload.read_bytes()
    if digest(payload)!=data['payload_sha256']:raise ValueError('payload identity')
    args.work.mkdir(parents=True,exist_ok=False);count=len(data['chunks']);policies={};preparation={}
    for name in ('physical','static-cluster','reinforce-decay','cost-size'):
        started=time.perf_counter_ns()
        if name in ('physical','cost-size'):order=list(range(count));width=1 if name=='cost-size' else 8
        elif name=='static-cluster':order=cluster(count,data['training_edges']);width=8
        else:order=cluster(count,reinforced(data['training'],count));width=8
        policy_ns=time.perf_counter_ns()-started
        path=args.work/(name+'.pack');locations,layout_ns,written=build_layout(payload,order,width,path)
        policies[name]=(path,locations,name=='cost-size');preparation[name]={'policy_ns':policy_ns,'layout_ns':layout_ns,'written_bytes':written,'order_sha256':digest(b''.join(n.to_bytes(4,'big') for n in order)),'scope':'Every policy writes one full pack here, including canonical layout; producer acquisition is common and separate.'}
    if args.geometry:
        geometry=json.loads(args.geometry.read_text())
        if geometry['input_sha256']!=digest(input_body):raise ValueError('geometry input identity')
        for label,order in geometry['orders'].items():
            assert sorted(order)==list(range(count));name='geometry-'+label;path=args.work/(name+'.pack');locations,layout_ns,written=build_layout(payload,order,8,path);policies[name]=(path,locations,False)
            construction=geometry['construction'][label];policy_ns=construction['wall_ns'] if isinstance(construction,dict) else construction
            preparation[name]={'policy_ns':policy_ns,'layout_ns':layout_ns,'written_bytes':written,'order_sha256':digest(b''.join(n.to_bytes(4,'big') for n in order)),'source_sha256':digest(args.geometry.read_bytes())}
    rows=[];oracles={}
    for phase in ('heldout','reverse_synthetic'):
        result=hashlib.sha256()
        for node in data[phase]:result.update(node.to_bytes(4,'big'));result.update(bytes.fromhex(data['chunks'][node]['sha256']))
        oracles[phase]=result.hexdigest()
    for block in range(args.trials):
        cases=[(name,phase) for name in policies for phase in oracles];random.Random(block+71).shuffle(cases)
        for name,phase in cases:
            path,locations,cost_size=policies[name]
            with measured(args.lock):result=evaluate(path,locations,data['chunks'],data[phase],args.budget,cost_size)
            if result['result_sha256']!=oracles[phase]:raise ValueError('consumer mismatch')
            result['modeled_io_ms']=1000*(result['reads']*.001+result['read_bytes']/(16*1024*1024));rows.append({'block':block,'policy':name,'phase':phase,**result})
    assert before==pins(sources)
    summary=[]
    for name in policies:
        for phase in oracles:
            chosen=[r for r in rows if r['policy']==name and r['phase']==phase]
            summary.append({'policy':name,'phase':phase,'median_warm_read_verify_ms':statistics.median(r['wall_ns']/1e6 for r in chosen),'read_bytes':chosen[0]['read_bytes'],'read_calls':chosen[0]['reads'],'modeled_io_ms':chosen[0]['modeled_io_ms'],'policy_plus_layout_ms':(preparation[name]['policy_ns']+preparation[name]['layout_ns'])/1e6})
    result={'schema':'GAIA-SCIENCE-LOCALITY-1','scope':'Warm actual pack-file reads and per-chunkSHA; immutableproducer payload retained outside logicalreader cache budget. ActualDjango training/heldout access traces; reversedtrace synthetic. Everylayoutconstruction charged separately inclcanonical producer. Modeled1mscall+16MiBps I/O prediction is not actualdevice timing. No readerleases/concurrentcompaction/durability claim.','input_sha256':digest(input_body),'sources':before,'training_events':len(data['training']),'heldout_events':len(data['heldout']),'preparation':preparation,'rows':rows}
    print(publish(args.output,result,{'cases':summary},{'passed':True,'operations':len(rows),'exact_content_order':True,'cache_budget_overshoots':sum(r['peak_cache_bytes']>args.budget for r in rows),'training_only_placement':True},sources))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--payload',type=Path,required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--geometry',type=Path);p.add_argument('--budget',type=int,default=8*1024*1024);p.add_argument('--trials',type=int,default=3);p.add_argument('--lock',type=Path);run(p.parse_args())
