"""Compare equal-cache policies on declared IR edits and two exact consumers."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
MODES = ("native_cached", "compact_eager", "compact_lazy")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n")


def invoke(command, **kwargs):
    return subprocess.run([str(x) for x in command], check=True, capture_output=True, text=True, **kwargs)


def stats(values):
    return {"median_ms": statistics.median(values) / 1e6, "min_ms": min(values) / 1e6,
            "max_ms": max(values) / 1e6, "samples": len(values)}


def summarize(raw):
    summary = {"cases": {}}
    for label, measurement in raw["cases"].items():
        rows = measurement["observations"]
        modes = {}
        totals = {mode: {b: sum(r["ns"] for r in rows if r["block"] == b and r["mode"] == mode)
                         for b in range(measurement["blocks"])} for mode in MODES}
        for mode in MODES:
            selected = [r for r in rows if r["mode"] == mode]
            modes[mode] = {
                "request_span_sum": stats(list(totals[mode].values())),
                "peak_logical_payload_bytes": max(r["payload_bytes"] for r in selected),
                "counts_per_trace": {key: sum(r["counts"][key] for r in selected if r["block"] == 0)
                                     for key in selected[0]["counts"]},
                "events": {event: {**stats([r["ns"] for r in selected if r["event"] == event]),
                                   "liveness": stats([r["liveness_ns"] for r in selected if r["event"] == event]),
                                   "queries": stats([r["queries_ns"] for r in selected if r["event"] == event]),
                                   "mutation": stats([r["mutation_ns"] for r in selected if r["event"] == event])}
                           for event in dict.fromkeys(r["event"] for r in selected)},
            }
            if mode != MODES[0]:
                modes[mode]["request_span_sum"]["paired_wins_vs_native"] = sum(
                    totals[mode][b] < totals[MODES[0]][b] for b in totals[mode])
        summary["cases"][label] = {"target": measurement["target"], "target_argument": measurement["target_argument"],
                                    "explore": measurement["explore"], "original_functions": rows[0]["functions"], "modes": modes}
    return summary


def validate_fixture(data):
    expected = {
        ("diamond", 0): [0, 3], ("diamond", 1): [1, 4, 7, 8, 9], ("diamond", 2): [2, 7, 8, 9],
        ("loop", 0): [0, 6, 7], ("loop", 1): [1, 4, 8],
        ("unreachable_blocks", 0): [0, 1, 2, 4], ("self_phi", 0): [0, 2],
        ("invoke_edge", 0): [0, 3, 4, 6],
    }
    if len(data["fixture_slices"]) != len(expected) * len(MODES):
        raise AssertionError("fixture query coverage changed")
    for row in data["fixture_slices"]:
        if row["nodes"] != expected[row["function"], row["argument"]]:
            raise AssertionError(f"hand-checked slice mismatch: {row}")


def validate_counts(data):
    functions = data["observations"][0]["functions"]
    productions = {"initial": functions, "explore": 0, "unchanged": 0, "operand_edit": 1,
                   "value_renumber": 1, "cfg_split": 1, "add_function": 1, "remove_function": 0,
                   "context_refresh": functions, "final_hit": 0}
    for row in data["observations"]:
        for key in ("solves", "productions"):
            if row["counts"][key] != productions[row["event"]]:
                raise AssertionError(f"invalidation scope mismatch: {row}")
        if row["event"] in ("unchanged", "final_hit") and row["counts"]["slice_misses"]:
            raise AssertionError("unchanged query missed its cache")


def main(a):
    for key in ("host", "library", "output", "lock"):
        setattr(a, key, getattr(a, key).resolve())
    if not 1 <= a.blocks <= 100:
        raise ValueError("blocks must be in [1,100]")
    inputs = {}
    for entry in a.ir:
        label, path = entry.split("=", 1)
        if label in inputs or not label:
            raise ValueError("IR labels must be unique and nonempty")
        inputs[label] = Path(path).resolve()
    a.output.mkdir(parents=True, exist_ok=True)
    if (a.output / "results.json").exists():
        raise FileExistsError("refusing to overwrite observations")
    build_path = a.host.parent / "retained-build.json"
    build = json.loads(build_path.read_text())
    for path in (a.host, a.library):
        if sha(path) != build["outputs_sha256"][str(path)]:
            raise ValueError("binary differs from manifest")
    pinned = [*inputs.values(), a.host, a.library, build_path, HERE / "run.py", HERE / "host.cpp",
              HERE / "build.py", HERE.parent / "host.cpp", HERE.parent / "liveness.odin",
              HERE.parent / "test_liveness.py", HERE.parent / "fixtures.ll"]
    pinned += [Path(p) for p in {**build["inputs_sha256"], **build["kernel_and_original_adapter"]["inputs_sha256"]}]
    pins = {str(p): sha(p) for p in pinned}
    for path, digest in {**build["inputs_sha256"], **build["kernel_and_original_adapter"]["inputs_sha256"]}.items():
        if sha(Path(path)) != digest:
            raise ValueError("source or SDK differs from build")
    env = dict(os.environ, GAIA_LIVENESS_LIBRARY=str(a.library),
               GAIA_LIVENESS_HOST=str(a.host.parent / "liveness-host"))
    tests = invoke([sys.executable, HERE.parent / "test_liveness.py"], env=env)
    fixture_command = [a.host, HERE.parent / "fixtures.ll", a.library, "1", str(a.seed), "--dump-slices"]
    fixture = json.loads(invoke(fixture_command).stdout)
    validate_fixture(fixture)
    validate_counts(fixture)
    raw = {"schema_version": 1, "started_unix_ns": time.time_ns(), "build": build,
           "inputs_sha256": pins, "input_ir": {label: {"path": str(p), "sha256": sha(p)} for label, p in inputs.items()},
           "machine": {"platform": platform.platform(), "cpu": next((l.split(":", 1)[1].strip() for l in
                        Path("/proc/cpuinfo").read_text().splitlines() if l.startswith("model name")), "unknown"),
                       "affinity": sorted(os.sched_getaffinity(0)), "python": platform.python_version()},
           "lock": {"path": str(a.lock), "scope": "advisory, cooperating measured hosts only; unrelated load/preparation possible"},
           "tests": {"kernel_and_extraction": tests.stdout + tests.stderr, "fixture": fixture},
           "commands": [[str(x) for x in fixture_command]], "cases": {}}
    a.lock.parent.mkdir(parents=True, exist_ok=True)
    for label, path in inputs.items():
        command = [a.host, path, a.library, str(a.blocks), str(a.seed)]
        print(f"measuring {label}", flush=True)
        with a.lock.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            measurement = json.loads(invoke(command).stdout)
        validate_counts(measurement)
        raw["commands"].append([str(x) for x in command])
        raw["cases"][label] = measurement
    if pins != {str(p): sha(p) for p in pinned}:
        raise RuntimeError("run input changed")
    raw["frozen_inputs_verified_after"] = True
    save(a.output / "results.json", raw)
    summary = summarize(raw)
    save(a.output / "summary.json", summary)
    save(a.output / "validation.json", {"passed": True, "kernel_and_extraction_tests": tests.stdout + tests.stderr,
         "hand_checked_slice_queries": len(fixture["fixture_slices"]), "fixture_trace_responses": len(fixture["observations"]),
         "real_ir_trace_responses": sum(len(c["observations"]) for c in raw["cases"].values()),
         "exact_liveness_and_slice_comparison": True, "stale_generation_and_invalid_argument_rejection": True,
         "old_result_immutability": True, "exact_function_invalidation_counts": True, "frozen_inputs_verified_after": True,
         "limits": "Declared edits, single-threaded requests, syntactic intraprocedural data edges only; no alias/control/call effects or source-to-binary cycle."})
    save(a.output / "provenance.json", {k: raw[k] for k in ("build", "inputs_sha256", "input_ir", "machine", "lock", "commands", "started_unix_ns")})
    path = a.output / "results.json"
    save(a.output / "raw-identity.json", {"file": path.name, "bytes": path.stat().st_size, "sha256": sha(path)})
    print(json.dumps({label: {mode: c["modes"][mode]["request_span_sum"] for mode in MODES}
                      for label, c in summary["cases"].items()}, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("host", "library", "output", "lock"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--ir", action="append", required=True, metavar="LABEL=PATH")
    p.add_argument("--blocks", type=int, default=7)
    p.add_argument("--seed", type=int, default=731)
    main(p.parse_args())
