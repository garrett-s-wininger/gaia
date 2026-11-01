#!/usr/bin/env python3
"""Apply the small parser-boundary patch and build a private native module."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time

ARCHIVE_SHA256 = "5161e03c6f518fe4da43b06c97ff49a1e224ecb0e4b9fd6ef48235373d1b7b33"
HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--work", type=Path, required=True)
    p.add_argument("--cargo", type=Path, required=True)
    p.add_argument("--rustc", type=Path, required=True)
    p.add_argument("--offline", action="store_true")
    a = p.parse_args()
    for key in ("archive", "work", "cargo", "rustc"):
        # Keep rustup shim names: resolve() would turn cargo/rustc into rustup.
        setattr(a, key, Path(os.path.abspath(getattr(a, key))))
    if a.work.exists() or sha(a.archive) != ARCHIVE_SHA256:
        p.error("need fresh work directory and the pinned Grimp 3.17 source archive")
    a.work.mkdir(parents=True)
    with tarfile.open(a.archive) as archive:
        archive.extractall(a.work, filter="data")
    source = a.work / "grimp-3.17"
    subprocess.run(["patch", "-p1", "-i", str(HERE / "native.patch")], cwd=source, check=True)
    env = {**os.environ, "PYO3_PYTHON": sys.executable, "RUSTC": str(a.rustc)}
    cmd = [str(a.cargo), "build", "--manifest-path", str(source / "rust/Cargo.toml"), "--locked", "--release", "-j", "4"]
    if a.offline:
        cmd.append("--offline")
    start = time.perf_counter_ns()
    subprocess.run(cmd, env=env, check=True)
    elapsed = time.perf_counter_ns() - start
    binary = source / "rust/target/release/lib_rustgrimp.so"
    record = {"archive_sha256": sha(a.archive), "patch_sha256": sha(HERE / "native.patch"),
              "cargo_lock_sha256": sha(source / "rust/Cargo.lock"),
              "patched_scanner_sha256": sha(source / "rust/src/import_scanning.rs"),
              "native_sha256": sha(binary), "native_path": str(binary), "build_ns": elapsed,
              "command": cmd, "python": sys.version,
              "rustc": subprocess.check_output([str(a.rustc), "--version", "--verbose"], env=env, text=True),
              "cargo": subprocess.check_output([str(a.cargo), "--version"], env=env, text=True)}
    (a.work / "build.json").write_text(json.dumps(record, indent=2, sort_keys=True)+"\n")
    print(binary)


if __name__ == "__main__":
    main()
