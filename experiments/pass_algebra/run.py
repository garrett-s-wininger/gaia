"""Measure equivalent liveness formulations on freshly compiled upstream IR."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import tarfile
import time

HERE = Path(__file__).resolve().parent
MODES = {0: "block_worklist", 1: "boolean_sweeps", 2: "per_value_sparse"}


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def run_command(command):
    return subprocess.run([str(x) for x in command], capture_output=True, text=True, check=True)


def summarize(data, output):
    summary = {"cases": {}}
    for case in data["cases"]:
        measurement = case["measurement"]
        shapes = measurement["functions"]
        result = {"functions": len(shapes),
                  **{key: sum(f[key] for f in shapes) for key in
                     ("blocks", "values", "edges", "seed_facts", "live_facts", "phis", "phi_operands")},
                  "max_function_blocks": max(f["blocks"] for f in shapes),
                  "max_function_values": max(f["values"] for f in shapes),
                  "parse_and_verify_ms": measurement["parse_and_verify_ns"] / 1e6,
                  "modes": {}}
        for mode, name in MODES.items():
            preparation = next(p for p in measurement["preparation"] if p["mode"] == mode)
            result["modes"][name] = {"retained_payload_and_scratch_bytes": preparation["retained_payload_and_scratch_bytes"],
                                      "layout_ms": preparation["layout_ns"] / 1e6,
                                      "work_units": preparation["work_units"]}
            for boundary in ("prepared_kernel", "resident_ir_to_result"):
                observations = [r for r in measurement["observations"] if r["mode"] == mode and r["boundary"] == boundary]
                samples = [r["ns"] / r["repetitions"] / 1e6 for r in observations]
                result["modes"][name][boundary] = {
                    "median_ms": statistics.median(samples), "min_ms": min(samples), "max_ms": max(samples),
                    "blocks": len(samples)}
                if mode:
                    baseline = {r["block"]: r["ns"] / r["repetitions"] for r in measurement["observations"]
                                if r["mode"] == 0 and r["boundary"] == boundary}
                    result["modes"][name][boundary]["paired_wins_vs_worklist"] = sum(
                        r["ns"] / r["repetitions"] < baseline[r["block"]] for r in observations)
        summary["cases"][case["label"]] = result
    save(output / "summary.json", summary)
    save(output / "validation.json", {
        "passed": all(c["measurement"]["oracle_validated_all_bits"] for c in data["cases"]),
        "real_source_functions": sum(c["functions"] for c in summary["cases"].values()),
        "formulations": 3, "oracle": "independent ordered-set synchronous least fixed point; every output bit checked",
        "source_and_tool_pins_verified_after": data["frozen_inputs_verified_after"],
        "tests": data["unit_tests"],
        "limits": "Extraction is shared across formulations; hand-checked LLVM fixtures validate its edge semantics. No stock LLVM liveness implementation is timed."})
    save(output / "provenance.json", {key: data[key] for key in
         ("machine", "build", "commands", "implementation_and_tools", "archives", "unit_tests", "scope", "lock")})
    raw = output / "results.json"
    save(output / "raw-identity.json", {"file": "results.json", "bytes": raw.stat().st_size, "sha256": sha(raw)})
    lines = ["# Three formulations of SSA value liveness", "",
             "These are measurements of an analysis pass on real Zstandard/zlib LLVM IR, not a complete compiler or development-session speedup. All formulations produce the same block-by-value live-in relation. Values below are milliseconds per module pass, medians of shuffled blocks.", "",
             "| Input | Functions / blocks | Worklist kernel | Boolean sweeps kernel | Per-value kernel | Worklist full pass | Sweeps full pass | Per-value full pass |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for label, case in summary["cases"].items():
        values = [case["modes"][name][boundary]["median_ms"] for boundary in
                  ("prepared_kernel", "resident_ir_to_result") for name in MODES.values()]
        lines.append(f"| {label} | {case['functions']} / {case['blocks']} | " + " | ".join(f"{v:.4f}" for v in values) + " |")
    lines += ["", "The full pass starts with an already parsed LLVM module. It extracts facts, constructs each formulation's layout and scratch space, solves liveness, consumes the complete output through a checksum, and destroys request state. IR parsing/verification and source-to-IR compilation are separate preparation measurements. The prepared kernel includes output reset and solving with caller-owned retained buffers; it excludes layout and full-output hashing.", "",
              "All three kernels are native Odin compiled with the same flags. The ordinary row loops may auto-vectorize. The full-sweep formulation is an exact Boolean operation; no floating-point approximation or GPU/NPU execution is involved. Repeated timing batches amortize clock noise and do not establish a natural cache-reuse workload.", "",
              "[Summary](summary.json), [validation](validation.json), [provenance](provenance.json), [raw identity](raw-identity.json), [reproduction and mathematical contract](../../README.md). Full observations remain in ignored `results.json`."]
    (output / "REPORT.md").write_text("\n".join(lines) + "\n")
    return summary


def main(args):
    for name in ("host", "library", "clang", "zstd_archive", "zlib_archive", "work", "output", "lock"):
        setattr(args, name, getattr(args, name).resolve())
    if not 1 <= args.blocks <= 1000 or not 1 <= args.repetitions <= 10000:
        raise ValueError("invalid measurement counts")
    args.work.mkdir(parents=True, exist_ok=False)
    args.output.mkdir(parents=True, exist_ok=True)
    if (args.output / "results.json").exists():
        raise FileExistsError("output already contains observations")
    build_path = args.host.parent / "build.json"
    build = json.loads(build_path.read_text())
    for path, expected in build["outputs_sha256"].items():
        if sha(Path(path)) != expected:
            raise ValueError("binary differs from build manifest")
    pinned = [args.host, args.library, args.clang, build_path, *sorted(HERE.glob("*.py")),
              *sorted(HERE.glob("*.cpp")), *sorted(HERE.glob("*.odin")), HERE / "fixtures.ll"]
    pins = {str(p): sha(p) for p in pinned}
    archives = {str(p): sha(p) for p in (args.zstd_archive, args.zlib_archive)}
    data = {"status": "running", "implementation_and_tools": pins, "archives": archives, "build": build,
            "commands": [], "cases": [], "lock": str(args.lock),
            "machine": {"platform": platform.platform(), "python": platform.python_version(),
                        "cpu_model": next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                                           if line.startswith("model name")), "unknown"),
                        "affinity": sorted(os.sched_getaffinity(0)),
                        "clang": run_command([args.clang, "--version"]).stdout},
            "scope": "Warm native, single-threaded pass comparison on immutable LLVM IR. Shared advisory timing lock with integration thread; preparation and unrelated host activity are not excluded. Native-target Odin/C++ builds. No device dispatch, output code changes, incremental update policy, full compiler timing, peak RSS or enforced memory quota."}
    save(args.output / "results.json", data)
    try:
        env = dict(os.environ, GAIA_LIVENESS_LIBRARY=str(args.library), GAIA_LIVENESS_HOST=str(args.host))
        tests = subprocess.run([os.sys.executable, "-B", "-m", "unittest", "discover", "-s", str(HERE), "-p", "test_*.py", "-v"],
                               capture_output=True, text=True, env=env, check=True)
        if "skipped" in tests.stderr:
            raise RuntimeError("required validation was skipped")
        data["unit_tests"] = {"passed": True, "methods": 4, "exhaustive_graph_fact_combinations": 4096,
                              "random_graph_fact_combinations": 175, "hand_checked_llvm_functions": 6,
                              "stdout": tests.stdout, "stderr": tests.stderr}
        for archive in (args.zstd_archive, args.zlib_archive):
            with tarfile.open(archive) as source:
                source.extractall(args.work, filter="data")
        cases = [("zstd-common-O1", args.work / "zstd-1.5.7/lib/common/zstd_common.c"),
                 ("zstd-lazy-O1", args.work / "zstd-1.5.7/lib/compress/zstd_lazy.c"),
                 ("zlib-deflate-O1", args.work / "zlib-1.3.2/deflate.c")]
        for label, source in cases:
            ir = args.work / (label + ".ll")
            command = [str(args.clang), "-O1", "-S", "-emit-llvm", "-Werror=date-time", str(source), "-o", str(ir)]
            begin = time.perf_counter_ns()
            result = run_command(command)
            data["commands"].append({"command": command, "ns": time.perf_counter_ns() - begin,
                                     "source_sha256": sha(source), "ir_sha256": sha(ir), "stderr": result.stderr})
            command = [str(args.host), "bench", str(ir), str(args.library), str(args.blocks), str(args.repetitions)]
            print(f"measuring {label}", flush=True)
            with args.lock.open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                measurement = json.loads(run_command(command).stdout)
            data["cases"].append({"label": label, "command": command, "measurement": measurement})
            save(args.output / "results.json", data)
        if pins != {str(p): sha(p) for p in pinned} or archives != {str(p): sha(p) for p in (args.zstd_archive, args.zlib_archive)}:
            raise RuntimeError("source/tool inputs changed during measurement")
        data["frozen_inputs_verified_after"] = True
        data["status"] = "complete"
        save(args.output / "results.json", data)
        summary = summarize(data, args.output)
        print(json.dumps(summary, indent=2))
    except BaseException as error:
        data["status"] = "failed"
        data["error"] = {"type": type(error).__name__, "message": str(error)}
        save(args.output / "results.json", data)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("host", "library", "clang", "zstd-archive", "zlib-archive", "work", "output", "lock"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--blocks", type=int, default=7)
    parser.add_argument("--repetitions", type=int, default=10)
    main(parser.parse_args())
