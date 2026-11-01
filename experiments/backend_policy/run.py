"""Profile changed-source compilation and measure compiler policy through executed tests."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import statistics
import subprocess
import tarfile
import time

HERE = Path(__file__).resolve().parent
POLICIES = {"O0": ["-O0"], "Og": ["-Og"], "O1": ["-O1"], "O2": ["-O2"],
            "O2_fast_machine": ["-O2", "-mllvm", "-fast-isel=true", "-mllvm", "-optimize-regalloc=false"]}
COMMON = ["-DNDEBUG", "-DZSTD_LEGACY_SUPPORT=0", "-DZSTD_DISABLE_ASM", "-Werror=date-time"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def run(command):
    start = time.perf_counter_ns()
    p = subprocess.run([str(x) for x in command], capture_output=True, text=True)
    ns = time.perf_counter_ns() - start
    if p.returncode:
        raise RuntimeError(f"{command}\n{p.stdout}\n{p.stderr}")
    return {"command": [str(x) for x in command], "ns": ns, "stdout": p.stdout, "stderr": p.stderr}


def edits(original):
    changes = {
        "search_budget": ("U32 nbAttempts = 1U << cParams->searchLog;",
                          "U32 nbAttempts = MAX(1U, (1U << cParams->searchLog) / 2);"),
        "lazy_depth": ("search_hashChain, 1, ZSTD_noDict);",
                       "search_hashChain, 2, ZSTD_noDict);"),
    }
    result = {}
    for name, (before, after) in changes.items():
        if original.count(before) != 1:
            raise ValueError(f"ambiguous edit {name}")
        result[name] = original.replace(before, after)
    return result, changes


@contextmanager
def locked(path):
    with path.open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def profile_summary(path):
    events = json.loads(path.read_text())["traceEvents"]
    totals = {e["name"][6:]: {"ms": e["dur"] / 1000, **e.get("args", {})}
              for e in events if e["name"].startswith("Total ")}
    hot = sorted((e for e in events if e["name"] == "OptFunction"), key=lambda e: -e["dur"])[:12]
    return {"totals_inclusive_nonadditive": totals,
            "largest_machine_codegen_functions": [{"function": e.get("args", {}).get("detail"), "ms": e["dur"] / 1000} for e in hot]}


def stats(values):
    return {"median_ms": statistics.median(values) / 1e6, "min_ms": min(values) / 1e6,
            "max_ms": max(values) / 1e6, "samples": len(values)}


def summarize(raw):
    result = {"cases": {}, "note": "Unprofiled requests; edit admission, compile, link, and first suite are inside cycle_ns. Long-suite cost is a separately measured alternative demand."}
    for variant in raw["edits"]:
        result["cases"][variant] = {}
        rows = [r for r in raw["observations"] if r["edit"] == variant]
        controls = {r["block"]: r for r in rows if r["policy"] == "O2"}
        for policy in POLICIES:
            current = [r for r in rows if r["policy"] == policy]
            item = {key: stats([r[key] for r in current]) for key in
                    ("compile_ns", "link_ns", "test_ns", "cycle_ns", "long_test_ns", "long_demand_sum_ns")}
            item["object_bytes"] = sorted({r["object_bytes"] for r in current})
            item["cases_per_short_suite"] = current[0]["test"]["cases"]
            for key in ("cycle_ns", "compile_ns", "long_demand_sum_ns"):
                item[key]["paired_wins_vs_O2"] = sum(r[key] < controls[r["block"]][key] for r in current)
            result["cases"][variant][policy] = item
    return result


def main(a):
    for key in ("clang", "ar", "archive", "work", "output", "lock"):
        setattr(a, key, getattr(a, key).resolve())
    if not 1 <= a.blocks <= 30 or not 1 <= a.long_repeats <= 100:
        raise ValueError("invalid counts")
    a.work.mkdir(parents=True, exist_ok=False)
    a.output.mkdir(parents=True, exist_ok=False)
    a.lock.parent.mkdir(parents=True, exist_ok=True)
    pins = {str(p): sha(p) for p in (a.clang, a.ar, a.archive, HERE / "run.py", HERE / "roundtrip.c")}
    dynamic = run(["ldd", a.clang])
    for line in dynamic["stdout"].splitlines():
        tokens = line.split()
        path = next((Path(t) for t in tokens if t.startswith("/") and Path(t).is_file()), None)
        if path:
            pins[str(path.resolve())] = sha(path)
    start = time.perf_counter_ns()
    with tarfile.open(a.archive) as archive:
        archive.extractall(a.work, filter="data")
    project = a.work / "zstd-1.5.7"
    lib = project / "lib"
    source = lib / "compress/zstd_lazy.c"
    original = source.read_text()
    variants, changes = edits(original)
    source_pins = {str(p.relative_to(project)): sha(p) for p in project.rglob("*") if p.is_file()}
    corpus = a.work / "corpus.txt"; corpus.write_text(original)
    common = [str(a.clang), *COMMON, "-I" + str(lib)]
    fixed = sorted(p for directory in ("common", "compress", "decompress", "dictBuilder")
                   for p in (lib / directory).glob("*.c") if p != source)
    objdir = a.work / "fixed"; objdir.mkdir()
    def build_fixed(p):
        obj = objdir / (p.parent.name + "-" + p.stem + ".o")
        return obj, run([*common, "-O2", "-c", p, "-o", obj])
    with ThreadPoolExecutor(max_workers=4) as pool:
        built = list(pool.map(build_fixed, fixed))
    archive = a.work / "fixed.a"
    preparation = [record for _, record in built]
    preparation.append(run([a.ar, "rcs", archive, *[p for p, _ in built]]))
    harness = a.work / "roundtrip.o"
    preparation.append(run([*common, "-O2", "-c", HERE / "roundtrip.c", "-o", harness]))
    output = a.work / "current.o"; exe = a.work / "roundtrip"; frames = a.work / "frames.bin"
    link = [a.clang, harness, output, archive, "-pthread", "-o", exe]
    test = [exe, corpus, frames, "1"]
    raw = {"schema_version": 1, "started_unix_ns": time.time_ns(), "inputs_sha256": pins,
           "archive_sha256": sha(a.archive), "source_tree_sha256": source_pins,
           "policies": POLICIES, "common_flags": COMMON, "edits": changes,
           "machine": {"platform": platform.platform(), "affinity": sorted(os.sched_getaffinity(0)),
                       "cpu": next(l.split(":", 1)[1].strip() for l in Path("/proc/cpuinfo").read_text().splitlines() if l.startswith("model name"))},
           "compiler_version": run([a.clang, "--version"])["stdout"], "compiler_dynamic_libraries": dynamic,
           "environment_sha256": hashlib.sha256(json.dumps(dict(os.environ), sort_keys=True).encode()).hexdigest(), "lock": str(a.lock),
           "blocks": a.blocks, "seed": a.seed, "long_repeats": a.long_repeats,
           "preparation": preparation, "references": {}, "profiles": [], "observations": []}
    references = {}
    for name, body in {"baseline": original, **variants}.items():
        source.write_text(body)
        with locked(a.lock):
            compile_record = run([*common, "-O2", "-c", source, "-o", output])
            link_record = run(link); test_record = run(test)
        references[name] = frames.read_bytes()
        raw["references"][name] = {"compile": compile_record, "link": link_record, "test": test_record,
                                    "source_sha256": sha(source), "frames_sha256": sha(frames),
                                    "object_sha256": sha(output), "tests": json.loads(test_record["stdout"])}
        if name != "baseline" and references[name] == references["baseline"]:
            raise AssertionError(f"edit {name} did not change compressed outputs in this workload")
    raw["preparation_ns"] = time.perf_counter_ns() - start
    print("prepared full library; both edits change tested compression outputs", flush=True)
    immutable = {str(p): sha(p) for p in (archive, harness, corpus, *[p for p, _ in built])}
    # Intrusive profiles are diagnostics only. Optimization and codegen are
    # nested under Backend; pass-manager totals are not additive.
    for variant, body in variants.items():
        source.write_text(body)
        irs = []
        for policy in ("O2", "O2_fast_machine"):
            trace = a.output / f"compiler-{variant}-{policy}-trace.json"
            with locked(a.lock):
                record = run([*common, *POLICIES[policy], "-c", source, "-o", output,
                              "-ftime-trace=" + str(trace), "-ftime-trace-granularity=0"])
                # Capture exact optimized IR as a separate untimed diagnostic.
                ir = a.work / f"{variant}-{policy}.ll"
                ir_record = run([*common, *POLICIES[policy], "-S", "-emit-llvm", source, "-o", ir])
            irs.append(ir.read_bytes())
            raw["profiles"].append({"edit": variant, "policy": policy, "record": record,
                "trace": str(trace), "trace_sha256": sha(trace), "trace_bytes": trace.stat().st_size,
                "optimized_ir_record": ir_record, "optimized_ir_sha256": sha(ir), "summary": profile_summary(trace)})
        if irs[0] != irs[1]:
            raise AssertionError("machine policy changed optimized IR")
    raw["optimized_ir_identical_between_O2_policies"] = True
    print("profiled edits; O2 policies produce identical optimized IR", flush=True)
    rng = random.Random(a.seed)
    object_identities = {}
    for block in range(a.blocks):
        order = [(variant, policy) for variant in variants for policy in POLICIES]
        rng.shuffle(order)
        for variant, policy in order:
            with locked(a.lock):
                start = time.perf_counter_ns()
                source.write_text(variants[variant])
                compiled = run([*common, *POLICIES[policy], "-c", source, "-o", output])
                linked = run(link)
                tested = run(test)
                cycle_ns = time.perf_counter_ns() - start
                first_frames = frames.read_bytes()
                longer = run([exe, corpus, frames, str(a.long_repeats)])
            if first_frames != references[variant] or frames.read_bytes() != references[variant]:
                raise AssertionError(f"compressed outputs differ: {variant}/{policy}")
            object_digest = sha(output)
            key = (variant, policy)
            if key in object_identities and object_identities[key] != object_digest:
                raise AssertionError("object identity changed across repeated measurements")
            object_identities[key] = object_digest
            row = {"block": block, "edit": variant, "policy": policy,
                   "compile_ns": compiled["ns"], "link_ns": linked["ns"], "test_ns": tested["ns"],
                   "cycle_ns": cycle_ns, "long_test_ns": longer["ns"],
                   "long_demand_sum_ns": cycle_ns - tested["ns"] + longer["ns"],
                   "compile_command": compiled["command"], "link_command": linked["command"],
                   "test_command": tested["command"], "long_test_command": longer["command"],
                   "test": json.loads(tested["stdout"]), "long_test": json.loads(longer["stdout"]),
                   "object_sha256": object_digest, "object_bytes": output.stat().st_size,
                   "executable_sha256": sha(exe), "exact_frames_match_O2_reference": True}
            raw["observations"].append(row)
            print(block, variant, policy, f"{cycle_ns / 1e6:.1f} ms", flush=True)
    source.write_text(original)
    if pins != {p: sha(Path(p)) for p in pins} or immutable != {p: sha(Path(p)) for p in immutable}:
        raise AssertionError("tool, source, or stable artifact changed")
    if source_pins != {str(p.relative_to(project)): sha(p) for p in project.rglob("*") if p.is_file()}:
        raise AssertionError("upstream source tree changed")
    raw["fixed_artifacts_sha256"] = immutable
    raw["frozen_inputs_verified_after"] = True
    save(a.output / "results.json", raw)
    save(a.output / "summary.json", summarize(raw))
    save(a.output / "profiles-summary.json", {"diagnostic_only": True, "profiles": [
        {k: p[k] for k in ("edit", "policy", "summary", "trace_sha256", "trace_bytes", "optimized_ir_sha256")} for p in raw["profiles"]]})
    save(a.output / "validation.json", {"passed": True, "real_compiles_linked_and_executed": len(raw["observations"]),
        "round_trips_checked": sum(r["test"]["cases"] + r["long_test"]["cases"] for r in raw["observations"]),
        "exact_compressed_frames_match_current_edit_O2_reference": True, "both_edits_change_observed_compressed_bytes": True,
        "optimized_ir_identical_between_O2_policies": True, "stable_objects_across_blocks": True,
        "source_and_tools_verified_after": True,
        "limits": "Deterministic experimental API workload, not upstream conformance suite or proof of all Zstandard/compiler behavior. No sanitizers, debug-info or multithreaded compression tested."})
    save(a.output / "provenance.json", {k: raw[k] for k in ("inputs_sha256", "archive_sha256", "source_tree_sha256", "machine",
         "compiler_version", "compiler_dynamic_libraries", "environment_sha256", "common_flags", "policies", "edits", "blocks", "seed", "long_repeats", "lock", "preparation_ns", "preparation",
         "fixed_artifacts_sha256", "started_unix_ns")})
    paths = [a.output / "results.json", *sorted(a.output.glob("compiler-*-trace.json"))]
    save(a.output / "raw-identity.json", {"artifacts": [{"file": p.name, "bytes": p.stat().st_size, "sha256": sha(p)} for p in paths]})
    print("complete", flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("clang", "ar", "archive", "work", "output", "lock"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--blocks", type=int, default=7)
    p.add_argument("--seed", type=int, default=9181)
    p.add_argument("--long-repeats", type=int, default=8)
    main(p.parse_args())
