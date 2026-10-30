#!/usr/bin/env python3
"""Build/test a Linux Odin accessor and compare identical admitted inputs."""

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
import time
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import benchmark
import binary_index
from precomputed_index import build_index


def compile_native(output, odin):
    obj = output.with_suffix(".o")
    commands = [[odin, "build", str(benchmark.HERE / "native"), "-o:speed", "-build-mode:obj", "-out:" + str(obj)],
                [shutil.which("cc") or "cc", str(obj), "-o", str(output), "-Wl,-z,now", "-Wl,-z,relro",
                 "-lz", "-lcrypto", "-lm", "-pie"]]
    start = time.perf_counter()
    for command in commands:
        subprocess.run(command, check=True, capture_output=True, text=True)
    return {"commands": commands, "seconds": time.perf_counter() - start,
            "odin_version": subprocess.check_output([odin, "version"], text=True).strip(),
            "link_driver": subprocess.check_output([commands[1][0], "--version"], text=True).splitlines()[0],
            "binary_sha256": hashlib.sha256(output.read_bytes()).hexdigest()}


def compile_extension(directory, odin):
    directory.mkdir(parents=True, exist_ok=True)
    obj = directory / "native-extension.o"
    output = directory / ("_gaia_native" + sysconfig.get_config_var("EXT_SUFFIX"))
    commands = [[odin, "build", str(benchmark.HERE / "native"), "-o:speed", "-build-mode:obj",
                 "-no-entry-point", "-reloc-mode:pic", "-out:" + str(obj)],
                [shutil.which("cc") or "cc", "-shared", "-fPIC", "-O2", "-I" + sysconfig.get_path("include"),
                 str(benchmark.HERE / "native/python_shim.c"), str(obj), "-o", str(output),
                 "-Wl,-z,now", "-Wl,-z,relro", "-lz", "-lcrypto", "-lm"]]
    start = time.perf_counter()
    for command in commands:
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
    return output, {"commands": commands, "seconds": time.perf_counter()-start,
                    "odin_version": subprocess.check_output([odin, "version"], text=True).strip(),
                    "extension_sha256": hashlib.sha256(output.read_bytes()).hexdigest()}


def consume(case):
    sample = benchmark.consume(case["command"])
    if not sample["correct"] or sample["entries"] != case["entries"]:
        raise ValueError("entry count/correctness differs")
    if sample["application_checksum"] != case["token_per_pass"] * 4:
        raise ValueError("payload checksum differs")
    if case["implementation"] == "odin":
        if sample["validation_digest"] != case["validation_digest"]:
            raise ValueError("full member SHA-256 aggregate differs")
        if sample["payload_bytes"] != case["payload_bytes"]:
            raise ValueError("payload length differs")
    return sample


