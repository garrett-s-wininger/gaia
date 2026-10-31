"""Exact inventory, prefix-Merkle and IBLT-style set reconciliation proof."""
from collections import deque
import argparse,hashlib,math,random,statistics,time
from pathlib import Path
from common import HERE,digest,measured,pins,publish,read_corpus

def checksum(key):return int.from_bytes(hashlib.blake2b(key.to_bytes(32,'big'),digest_size=8,person=b'gaia-iblt').digest(),'big')
def positions(key,size):
    # Three distinct positions; deterministic domain-separated SHA-256.
    raw=hashlib.sha256(b'GAIA-IBLT-POS-1'+key.to_bytes(32,'big')).digest();out=[]
    for i in range(3):
        at=int.from_bytes(raw[i*8:i*8+8],'big')%size
        while at in out:at=(at+1)%size
        out.append(at)
    return out

class Table:
    def __init__(self,size):self.cells=[[0,0,0] for _ in range(max(3,size))]
    def update(self,key,sign):
        pin=checksum(key)
        for at in positions(key,len(self.cells)):
            cell=self.cells[at];cell[0]+=sign;cell[1]^=key;cell[2]^=pin
    def subtract(self,other):
        if len(self.cells)!=len(other.cells):raise ValueError('table shape')
        result=Table(len(self.cells));result.cells=[[a[0]-b[0],a[1]^b[1],a[2]^b[2]] for a,b in zip(self.cells,other.cells)];return result
    def decode(self):
        queue=deque(range(len(self.cells)));positive=set();negative=set();steps=0
        while queue:
            at=queue.popleft();count,key,pin=self.cells[at]
            if abs(count)!=1 or checksum(key)!=pin:continue
            target=positive if count==1 else negative
            if key in target:return None
            target.add(key);steps+=1
            if steps>len(self.cells):return None
            for slot in positions(key,len(self.cells)):
                c=self.cells[slot];c[0]-=count;c[1]^=key;c[2]^=pin;queue.append(slot)
        return (positive,negative) if all(c==[0,0,0] for c in self.cells) else None
    def wire(self):
        # signed64 count +256bit key XOR +64bit checksum XOR, plus header.
        return 16+48*len(self.cells)

def merkle(values,leaf=32,prefix=''):
    ordered=tuple(sorted(values));body=b''.join(x.to_bytes(32,'big') for x in ordered)
    node={'hash':hashlib.sha256(b'GAIA-MERKLE-1'+body).digest(),'values':ordered,'children':{}}
    if len(ordered)>leaf and len(prefix)<64:
        groups={}
        for key in ordered:groups.setdefault(format(key,'064x')[len(prefix)],[]).append(key)
        node['children']={n:merkle(group,leaf,prefix+n) for n,group in groups.items()}
    return node

EMPTY=merkle([])
def merkle_diff(a,b):
    wire=0;rounds=0;positive=set();negative=set();front=[('',a,b)]
    while front:
        rounds+=1;next_front=[]
        for prefix,left,right in front:
            wire+=1+len(prefix)+32+1+32 # explicit prefix/hash query and response
            if left['hash']==right['hash']:continue
            if not left['children'] or not right['children']:
                wire+=8+32*(len(left['values'])+len(right['values']))
                positive.update(set(left['values'])-set(right['values']));negative.update(set(right['values'])-set(left['values']))
            else:
                wire+=4
                for nibble in sorted(left['children'].keys()|right['children'].keys()):next_front.append((prefix+nibble,left['children'].get(nibble,EMPTY),right['children'].get(nibble,EMPTY)))
        front=next_front
    return positive,negative,wire,rounds

def full(a,b):
    aa=sorted(a);bb=sorted(b);i=j=0;positive=set();negative=set()
    while i<len(aa) and j<len(bb):
        if aa[i]==bb[j]:i+=1;j+=1
        elif aa[i]<bb[j]:positive.add(aa[i]);i+=1
        else:negative.add(bb[j]);j+=1
    positive.update(aa[i:]);negative.update(bb[j:]);return positive,negative,16+32*(len(a)+len(b)),1

