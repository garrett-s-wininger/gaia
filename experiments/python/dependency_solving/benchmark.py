#!/usr/bin/env python3
"""Same finite wheel sets and resolver; vary metadata delivery and generic caches."""
import time
_entered=time.perf_counter()
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import random
import statistics
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import solver
import fixtures
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"dependency_bundles"))
# The current script is __main__, so load the sibling harness under a distinct name.
import importlib.util
spec=importlib.util.spec_from_file_location("bundle_measurements",Path(__file__).resolve().parent.parent/"dependency_bundles/benchmark.py")
measurements=importlib.util.module_from_spec(spec);spec.loader.exec_module(measurements)
sys.path.pop(0)
_prepared=time.perf_counter()
HERE=Path(__file__).resolve().parent
VARIANTS={
    "catalog-trail":dict(backend="catalog",parsed_cache=True,match_cache=True,heuristic=False,engine="trail"),
    "wheel-uncached":dict(backend="files",parsed_cache=False,match_cache=False,heuristic=False),
    "wheel-cached":dict(backend="cached",parsed_cache=True,match_cache=False,heuristic=False),
    "catalog":dict(backend="catalog",parsed_cache=True,match_cache=False,heuristic=False),
    "catalog-filter-cache":dict(backend="catalog",parsed_cache=True,match_cache=True,heuristic=False),
    "catalog-constrained-first":dict(backend="catalog",parsed_cache=True,match_cache=True,heuristic=True),
    "catalog-incremental":dict(backend="catalog",parsed_cache=True,match_cache=True,heuristic=False,engine="incremental"),
}


def worker(args):
    request=json.loads(args.request.read_text())
    variant=VARIANTS[request["variant"]]
    kind="catalog" if variant["backend"]=="catalog" else "inventory"
    descriptor=request["admission"]["inputs"][kind]
    begin=time.perf_counter()
    source=solver.Source(descriptor["path"],descriptor["sha256"],variant["backend"])
    session=solver.Session(source,request["target"],**{k:v for k,v in variant.items() if k!="backend"},
                           prereleases=request.get("prereleases",False))
    opened=time.perf_counter()-begin
    solves=[]
    for _ in range(args.passes):
        before=Counter(source.counts);parsed=Counter(session.counts);metadata=source.metadata_seconds
        begin=time.perf_counter()
        result=session.solve(request["roots"],request.get("constraints",()),request.get("max_rounds",10000),validate=False)
        seconds=time.perf_counter()-begin
        observation={"seconds":seconds,"metadata_seconds":source.metadata_seconds-metadata,
                     "source":dict(source.counts-before),"parsing":dict(session.counts-parsed),
                     **{k:v for k,v in result.items() if not k.startswith("_")}}
        verify=time.perf_counter()
        if "_validation" in result:
            solver.validate_solution(session,*result.pop("_validation"))
        observation["validation_seconds"]=time.perf_counter()-verify
        solves.append(observation)
    stable={(s["status"],solver.digest(s["selected"])) for s in solves}
    if len(stable)!=1:
        raise RuntimeError("repeated solve changed status/selection")
    if "expected_status" in request and request["expected_status"]!=solves[0]["status"]:
        raise RuntimeError(f"unexpected resolution status: {solves[0]['status']}")
    if "expected" in request:
        if sorted([s[0],s[1]] for s in solves[0]["selected"])!=request["expected"]:
            raise RuntimeError("selection differs from pip reference")
    print(json.dumps({"correct":True,"complete":solves[0]["status"]!="round_limit",
                      "bootstrap_seconds":_prepared-_entered,"open_seconds":opened,
                      "first_solve_seconds":solves[0]["seconds"],"first_use_seconds":opened+solves[0]["seconds"],
                      "reused_solve_seconds":statistics.mean(s["seconds"] for s in solves[1:]) if len(solves)>1 else 0,
                      "snapshot":source.snapshot,"target":session.target_id,"status":solves[0]["status"],
                      "selected_count":len(solves[0]["selected"]),"selection_sha256":solver.digest(solves[0]["selected"]),
                      "cache_entries":{"metadata":len(source.cache),"requirements":len(session.requirements),
                                       "filters":len(session.matches),"satisfaction":len(session.satisfaction)},
                      "passes":solves}))


