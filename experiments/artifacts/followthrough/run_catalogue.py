"""Same producer catalogue consumed by Python, Odin and Node without object handoff."""
from pathlib import Path
import argparse,ctypes,hashlib,json,platform,random,statistics,subprocess,sys,time,tracemalloc
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parent))
import catalogue,compact_python as compact

def digest(body):return hashlib.sha256(body).hexdigest()
def source_rows(index):
    body=index.read_bytes();magic,version,metadata,n,m,d,c,s=compact.HEADER.unpack_from(body)
    table=compact.HEADER.size+metadata;pool=table+n*compact.FILE.size+m*compact.MODULE.size+d*compact.DIRECTORY.size+c*4
    result=[]
    for i in range(n):
        a,l,container,flags,offset,size,pin,crc=compact.FILE.unpack_from(body,table+i*compact.FILE.size)
        result.append(dict(name=body[pool+a:pool+a+l].decode(),offset=offset,size=size,sha256=pin.hex()))
    return result

def run(args):
    args.work.mkdir(parents=True,exist_ok=True);args.output.mkdir(parents=True,exist_ok=True)
    rows=source_rows(args.index);prep=time.perf_counter();encoded=catalogue.encode(rows);producer=time.perf_counter()-prep;json_body=json.dumps(rows,separators=(',',':'),sort_keys=True).encode();pins={mode:digest(body) for mode,body in [('binary',encoded),('json',json_body)]}
    for mode,body in [('binary',encoded),('json',json_body)]:(args.work/('catalogue.'+mode)).write_bytes(body)
    expected=catalogue.query_objects(rows);native=catalogue.Native(args.library.resolve());results=[];rng=random.Random(572)
    for block in range(args.trials):
        cases=['python-json','python-objects','python-direct','odin-direct','node-json','node-direct'];rng.shuffle(cases)
        for mode in cases:
            binary=not mode.endswith('json');path=args.work/('catalogue.'+('binary' if binary else 'json'));pin=pins['binary' if binary else 'json']
            if mode.startswith('node'):
                begin=time.perf_counter();child=subprocess.run(['node',str(HERE/'catalogue_node.js'),str(path),mode.split('-')[1],str(args.iterations),pin],capture_output=True,text=True,check=True);elapsed=time.perf_counter()-begin;result=json.loads(child.stdout)
                assert result['result']==expected
                results.append(dict(block=block,mode=mode,operation_ms=result['operation_ms'],fresh_process_seconds=elapsed));continue
            times=[]
            for trial in range(args.iterations):
                begin=time.perf_counter();body=path.read_bytes()
                if digest(body)!=pin:raise ValueError('catalogue pin')
                if mode=='python-json':out=catalogue.query_objects(json.loads(body))
                elif mode=='python-objects':out=catalogue.query_objects(catalogue.objects(body))
                elif mode=='python-direct':out=catalogue.query_direct(body)
                else:out=native.query(body)
                times.append((time.perf_counter()-begin)*1000);assert out==expected
            results.append(dict(block=block,mode=mode,operation_ms=times))
    # Traced peak allocations are diagnostic and excluded from timing; native internal
    # allocation is not measured by tracemalloc (the exported loop allocates no objects).
    peaks={}
    for mode in ('python-json','python-objects','python-direct','odin-direct'):
        tracemalloc.start()
        if mode=='python-json':out=catalogue.query_objects(json.loads(json_body))
        elif mode=='python-objects':out=catalogue.query_objects(catalogue.objects(encoded))
        elif mode=='python-direct':out=catalogue.query_direct(encoded)
        else:out=native.query(encoded)
        peaks[mode]=tracemalloc.get_traced_memory()[1];tracemalloc.stop();assert out==expected
    source=[HERE/'catalogue.odin',HERE/'catalogue.py',HERE/'catalogue_node.js',HERE/'run_catalogue.py'];data=dict(rows=len(rows),expected=expected,producer_seconds=producer,sizes=dict(binary=len(encoded),json=len(json_body)),pins=pins,python=sys.version,platform=platform.platform(),source_hashes={p.name:digest(p.read_bytes()) for p in source},library_sha256=digest(args.library.read_bytes()),index_sha256=digest(args.index.read_bytes()),observations=results,python_traced_peak_bytes=peaks)
    raw=json.dumps(data,sort_keys=True).encode();(args.output/'results.json').write_bytes(raw)
    reduced=[dict(mode=mode,median_operation_ms=statistics.median(t for r in results if r['mode']==mode for t in r['operation_ms']),block_median_ms=[statistics.median(r['operation_ms']) for r in results if r['mode']==mode]) for mode in sorted({r['mode'] for r in results})]
    (args.output/'summary.json').write_text(json.dumps(dict(rows=len(rows),sizes=data['sizes'],rows_by_mode=reduced,python_traced_peak_bytes=peaks,raw_identity=dict(bytes=len(raw),sha256=digest(raw))),indent=2)+'\n')
    print(json.dumps(reduced,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--index',type=Path,required=True);p.add_argument('--library',type=Path,required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--trials',type=int,default=5);p.add_argument('--iterations',type=int,default=15);run(p.parse_args())
