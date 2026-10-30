#!/usr/bin/env python3
"""Actual CPython loading through Odin: synthetic continuity + offline real pip."""
import os
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
import sysconfig
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import benchmark
from native_benchmark import compile_extension
from precomputed_index import build_index


def make_wheelhouse(root):
    root.mkdir()
    packages = [("gaia-app", "1.0", ["gaia-a>=1", "gaia-b==1"] + [f"gaia-leaf-{i:02}>=1" for i in range(8)]),
                ("gaia-a", "2.0", ["gaia-c>=2"]), ("gaia-a", "1.0", ["gaia-c<2"]),
                ("gaia-b", "1.0", ["gaia-c<2"]), ("gaia-c", "2.0", []), ("gaia-c", "1.0", [])]
    packages += [(f"gaia-leaf-{i:02}", v, []) for i in range(8) for v in ("1.0", "2.0")]
    for name, version, dependencies in packages:
        normalized = name.replace("-", "_")
        prefix = f"{normalized}-{version}.dist-info/"
        metadata = f"Metadata-Version: 2.3\nName: {name}\nVersion: {version}\n"
        metadata += "".join(f"Requires-Dist: {d}\n" for d in dependencies) + "\n"
        with zipfile.ZipFile(root / f"{normalized}-{version}-py3-none-any.whl", "w") as wheel:
            for member, value in (("METADATA", metadata), ("WHEEL", "Wheel-Version: 1.0\nGenerator: gaia-fixture\nRoot-Is-Purelib: true\nTag: py3-none-any\n"), ("RECORD", "")):
                info = zipfile.ZipInfo(prefix+member, (2020,1,1,0,0,0))
                info.external_attr = 0o100644 << 16
                wheel.writestr(info, value)
    return sorted([["gaia-app", "1.0"], ["gaia-a", "1.0"], ["gaia-b", "1.0"], ["gaia-c", "1.0"]]
                  + [[f"gaia-leaf-{i:02}", "2.0"] for i in range(8)])


