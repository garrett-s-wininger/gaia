#!/usr/bin/env python3
"""Separate startup, harness, import and compilation costs without replacing prior runs."""

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import pstats
import random
import statistics
import subprocess
import sys
import time

import benchmark


def profile_bucket(filename, name):
    if "builtins.compile" in name:
        return "source compilation"
    if "marshal.loads" in name:
        return "bytecode decoding"
    if "zipfile" in filename:
        return "ZIP implementation"
    if "persistent_zip_loader.py" in filename:
        return "provider callbacks"
    if "importlib" in filename:
        return "Python import machinery"
    if "gaia_fixture_p" in filename:
        return "fixture module initialization"
    return "other builtins/runtime"


def parse_profile(path):
    stats = pstats.Stats(str(path))
    buckets = defaultdict(float)
    rows = []
    for (filename, line, name), (primitive, calls, own, cumulative, _) in stats.stats.items():
        buckets[profile_bucket(filename, name)] += own
        rows.append({"file": filename, "line": line, "name": name, "calls": calls,
                     "self_seconds": own, "cumulative_seconds": cumulative})
    return {"total_seconds": stats.total_tt, "total_calls": stats.total_calls,
            "self_time_buckets": dict(buckets),
            "functions_by_self": sorted(rows, key=lambda r: r["self_seconds"], reverse=True)[:25],
            "functions_by_cumulative": sorted(rows, key=lambda r: r["cumulative_seconds"], reverse=True)[:25]}


