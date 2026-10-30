#!/usr/bin/env python3
"""Compare consumer-built ZIP indexes with producer-built, digest-pinned sidecars."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import statistics
import sys
import time
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import benchmark
from precomputed_index import build_index
import binary_index


def diagnose_decoding(path):
    data = json.loads(path.read_text())
    corpus = next(c for c in data["corpora"] if c["name"] == "source")
    encoded = {i["encoding"]: Path(i["index"]).read_bytes() for i in corpus["indexes"]}

    def decode(kind):
        document = json.loads(encoded[kind]) if kind == "json" else binary_index.decode(encoded[kind])
        if kind == "binary":
            document["entries"] = list(document["entries"])
        return document

    logical = decode("binary")
    logical["entries"] = [list(row) for row in logical["entries"]]
    if logical != decode("json"):
        raise ValueError("binary and JSON logical metadata differ")
    samples = {"json": [], "binary": []}
    rng = random.Random(20261028)
    for _ in range(5):
        decode("json")
        decode("binary")
    for _ in range(100):
        order = ["json", "binary"]
        rng.shuffle(order)
        for kind in order:
            start = time.perf_counter()
            document = decode(kind)
            samples[kind].append(time.perf_counter() - start)
            del document
    report = {"run_id": data["run_id"], "trials": 100, "corpus": "source",
              "scope": "Already resident encoded bytes; full logical document decode, with binary rows "
              "fully consumed into an outer list. JSON rows are lists; binary rows are tuples. No file I/O, "
              "hashing, Entry objects or range validation. Production binary reader streams rows instead "
              "of retaining this outer list. Separate diagnostic, not end-to-end timing.",
              "json_scanner_module": type(json.JSONDecoder().scan_once).__module__,
              "samples_seconds": samples,
              "median_seconds": {k: statistics.median(v) for k, v in samples.items()}}
    target = path.parent / "decode-diagnostic.json"
    benchmark.write_json(target, report)
    print(target)


def render(data, path):
    lines = ["# Precomputed ZIP index experiment", "", f"Run: `{data['run_id']}`.", "",
             "Warm/reused filesystem cache, fresh isolated process per trial, randomized case order. "
             "Every reader uses the exact same stored ZIP within a corpus, demand-paged mmap, and CRC "
             "on every payload read/view. Full SHA-256 member equivalence is checked after timing. "
             "Sidecar encodings are experimental version 1; no container/protocol is standardized.", "",
             "## Verification and timing boundaries", "",
             "- `mmap`: reparse ZIP central directory and validate names/local headers/ranges on each open.",
             "- `index-hash`: load/hash the pinned sidecar, verify whole-bundle SHA-256 on each open, "
             "check index structure/ranges, map bundle. ZIP validation occurred when building the index.",
             "- `index-local`: same sidecar loading/validation, but compare the admitted bundle's device, "
             "inode, size, mtime and ctime rather than hash its bytes. Assumes a trusted immutable local "
             "store; stat checks are cache invalidation, not cryptographic verification. Transfer/replacement "
             "requires hash verification or readmission. Concurrent mutation/truncation is unsupported.",
             "- `index-*` uses JSON. Where present, `binary-*` uses a 128-byte little-endian header, "
             "28-byte fixed entry records, directory lengths and a UTF-8 string pool. Directories are stored "
             "once; records reference a directory ID and basename. Reads still decode names and construct "
             "the same Python entry/range dictionaries. Sidecars are read into bytes in both cases, "
             "not directly queried in place. Binary rows are decoded one at a time without JSON's row lists.",
             "- The caller pins the sidecar's SHA-256 outside the index. This experiment's trusted harness "
             "supplies it on the command line. Index integrity is checked on every open; a self-reported "
             "bundle hash alone would not certify an index's name-to-range mapping.",
             "- Producer admission parses/checks ZIP metadata, verifies all payload CRCs, hashes the bundle, "
             "builds names/ranges/directories, and serializes/writes the sidecar. Its cost is reported separately. "
             "Writes are buffered; durability/fsync, transfer and dependency resolution are not timed.",
             "- Consumer open time includes sidecar I/O/hash/decode, entry construction, range checks, "
             "bundle verification and mapping. Producer work is not charged to every consumer; one-use cost "
             "must add it back. Reader close and extra validation are outside access timing.", "",
             "## Producer cost and storage", "",
             f"{data['trials']} index builds per corpus. Index bytes include the range/name/directory table "
             "and identity metadata. ZIP bytes remain unchanged.", "",
             "| Corpus | Encoding | Entries | Payload bytes | ZIP bytes | Index bytes | Added storage | Build median ms |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for corpus in data["corpora"]:
        for index in corpus.get("indexes", [dict(corpus, encoding="json")]):
            lines.append(f"| {corpus['name']} | {index['encoding']} | {corpus['entries']} | {corpus['payload_bytes']:,} | "
                         f"{corpus['archive_bytes']:,} | {index['index_bytes']:,} | "
                         f"{index['index_bytes']/corpus['archive_bytes']:.3%} | "
                         f"{statistics.median(s['build_seconds'] for s in index['build_samples'])*1000:.3f} |")
    lines += ["", "## Byte access", "",
              f"{data['trials']} trials per case; four lexical scans per process. Medians, ms. "
              "First use is index + first scan for each sample, then median; reused is mean of scans 2–4, "
              "then median. Bytes mode copies; view mode avoids payload copying.", "",
              "| Corpus | Result | Reader | Open/index ms | First scan ms | Reused scan ms | First use ms | First use p95 ms | Peak RSS MiB |",
              "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for case in data["cases"]:
        if case["kind"] != "access":
            continue
        summary = case["summary"]
        lines.append(f"| {case['corpus']} | {case['representation']} | {case['reader']} | "
                     + " | ".join(f"{summary[k]['median']*1000:.3f}" for k in
                                  ("index_seconds", "first_pass_seconds", "reused_pass_seconds", "first_use_seconds"))
                     + f" | {summary['first_use_seconds']['p95']*1000:.3f} | "
                     f"{summary['peak_rss_bytes']['median']/2**20:.2f} |")
    lines += ["", "## Fixed language loader", "",
              "Same persistent module loader, compilation/bytecode behavior, resource wrapper and validation "
              "under every reader. Sidecars are loaded lazily inside the import phase. Adapter imports/setup "
              "are equal across cases and included in process wall time. Medians, ms.", "",
              "| Input | Reader | Import ms | Resources ms | Workload ms | Process wall ms | Peak RSS MiB |",
              "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for case in data["cases"]:
        if case["kind"] != "loader":
            continue
        summary = case["summary"]
        lines.append(f"| {case['corpus']} | {case['reader']} | "
                     + " | ".join(f"{summary[k]['median']*1000:.3f}" for k in
                                  ("import_seconds", "resource_seconds", "workload_seconds", "process_wall_seconds"))
                     + f" | {summary['peak_rss_bytes']['median']/2**20:.2f} |")
    lines += ["", "## Limits", "",
              "Synthetic regular source/sourceless-bytecode packages and stored entries only, no real package "
              "startup, cold storage, sparse requests, network transport or memory pressure. The larger corpus "
              "is 64 one-MiB payloads. Full bundle hashing touches every byte; local stat mode does not and "
              "has a different trust boundary. Neither mode permits mutable mapped files. The trusted producer "
              "must use the validated builder: consumer checks do not repeat ZIP/name-to-content certification. "
              "CRC detects accidental corruption and is not authentication. Decoding and Python dictionaries still "
              "allocate per entry; this is not a native or hardware floor. The reader skips ZIP parsing; "
              "missing-module correctness probes can still invoke the standard ZIP fallback outside the "
              "timed workload, and process wall includes those probes. No syscall traces are claimed for this run. "
              "Raw commands, archive/index identities, timings, fault deltas and correctness are in results.json.", ""]
    path.write_text("\n".join(lines))


def run(args):
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    work = benchmark.HERE / "_work" / ("index-" + run_id)
    work.mkdir(parents=True, exist_ok=False)
    source, bytecode = work / "source", work / "bytecode"
    manifest = benchmark.make_fixture(source, args.modules)
    manifest_path = work / "manifest.json"
    benchmark.write_json(manifest_path, manifest)
    benchmark.precompile(source, bytecode)
    archives = []
    for name, directory in (("source", source), ("bytecode", bytecode)):
        archive = work / (name + ".zip")
        benchmark.pack(directory, archive, zipfile.ZIP_STORED)
        archives.append((name, archive))
    large = work / "large.zip"
    with zipfile.ZipFile(large, "w", compression=zipfile.ZIP_STORED) as archive:
        payload = bytes(range(256)) * 4096
        for i in range(64):
            info = zipfile.ZipInfo(f"pkg/data{i:03}.bin", date_time=(2020, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            archive.writestr(info, payload)
    archives.append(("1 MiB entries", large))
    data = {"run_id": run_id, "trials": args.trials, "modules": args.modules, "encodings": args.encodings,
            "environment": benchmark.environment(work), "corpora": [], "cases": []}
    for name, archive_path in archives:
        indexes = []
        # Interleave producer builds too: each encoding performs full admission.
        for encoding in args.encodings:
            indexes.append({"encoding": encoding, "index": str(archive_path.with_suffix(".index." + encoding)),
                            "build_samples": []})
        for _ in range(args.trials):
            for index in indexes:
                index["build_samples"].append(build_index(archive_path, index["index"], encoding=index["encoding"]))
        for index in indexes:
            index.update(index["build_samples"][-1])
        with zipfile.ZipFile(archive_path) as archive:
            values = {n: archive.read(n) for n in archive.namelist()}
        expected = {"members": {n: hashlib.sha256(v).hexdigest() for n, v in values.items()},
                    "payload_bytes": sum(map(len, values.values())),
                    "token_per_pass": sum(len(v) + (v[0] + v[-1] if v else 0) for v in values.values())}
        expected_path = archive_path.with_suffix(".expected.json")
        benchmark.write_json(expected_path, expected)
        data["corpora"].append({"name": name, "archive": str(archive_path),
                                "entries": len(values), "payload_bytes": expected["payload_bytes"],
                                "archive_bytes": archive_path.stat().st_size, "indexes": indexes,
                                **indexes[0]})
        del values
        variants = [("mmap", [])]
        for index in indexes:
            label = "index" if index["encoding"] == "json" else "binary"
            for policy in ("hash", "local"):
                variants.append((label + "-" + policy,
                                 ["--index", index["index"], "--index-sha256", index["index_sha256"],
                                  "--index-verification", policy]))
        for reader, index_args in variants:
            for representation in ("bytes", "view"):
                command = [sys.executable, "-I", "-S", "-B", str(benchmark.HERE / "access_benchmark.py"),
                           "--worker", "--archive", str(archive_path), "--expected", str(expected_path),
                           "--backend", "mmap", "--representation", representation, "--passes", "4", *index_args]
                data["cases"].append({"kind": "access", "corpus": name, "reader": reader,
                                      "representation": representation, "command": command, "samples": []})
            if name in ("source", "bytecode"):
                command = benchmark.worker_command(manifest_path, archive_path, "access-mmap", name) + index_args
                data["cases"].append({"kind": "loader", "corpus": name, "reader": reader,
                                      "command": command, "samples": []})
    for case in data["cases"]:
        benchmark.consume(case["command"])
    rng = random.Random(20261028)
    for trial in range(args.trials):
        cases = data["cases"].copy()
        rng.shuffle(cases)
        for case in cases:
            case["samples"].append(benchmark.consume(case["command"]))
        if (trial + 1) % 5 == 0:
            print(f"index trials {trial+1}/{args.trials}", flush=True)
    for case in data["cases"]:
        case["summary"] = benchmark.summarize(
            [{k: v for k, v in s.items() if k != "pass_times_seconds"} for s in case["samples"]])
    args.output.mkdir(parents=True, exist_ok=True)
    benchmark.write_json(args.output / "results.json", data)
    render(data, args.output / "REPORT.md")
    print(args.output / "REPORT.md")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modules", type=int, default=2048)
    parser.add_argument("--trials", type=int, default=15)
    parser.add_argument("--encodings", nargs="+", choices=("json", "binary"), default=["json"])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--decode-diagnostic", type=Path)
    args = parser.parse_args()
    if args.trials < 1 or args.modules < 16 or args.modules % 16:
        parser.error("trials must be positive; modules must be >=16 and divisible by 16")
    if len(set(args.encodings)) != len(args.encodings):
        parser.error("encodings must be unique")
    if args.output is None:
        args.output = benchmark.HERE / ("_work/runs/binary-index" if "binary" in args.encodings else "_work/runs/index")
    if args.decode_diagnostic:
        diagnose_decoding(args.decode_diagnostic)
    else:
        run(args)