def render(data, path):
    pip_sample = next(c["samples"][0] for c in data["cases"] if c["workload"] == "pip")
    boundary = ("Extension loading, native open and Python catalog construction occur inside the timed workload."
                if data.get("pip_setup_timing_corrected", False) else
                "Timing correction: in this original run, a lazy host import during temporary-directory setup "
                "opened pip bundle providers before the workload timer. Pip workload columns exclude that "
                "provider setup, while process-wall columns include it and remain valid. Synthetic workload "
                "timing is unaffected. The current worker defers provider/input publication until the timer "
                "starts; corrected phase diagnostics are in ../resolution/REPORT.md. Original observations "
                "are preserved rather than relabeled as corrected measurements.")
    lines = ["# Odin connected to CPython", "", f"Run: `{data['run_id']}`.", "",
             "Fresh `python -I -S -B` per observation, warm/reused filesystem cache, randomized trials. "
             "All module source/bytecode is interpreted by CPython. Odin supplies byte access through "
             "a GIL-held C extension shim; no per-read IPC or external native worker is involved. "
             "The module/resource loader, compiler and bytecode semantics are unchanged.", "",
             "## Cases and integrity", "",
             "- `directory`: equivalent source-only/pyc-only loose input tree; generated caches disabled.",
             "- `mmap`: Python index construction from ZIP metadata and mapped reads.",
             "- `python-*`: Python binary-sidecar reader.",
             "- `odin-*`: Odin loads/verifies/maps the sidecar and bundle, returns a catalog in one call, "
             "and checks CRC in native code on every read. The C shim copies the payload directly into "
             "an owned Python bytes object before returning, with the GIL held. Python still builds "
             "the name/module lookup objects; this measures the real boundary overhead too.",
             "- `hash` rechecks whole-bundle SHA-256 at open; `local` checks admitted file identity in "
             "a trusted immutable local store. Sidecar digest pinning, bounds/UTF-8 checks and CRC remain. "
             "Mapping mutation/truncation is unsupported. Native input failures return Python exceptions; "
             "capsule destruction and explicit close release native mappings/allocations.",
             "- " + boundary + " Their separate observed times are retained in raw samples. Common "
             "Python adapter imports are equal across controls. Process wall includes interpreter setup, "
             "the workload, validation and cleanup. Build and producer costs are outside consumer timing.", "",
             "## Workloads", "",
             "Synthetic: the existing 2,048-leaf fixture, 2,072 imported modules, relative imports, "
             "32 package resources and a deterministic application checksum. The same worker/validation "
             "is used as before.", "",
             f"Representative: bundled pip {data['pip']['version']} from `{data['pip']['wheel_name']}`, "
             f"SHA-256 `{data['pip']['wheel_sha256']}`. Its real pure-Python package/vendored dependency "
             "code executes normally through `runpy` as a CLI invocation. It performs an offline "
             "`install --dry-run --ignore-installed --no-index --find-links ... --report ...`, with isolated "
             "settings, cache/version checks disabled and an audit hook rejecting network operations. "
             "The 22 generated tiny wheels model a 12-package solution and force A 2.0 → A 1.0 backtracking. "
             "The graph/target wheels are synthetic; pip and its vendored implementation are unmodified. "
             "Nothing is installed. Host stdlib/native extensions remain ordinary interpreter inputs.", "",
             "Pip validation compares exact selected versions, normalized report SHA-256 across layouts, "
             "all imported pip module origins/loaders, vendor.txt contents, missing-module rejection, "
             "one provider open, matching code-read counts across bundle providers, file-execution counts "
             "across all readers, and zero network events. "
             "Any certificate/path materialization and standard distribution-metadata/wheel access performed "
             "by pip are included in the workload; they are not intercepted by the Odin content adapter.", "",
             f"This invocation retains {pip_sample['pip_modules']} unique pip module origins and "
             f"{pip_sample['module_aliases']} aliases; the execution audit records "
             f"{len(pip_sample['executed_files'])} distinct pip code files, including the CLI main and code no longer retained "
             "in sys.modules. Bundle code-read counts match the file-execution counts. Source and bytecode "
             "execution filenames are normalized to the same logical paths.", "",
             f"{data['trials']} trials per case, plus one warmup. Medians, ms. Source/bytecode inputs have "
             "identical contents across readers within each mode; all timings are actual Python consumption.", "",
             "| Workload | Input | Reader | Workload ms | Process wall ms | Workload p95 ms | Unique module origins | Peak RSS MiB |",
             "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for case in data["cases"]:
        s = case["summary"]
        modules = case["samples"][0].get("pip_modules", case["samples"][0].get("verified_modules"))
        lines.append(f"| {case['workload']} | {case['mode']} | {case['reader']} | "
                     f"{s['workload_seconds']['median']*1000:.3f} | {s['process_wall_seconds']['median']*1000:.3f} | "
                     f"{s['workload_seconds']['p95']*1000:.3f} | {modules} | {s['peak_rss_bytes']['median']/2**20:.2f} |")
    lines += ["", "## Limits", "",
              "Linux/CPython-specific bridge; no stable platform ABI or container format is declared. "
              "The extension holds the GIL, returns bytes rather than exposed mapped views, and does not "
              "accelerate compilation, marshal, import machinery or application execution. Pip is one "
              "representative real tool over a generated graph, not evidence of typical ecosystem module "
              "counts, graph sizes or arbitrary real package startup. Repeated consumers, cold storage, "
              "concurrent mutation, namespace packages and native extensions inside the bundle are not covered. "
              "No syscall-count claim is made. Exact commands, input/extension hashes, raw phases and "
              "correctness observations are retained in results.json.", ""]
    path.write_text("\n".join(lines))


def run(args):
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    work = benchmark.HERE / "_work" / ("python-native-"+run_id)
    work.mkdir(parents=True)
    library, build = compile_extension(work, args.odin)
    synthetic = work / "synthetic-source"
    manifest = benchmark.make_fixture(synthetic, args.modules)
    manifest_path = work / "manifest.json"
    benchmark.write_json(manifest_path, manifest)
    pip_wheel = args.pip_wheel
    if pip_wheel is None:
        pip_wheel = next((Path(sysconfig.get_path("stdlib"))/"ensurepip/_bundled").glob("pip-*.whl"), None)
        if pip_wheel is None:raise RuntimeError("Supply --pip-wheel or GAIA_PIP_WHEEL when ensurepip has no bundled wheel")
    pip_source = work / "pip-source"
    with zipfile.ZipFile(pip_wheel) as wheel:
        for info in wheel.infolist():
            if info.is_dir():
                continue
            if info.filename.startswith("/") or ".." in Path(info.filename).parts:
                raise ValueError("invalid wheel path")
            target = pip_source / info.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(wheel.read(info))
    version = next(pip_source.glob("pip-*.dist-info")).name[len("pip-"):-len(".dist-info")]
    wheelhouse = work / "wheelhouse"
    expected = {"selected": make_wheelhouse(wheelhouse), "pip_version": version,
                "vendor_sha256": hashlib.sha256((pip_source/"pip/_vendor/vendor.txt").read_bytes()).hexdigest()}
    expected_path = work / "pip-expected.json"
    benchmark.write_json(expected_path, expected)
    data = {"run_id": run_id, "trials": args.trials, "modules": args.modules, "pip_setup_timing_corrected": True,
            "environment": benchmark.environment(work), "build": build, "inputs": [], "cases": [],
            "pip": {"version": version, "wheel_name": pip_wheel.name,
                    "wheel_sha256": hashlib.sha256(pip_wheel.read_bytes()).hexdigest()}}
    for workload, source in (("synthetic", synthetic), ("pip", pip_source)):
        bytecode = work / (workload+"-bytecode")
        benchmark.precompile(source, bytecode)
        for mode, directory in (("source", source), ("bytecode", bytecode)):
            archive = work / (workload+"-"+mode+".zip")
            benchmark.pack(directory, archive, zipfile.ZIP_STORED)
            index = archive.with_suffix(".index")
            built = build_index(archive, index, encoding="binary")
            data["inputs"].append({"workload": workload, "mode": mode, "archive": str(archive),
                                    "directory": str(directory), "index": str(index), **built})
            for reader in ("directory", "mmap", "python-hash", "python-local", "odin-hash", "odin-local"):
                root = directory if reader == "directory" else archive
                policy = "local" if reader.endswith("local") else "hash"
                index_args = [] if reader in ("directory", "mmap") else ["--index", str(index)]
                if workload == "synthetic":
                    command = benchmark.worker_command(manifest_path, root, "directory" if reader == "directory" else "access-mmap", mode)
                    if index_args:
                        command += index_args + ["--index-sha256", built["index_sha256"], "--index-verification", policy]
                    if reader.startswith("odin"):
                        command += ["--native-library", str(library)]
                else:
                    kind = reader.split("-")[0]
                    command = [sys.executable, "-I", "-S", "-B", str(benchmark.HERE/"pip_worker.py"),
                               "--root", str(root), "--reader", kind, "--wheelhouse", str(wheelhouse),
                               "--expected", str(expected_path)]
                    if index_args:
                        command += index_args + ["--pin", built["index_sha256"], "--policy", policy]
                    if reader.startswith("odin"):
                        command += ["--library", str(library)]
                data["cases"].append({"workload": workload, "mode": mode, "reader": reader,
                                      "command": command, "samples": []})
    report_hashes = set()
    module_sets = {"source": set(), "bytecode": set()}
    execution_sets = {"source": set(), "bytecode": set()}
    read_counts = {"source": set(), "bytecode": set()}
    def consume(case):
        try:
            sample = benchmark.consume(case["command"])
        except subprocess.CalledProcessError as error:
            raise RuntimeError(error.stdout+error.stderr) from error
        if not sample["correct"]:
            raise RuntimeError("incorrect consumer")
        if case["workload"] == "pip":
            report_hashes.add(sample["report_sha256"])
            module_sets[case["mode"]].add(tuple(sorted(sample["module_origins"].items())))
            execution_sets[case["mode"]].add(tuple(sorted(sample["executed_files"].items())))
            if sample["module_reads"] is not None:
                read_counts[case["mode"]].add(sample["module_reads"])
            if (len(report_hashes) != 1 or len(module_sets[case["mode"]]) != 1
                    or len(execution_sets[case["mode"]]) != 1 or len(read_counts[case["mode"]]) > 1):
                raise RuntimeError("pip report/import set differs across readers")
        return sample
    for case in data["cases"]:
        consume(case)
    rng = random.Random(20261028)
    for trial in range(args.trials):
        cases = data["cases"].copy()
        rng.shuffle(cases)
        for case in cases:
            case["samples"].append(consume(case))
        if (trial+1)%5 == 0:
            print(f"Python/Odin trials {trial+1}/{args.trials}", flush=True)
    for case in data["cases"]:
        case["summary"] = benchmark.summarize(case["samples"])
    args.output.mkdir(parents=True, exist_ok=True)
    benchmark.write_json(args.output/"results.json", data)
    render(data, args.output/"REPORT.md")
    print(args.output/"REPORT.md")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--odin", default=shutil.which(os.environ.get("ODIN", "odin")) or os.environ.get("ODIN", "odin"))
    parser.add_argument("--pip-wheel", type=Path, default=Path(os.environ["GAIA_PIP_WHEEL"]) if os.environ.get("GAIA_PIP_WHEEL") else None)
    parser.add_argument("--modules", type=int, default=2048)
    parser.add_argument("--trials", type=int, default=15)
    parser.add_argument("--output", type=Path, default=benchmark.HERE/"_work/runs/python-native")
    args = parser.parse_args()
    if args.trials < 1 or args.modules < 16 or args.modules%16:
        parser.error("positive trials; modules >=16 divisible by16")
    run(args)