def one(a,b,method,estimate):
    started=time.perf_counter_ns();build_ns=update_ns=0;fallback=False;update_check=None
    if method=='full':result=full(a,b)
    elif method=='merkle':
        left=merkle(a);right=merkle(b);build_ns=time.perf_counter_ns()-started;result=merkle_diff(left,right)
    else:
        cells=max(3,math.ceil(estimate*1.8));left=Table(cells);right=Table(cells)
        for key in a:left.update(key,1)
        for key in b:right.update(key,1)
        build_ns=time.perf_counter_ns()-started
        decoded=left.subtract(right).decode();wire=left.wire()+32;rounds=1
        if decoded is None:
            fallback=True;positive,negative,more,extra=full(a,b);wire+=more;rounds+=extra
        else:positive,negative=decoded
        result=(positive,negative,wire,rounds)
        # Maintain already-built summary after replacing one actual member.
        if a:
            old=min(a);new=int.from_bytes(hashlib.sha256(b'update'+old.to_bytes(32,'big')).digest(),'big');t=time.perf_counter_ns();left.update(old,-1);left.update(new,1);update_ns=time.perf_counter_ns()-t
            update_check=(left,cells,(a-{old})|{new})
    positive,negative,wire,rounds=result
    update_end=time.perf_counter_ns()
    # Reconstruct and authenticate the remote set. Its root is a distinct32B
    # semantic check, not a probabilistic cell checksum.
    verify=time.perf_counter_ns();reconstructed=(a-positive)|negative
    encode=lambda values:b''.join(k.to_bytes(32,'big') for k in sorted(values))
    if hashlib.sha256(encode(reconstructed)).digest()!=hashlib.sha256(encode(b)).digest():raise ValueError('remote set commitment mismatch')
    verification_ns=time.perf_counter_ns()-verify;wall=time.perf_counter_ns()-started
    # Independent full-set/update rebuild oracles are outside all request clocks.
    if positive!=a-b or negative!=b-a:raise ValueError('incorrect reconciliation')
    if update_check:
        left,cells,values=update_check;oracle=Table(cells)
        for key in values:oracle.update(key,1)
        assert left.cells==oracle.cells
    return {'wall_ns':wall-update_ns,'build_ns':build_ns,'final_verification_ns':verification_ns,'incremental_summary_update_ns':update_ns,'wire_bytes':wire+32,'round_trips':rounds,'fallback':fallback,'difference':len(positive)+len(negative)}

def run(args):
    sources=[Path(__file__),HERE/'common.py'];before=pins(sources);_,_,objects=read_corpus(args.index,args.payload)
    real={int(k,16) for k in objects};datasets={'real-package-ids':real,'generated-1000':{int.from_bytes(hashlib.sha256(f'id{i}'.encode()).digest(),'big') for i in range(1000)},'generated-10000':{int.from_bytes(hashlib.sha256(f'id{i}'.encode()).digest(),'big') for i in range(10000)}}
    rows=[]
    for name,a in datasets.items():
        ordered=sorted(a)
        for rate in (.001,.01,.1):
            count=max(1,int(len(a)*rate));b=set(ordered[count:]);b.update(int.from_bytes(hashlib.sha256(f'new-{i}'.encode()).digest(),'big') for i in range(count));difference=len(a^b)
            for block in range(args.trials):
                cases=[('full',difference),('merkle',difference),('iblt',difference),('iblt-underestimate',max(1,difference//4))];random.Random(101+block).shuffle(cases)
                for label,estimate in cases:
                    with measured(args.lock):value=one(a,b,'iblt' if label.startswith('iblt') else label,estimate)
                    rows.append(dict(dataset=name,count=len(a),rate=rate,block=block,method=label,estimate=estimate,**value))
    assert before==pins(sources)
    summary=[]
    for name in datasets:
        for rate in (.001,.01,.1):
            for method in ('full','merkle','iblt','iblt-underestimate'):
                selected=[r for r in rows if r['dataset']==name and r['rate']==rate and r['method']==method]
                summary.append(dict(dataset=name,rate=rate,method=method,median_ms=statistics.median(r['wall_ns']/1e6 for r in selected),wire_bytes=selected[0]['wire_bytes'],round_trips=selected[0]['round_trips'],fallbacks=sum(r['fallback'] for r in selected)))
    data={'schema':'GAIA-SCIENCE-RECONCILE-1','scope':'Python algorithm and encoded-metadata accounting; no network/payload-transfer timing. Build both summaries and exact-set cryptographic commitment reconstruction charged. Independent full-set/update-rebuild oracles outside every request clock. Diagnostic IBLT update_ns separately records only two updates. No native algorithm floor.','corpus':{'real_objects':len(real),'index_sha256':digest(args.index.read_bytes()),'payload_sha256':digest(args.payload.read_bytes())},'sources':before,'rows':rows}
    print(publish(args.output,data,{'cases':summary},{'passed':True,'operations':len(rows),'exact_difference_oracles':True,'summary_update_oracles':True,'forced_underestimate_fallbacks':sum(r['fallback'] for r in rows if r['method']=='iblt-underestimate')},sources))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--index',type=Path,required=True);p.add_argument('--payload',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--lock',type=Path);p.add_argument('--trials',type=int,default=3);run(p.parse_args())
