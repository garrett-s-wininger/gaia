#!/usr/bin/env python3
"""Standard-library-only bundle/load benchmark; no package downloads or installs."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import py_compile
import random
import re
import shutil
import statistics
import subprocess
import sys
import time
import zipfile


HERE = Path(__file__).resolve().parent
WORKER = HERE / "worker.py"
PREFIX = "gaia_fixture_p"
LAYOUTS = ("directory", "stored", "deflated", "shared-stored", "shared-deflated",
           "persistent-stored", "persistent-deflated", "access-zipfile", "access-pread",
           "access-mmap", "access-resident")
MODES = ("source", "bytecode")
TRACE_SYSCALLS = "%file,read,pread64,close,lseek,getdents64,mmap,munmap,write,fstat"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def make_fixture(root, count, rounds=16):
    if count < 16 or count % 16:
        raise ValueError("module counts must be positive multiples of 16")
    root.mkdir(parents=True, exist_ok=False)
    manifest = {"prefix": PREFIX, "modules": [], "module_paths": {}, "resources": [],
                "application_rounds": rounds}
    salts = []

    def module(name, relative, source):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(source.encode())
        manifest["module_paths"][name] = relative

    ordinal = 0
    for package_index in range(4):
        package = f"{PREFIX}{package_index:02}"
        salt = 101 + package_index * 17
        module(package, f"{package}/__init__.py", '"""Controlled Gaia dependency fixture."""\n')
        module(package + ".shared", f"{package}/shared.py",
               f"SALT = {salt}\ndef mix(value):\n    return ((value * 33) ^ SALT) & 0xffffffff\n")
        for sub_index in range(4):
            sub = f"{package}.sub{sub_index:02}"
            subpath = sub.replace(".", "/")
            module(sub, subpath + "/__init__.py", '"""Regular subpackage."""\n')
            for _ in range(count // 16):
                name = f"{sub}.module{ordinal:05}"
                source = (f'"""Fixture module {ordinal}, including relative dependency loading."""\n'
                          f"from ..shared import mix\nTOKEN = {ordinal}\n"
                          "def evaluate(value):\n    return (mix(value + TOKEN) + TOKEN) & 0xffffffff\n")
                module(name, name.replace(".", "/") + ".py", source)
                manifest["modules"].append(name)
                salts.append(salt)
                ordinal += 1
            for name, data in (
                ("settings.json", json.dumps({"package": sub, "enabled": True}).encode()),
                ("payload.bin", hashlib.sha256(sub.encode()).digest() * 128),
            ):
                (root / subpath / name).write_bytes(data)
                manifest["resources"].append({"package": sub, "name": name, "sha256": digest(data)})
    manifest["all_modules"] = sorted(manifest["module_paths"])
    manifest["application_checksum"] = sum(
        (((((iteration + index * 2) * 33) ^ salt) & 0xffffffff) + index) & 0xffffffff
        for iteration in range(rounds) for index, salt in enumerate(salts)
    ) & ((1 << 64) - 1)
    return manifest


def precompile(source, destination):
    destination.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".py":
            py_compile.compile(str(path), cfile=str(target.with_suffix(".pyc")),
                               dfile="gaia-fixture:///" + relative.as_posix(), doraise=True,
                               invalidation_mode=py_compile.PycInvalidationMode.CHECKED_HASH)
        else:
            target.write_bytes(path.read_bytes())
    return time.perf_counter() - start


def file_map(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in sorted(root.rglob("*")) if p.is_file()}


def validate_archive(archive):
    """Accept our regular-file bundle fixture, rejecting ambiguous/unsafe names."""
    entries, folded = set(), set()
    with zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            name = info.filename
            path = PurePosixPath(name)
            if (not name or name.startswith("/") or "\\" in name or "\x00" in name
                    or any(p in ("", ".", "..") for p in name.split("/"))
                    or path.is_absolute() or (len(name) > 1 and name[1] == ":")):
                raise ValueError(f"unsupported archive path: {name!r}")
            if name in entries or name.casefold() in folded:
                raise ValueError(f"duplicate/colliding archive path: {name!r}")
            # Generated archives contain regular files, no links or directories.
            kind = (info.external_attr >> 16) & 0o170000
            if kind not in (0, 0o100000) or info.is_dir():
                raise ValueError(f"unsupported archive entry: {name!r}")
            entries.add(name)
            folded.add(name.casefold())
        for name in entries:
            parents = PurePosixPath(name).parents
            if any(str(parent) in entries for parent in parents if str(parent) != "."):
                raise ValueError(f"file/directory collision at {name!r}")
        bad = bundle.testzip()
        if bad is not None:
            raise ValueError(f"archive CRC mismatch: {bad}")
    return entries


def pack(source, target, compression):
    start = time.perf_counter()
    with zipfile.ZipFile(target, "w", compression=compression,
                         compresslevel=6 if compression == zipfile.ZIP_DEFLATED else None) as bundle:
        for name, data in file_map(source).items():
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = compression
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, data, compresslevel=6 if compression == zipfile.ZIP_DEFLATED else None)
    elapsed = time.perf_counter() - start
    validate_archive(target)
    with zipfile.ZipFile(target) as bundle:
        if {name: bundle.read(name) for name in bundle.namelist()} != file_map(source):
            raise RuntimeError("bundle content differs from source")
    return elapsed


def footprint(path):
    files = [path] if path.is_file() else [p for p in path.rglob("*") if p.is_file()]
    entries = files if path.is_file() else [path, *path.rglob("*")]
    return {"files": len(files), "logical_bytes": sum(p.stat().st_size for p in files),
            "allocated_bytes": sum(p.stat().st_blocks * 512 for p in entries)}


def worker_command(manifest, root, layout, mode, markers=False):
    cmd = [sys.executable, "-I", "-S", "-B", str(WORKER), "--manifest", str(manifest),
           "--root", str(root), "--layout", layout, "--mode", mode]
    return cmd + (["--markers"] if markers else [])


def consume(cmd):
    start = time.perf_counter()
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=120)
    wall = time.perf_counter() - start
    output = json.loads(result.stdout)
    output["process_wall_seconds"] = wall
    return output


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def summarize(samples):
    metrics = [k for k in samples[0] if k.endswith("_seconds") or k == "peak_rss_bytes"]
    return {key: {"median": statistics.median([s[key] for s in samples]),
                  "p95": percentile([s[key] for s in samples], 0.95),
                  "min": min(s[key] for s in samples), "max": max(s[key] for s in samples)}
            for key in metrics}


def parse_trace(path, begin_marker="GAIA_WORKLOAD_BEGIN", end_marker="GAIA_WORKLOAD_END"):
    calls, errors, read_sizes, read_bytes = Counter(), Counter(), Counter(), 0
    active, begins, ends = False, 0, 0
    for line in path.read_text().splitlines():
        if begin_marker in line:
            begins += 1
            active = True
            continue
        if end_marker in line:
            ends += 1
            active = False
            continue
        if not active:
            continue
        match = re.match(r"^(?:\d+\s+)?(\w+)\(.*\)\s+=\s+(-?\d+)", line)
        if not match:
            raise ValueError(f"unparsed workload trace line: {line}")
        name, value = match.group(1), int(match.group(2))
        calls[name] += 1
        if value < 0:
            errors[name] += 1
        if name in ("read", "pread64") and value > 0:
            read_bytes += value
            read_sizes[value] += 1
    if begins != 1 or ends != 1 or active:
        raise ValueError(f"invalid trace markers: {begins}/{ends}")
    metadata = {"newfstatat", "fstat", "stat", "statx", "lstat", "access", "faccessat",
                "faccessat2", "readlink", "readlinkat", "statfs", "fstatfs"}
    return {"calls": dict(calls), "errors": dict(errors), "read_bytes": read_bytes,
            "read_return_sizes": dict(read_sizes),
            "metadata_calls": sum(n for k, n in calls.items() if k in metadata),
            "open_calls": sum(n for k, n in calls.items() if k in ("open", "openat", "openat2")),
            "read_calls": sum(n for k, n in calls.items() if k in ("read", "pread64")),
            "counted_calls": sum(calls.values())}


def environment(root):
    memory = {}
    if Path("/proc/meminfo").exists():
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, value = line.split(":", 1)
            if key in ("MemTotal", "MemAvailable"):
                memory[key] = value.strip()
    cpu = next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                if line.startswith("model name")), "unknown")
    fs = subprocess.run(["stat", "-f", "-c", "%T", str(root)], capture_output=True,
                        text=True, check=True).stdout.strip()
    return {"python": sys.version, "executable": sys.executable, "platform": platform.platform(),
            "machine": platform.machine(), "cpu_model": cpu, "logical_cpus": os.cpu_count(),
            "reported_memory": memory, "filesystem": fs,
            "disk": dict(zip(("total", "used", "free"), shutil.disk_usage(root))),
            "hardware_scope": "execution environment; not verified as the developer's physical laptop",
            "cache_policy": "warm/reused filesystem cache after preparation/warmup; no cold-cache claim",
            "stdlib_setup": "common worker imports before workload; process-wall timing includes setup",
            "source_policy": "source-only, -I -S -B; no pre-existing/generated fixture pyc",
            "bytecode_policy": "separate pyc-only equivalent layout; compilation cost reported separately",
            "rss_scope": "Linux /proc/self/status VmHWM including setup/validation, not incremental bundle memory"}


def render_report(data):
    lines = ["# Dependency-bundle experiment results", "", f"Run: {data['run_id']}", "",
             "Controlled synthetic pure-Python fixtures; no dependency downloads. Fresh process per trial, "
             "reused/warm filesystem cache. These results describe the recorded execution environment, "
             "not a verified physical developer-laptop baseline.", "",
             f"Interpreter: `{data['environment']['python'].splitlines()[0]}`. "
             f"Trials: {data['trials']} per case after {data['warmups']} warmup(s). "
             "Case order is deterministically shuffled within each repetition. "
             "Shared-reader cases use the same ZIP bytes as stock cases, with a path hook "
             "that retains one resource archive handle; module loading remains standard. "
             "Persistent cases keep one archive/index for BOTH modules and resources, "
             "discover names without loading code and read each module once. "
             "Access cases use a common reader/resource interface with ZipFile, indexed positional reads, "
             "mmap or resident bytes over the same stored container; header/range validation is paid "
             "at index creation for direct readers and CRC remains checked on every read. "
             "Loader integration returns copied bytes in every backend, without changing compilation.", "",
             "## Load timing", "",
             "Medians in milliseconds; parent-observed process wall includes interpreter/setup/validation. "
             "Workload timing covers imports + resource reads + a small application loop. "
             "All modules/resources/origins/output and missing-input behavior are checked. "
             "Peak RSS uses executed-address-space VmHWM; if a separate memory pass is present "
             "it is one additional untraced process per case, not a timing-sample median.", "",
             "| Leaf modules | Inputs | Layout | Import ms | Resource ms | App ms | Workload ms | "
             "Process ms | Process p95 ms | Peak RSS MiB |", "| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for case in data["cases"]:
        s = case["summary"]
        rss = (case["memory_sample"]["peak_rss_bytes"] if case.get("memory_sample")
               else s["peak_rss_bytes"]["median"])
        values = [s[k]["median"] * 1000 for k in ("import_seconds", "resource_seconds",
                  "application_seconds", "workload_seconds", "process_wall_seconds")]
        lines.append(f"| {case['modules']} | {case['mode']} | {case['layout']} | "
                     + " | ".join(f"{v:.2f}" for v in values)
                     + f" | {s['process_wall_seconds']['p95'] * 1000:.2f} | {rss / 2**20:.2f} |")
    lines += ["", "## Preparation and storage", "",
              "Packing and compatibility export are single observed runs, not trial medians. "
              "Pack/export correctness validation is outside their reported timings. Directory allocation includes directory blocks; ZIP allocation "
              "counts its container. Values depend on this filesystem. Bytecode input construction is separate.", "",
              "| Leaf modules | Inputs | Layout | Files | Logical KiB | Allocated KiB | Pack ms | "
              "Export ms | One-shot pack + process ms |", "| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for case in data["cases"]:
        p = case["preparation"]
        f = p["footprint"]
        one_shot = (p["pack_seconds"] + case["summary"]["process_wall_seconds"]["median"]) * 1000
        export = f"{p['export_seconds'] * 1000:.2f}" if p["export_seconds"] is not None else "—"
        lines.append(f"| {case['modules']} | {case['mode']} | {case['layout']} | {f['files']} | "
                     f"{f['logical_bytes'] / 1024:.2f} | {f['allocated_bytes'] / 1024:.2f} | "
                     f"{p['pack_seconds'] * 1000:.2f} | {export} | {one_shot:.2f} |")
    lines += ["", "Source generation and bytecode compilation costs are recorded in `results.json`. "
              "One-shot above starts from already prepared mode-specific directory inputs, not from dependency resolution. "
              "Compatibility use additionally pays the listed export cost. These columns are pack + process, "
              "not complete validation-inclusive preparation or registry-install benchmarks.", "", "## Filesystem activity", "",
              "Separate strace runs count calls only between worker markers, excluding interpreter setup "
              "and correctness validation. Counts cover all activity in that workload, including lazy stdlib "
              "loading; they are not dependency-only path attribution. Read bytes are returned syscall bytes, "
              "not physical disk traffic or unique file content. Traced timings are excluded from timing statistics."]
    traced = [case for case in data["cases"] if case.get("trace")]
    if traced:
        lines += ["", "| Leaf modules | Inputs | Layout | Metadata calls | Opens | Reads | Read KiB | Counted calls |",
                  "| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |"]
        for case in traced:
            t = case["trace"]
            lines.append(f"| {case['modules']} | {case['mode']} | {case['layout']} | {t['metadata_calls']} | "
                         f"{t['open_calls']} | {t['read_calls']} | {t['read_bytes'] / 1024:.2f} | {t['counted_calls']} |")
    else:
        lines += ["", "No syscall observations are attached to this timing run. "
                  "The access-only experiment reports separately scoped index/read-loop counts where collected. "
                  "The generated trace plan can be used to add observations without changing timing samples."]
    lines += ["", "## Interpretation limits", "",
              "- Synthetic import-heavy packages are not evidence of a real ecosystem-wide speedup.",
              "- A fresh interpreter resets module caches, not filesystem caches. Cold storage was not controlled.",
              "- Source-only and precompiled-input results must not be conflated. ZIP cannot generate its own bytecode cache.",
              "- Fewer metadata calls may coexist with more archive reads/seeks or higher CPU/memory.",
              "- Single-run preparation/export costs, compression policy, cache warming and process noise limit precision.",
              "- Shared-resource and persistent-provider hooks are experimental Python code, not a new native loader or bundle format.",
              "- mmap/resident access can avoid per-entry read syscalls but still pays setup, copying/CRC and page-fault costs. This is not a native hardware floor.",
              "- A programmatic compiler integration and a pinned real-package follow-up remain untested.", ""]
    return "\n".join(lines)


def summarize_run(result_path, trace_prefix=None):
    data = json.loads(result_path.read_text())
    if trace_prefix is not None:
        mapping = json.loads(Path(str(trace_prefix) + ".workers.json").read_text())
        if mapping["run_id"] != data["run_id"]:
            raise ValueError("trace map belongs to a different run")
        if len(mapping["workers"]) != len(data["cases"]):
            raise ValueError("trace map does not cover every case")
        if {entry["case_index"] for entry in mapping["workers"]} != set(range(len(data["cases"]))):
            raise ValueError("trace map has duplicate or missing case indexes")
        for entry in mapping["workers"]:
            source = Path(str(trace_prefix) + "." + str(entry["pid"]))
            destination = Path(data["cases"][entry["case_index"]]["trace_path"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
    for case in data["cases"]:
        trace_path = Path(case["trace_path"])
        if trace_path.is_file():
            case["trace"] = parse_trace(trace_path)
    write_json(result_path, data)
    report = result_path.parent / "REPORT.md"
    report.write_text(render_report(data))
    print(report)


def collect_memory(result_path):
    """Supplement the original timings after detecting inherited ru_maxrss."""
    data = json.loads(result_path.read_text())
    for case in data["cases"]:
        sample = consume(case["command"])
        if sample["application_checksum"] != case["samples"][0]["application_checksum"]:
            raise ValueError("memory pass did not reproduce the measured workload")
        case["memory_sample"] = {key: sample[key] for key in
                                 ("peak_rss_bytes", "peak_rss_source", "reported_ru_maxrss_bytes",
                                  "application_checksum", "correct")}
        # Preserve but relabel the original values instead of reporting them as
        # the executed consumer's memory. Original timing observations stay intact.
        legacy_rss = all("peak_rss_source" not in original for original in case["samples"])
        if legacy_rss and "peak_rss_bytes" in case["summary"]:
            case["summary"]["reported_ru_maxrss_bytes"] = case["summary"].pop("peak_rss_bytes")
        for original in case["samples"]:
            if "peak_rss_bytes" in original and "peak_rss_source" not in original:
                original["reported_ru_maxrss_bytes"] = original.pop("peak_rss_bytes")
    data["environment"]["rss_scope"] = (
        "separate fresh-process /proc/self/status VmHWM including setup/validation; "
        "ru_maxrss diagnostics (including legacy samples) preserved under reported_ru_maxrss_bytes, "
        "not used for consumer RSS; valid timed-sample VmHWM is preserved when present")
    data["memory_pass"] = {"method": "one additional untraced verified consumer per case",
                           "collected_at": datetime.now(timezone.utc).isoformat()}
    write_json(result_path, data)
    summarize_run(result_path)


def run(args):
    if sys.platform != "linux":
        raise RuntimeError("first benchmark reports Linux RSS/filesystem semantics only")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    work = HERE / "_work" / run_id
    work.mkdir(parents=True, exist_ok=False)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    traces = output / "traces" / run_id
    traces.mkdir(parents=True, exist_ok=False)
    data = {"schema": 1, "run_id": run_id, "trials": args.trials, "warmups": args.warmups,
            "seed": args.seed, "environment": environment(work), "fixtures": [], "cases": []}
    rng = random.Random(args.seed)
    trace_plan = []
    for count in args.modules:
        fixture = work / str(count)
        fixture.mkdir()
        source = fixture / "source"
        start = time.perf_counter()
        manifest = make_fixture(source, count)
        generated = time.perf_counter() - start
        manifest_path = fixture / "manifest.json"
        write_json(manifest_path, manifest)
        bytecode = fixture / "bytecode"
        compiled = precompile(source, bytecode)
        data["fixtures"].append({"modules": count, "all_modules": len(manifest["all_modules"]),
                                 "resources": len(manifest["resources"]),
                                 "source_generation_seconds": generated, "precompile_seconds": compiled})
        cases = []
        prepared_archives = {}
        for mode, directory in (("source", source), ("bytecode", bytecode)):
            for layout in args.layouts:
                container = ("stored" if layout.startswith("access-") else
                             layout.removeprefix("shared-").removeprefix("persistent-"))
                root = directory if layout == "directory" else fixture / f"{mode}-{container}.zip"
                pack_seconds, export_seconds = 0.0, None
                if layout != "directory" and (mode, container) not in prepared_archives:
                    pack_seconds = pack(directory, root, zipfile.ZIP_STORED if container == "stored"
                                        else zipfile.ZIP_DEFLATED)
                    exported = fixture / f"{mode}-{container}-export"
                    exported.mkdir()
                    start = time.perf_counter()
                    with zipfile.ZipFile(root) as bundle:
                        bundle.extractall(exported)  # Only our generated, prevalidated regular-file fixture.
                    export_seconds = time.perf_counter() - start
                    if file_map(exported) != file_map(directory):
                        raise RuntimeError("compatibility export mismatch")
                    prepared_archives[(mode, container)] = (pack_seconds, export_seconds)
                elif layout != "directory":
                    pack_seconds, export_seconds = prepared_archives[(mode, container)]
                label = f"{count}-{mode}-{layout}"
                trace_path = traces / (label + ".strace")
                cmd = worker_command(manifest_path, root, layout, mode)
                case = {"modules": count, "mode": mode, "layout": layout, "samples": [],
                        "command": cmd, "trace_path": str(trace_path),
                        "preparation": {"pack_seconds": pack_seconds, "export_seconds": export_seconds,
                                        "footprint": footprint(root)}}
                cases.append(case)
                trace_plan.append({"label": label, "trace_path": str(trace_path),
                                   "argv": ["strace", "-qq", "-f", "-s", "256", "-e",
                                            "trace=" + TRACE_SYSCALLS, "-o", str(trace_path),
                                            *worker_command(manifest_path, root, layout, mode, markers=True)]})
        for _ in range(args.warmups):
            order = cases.copy()
            rng.shuffle(order)
            for case in order:
                consume(case["command"])
        for iteration in range(args.trials):
            order = cases.copy()
            rng.shuffle(order)
            for case in order:
                case["samples"].append(consume(case["command"]))
            if (iteration + 1) % 5 == 0 or iteration + 1 == args.trials:
                print(f"{count} modules: {iteration + 1}/{args.trials} repetitions", flush=True)
        for case in cases:
            case["summary"] = summarize(case["samples"])
            if case["mode"] == "source":
                source_root = Path(case["command"][case["command"].index("--root") + 1])
                if source_root.is_dir() and list(source_root.rglob("*.pyc")):
                    raise RuntimeError("source-only run produced fixture bytecode")
        data["cases"].extend(cases)
        # Keep completed results even if a later fixture or trial fails.
        write_json(output / "results.json", data)
    write_json(output / "trace-plan.json", trace_plan)
    summarize_run(output / "results.json")
    print(f"{len(data['cases'])} verified cases; {sum(len(c['samples']) for c in data['cases'])} measured subprocesses")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modules", nargs="+", type=int, default=[64, 512, 2048])
    parser.add_argument("--layouts", nargs="+", choices=LAYOUTS, default=list(LAYOUTS))
    parser.add_argument("--trials", type=int, default=15)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20261028)
    parser.add_argument("--output", type=Path, default=HERE / "_work/runs")
    parser.add_argument("--summarize", type=Path, help="parse available traces and regenerate a saved report")
    parser.add_argument("--trace-prefix", type=Path, help="ingest traces from trace_workers.py under strace -ff")
    parser.add_argument("--memory-pass", type=Path, help="supplement saved timings with executed-process VmHWM")
    args = parser.parse_args()
    if args.memory_pass:
        collect_memory(args.memory_pass.resolve())
    elif args.summarize:
        summarize_run(args.summarize.resolve(), args.trace_prefix)
    else:
        if args.trials < 1 or args.warmups < 0:
            parser.error("trials must be positive; warmups must be nonnegative")
        run(args)


if __name__ == "__main__":
    main()