def run(args):
    original = json.loads(args.input.read_text())
    cases = [c for c in original["cases"] if c["layout"] in ("directory", "persistent-stored")]
    if len(cases) != 4:
        raise ValueError("use the one-size persistent follow-up with source/bytecode directory/provider cases")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    work = benchmark.HERE / "_work" / ("diagnostics-" + run_id)
    work.mkdir(parents=True, exist_ok=False)
    args.output.mkdir(parents=True, exist_ok=True)
    data = {"run_id": run_id, "original_run_id": original["run_id"], "trials": args.trials,
            "environment": benchmark.environment(work), "cases": [], "startup": {}}
    selected = next(c for c in cases if c["mode"] == "source" and c["layout"] == "persistent-stored")
    representative = sorted(selected["samples"], key=lambda s: s["process_wall_seconds"])[len(selected["samples"]) // 2]
    data["original_median_wall_sample"] = representative
    startup = {
        "isolated_noop": [sys.executable, "-I", "-S", "-B", "-c", "pass"],
        "worker_common_setup_only": [sys.executable, "-I", "-S", "-B", str(benchmark.WORKER), "--setup-only"],
    }
    observations = {name: [] for name in startup}
    rng = random.Random(20261028)
    for case in cases:
        benchmark.consume(case["command"])
        case = {"mode": case["mode"], "layout": case["layout"], "command": case["command"], "samples": []}
        data["cases"].append(case)
    for iteration in range(args.trials):
        order = [("startup", name) for name in startup] + [("case", c) for c in data["cases"]]
        rng.shuffle(order)
        for kind, value in order:
            if kind == "startup":
                begin = time.perf_counter()
                child = subprocess.run(startup[value], capture_output=True, text=True, check=True, timeout=120)
                observations[value].append({"process_wall_seconds": time.perf_counter() - begin,
                                            "child_output": child.stdout.strip()})
            else:
                sample = benchmark.consume(value["command"])
                sample["outside_observed_child_seconds"] = sample["process_wall_seconds"] - sample["child_observed_seconds"]
                total = sum(sample[k] for k in ("module_setup_seconds", "request_setup_seconds",
                            "import_seconds", "resource_seconds", "application_seconds", "validation_seconds", "cleanup_seconds"))
                if abs(total - sample["child_observed_seconds"]) > 1e-8:
                    raise ValueError("phase clocks do not partition child-observed time")
                value["samples"].append(sample)
        if (iteration + 1) % 5 == 0:
            print(f"diagnostic trials {iteration + 1}/{args.trials}", flush=True)
    for name, samples in observations.items():
        data["startup"][name] = {"samples": samples, "median_process_seconds": statistics.median(
            s["process_wall_seconds"] for s in samples)}
    for case in data["cases"]:
        case["summary"] = benchmark.summarize(case["samples"])
        case["mean_phase_seconds"] = {key: statistics.mean(s[key] for s in case["samples"]) for key in
            ("module_setup_seconds", "request_setup_seconds", "import_seconds", "resource_seconds",
             "application_seconds", "validation_seconds", "cleanup_seconds", "outside_observed_child_seconds",
             "process_wall_seconds")}
        if case["layout"] == "persistent-stored":
            profile_path = work / (case["mode"] + ".pstats")
            profiled = benchmark.consume(case["command"] + ["--profile-import", str(profile_path)])
            case["profile"] = parse_profile(profile_path)
            case["profile"]["verified_consumer"] = profiled
    benchmark.write_json(args.output / "diagnostics.json", data)
    render(data, args.output / "REPORT.md")


def render(data, destination):
    original = data["original_median_wall_sample"]
    residual = original["process_wall_seconds"] - original["workload_seconds"]
    lines = ["# Loader cost and interpreter-floor diagnostics", "", f"Run: `{data['run_id']}`. "
             f"Original run: `{data['original_run_id']}`. Same retained fixture inputs; new diagnostic processes.", "",
             "## The original 298 ms sample", "",
             "These phases come from the SAME observation at the median process wall time, so they add exactly. "
             "They differ from independently computed phase medians. Its remainder was not originally subdivided.", "",
             "| Phase | ms |", "| --- | ---: |"]
    for title, seconds in (("Import", original["import_seconds"]), ("Resources", original["resource_seconds"]),
                           ("Application loop", original["application_seconds"]), ("Other process/harness work", residual),
                           ("Process total", original["process_wall_seconds"])):
        lines.append(f"| {title} | {seconds*1000:.2f} |")
    lines += ["", "## Additional unprofiled phase observations", "",
              f"{data['trials']} fresh-process trials per case, warm/reused filesystem cache. Means are used below "
              "so additive phases equal mean process wall. They diagnose new observations, not a retroactive "
              "partition of the original run. Common setup starts after importing the clock module. "
              "Outside-child time combines process launch, earlier interpreter bootstrap, output, shutdown and parent overhead.", "",
              "| Phase (ms, means) | Source directory | Source persistent | Bytecode directory | Bytecode persistent |",
              "| --- | ---: | ---: | ---: | ---: |"]
    ordered = [next(c for c in data["cases"] if c["mode"] == mode and c["layout"] == layout)
               for mode, layout in (("source", "directory"), ("source", "persistent-stored"),
                                     ("bytecode", "directory"), ("bytecode", "persistent-stored"))]
    for key, title in (("module_setup_seconds", "Common harness imports/definitions"),
                       ("request_setup_seconds", "Arguments, manifest, provider registration"),
                       ("import_seconds", "Fixture imports"), ("resource_seconds", "Resources"),
                       ("application_seconds", "Application loop"), ("validation_seconds", "Correctness checks"),
                       ("cleanup_seconds", "Close/metrics"), ("outside_observed_child_seconds", "Outside observed child body"),
                       ("process_wall_seconds", "Process total")):
        lines.append(f"| {title} | " + " | ".join(f"{c['mean_phase_seconds'][key]*1000:.2f}" for c in ordered) + " |")
    lines += ["", "## Startup probes", "",
              "These are complete parent-observed process lifetimes, not a theoretical interpreter lower bound. "
              "The setup-only probe imports/defines the same harness but does not parse fixture arguments or load dependencies.", ""]
    for name, probe in data["startup"].items():
        lines.append(f"- `{name}` median: **{probe['median_process_seconds']*1000:.2f} ms**.")
    lines += ["", "## Import-only cProfile diagnostics", "",
              "Separate instrumented runs: timing overhead is material. Self-time buckets are disjoint and sum "
              "to the profiled import interval; they must NOT be substituted directly into unprofiled timings. "
              "Detailed per-function self/cumulative data is in diagnostics.json; cumulative times overlap.", "",
              "| Self-time bucket | Source ms | Bytecode ms |", "| --- | ---: | ---: |"]
    profiles = [c["profile"] for c in ordered if c["layout"] == "persistent-stored"]
    for key in sorted(set().union(*(p["self_time_buckets"] for p in profiles))):
        lines.append(f"| {key} | " + " | ".join(f"{p['self_time_buckets'].get(key,0)*1000:.2f}" for p in profiles) + " |")
    lines += ["", "## Scope", "",
              "This fixture eagerly imports 2,072 deliberately tiny modules. Installed module count is not "
              "the same as modules actually imported by a real startup. Real-package/application import traces "
              "are still required before treating this count or per-module workload as representative.", "",
              "Precompiled inputs reduce source compilation work but require separate construction/version handling. "
              "Persistent sessions, lazy imports, native access implementations and alternative formats remain "
              "unmeasured optimizations. Fewer calls or faster probes do not establish their benefit automatically.", ""]
    destination.write_text("\n".join(lines))
    print(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=benchmark.HERE / "_work/runs/persistent/results.json")
    parser.add_argument("--output", type=Path, default=benchmark.HERE / "_work/runs/diagnostics")
    parser.add_argument("--trials", type=int, default=15)
    args = parser.parse_args()
    if args.trials < 1:
        parser.error("trials must be positive")
    run(args)


if __name__ == "__main__":
    main()
