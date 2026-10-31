"""Matched catalogue study with a fused Python binary control."""
from pathlib import Path
import argparse,hashlib,json
import catalogue,fused_catalogue,run_catalogue

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--index',type=Path,required=True);p.add_argument('--library',type=Path,required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--trials',type=int,default=5);p.add_argument('--iterations',type=int,default=15);args=p.parse_args()
    catalogue.query_direct=fused_catalogue.query_direct
    pins={path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in [Path(__file__),Path(fused_catalogue.__file__)]}
    run_catalogue.run(args)
    path=args.output/'results.json';data=json.loads(path.read_text());data['python_direct_override']='fused_catalogue.query_direct';data['override_source_hashes']=pins
    raw=json.dumps(data,sort_keys=True).encode();path.write_bytes(raw)
    path=args.output/'summary.json';summary=json.loads(path.read_text());summary['python_direct_override']=data['python_direct_override'];summary['raw_identity']=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest());path.write_text(json.dumps(summary,indent=2)+'\n')
