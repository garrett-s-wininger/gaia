import argparse,json,statistics,time
from pathlib import Path
from common import HERE,save,sources,provenance,publish
import assets,native_and_tests,workspaces

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--work',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--native',type=Path,required=True);parser.add_argument('--lock',type=Path,required=True);parser.add_argument('--trials',type=int,default=5);parser.add_argument('--only',choices=['assets','native','workspaces','editor','doctests'],nargs='*');args=parser.parse_args();args.work.mkdir(parents=True,exist_ok=True)
    pins=sources();functions=dict(assets=assets.run,native=native_and_tests.native,workspaces=workspaces.run,editor=workspaces.editor,doctests=native_and_tests.doctests)
    for name in args.only or functions:
        result=functions[name](args);assert pins==sources(),'source drift'
        data=dict(study=name,trials=args.trials,provenance=provenance(),result=result,source_pins_verified_after=True)
        entry=publish(args.output/name,data);summary=[]
        for mode in sorted({r['mode'] for r in result['rows']}):
            rows=[r for r in result['rows'] if r['mode']==mode];summary.append(dict(mode=mode,median_ms=statistics.median(r['wall_ns']/1e6 for r in rows),samples=len(rows)))
        save(args.output/name/'summary.json',dict(rows=summary,raw_identity=entry));save(args.output/name/'validation.json',dict(passed=True,operations=len(result['rows']),source_pins_verified_after=True,scope=result['scope']));print(name,json.dumps(summary),flush=True)
if __name__=='__main__':main()
