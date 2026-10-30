#!/usr/bin/env python3
"""Fresh-process, offline real-pip workload through directory/Python/Odin inputs."""
import time
_entered = time.perf_counter()

import argparse
import contextlib
import hashlib
import importlib
import importlib.resources
import io
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bundle_access import BundleReader, BundleResources
from precomputed_index import IndexedBundleReader
from native_loader import NativeBundleReader
from persistent_zip_loader import PersistentZipProvider, ModuleLoader
sys.path.pop(0)
_prepared = time.perf_counter()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--reader", choices=("directory", "mmap", "python", "odin"), required=True)
    parser.add_argument("--index", type=Path)
    parser.add_argument("--pin")
    parser.add_argument("--policy", choices=("hash", "local"), default="hash")
    parser.add_argument("--library", type=Path)
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--profile", type=Path, help="separate instrumented whole-command diagnostic")
    args = parser.parse_args()
    if not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError("requires -I -S -B")
    # Preparing the profiler after registering the provider would let importing
    # cProfile open/index the bundle before the measured/profiled workload.
    profiler = None
    if args.profile:
        import cProfile
        profiler = cProfile.Profile()
    expected = json.loads(args.expected.read_text())
    root = str(args.root.resolve(strict=True))
    if any(n == "pip" or n.startswith("pip.") for n in sys.modules):
        raise RuntimeError("pip preloaded")
    provider = None
    if args.reader != "directory":
        if args.reader == "mmap":
            factory = lambda path: BundleReader(path, "mmap")
        elif args.reader == "python":
            factory = lambda path: IndexedBundleReader(path, args.index, index_sha256=args.pin, verify=args.policy)
        else:
            factory = lambda path: NativeBundleReader(path, args.index, index_sha256=args.pin,
                                                       verify=args.policy, library=args.library)
        provider = PersistentZipProvider(root, archive_factory=factory, resource_factory=BundleResources)
    network_events = []
    executions = {}
    def offline(event, arguments):
        if event in ("socket.connect", "socket.getaddrinfo", "socket.bind"):
            network_events.append(event)
            raise RuntimeError("network operation in offline workload")
        elif event == "exec":
            code = arguments[0]
            filename = code.co_filename
            if filename.startswith(root+os.sep):
                filename = filename[len(root)+1:]
            elif filename.startswith("gaia-fixture:///"):
                filename = filename[len("gaia-fixture:///"):]
            if code.co_name == "<module>" and filename.startswith("pip/"):
                executions[filename] = executions.get(filename, 0)+1
    sys.addaudithook(offline)
    with tempfile.TemporaryDirectory(prefix="gaia-pip-") as temporary:
        report_path = Path(temporary) / "report.json"
        output, errors = io.StringIO(), io.StringIO()
        sys.argv = ["pip", "--isolated", "--disable-pip-version-check", "--no-input", "--no-cache-dir",
                    "install", "--dry-run", "--ignore-installed", "--no-index", "--find-links",
                    str(args.wheelhouse), "--report", str(report_path), "gaia-app==1.0"]
        if provider is not None and provider.archive is not None:
            raise RuntimeError("input provider opened before workload timer")
        begin = time.perf_counter()
        if profiler:
            profiler.enable()
        # Publish inputs only after common tempfile/profiler setup. Otherwise a
        # lazy host import (e.g. weakref.finalize importing atexit) can open them.
        sys.path.insert(0, root)
        if provider is not None:
            sys.meta_path.insert(0, provider)
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            try:
                runpy.run_module("pip", run_name="__main__")
            except SystemExit as error:
                if error.code not in (0, None):
                    raise RuntimeError(output.getvalue()+errors.getvalue()) from error
        finished = time.perf_counter()
        if profiler:
            profiler.disable()
            profiler.dump_stats(args.profile)
        report = json.loads(report_path.read_text())
        selected = sorted((e["metadata"]["name"], e["metadata"]["version"]) for e in report["install"])
        if selected != [tuple(e) for e in expected["selected"]]:
            raise RuntimeError(f"resolution differs: {selected}")
        if "multiple versions of gaia-a" not in output.getvalue():
            raise RuntimeError("expected resolver backtracking was not exercised")
        modules = {n: m for n, m in sys.modules.items() if n == "pip" or n.startswith("pip.")}
        origins = {}
        for name, module in modules.items():
            spec = module.__spec__
            if spec is None or not spec.origin or not spec.origin.startswith(root + os.sep):
                raise RuntimeError(f"pip escaped controlled inputs: {name}")
            if provider is not None and not isinstance(spec.loader, ModuleLoader):
                raise RuntimeError(f"pip bypassed bundle provider: {name}")
            origins[name] = spec.origin[len(root)+1:]
        if modules["pip"].__version__ != expected["pip_version"]:
            raise RuntimeError("pip version differs")
        resource = importlib.resources.files("pip._vendor").joinpath("vendor.txt").read_bytes()
        if hashlib.sha256(resource).hexdigest() != expected["vendor_sha256"]:
            raise RuntimeError("vendor resource differs")
        try:
            importlib.import_module("pip.gaia_missing_module")
        except ModuleNotFoundError as error:
            if error.name != "pip.gaia_missing_module":
                raise
        else:
            raise RuntimeError("missing pip module unexpectedly loaded")
        if network_events:
            raise RuntimeError("network attempted")
        # Resolver output is compared semantically; timings/paths are kept separately.
        report_digest = hashlib.sha256(json.dumps(report, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        native_timings = getattr(provider.archive, "native_timings", None) if provider else None
        archive_opens = provider.archive_opens if provider else None
        reads = provider.module_reads if provider else None
        unique_origins = len(set(origins.values()))
        if not executions:
            raise RuntimeError("no controlled file executions recorded")
        if provider and (archive_opens != 1 or reads != sum(executions.values())):
            raise RuntimeError(f"unexpected archive/code read counts: {archive_opens}, {reads}, {unique_origins}")
        if provider:
            provider.close()
        rss = next(int(line.split()[1])*1024 for line in Path("/proc/self/status").read_text().splitlines()
                   if line.startswith("VmHWM:"))
        print(json.dumps({"correct": True, "setup_seconds": _prepared-_entered,
                          "workload_seconds": finished-begin, "validation_seconds": time.perf_counter()-finished,
                          "pip_modules": unique_origins, "module_aliases": len(modules)-unique_origins,
                          "module_origins": origins, "selected": selected,
                          "executed_files": executions,
                          "report_sha256": report_digest, "network_events": network_events,
                          "archive_opens": archive_opens, "module_reads": reads,
                          "native_timings": native_timings, "peak_rss_bytes": rss,
                          "backtracked": True, "pip_version": modules["pip"].__version__}))


if __name__ == "__main__":
    main()
