#!/usr/bin/env python3
"""Separate warm-solve profiles; never mix these times into benchmark samples."""
import argparse
import cProfile
import json
from pathlib import Path
import pstats
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import solver


def bucket(filename,name):
    if filename.endswith("/trail.py"):return "Trail storage/overlay"
    if filename.endswith("/incremental.py"):return "Incremental scheduler"
    if "/resolvelib/" in filename:return "Resolver core"
    if "/packaging/" in filename:return "Requirement/version/marker library"
    if filename.endswith("solver.py"):return "Provider/session glue"
    if "/zipfile/" in filename or "/email/" in filename:return "ZIP/metadata parser"
    if filename=="~" and any(t in name for t in ("'dict'","'set'","'list'","builtins.hash")):
        return "Built-in containers/hash"
    return "Other runtime/stdlib"


def main(args):
    data=json.loads(args.results.read_text())
    profiles=[]
    args.output.mkdir(parents=True,exist_ok=True)
    for case in data["cases"]:
        if case["dataset"] not in ("wide-250","shared-100","conflicts") or case["variant"] not in ("catalog","catalog-filter-cache","catalog-constrained-first","catalog-incremental","catalog-trail"):
            continue
        request=json.loads(Path(case["command"][case["command"].index("--request")+1]).read_text())
        descriptor=request["admission"]["inputs"]["catalog"]
        source=solver.Source(descriptor["path"],descriptor["sha256"],"catalog")
        session=solver.Session(source,request["target"],parsed_cache=True,match_cache=case["variant"]!="catalog",
                               heuristic=case["variant"]=="catalog-constrained-first",prereleases=request.get("prereleases",False),
                               engine={"catalog-incremental":"incremental","catalog-trail":"trail"}.get(case["variant"],"baseline"))
        session.solve(request["roots"],request.get("constraints",()),max_rounds=request.get("max_rounds",10000))
        profile=cProfile.Profile();profile.enable()
        result=session.solve(request["roots"],request.get("constraints",()),max_rounds=request.get("max_rounds",10000),validate=False)
        profile.disable()
        if "_validation" in result:solver.validate_solution(session,*result.pop("_validation"))
        if solver.digest(result["selected"])!=case["samples"][0]["selection_sha256"]:
            raise ValueError("profile changed selection")
        raw=args.output/(case["dataset"]+"-"+case["variant"]+".pstats")
        profile.dump_stats(raw)
        stats=pstats.Stats(str(raw))
        totals={};functions=[]
        for (filename,line,name),(primitive,calls,self_seconds,inclusive,callers) in stats.stats.items():
            category=bucket(filename,name);totals[category]=totals.get(category,0)+self_seconds
            functions.append({"file":filename,"line":line,"function":name,"calls":calls,
                              "self_seconds":self_seconds,"inclusive_seconds":inclusive})
        assert abs(sum(totals.values())-stats.total_tt)<1e-6
        profiles.append({"dataset":case["dataset"],"variant":case["variant"],"total_self_seconds":stats.total_tt,
                         "buckets":totals,"functions":sorted(functions,key=lambda f:f["self_seconds"],reverse=True),
                         "result":result})
    report={"parent_run_id":data["run_id"],"method":"One separate profiled warm solve after one completed solve; validation excluded. Profiler overhead is material. Self buckets are disjoint; inclusive functions overlap. Not an unprofiled speed comparison.","profiles":profiles}
    (args.output/"profiles.json").write_text(json.dumps(report,indent=2)+"\n")
    print(args.output/"profiles.json")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results",type=Path,default=Path(__file__).resolve().parent/"_work/runs/initial/results.json")
    parser.add_argument("--output",type=Path,default=Path(__file__).resolve().parent/"_work/runs/initial/profile-data")
    main(parser.parse_args())
