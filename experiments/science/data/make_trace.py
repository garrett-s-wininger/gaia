"""Create portable training/heldout chunk traces from a frozen consumer run."""
from collections import Counter
import argparse,json,time
from pathlib import Path
from common import digest,save

def run(args):
    started=time.perf_counter_ns();raw=args.payload.read_bytes();data=json.loads(args.trace.read_text());row=data['rows'][0]
    if digest(raw)!=data['descriptors']['payload']['digest']:raise ValueError('trace/payload identity')
    first=row['children'][0]['server_after']['consumer_requests'];second=row['children'][1]['server_after']['consumer_requests']
    def chunks(ranges):
        out=[]
        for off,size in ranges:
            if size:out.extend(range(off//65536,(off+size-1)//65536+1))
        return out
    train=chunks(row['trace'][:first]);heldout=chunks(row['trace'][first:second]);edges=Counter();graph=time.perf_counter_ns()
    for i,b in enumerate(train):
        for a in train[max(0,i-3):i]:
            if a!=b:edges[tuple(sorted((a,b)))]+=1
    graph_ns=time.perf_counter_ns()-graph
    meta=[{'size':len(raw[i:i+65536]),'sha256':digest(raw[i:i+65536])} for i in range(0,len(raw),65536)]
    result={'schema':'GAIA-COACCESS-1','payload_sha256':digest(raw),'chunk_bytes':65536,'chunks':meta,'training':train,'heldout':heldout,'reverse_synthetic':list(reversed(heldout)),'training_edges':[[a,b,w] for (a,b),w in sorted(edges.items())],'scope':'Actual first/second fresh Django consumer ranges from prior frozen study; graph edges from training only; reverse is explicitly synthetic.'}
    save(args.output,result);save(args.output.with_suffix('.preparation.json'),{'input_trace_sha256':digest(args.trace.read_bytes()),'output_sha256':digest(args.output.read_bytes()),'total_preparation_ns':time.perf_counter_ns()-started,'edge_construction_ns':graph_ns,'scope':'Replayinput preparation, not originalDjango tracecollection; payloadread/hash, rawJSONparse and chunkpins charged here.'})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--payload',type=Path,required=True);p.add_argument('--trace',type=Path,required=True);p.add_argument('--output',type=Path,required=True);run(p.parse_args())
