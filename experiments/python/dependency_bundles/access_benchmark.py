#!/usr/bin/env python3
"""Byte-access-only comparison: same stored bundle, no module execution."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import resource
import statistics
import sys
import time
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import benchmark
from bundle_access import BACKENDS, BundleReader
from precomputed_index import IndexedBundleReader


def worker(args):
    expected = json.loads(args.expected.read_text())
    if args.markers:
        os.write(2, b"GAIA_INDEX_BEGIN\n")
    before_index = resource.getrusage(resource.RUSAGE_SELF)
    begin = time.perf_counter()
    if args.index is not None:
        reader = IndexedBundleReader(args.archive, args.index, index_sha256=args.index_sha256,
                                     verify=args.index_verification)
    else:
        reader = BundleReader(args.archive, args.backend, prefault=args.prefault)
    indexed = time.perf_counter()
    after_index = resource.getrusage(resource.RUSAGE_SELF)
    if args.markers:
        os.write(2, b"GAIA_INDEX_END\n")
    names = sorted(reader.entries)
    if names != sorted(expected["members"]):
        raise RuntimeError("bundle membership differs")
    if args.order == "shuffled":
        random.Random(20261028).shuffle(names)
    checksum = 0
    times = []
    faults = []
    if args.markers:
        os.write(2, b"GAIA_WORKLOAD_BEGIN\n")
    cpu = time.process_time()
    for _ in range(args.passes):
        before_pass = resource.getrusage(resource.RUSAGE_SELF)
        start = time.perf_counter()
        for name in names:
            if args.representation == "view":
                with reader.view(name) as value:
                    checksum += len(value) + (value[0] + value[-1] if value else 0)
            else:
                value = reader.read(name)
                checksum += len(value) + (value[0] + value[-1] if value else 0)
        times.append(time.perf_counter() - start)
        after_pass = resource.getrusage(resource.RUSAGE_SELF)
        faults.append({"minor": after_pass.ru_minflt - before_pass.ru_minflt,
                       "major": after_pass.ru_majflt - before_pass.ru_majflt})
    cpu = time.process_time() - cpu
    if args.markers:
        os.write(2, b"GAIA_WORKLOAD_END\n")
    if checksum != expected["token_per_pass"] * args.passes:
        raise RuntimeError("access workload differs")
    # Full member equivalence outside the measured access interval, not just CRC.
    for name, digest in expected["members"].items():
        if hashlib.sha256(reader.read(name)).hexdigest() != digest:
            raise RuntimeError(f"content mismatch: {name}")
    reader.close()
    rss = next(int(s.split()[1]) * 1024 for s in Path("/proc/self/status").read_text().splitlines()
               if s.startswith("VmHWM:"))
    print(json.dumps({"index_seconds": indexed - begin, "first_pass_seconds": times[0],
                      "reused_pass_seconds": statistics.mean(times[1:]) if len(times) > 1 else 0,
                      "all_passes_seconds": sum(times), "access_cpu_seconds": cpu,
                      "first_use_seconds": indexed - begin + times[0],
                      "peak_rss_bytes": rss, "pass_times_seconds": times,
                      "index_faults": {"minor": after_index.ru_minflt - before_index.ru_minflt,
                                       "major": after_index.ru_majflt - before_index.ru_majflt},
                      "pass_faults": faults,
                      "entries": len(names), "payload_bytes_per_pass": expected["payload_bytes"],
                      "application_checksum": checksum, "correct": True}))


def render(data, path):
    lines = ["# Generic stored-bundle access experiment", "", f"Run: `{data['run_id']}`.", "",
             "Same immutable ZIP bytes for all cases, no fixture imports/compilation/execution. "
             "Warm/reused filesystem cache; new process per trial. All backends verify payload CRC on every "
             "read/view. Indexed backends validate local headers/names/ranges up front; ZipFile validates "
             "its entry headers during reads. Full SHA-256 member equivalence is checked outside timing.", "",
             f"{data['entries']} entries, {data['payload_bytes']:,} payload bytes, "
             f"{data['trials']} trials per case, {data['passes']} passes per process.", "",
             "`zipfile` is the common-wrapper baseline. `pread` uses indexed positional reads. "
             "`mmap` uses mapped ranges. `resident` reads the whole archive into memory once. "
             "Opening, central parsing, header validation, mapping/whole-file reading are included in index time. "
             "Bytes mode returns copied bytes in every case. View mode can avoid payload copies for mmap/resident; "
             "ZipFile/pread views still wrap allocated bytes. All views are released before close.", "",
             "## Timing", "", "Medians, ms. Reused pass is the per-process mean of passes after the first. "
             "First-use median is computed from each sample's index + first-pass time, not a sum of medians. "
             "Close and extra correctness checks are outside these access intervals.", "",
             "| Backend | Result | Order | Open/index ms | First pass ms | Reused pass ms | First use ms | Peak RSS MiB |",
             "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for c in data["cases"]:
        s = c["summary"]
        lines.append(f"| {c['layout']} | {c['representation']} | {c['order']} | "
                     + " | ".join(f"{s[k]['median']*1000:.3f}" for k in
                                  ("index_seconds", "first_pass_seconds", "reused_pass_seconds", "first_use_seconds"))
                     + f" | {s['peak_rss_bytes']['median']/2**20:.2f} |")
    traced = [c for c in data["cases"] if "trace" in c]
    if traced:
        lines += ["", "## Separate syscall observations", "",
                  "Read-loop counts cover all repeated passes; index work is bracketed separately. "
                  "mmap page faults are not `read` syscalls and may still perform work/I/O. Returned read bytes "
                  "are syscall results, not physical disk traffic. Timing samples exclude tracing.", "",
                  "| Backend | Result | Order | Index calls | Loop reads | Loop seeks | Loop calls |",
                  "| --- | --- | --- | ---: | ---: | ---: | ---: |"]
        for c in traced:
            t = c["trace"]
            lines.append(f"| {c['layout']} | {c['representation']} | {c['order']} | "
                         f"{c['index_trace']['counted_calls']} | {t['read_calls']} | "
                         f"{t['calls'].get('lseek',0)} | {t['counted_calls']} |")
    lines += ["", "## Limits", "",
              "This establishes a relative access-layer baseline under Python with this CRC/copy policy, "
              "not a universal hardware/native-language floor. Directory parsing and request iteration still "
              "use Python/ZipFile. The synthetic corpus is many tiny source files plus a few resources. "
              "Compressed/encrypted/descriptor/ZIP64 members, mutable files during mapping, large-file workloads, "
              "network access, and cold storage are not covered. Views have explicit reader lifetimes. "
              "Whole-file residency and mmap setup are not free. End-to-end language-loader measurements "
              "are reported separately in the access-loader run.", ""]
    path.write_text("\n".join(lines))


def summarize(path, trace_prefix=None):
    data = json.loads(path.read_text())
    if trace_prefix:
        mapping = json.loads(Path(str(trace_prefix) + ".workers.json").read_text())
        if (mapping["run_id"] != data["run_id"] or len(mapping["workers"]) != len(data["cases"])
                or {e["case_index"] for e in mapping["workers"]} != set(range(len(data["cases"])))):
            raise ValueError("trace mapping does not match this run")
        import shutil
        for entry in mapping["workers"]:
            target = Path(data["cases"][entry["case_index"]]["trace_path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(str(trace_prefix) + "." + str(entry["pid"]), target)
    for c in data["cases"]:
        trace = Path(c["trace_path"])
        if trace.exists():
            c["trace"] = benchmark.parse_trace(trace)
            c["index_trace"] = benchmark.parse_trace(trace, "GAIA_INDEX_BEGIN", "GAIA_INDEX_END")
    benchmark.write_json(path, data)
    render(data, path.parent / "REPORT.md")
    print(path.parent / "REPORT.md")


def run(args):
    if args.archive is None:
        source_run = benchmark.HERE / "_work/runs/access-loader/results.json"
        if not source_run.is_file():
            source_run = benchmark.HERE / "_work/runs/persistent/results.json"
        original = json.loads(source_run.read_text())
        case = next(c for c in original["cases"] if c["mode"] == "source" and c["layout"] == "persistent-stored")
        args.archive = Path(case["command"][case["command"].index("--root") + 1])
    args.archive = args.archive.resolve(strict=True)
    benchmark.validate_archive(args.archive)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    work = benchmark.HERE / "_work" / ("access-" + run_id)
    work.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(args.archive) as archive:
        contents = {name: archive.read(name) for name in archive.namelist()}
    expected = {"members": {name: hashlib.sha256(value).hexdigest() for name,value in contents.items()},
                "payload_bytes": sum(map(len,contents.values())),
                "token_per_pass": sum(len(value)+(value[0]+value[-1] if value else 0) for value in contents.values())}
    expected_path = work / "expected.json"
    benchmark.write_json(expected_path, expected)
    args.output.mkdir(parents=True, exist_ok=True)
    traces = args.output.resolve() / "traces" / run_id
    traces.mkdir(parents=True, exist_ok=False)
    data = {"run_id": run_id, "archive": str(args.archive), "archive_sha256": hashlib.sha256(args.archive.read_bytes()).hexdigest(),
            "environment": benchmark.environment(work), "trials": args.trials, "passes": args.passes,
            "entries": len(contents), "payload_bytes": expected["payload_bytes"], "cases": []}
    for backend in BACKENDS:
        for representation in ("bytes", "view"):
            for order in ("lexical", "shuffled"):
                command = [sys.executable,"-I","-S","-B",str(Path(__file__).resolve()),"--worker",
                           "--archive",str(args.archive),"--expected",str(expected_path),"--backend",backend,
                           "--representation",representation,"--order",order,"--passes",str(args.passes)]
                data["cases"].append({"layout":backend,"mode":representation+"-"+order,"modules":len(contents),
                                      "representation":representation,"order":order,"command":command,"samples":[],
                                      "trace_path":str(traces/(backend+"-"+representation+"-"+order+".strace"))})
    rng = random.Random(20261028)
    for c in data["cases"]:
        benchmark.consume(c["command"])
    for iteration in range(args.trials):
        order = data["cases"].copy()
        rng.shuffle(order)
        for c in order:
            c["samples"].append(benchmark.consume(c["command"]))
        if (iteration+1)%5==0:
            print(f"access trials {iteration+1}/{args.trials}",flush=True)
    for c in data["cases"]:
        # pass_times is a diagnostic array, not a scalar metric for summarize().
        scalar = [{k:v for k,v in s.items() if k!="pass_times_seconds"} for s in c["samples"]]
        c["summary"] = benchmark.summarize(scalar)
    path = args.output / "results.json"
    benchmark.write_json(path,data)
    summarize(path)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker",action="store_true")
    parser.add_argument("--archive",type=Path)
    parser.add_argument("--expected",type=Path)
    parser.add_argument("--backend",choices=BACKENDS,default="zipfile")
    parser.add_argument("--prefault",choices=("none","populate","touch"),default="none")
    parser.add_argument("--index",type=Path)
    parser.add_argument("--index-sha256")
    parser.add_argument("--index-verification",choices=("hash","local"),default="hash")
    parser.add_argument("--representation",choices=("bytes","view"),default="bytes")
    parser.add_argument("--order",choices=("lexical","shuffled"),default="lexical")
    parser.add_argument("--passes",type=int,default=4)
    parser.add_argument("--trials",type=int,default=15)
    parser.add_argument("--markers",action="store_true")
    parser.add_argument("--output",type=Path,default=benchmark.HERE/"_work/runs/access")
    parser.add_argument("--summarize",type=Path)
    parser.add_argument("--trace-prefix",type=Path)
    args=parser.parse_args()
    if args.passes<1 or args.trials<1:parser.error("passes/trials must be positive")
    if args.worker:worker(args)
    elif args.summarize:summarize(args.summarize,args.trace_prefix)
    else:run(args)


if __name__=="__main__":
    main()