def render(data, path):
    lines = ["# Odin binary-index access experiment", "", f"Run: `{data['run_id']}`.", "",
             "Linux, warm/reused filesystem cache, fresh process per observation. All cases in a corpus "
             "consume identical payloads from the same ZIP or an exact materialization. No module compilation, "
             "imports or application initialization is performed. This is a native data-access experiment, "
             "not an Odin integration into CPython or a new end-to-end language-loader result.", "",
             "## Methods", "",
             "- Odin is built with `-o:speed`, bounds checks retained, as an object file, then linked with "
             "the installed C driver and system zlib/OpenSSL. The local Odin executable expects absent Clang "
             "for automatic linking; no compiler/dependency download was needed. Build commands/version/hash "
             "are recorded in results.json. Executable bootstrap primes SHA/CRC once, outside access setup; "
             "process wall includes bootstrap, library/runtime startup, validation, cleanup and output.",
             "- `index`: mmap the pinned binary sidecar and bundle; validate header/tables/UTF-8/ranges; "
             "retain offsets into the table/string pool. No per-entry Entry objects are built. The basename "
             "position array and directory views are built at setup because names are variable length.",
             "- `named`: construct full names and a native name-to-entry map during setup, then look up "
             "each name in the timed loop. This is the closest comparison to Python's named-read API. "
             "`ordinal`: request entries by stable row number, bypassing name-map construction/lookup. "
             "It is a different access API and must not be credited solely to the implementation language.",
             "- `zip`: additionally rebuild entry ranges from central/local ZIP headers and compare every "
             "name/range/size/CRC to the certified manifest. This is a controlled stored-ZIP parser: ordered "
             "central entries, no ZIP64/multipart/encryption/descriptors/compression or non-ASCII CP437. "
             "It uses the pinned sidecar as a certified request manifest, so it is not an independent "
             "general ZIP-reader baseline and its startup includes that manifest loading too.",
             "- `directory`: known-file requests from that same pinned manifest; build full C paths during "
             "setup. Each read opens, fstats, reads the exact bytes and closes the file. No directory walk "
             "or dependency discovery is charged. CRC is checked against the manifest. There is no "
             "whole-directory hash/stat admission at setup; this baseline favors known inputs.",
             "- `bytes`: allocate/copy/release a payload buffer per request in both native file and bundle "
             "readers. `view`: use mapped payload slices, with no per-read payload allocation. Python bytes "
             "likewise copy and views avoid copying, but Python still uses its existing Entry/dictionary reader.",
             "- Every payload read verifies CRC using system zlib in both implementations. Sidecar SHA-256 "
             "is pinned by the parent and checked at every setup. `hash` verifies bundle SHA-256 per open; "
             "`local` compares dev/inode/size/mtime/ctime from producer admission in a trusted immutable "
             "local store. All archive setups compare fstat identity again after loading. Stat checks are "
             "cache invalidation, not authentication. Mutation/truncation during mapped access is unsupported.",
             "- Full member SHA-256 checks happen after timed scans. Odin reports SHA-256 of concatenated "
             "per-member SHA-256 digests in physical/lexical fixture order; the parent independently checks "
             "it against Python's expected payloads. Python checks each member against expected SHA-256.", "",
             f"{data['trials']} randomized trials per case, four lexical scans per process, plus one warmup. "
             "Medians in ms. First-use median is taken from each setup + first-pass sample, not a sum "
             "of independent medians. Reused scan is each process's mean of scans 2–4, then median.", "",
             "| Corpus | Implementation | Reader | Binding | Result | Lookup | Setup ms | First scan ms | Reused scan ms | First use ms | First use p95 ms | Process wall ms |",
             "| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for case in data["cases"]:
        summary = case["summary"]
        lines.append(f"| {case['corpus']} | {case['implementation']} | {case['reader']} | {case['policy']} | "
                     f"{case['representation']} | {case['lookup']} | "
                     + " | ".join(f"{summary[k]['median']*1000:.3f}" for k in
                                  ("index_seconds", "first_pass_seconds", "reused_pass_seconds", "first_use_seconds"))
                     + f" | {summary['first_use_seconds']['p95']*1000:.3f} | {summary['process_wall_seconds']['median']*1000:.3f} |")
    lines += ["", "## Inputs and limits", ""]
    for corpus in data["corpora"]:
        lines.append(f"- {corpus['name']}: {corpus['entries']:,} entries, {corpus['payload_bytes']:,} payload bytes; "
                     f"ZIP SHA-256 `{corpus['archive_sha256']}`, index SHA-256 `{corpus['index_sha256']}`.")
    lines += ["", "The existing binary encoding is unchanged. Producer validation/index creation occurs before "
              "consumer timing and is recorded separately; materialization cost is recorded too. Known-path "
              "directory reading is compared with mapped views and copied bytes separately. This experiment "
              "does not test real dependency startup, random/sparse requests, memory pressure, cold storage, "
              "remote exchange or an Odin-only crypto/CRC implementation. Native RSS and syscall counts are "
              "not measured. Odin named lookups remain eager; ordinal scans do not establish a generic "
              "path-lookup floor. Neither microbenchmark speed ratios nor native process-wall timings can "
              "be substituted for the previous CPython module-loading measurements.", ""]
    path.write_text("\n".join(lines))


def run(args):
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    work = benchmark.HERE / "_work" / ("native-" + run_id)
    work.mkdir(parents=True)
    executable = work / "native-reader"
    data = {"run_id": run_id, "trials": args.trials, "environment": benchmark.environment(work),
            "build": compile_native(executable, args.odin), "corpora": [], "cases": []}
    source = json.loads(args.inputs.read_text())
    for original in source["corpora"]:
        archive = Path(original["archive"])
        index = work / (archive.stem + ".index")
        built = build_index(archive, index, encoding="binary")
        doc = binary_index.decode(index.read_bytes())
        rows = list(doc["entries"])
        directory = work / (archive.stem + "-files")
        start = time.perf_counter()
        with zipfile.ZipFile(archive) as bundle:
            payloads = [(name, bundle.read(name)) for name, _, _, _ in rows]
        for name, payload in payloads:
            target = directory / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
        materialize_seconds = time.perf_counter() - start
        expected = {"members": {n: hashlib.sha256(v).hexdigest() for n, v in payloads},
                    "payload_bytes": sum(len(v) for _, v in payloads),
                    "token_per_pass": sum(len(v)+(v[0]+v[-1] if v else 0) for _, v in payloads)}
        validation = hashlib.sha256(b"".join(hashlib.sha256(v).digest() for _, v in payloads)).hexdigest()
        expected_path = work / (archive.stem + ".expected.json")
        benchmark.write_json(expected_path, expected)
        corpus = {"name": original["name"], "archive": str(archive), "index": str(index),
                  "directory": str(directory), "entries": len(rows), "payload_bytes": expected["payload_bytes"],
                  "materialize_seconds": materialize_seconds, **built}
        data["corpora"].append(corpus)
        common = {"corpus": original["name"], "entries": len(rows), "payload_bytes": expected["payload_bytes"],
                  "token_per_pass": expected["token_per_pass"], "validation_digest": validation}
        del payloads
        variants = [("index", p, r, l) for p in ("hash", "local") for r in ("bytes", "view")
                    for l in ("named", "ordinal")]
        variants += [("zip", p, r, "named") for p in ("hash", "local") for r in ("bytes", "view")]
        variants += [("directory", "manifest", "bytes", "named")]
        for reader, policy, representation, lookup in variants:
            command = [str(executable), str(index), built["index_sha256"], str(archive), str(directory),
                       reader, "local" if policy == "manifest" else policy, representation, lookup]
            data["cases"].append({**common, "implementation": "odin", "reader": reader, "policy": policy,
                                  "representation": representation, "lookup": lookup, "command": command, "samples": []})
        for policy in ("hash", "local"):
            for representation in ("bytes", "view"):
                command = [sys.executable, "-I", "-S", "-B", str(benchmark.HERE / "access_benchmark.py"),
                           "--worker", "--archive", str(archive), "--expected", str(expected_path),
                           "--backend", "mmap", "--index", str(index), "--index-sha256", built["index_sha256"],
                           "--index-verification", policy, "--representation", representation, "--passes", "4"]
                data["cases"].append({**common, "implementation": "python", "reader": "index", "policy": policy,
                                      "representation": representation, "lookup": "named", "command": command, "samples": []})
    if args.test_only:
        args.output.mkdir(parents=True, exist_ok=True)
        benchmark.write_json(args.output / "inputs.json", data)
        print(executable)
        return
    for case in data["cases"]:
        consume(case)
    rng = random.Random(20261028)
    for trial in range(args.trials):
        cases = data["cases"].copy()
        rng.shuffle(cases)
        for case in cases:
            case["samples"].append(consume(case))
        if (trial+1) % 5 == 0:
            print(f"native trials {trial+1}/{args.trials}", flush=True)
    for case in data["cases"]:
        case["summary"] = benchmark.summarize(
            [{k: v for k, v in s.items() if k != "pass_times_seconds"} for s in case["samples"]])
    args.output.mkdir(parents=True, exist_ok=True)
    benchmark.write_json(args.output / "results.json", data)
    render(data, args.output / "REPORT.md")
    print(args.output / "REPORT.md")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--odin", default=shutil.which(os.environ.get("ODIN", "odin")) or os.environ.get("ODIN", "odin"))
    parser.add_argument("--inputs", type=Path, default=benchmark.HERE / "_work/runs/binary-index/results.json")
    parser.add_argument("--trials", type=int, default=15)
    parser.add_argument("--test-only", action="store_true")
    parser.add_argument("--output", type=Path, default=benchmark.HERE / "_work/runs/native")
    args = parser.parse_args()
    if args.trials < 1:
        parser.error("trials must be positive")
    run(args)
