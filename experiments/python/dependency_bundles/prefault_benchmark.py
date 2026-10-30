#!/usr/bin/env python3
"""Warm-cache mmap prefault comparison, including setup cost and fault counts."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import statistics
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import benchmark


def render(data, path):
    lines = ["# mmap prefault experiment", "", f"Run: `{data['run_id']}`.", "",
             "Warm/reused filesystem cache, fresh process/mapping per trial. Identical immutable ZIP bytes "
             "within each corpus. All modes parse and validate the same index and verify CRC on every scan; "
             "full SHA-256 equivalence is checked after timing. Population is charged to open/index time. "
             "`populate` requests Linux MAP_POPULATE at mapping creation; `touch` reads one byte per page "
             "immediately after mapping. `none` faults on demand. Population is not a residency guarantee.", "",
             f"{data['trials']} randomized trials per case; four scans per process, lexical order. "
             "Views avoid payload copies; bytes mode returns copied bytes. First use is each sample's "
             "index + first scan, then median. Fault counts are process-wide getrusage deltas, including "
             "Python allocations; they are not a count of archive pages. Fault counters bracket, but "
             "are outside, each timed interval.", "",
             "| Corpus | Result | Prefault | Index ms | First scan ms | Reused scan ms | First use ms | Index minor faults | First scan minor faults | Major faults, index + scans |",
             "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for case in data["cases"]:
        samples = case["samples"]
        med = lambda key: statistics.median(s[key] for s in samples)
        index_faults = statistics.median(s["index_faults"]["minor"] for s in samples)
        scan_faults = statistics.median(s["pass_faults"][0]["minor"] for s in samples)
        major = sum(s["index_faults"]["major"] + sum(p["major"] for p in s["pass_faults"]) for s in samples)
        lines.append(f"| {case['corpus']} | {case['representation']} | {case['prefault']} | "
                     + " | ".join(f"{med(k)*1000:.3f}" for k in
                                  ("index_seconds", "first_pass_seconds", "reused_pass_seconds", "first_use_seconds"))
                     + f" | {index_faults:g} | {scan_faults:g} | {major} |")
    lines += ["", "## Corpora", ""]
    for corpus in data["corpora"]:
        lines.append(f"- {corpus['name']}: {corpus['entries']:,} entries, {corpus['payload_bytes']:,} payload bytes, "
                     f"{corpus['archive_bytes']:,} archive bytes; SHA-256 `{corpus['archive_sha256']}`.")
    lines += ["", "## Limits", "",
              "No cache dropping or cold-storage measurement. A warm page cache still requires page-table "
              "population for a fresh mapping. Minor faults may map multiple pages (fault-around), so explicit "
              "touching need not produce a fault per page. Header validation itself touches mapping pages. "
              "This synthetic full-scan experiment does not test sparse consumption, working sets exceeding RAM, "
              "concurrent consumers, sustained memory pressure, or native-language implementations. Eager whole-file "
              "population can load unused data in those cases. Setup is synchronous; no work overlaps useful execution. "
              "No language/compiler changes or end-to-end loader improvement are inferred from this access-only run.", ""]
    path.write_text("\n".join(lines))


def run(args):
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    work = benchmark.HERE / "_work" / ("prefault-" + run_id)
    work.mkdir(parents=True)
    if args.archive is None:
        previous = json.loads((benchmark.HERE / "_work/runs/access/results.json").read_text())
        args.archive = Path(previous["archive"])
    large = work / "large.zip"
    # Deterministic, non-sparse stored entries: header reads leave most payload untouched.
    payload = bytes(range(256)) * 4096
    with zipfile.ZipFile(large, "w", compression=zipfile.ZIP_STORED) as archive:
        for i in range(64):
            info = zipfile.ZipInfo(f"pkg/data{i:03}.bin", date_time=(2020, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            archive.writestr(info, payload)
    data = {"run_id": run_id, "trials": args.trials, "environment": benchmark.environment(work),
            "corpora": [], "cases": []}
    for corpus, archive_path in (("tiny entries", args.archive.resolve(strict=True)), ("1 MiB entries", large)):
        with zipfile.ZipFile(archive_path) as archive:
            values = {name: archive.read(name) for name in archive.namelist()}
        expected = {"members": {n: hashlib.sha256(v).hexdigest() for n, v in values.items()},
                    "payload_bytes": sum(map(len, values.values())),
                    "token_per_pass": sum(len(v) + (v[0] + v[-1] if v else 0) for v in values.values())}
        expected_path = work / ("expected-" + str(len(data["corpora"])) + ".json")
        benchmark.write_json(expected_path, expected)
        data["corpora"].append({"name": corpus, "archive": str(archive_path), "entries": len(values),
                                "payload_bytes": expected["payload_bytes"],
                                "archive_bytes": archive_path.stat().st_size,
                                "archive_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest()})
        del values
        for representation in ("bytes", "view"):
            for policy in ("none", "populate", "touch"):
                command = [sys.executable, "-I", "-S", "-B", str(benchmark.HERE / "access_benchmark.py"),
                           "--worker", "--archive", str(archive_path), "--expected", str(expected_path),
                           "--backend", "mmap", "--prefault", policy, "--representation", representation,
                           "--passes", "4"]
                data["cases"].append({"corpus": corpus, "representation": representation,
                                      "prefault": policy, "command": command, "samples": []})
    for case in data["cases"]:
        benchmark.consume(case["command"])
    rng = random.Random(20261028)
    for trial in range(args.trials):
        cases = data["cases"].copy()
        rng.shuffle(cases)
        for case in cases:
            case["samples"].append(benchmark.consume(case["command"]))
        if (trial + 1) % 5 == 0:
            print(f"prefault trials {trial+1}/{args.trials}", flush=True)
    args.output.mkdir(parents=True, exist_ok=True)
    benchmark.write_json(args.output / "results.json", data)
    render(data, args.output / "REPORT.md")
    print(args.output / "REPORT.md")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--trials", type=int, default=15)
    parser.add_argument("--output", type=Path, default=benchmark.HERE / "_work/runs/prefault")
    args = parser.parse_args()
    if args.trials < 1:
        parser.error("trials must be positive")
    run(args)
