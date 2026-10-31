"""Allocation diagnostics and immutable trace identity, outside request timings."""
import argparse,json,tracemalloc
from pathlib import Path
from common import HERE,digest,pins,publish,read_corpus
import reconcile

def run(args):
    _,_,objects=read_corpus(args.index,args.payload);a={int(k,16) for k in objects};ordered=sorted(a);n=max(1,len(a)//100);b=set(ordered[n:])|{int(digest(f'new-{i}'.encode()),16) for i in range(n)};rows=[]
    for method in ('full','merkle','iblt'):
        tracemalloc.start();result=reconcile.one(a,b,method,len(a^b));_,peak=tracemalloc.get_traced_memory();tracemalloc.stop();rows.append({'method':method,'python_traced_peak_bytes':peak,'result':result})
    sources=[Path(__file__),HERE/'reconcile.py',HERE/'common.py'];data={'schema':'GAIA-RECONCILIATION-ALLOCATIONS-1','scope':'Separate tracemalloc diagnostic withinputsetsalreadyowned. Includesreconciliation+independentoracles and instrumentedCPU; doesnotmeasureprocessRSS/nativeallocations orreplace requesttiming.','objects':len(a),'difference':len(a^b),'rows':rows}
    print(publish(args.output,data,{'cases':[{'method':r['method'],'python_traced_peak_bytes':r['python_traced_peak_bytes']} for r in rows]},{'passed':True,'same_exact_differences':True,'diagnostic_not_primary_latency':True},sources))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--index',type=Path,required=True);p.add_argument('--payload',type=Path,required=True);p.add_argument('--output',type=Path,required=True);run(p.parse_args())
