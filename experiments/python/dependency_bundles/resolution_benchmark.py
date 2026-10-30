#!/usr/bin/env python3
"""Isolate import discovery and profile the separate dependency-solving phase."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.machinery
import json
from pathlib import Path
import pstats
import random
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import benchmark
from bundle_access import BundleReader, BundleResources
from native_loader import NativeBundleReader
from persistent_zip_loader import PersistentZipProvider
from precomputed_index import IndexedBundleReader


def worker(args):
    if not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError("requires -I -S -B")
    requests = json.loads(args.requests.read_text())
    original = requests["command"]
    value = lambda flag: original[original.index(flag)+1] if flag in original else None
    root = value("--root")
    reader = value("--reader")
    expected = requests["members"]
    if any(n == "pip" or n.startswith("pip.") for n in sys.modules):
        raise RuntimeError("pip preloaded")
    queries = []
    for member in expected:
        name = member[:-3].replace("/", ".")
        package = name.endswith(".__init__")
        if package:
            name = name[:-len(".__init__")]
        parent = name.rpartition(".")[0].replace(".", "/")
        search = [root+("/"+parent if parent else "")]
        relative = member[:-3]+".pyc" if requests["mode"] == "bytecode" else member
        queries.append((name, search, root+"/"+relative, package))
    misses = [(name.rpartition(".")[0]+("." if "." in name else "")+f"gaia_missing_{i}", search)
              for i, (name, search, _, _) in enumerate(queries)]
    begin = time.perf_counter()
    provider = None
    if reader == "directory":
        find = importlib.machinery.PathFinder.find_spec
    else:
        policy = value("--policy") or "hash"
        if reader == "mmap":
            factory = lambda path: BundleReader(path, "mmap")
        elif reader == "python":
            factory = lambda path: IndexedBundleReader(path, value("--index"), index_sha256=value("--pin"), verify=policy)
        else:
            factory = lambda path: NativeBundleReader(path, value("--index"), index_sha256=value("--pin"),
                                                       verify=policy, library=value("--library"))
        provider = PersistentZipProvider(root, archive_factory=factory, resource_factory=BundleResources)
        provider.open_archive()
        find = provider.find_spec
    setup_seconds = time.perf_counter()-begin
    hit_times, miss_times = [], []
    # Every pass redoes discovery, including spec allocation; no module is executed.
    for _ in range(4):
        begin = time.perf_counter()
        found = [find(name, search) for name, search, _, _ in queries]
        hit_times.append(time.perf_counter()-begin)
        for spec, (_, _, origin, package) in zip(found, queries, strict=True):
            if spec is None or spec.origin != origin or (spec.submodule_search_locations is not None) != package:
                raise RuntimeError("incorrect resolved origin/package")
        del found
        begin = time.perf_counter()
        missing = [find(name, search) for name, search in misses]
        miss_times.append(time.perf_counter()-begin)
        if any(spec is not None for spec in missing):
            raise RuntimeError("missing module was resolved")
    if any(n == "pip" or n.startswith("pip.") for n in sys.modules):
        raise RuntimeError("discovery executed/imported pip")
    if provider:
        if provider.module_reads != 0 or provider.archive_opens != 1:
            raise RuntimeError("discovery fetched code/reopened archive")
        provider.close()
    print(json.dumps({"correct": True, "hits": len(queries), "misses": len(misses),
                      "setup_seconds": setup_seconds, "first_hits_seconds": hit_times[0],
                      "reused_hits_seconds": statistics.mean(hit_times[1:]),
                      "first_misses_seconds": miss_times[0], "reused_misses_seconds": statistics.mean(miss_times[1:]),
                      "first_use_seconds": setup_seconds+hit_times[0], "pip_code_reads": 0, "pip_imports": 0}))


def profile_bucket(filename, name):
    normalized = filename.replace("\\", "/")
    if "builtins.compile" in name:
        return "Source compilation"
    if "marshal.loads" in name:
        return "Bytecode decoding"
    if "/pip/_vendor/resolvelib/" in normalized or "/pip/_internal/resolution/" in normalized:
        return "Dependency solver/core integration"
    if any(n in normalized for n in ("bundle_access.py", "precomputed_index.py", "binary_index.py", "native_loader.py")) or "_gaia_native." in name:
        return "Bundle provider/index"
    if "importlib._bootstrap" in filename or "frozen importlib" in filename or "persistent_zip_loader.py" in filename:
        return "Import machinery/discovery"
    if "/pip/" in normalized:
        return "Pip module bodies" if name == "<module>" else "Other pip code"
    if "/importlib/resources/" in normalized:
        return "Standard resource handling"
    if filename == "~" and any(n in name for n in ("posix.", "_io.", "read", "stat", "open", "hashlib", "crc32", "sha256")):
        return "C I/O/hash primitives"
    return "Other stdlib/runtime"


def parse_profile(path):
    stats = pstats.Stats(str(path))
    buckets = {}
    functions = []
    inclusive = []
    for (filename, line, name), (primitive, calls, self_seconds, cumulative, callers) in stats.stats.items():
        bucket = profile_bucket(filename, name)
        buckets[bucket] = buckets.get(bucket, 0)+self_seconds
        row = {"file": filename, "line": line, "function": name, "calls": calls,
               "primitive_calls": primitive, "self_seconds": self_seconds, "cumulative_seconds": cumulative}
        functions.append(row)
        normalized = filename.replace("\\", "/")
        label = None
        if name == "_find_spec" and "importlib" in filename:
            label = "All import finders (_find_spec)"
        elif name == "resolve" and normalized.endswith("/pip/_internal/resolution/resolvelib/resolver.py"):
            label = "Pip resolve phase (includes lazy imports/candidates/metadata)"
        elif name == "resolve" and "/pip/_vendor/resolvelib/" in normalized:
            label = "Vendored resolver (includes provider callbacks/metadata)"
        elif name == "open_archive" and filename.endswith("persistent_zip_loader.py"):
            label = "Provider open/catalog/module table (all calls)"
        if label:
            inclusive.append({"label": label, **row})
    if abs(sum(buckets.values())-stats.total_tt)>1e-6:
        raise RuntimeError("profile self times do not partition")
    return {"total_self_seconds": stats.total_tt, "buckets": buckets, "inclusive": inclusive,
            "functions": sorted(functions, key=lambda row: row["self_seconds"], reverse=True)}


def render(data, path):
    lines = ["# Resolution diagnostics", "", f"Run: `{data['run_id']}`.", "",
             "Two distinct questions: import discovery binds module names to code locations; dependency "
             "resolution selects compatible package versions. The prior pip CLI already exercised version "
             "selection/backtracking, but did not isolate its duration. These diagnostics do not replace "
             "the original end-to-end observations.", "",
             "## Import discovery with no code execution", "",
             f"{data['trials']} randomized fresh processes per case, warm filesystem cache. Requests use "
             "the 312 code files actually executed by pip. Each process does four successful discovery scans "
             "and four same-parent missing-name scans, with exactly one miss per hit. This is a controlled "
             "hit/miss stress mix, not a measured miss rate from the CLI. Parent search paths are provided "
             "explicitly, so discovery never imports parent packages. Every result's origin/package flag "
             "is validated. No pip module imports or per-module code fetches occur. Hash-policy setup "
             "still scans bundle bytes for integrity verification. Each pass measures hits before misses, "
             "so the first miss scan already has parent-finder caches warmed by the first hit scan.", "",
             "Directory discovery uses PathFinder/FileFinder, including normal per-directory importer caches. "
             "Bundle discovery opens/verifies/builds the module table during setup, then uses the existing "
             "Python meta-path provider for every indexed backend. Odin supplies bytes/index data, but the "
             "current module-name resolution map and spec creation still execute in Python. Request-list "
             "decoding/path construction is common untimed setup. Hit/miss scans include spec allocation; "
             "correctness validation and releasing result lists occur outside scans. Medians, ms; first "
             "use is computed per sample as setup + first successful scan.", "",
             "| Input | Reader | Setup | First hits | Reused hits | First misses | Reused misses | Setup + first hits |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for case in data["cases"]:
        s = case["summary"]
        lines.append(f"| {case['mode']} | {case['reader']} | " + " | ".join(f"{s[k]['median']*1000:.3f}" for k in
                     ("setup_seconds", "first_hits_seconds", "reused_hits_seconds", "first_misses_seconds",
                      "reused_misses_seconds", "first_use_seconds")) + " |")
    lines += ["", "## Separately profiled full CLI", "",
              "One whole-command cProfile run per selected case. Instrumentation adds overhead; these "
              "times must not be substituted into unprofiled timings. The profiler is imported before "
              "registering the input provider so it cannot accidentally prime the bundle index. "
              "Profiler imports can still change host-stdlib import state. Self-time buckets are disjoint and "
              "sum to profiled self time. Module-body self time does not include child functions called "
              "during initialization. The import bucket includes discovery/spec construction plus other "
              "import bookkeeping; it is not solely filesystem path resolution.", "",
              "| Input | Reader | Profiled workload ms | Compilation ms | Bytecode decode ms | Import machinery ms | Solver/core integration self ms | Bundle provider self ms |",
              "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for case in data["profiles"]:
        profile = case["profile"]
        buckets = profile["buckets"]
        lines.append(f"| {case['mode']} | {case['reader']} | {case['observation']['workload_seconds']*1000:.3f} | "
                     + " | ".join(f"{buckets.get(k,0)*1000:.3f}" for k in
                                  ("Source compilation", "Bytecode decoding", "Import machinery/discovery",
                                   "Dependency solver/core integration", "Bundle provider/index")) + " |")
    lines += ["", "### Inclusive phase observations", "",
              "Each row includes nested calls and overlaps other rows. In particular, solver resolve "
              "phases include candidate/provider callbacks, wheel metadata work and imports triggered "
              "inside solving. They are not measurements of pure solver-algorithm CPU time. Import "
              "finder time includes lazy provider opening/index construction. Do not add these rows.", "",
              "| Input | Reader | Phase | Calls | Inclusive ms |",
              "| --- | --- | --- | ---: | ---: |"]
    for case in data["profiles"]:
        for row in case["profile"]["inclusive"]:
            lines.append(f"| {case['mode']} | {case['reader']} | {row['label']} | {row['calls']} | {row['cumulative_seconds']*1000:.3f} |")
    lines += ["", "## Limits", "",
              "This retains the same offline 22-wheel/12-package graph and pip 26.2.1; it is not a "
              "dependency-solver scale benchmark or a claim about difficult real-world graphs. The "
              "metadata-only discovery test bypasses normal sys.modules and parent-import behavior to "
              "isolate finders. Repeated scans measure finder caches, not cached import speed. All full "
              "CLI runs still validate report/selected versions, origins, resources, code counts and "
              "zero network attempts. Detailed disjoint buckets, inclusive function records and raw "
              "discovery samples/commands are in results.json. No new native resolver implementation "
              "or workload-specific optimization is introduced.", ""]
    path.write_text("\n".join(lines))


def run(args):
    original = json.loads(args.inputs.read_text())
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    work = benchmark.HERE/"_work"/("resolution-"+run_id)
    work.mkdir(parents=True)
    args.output.mkdir(parents=True,exist_ok=True)
    data = {"run_id": run_id, "parent_run_id": original["run_id"], "trials": args.trials,
            "environment": benchmark.environment(work), "cases": [], "profiles": []}
    selected = [c for c in original["cases"] if c["workload"] == "pip"]
    for case in selected:
        members = sorted(case["samples"][0]["executed_files"])
        requests = {"command": case["command"], "mode": case["mode"], "members": members}
        request_path = work/(case["mode"]+"-"+case["reader"]+".json")
        benchmark.write_json(request_path,requests)
        command = [sys.executable,"-I","-S","-B",str(Path(__file__).resolve()),"--worker","--requests",str(request_path)]
        data["cases"].append({"mode":case["mode"],"reader":case["reader"],"command":command,"samples":[]})
    for case in data["cases"]:
        benchmark.consume(case["command"])
    rng = random.Random(20261028)
    for trial in range(args.trials):
        cases = data["cases"].copy();rng.shuffle(cases)
        for case in cases:
            sample = benchmark.consume(case["command"])
            if not sample["correct"] or sample["hits"]!=312 or sample["misses"]!=312:
                raise RuntimeError("incorrect discovery workload")
            case["samples"].append(sample)
        if (trial+1)%5==0:
            print(f"resolution trials {trial+1}/{args.trials}",flush=True)
    for case in data["cases"]:
        case["summary"]=benchmark.summarize(case["samples"])
    # Profiles are collected only after unprofiled discovery runs finish.
    for case in selected:
        if case["reader"] not in ("directory","python-local","odin-local"):
            continue
        profile_path = work/(case["mode"]+"-"+case["reader"]+".pstats")
        command = case["command"]+["--profile",str(profile_path)]
        observation = benchmark.consume(command)
        if not observation["correct"] or observation["report_sha256"]!=case["samples"][0]["report_sha256"]:
            raise RuntimeError("profiled CLI changed output")
        data["profiles"].append({"mode":case["mode"],"reader":case["reader"],"command":command,
                                 "observation":observation,"profile":parse_profile(profile_path)})
    benchmark.write_json(args.output/"results.json",data)
    render(data,args.output/"REPORT.md")
    print(args.output/"REPORT.md")


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker",action="store_true")
    parser.add_argument("--requests",type=Path)
    parser.add_argument("--inputs",type=Path,default=benchmark.HERE/"_work/runs/python-native/results.json")
    parser.add_argument("--output",type=Path,default=benchmark.HERE/"_work/runs/resolution")
    parser.add_argument("--trials",type=int,default=15)
    args=parser.parse_args()
    if args.trials<1:parser.error("positive trials required")
    if args.worker:worker(args)
    else:run(args)