def render(data,path):
    lines=["# Local dependency-solving experiment","",f"Run: `{data['run_id']}`.","",
           "Same admitted wheel set, target, requirements, ordering policy and resolvelib version within "
           "each storage/cache comparison. No pip CLI, network, installation, candidate-package code execution or "
           "remote service. Python packaging/resolvelib imports are prepared before solve timing; their "
           "bootstrap and complete process wall remain in raw observations. Warm filesystem cache, new "
           "process/session per trial; subsequent solves reuse the immutable session, not a saved solution.","",
           "## Contract and semantics","",
           "Admission hashes wheel bytes, validates filename/metadata identities and named requirements, "
           "and writes pinned inventory/catalog documents. Both carry the same content-derived snapshot ID; "
           "local artifact paths are excluded from that identity. Sources expose list_candidates(name) "
           "and metadata(artifact_id). Solving needs certified metadata only; full artifact delivery/hash "
           "verification is a later operation. The JSON encoding is experimental, not a transport protocol.","",
           "Named PEP 508 requirements, version constraints, extras/extra markers, target environment markers, "
           "Requires-Python, compatible wheel tags and explicit prerelease policy are supported. Source builds, "
           "direct URL/VCS requirements, installed-state preference, yanked data, pip config/index semantics "
           "and remote retrieval are excluded. This is a reference provider, not a drop-in pip replacement. "
           "Candidates prefer latest version/build, compatible tag priority, then stable artifact ID. Cache "
           "keys include snapshot, target, prerelease policy, requirements and incompatibilities; parsed data "
           "is scoped to a session. Selected closures are independently revalidated outside solve timing.","",
           "## Variants","",
           "- wheel-uncached: reopen/read/parse certified METADATA on each request, reparse requirements.",
           "- wheel-cached: lazy metadata and parsed requirement/specifier caches; realistic reuse control.",
           "- catalog: one admitted metadata table; same lazy parsed-object caches and lexical solver order.",
           "- catalog-filter-cache: deduplicate repeated predicates, memoize complete candidate filters, "
           "and cache repeated requirement/candidate satisfaction checks within the immutable session.",
           "- catalog-constrained-first: additionally prefer the smallest known candidate set. This changes "
           "decision order and can change which valid solution is found; it is not a storage-only comparison.","",
           "- catalog-incremental: same catalog/caches and lexical candidate/criterion order as "
           "catalog-filter-cache; replace full satisfaction/preference scans with a dirty-criterion heap. "
           "Reuse upstream candidate validation/backjumping and rebuild the heap conservatively on rollback. "
           "Full state/criteria copies remain; this is not a fully linear or native solver.","",
           "- catalog-trail: same incremental scheduler and candidate policy; saved maps are version "
           "handles into reversible mutation histories, and candidate attempts use small overlays. "
           "Backtracking replays mutations rather than copying full maps. Global scans on conflict, "
           "criterion information lists and backtrack-cause lists remain.","",
           "The reference provider eagerly enumerates candidate eligibility, including Requires-Python "
           "metadata checks. This is fixed across these variants and is not pip's exact candidate-preparation "
           "policy. Lazy candidates and compact eligibility summaries are not measured in this run.","",
           f"{data['trials']} interleaved fresh processes per case, {data['passes']} solves per session. "
           "Medians, ms. First-use median is computed per observation as source open + first solve. "
           "Reused is each session's mean after the first solve, then median. Validation is excluded. "
           "Metadata time is an included subset of solve time; do not add it. Callback counts are from "
           "the first solve, median across trials.","",
           "| Dataset | Variant | Status | Selected | Open ms | First solve ms | Reused solve ms | First use ms | Metadata ms | Wheel opens | Candidate checks | Satisfaction evals | Rejections |",
           "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    if data.get("parent_run_id"):
        lines[4:4]=[f"Reuses admitted snapshots and target from `{data['parent_run_id']}`. "
                    "Admission observations below are carried forward from that run, not measured again. "
                    "Requirements/constraints/options are inherited unless explicitly overridden.",""]
    for case in data["cases"]:
        s=case["summary"]
        first=[v["passes"][0] for v in case["samples"]]
        med=lambda f:statistics.median(f(v) for v in first)
        lines.append(f"| {case['dataset']} | {case['variant']} | {case['samples'][0]['status']} | {case['samples'][0]['selected_count']} | "
                     +" | ".join(f"{s[k]['median']*1000:.3f}" for k in ("open_seconds","first_solve_seconds","reused_solve_seconds","first_use_seconds"))
                     +f" | {med(lambda v:v['metadata_seconds'])*1000:.3f} | {med(lambda v:v['source'].get('wheel_opens',0)):g} | "
                     f"{med(lambda v:v['provider'].get('candidate_checks',0)):g} | {med(lambda v:v['provider'].get('satisfaction_evaluations',0)):g} | "
                     f"{med(lambda v:v['solver'].get('rejections',0)):g} |")
    if any(c["variant"] in ("catalog-incremental","catalog-trail") for c in data["cases"]):
        lines += ["","## Scheduling work","",
                  "First-solve medians. A dash means the baseline was not instrumented for that engine-specific "
                  "counter. Satisfaction callbacks are counted for both variants, including cache hits. "
                  "The test-only full-scan audit is disabled during timing. State-copy counts distinguish "
                  "the incremental baseline's full snapshots from the trail's version handles.","",
                  "| Dataset | Variant | Satisfaction callbacks | Changed-criterion checks | Queue rebuilds | State copies |",
                  "| --- | --- | ---: | ---: | ---: | ---: |"]
        for case in data["cases"]:
            samples=[s["passes"][0] for s in case["samples"]]
            callbacks=statistics.median(s["provider"].get("satisfaction_checks",0) for s in samples)
            values=[]
            for key in ("criterion_checks","queue_rebuilds","state_copies"):
                values.append(f"{statistics.median(s['engine_work'].get(key,0) for s in samples):g}"
                              if case["variant"] in ("catalog-incremental","catalog-trail") else "—")
            lines.append(f"| {case['dataset']} | {case['variant']} | {callbacks:g} | " + " | ".join(values) + " |")
    if any(c["variant"]=="catalog-trail" for c in data["cases"]):
        lines += ["","## Copy and mutation work","",
                  "First-solve medians. Whole-map entries copied counts state snapshots and candidate "
                  "attempts, including optimistic saves. Version handles share a reversible store. "
                  "Undo/redo counts include changing between retained historical branches. Zero "
                  "whole-map copies does not imply zero allocations or zero copying of lists.","",
                  "| Dataset | Variant | Whole-map entries copied | Trail mutations | Version handles | Undo | Redo |",
                  "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
        for case in data["cases"]:
            if case["variant"] not in ("catalog-incremental","catalog-trail"):continue
            work=[s["passes"][0]['engine_work'] for s in case['samples']]
            values=[statistics.median(w.get(k,0) for w in work) for k in
                    ('map_entries_copied','trail_mutations','map_version_handles','trail_undos','trail_redos')]
            lines.append(f"| {case['dataset']} | {case['variant']} | " + " | ".join(f"{v:g}" for v in values) + " |")
    lines += ["","## Admission and input size","",
              "One producer/admission observation per dataset; buffered writes, no fsync. Admission is not "
              "charged to every solve; one-shot use must add it back. Both inventory and catalog store "
              "local paths for this prototype. Raw package bytes are unchanged.","",
              "| Dataset | Projects | Artifacts | Artifact bytes | Raw METADATA bytes | Inventory bytes | Catalog bytes | Admission ms |",
              "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for d in data["datasets"]:
        a=d["admission"]
        lines.append(f"| {d['name']} | {a['projects']} | {a['artifacts']} | {a['artifact_bytes']:,} | {a['raw_metadata_bytes']:,} | "
                     f"{a['index_bytes']['inventory']:,} | {a['index_bytes']['catalog']:,} | {a['admission_seconds']*1000:.3f} |")
    lines += ["","## Interpretation limits","",
              "Generated graphs provide controlled breadth, shared constraints, conflicts and unsatisfiability; "
              "they are not evidence of real-world solve-time distributions. original-22 preserves the earlier "
              "pip package set and expected selection. All unmodified-order variants must return identical "
              "artifact selections; heuristic results must satisfy the same closure but may differ. Unsatisfiable "
              "results are resolver outcomes, not independent general unsat proofs; small correctness cases "
              "have additional finite-oracle coverage. A round limit is reported as incomplete, never unsat. "
              "The engine/provider remain Python; these measurements do not establish an Odin/native solver "
              "floor. Matched end-to-end pip comparisons are a separate experiment. The next source/backend "
              "can implement the same candidate/metadata semantics without changing the constraint engine.",""]
    path.write_text("\n".join(lines))


def run(args):
    run_id=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    work=HERE/"_work"/run_id;work.mkdir(parents=True)
    if args.inputs:
        previous=json.loads(args.inputs.read_text())
        datasets=previous["datasets"]
        previous_requests={}
        for case in previous["cases"]:
            if case["dataset"] not in previous_requests:
                request_path=Path(case["command"][case["command"].index("--request")+1])
                previous_requests[case["dataset"]]=json.loads(request_path.read_text())
    elif args.wide_sizes:
        datasets=fixtures.wide(work,args.wide_sizes)
    elif args.wheelhouse:
        roots=list(args.requirement)
        if args.requirements:
            roots += [line.strip() for line in args.requirements.read_text().splitlines() if line.strip() and not line.lstrip().startswith("#")]
        if not roots:raise ValueError("custom inventory requires requirements")
        datasets=[{"name":"custom","wheelhouse":str(args.wheelhouse.resolve()),"roots":roots}]
    else:datasets=fixtures.generated(work)
    target=json.loads(args.target.read_text()) if args.target else (previous["target"] if args.inputs else solver.target_default())
    data={"run_id":run_id,"trials":args.trials,"passes":args.passes,"environment":measurements.environment(work),
          "libraries":{"pip_wheel":str(solver.PIP_WHEEL),"pip_wheel_sha256":hashlib.sha256(solver.PIP_WHEEL.read_bytes()).hexdigest(),
                       "packaging":solver.packaging.__version__,"resolvelib":solver.resolvelib.__version__},
          "target":target,"datasets":[],"cases":[]}
    if args.inputs:data["parent_run_id"]=previous["run_id"]
    for dataset in datasets:
        admission=dataset["admission"] if args.inputs else solver.admit(dataset["wheelhouse"],work/(dataset["name"]+"-snapshot"))
        dataset={**dataset,"admission":admission}
        data["datasets"].append(dataset)
        for variant in args.variants:
            prior=previous_requests[dataset["name"]] if args.inputs else {}
            request={**dataset,"variant":variant,"target":target,"constraints":args.constraint,
                     "prereleases":args.prereleases,"max_rounds":args.max_rounds}
            request["constraints"]=args.constraint if args.constraint is not None else prior.get("constraints",[])
            request["prereleases"]=args.prereleases if args.prereleases is not None else prior.get("prereleases",False)
            request["max_rounds"]=args.max_rounds if args.max_rounds is not None else prior.get("max_rounds",10000)
            if args.inputs and any(v is not None for v in (args.constraint,args.prereleases,args.max_rounds,args.target)):
                # Old fixture expectations apply to the old query, not overrides.
                request.pop("expected",None);request.pop("expected_status",None)
            path=work/(dataset["name"]+"-"+variant+".json")
            measurements.write_json(path,request)
            command=[sys.executable,"-I","-S","-B",str(Path(__file__).resolve()),"--worker","--request",str(path),"--passes",str(args.passes)]
            data["cases"].append({"dataset":dataset["name"],"variant":variant,"command":command,"samples":[]})
    selections={}
    def consume(case):
        try:sample=measurements.consume(case["command"])
        except subprocess.CalledProcessError as e:raise RuntimeError(e.stdout+e.stderr) from e
        if case["variant"]!="catalog-constrained-first":
            reference=selections.setdefault(case["dataset"],(sample["status"],sample["selection_sha256"]))
            if reference!=(sample["status"],sample["selection_sha256"]):raise RuntimeError("backend/cache changed solution")
        return sample
    for case in data["cases"]:
        consume(case)
        print(f"verified {case['dataset']} / {case['variant']}",flush=True)
    rng=random.Random(20261028)
    for trial in range(args.trials):
        cases=data["cases"].copy();rng.shuffle(cases)
        for case in cases:case["samples"].append(consume(case))
        if (trial+1)%5==0:print(f"solver trials {trial+1}/{args.trials}",flush=True)
    for case in data["cases"]:case["summary"]=measurements.summarize(case["samples"])
    args.output.mkdir(parents=True,exist_ok=True)
    measurements.write_json(args.output/"results.json",data);render(data,args.output/"REPORT.md")
    print(args.output/"REPORT.md")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker",action="store_true");parser.add_argument("--request",type=Path)
    parser.add_argument("--inputs",type=Path,help="reuse exact admitted snapshots/target from a prior run")
    parser.add_argument("--wide-sizes",nargs="+",type=int,help="generate only wide graphs at these leaf counts")
    parser.add_argument("--variants",nargs="+",choices=VARIANTS,default=list(VARIANTS))
    parser.add_argument("--trials",type=int,default=15);parser.add_argument("--passes",type=int,default=3)
    parser.add_argument("--wheelhouse",type=Path);parser.add_argument("--requirement",action="append",default=[])
    parser.add_argument("--requirements",type=Path);parser.add_argument("--constraint",action="append")
    parser.add_argument("--target",type=Path);parser.add_argument("--prereleases",action=argparse.BooleanOptionalAction,default=None)
    parser.add_argument("--max-rounds",type=int)
    parser.add_argument("--output",type=Path,default=HERE/"_work/runs/initial")
    args=parser.parse_args()
    if args.trials<1 or args.passes<(1 if args.worker else 2):
        parser.error("positive trials and at least two passes required (one allowed for a startup worker)")
    if len(set(args.variants))!=len(args.variants):parser.error("variants must be unique")
    if args.inputs and (args.wheelhouse or args.requirement or args.requirements):
        parser.error("--inputs reuses its wheel sets and root requirements; select a new inventory separately")
    if args.wide_sizes and (args.inputs or args.wheelhouse or args.requirement or args.requirements):
        parser.error("--wide-sizes cannot be combined with existing inputs or custom roots")
    if args.wide_sizes and (min(args.wide_sizes)<1 or len(set(args.wide_sizes))!=len(args.wide_sizes)):
        parser.error("wide sizes must be unique positive leaf counts")
    if args.worker:worker(args)
    else:run(args)
