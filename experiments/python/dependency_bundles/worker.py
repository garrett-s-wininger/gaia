#!/usr/bin/env python3
"""Fresh-process consumer. Run with -I -S -B; stdout is one JSON result."""

import time

_worker_entered = time.perf_counter()

import argparse
import hashlib
import importlib
import importlib.machinery
import importlib.resources
import importlib.util
import json
import os
from pathlib import Path
import resource
import sys
import zipfile  # Equal stdlib preparation for all layouts, outside workload timing.
import zipimport
import zlib

# Prepare the adapter equally in all cases; opening/indexing its archive remains
# lazy and occurs inside the measured resource phase, not during this setup.
_adapter_spec = importlib.util.spec_from_file_location(
    "gaia_shared_zip_resources", Path(__file__).with_name("shared_zip_resources.py"))
_adapter = importlib.util.module_from_spec(_adapter_spec)
_adapter_spec.loader.exec_module(_adapter)
_persistent_spec = importlib.util.spec_from_file_location(
    "gaia_persistent_zip_loader", Path(__file__).with_name("persistent_zip_loader.py"))
_persistent = importlib.util.module_from_spec(_persistent_spec)
_persistent_spec.loader.exec_module(_persistent)
_access_spec = importlib.util.spec_from_file_location(
    "gaia_bundle_access", Path(__file__).with_name("bundle_access.py"))
_access = importlib.util.module_from_spec(_access_spec)
_access_spec.loader.exec_module(_access)
# Import the new adapter equally for every layout from the harness directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import precomputed_index as _index
import native_loader as _native
sys.path.pop(0)
_module_ready = time.perf_counter()


def main():
    if sys.argv[1:] == ["--setup-only"]:
        print(json.dumps({"module_setup_seconds": _module_ready - _worker_entered}))
        return
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--layout", choices=("directory", "stored", "deflated",
                                            "shared-stored", "shared-deflated",
                                            "persistent-stored", "persistent-deflated",
                                            "access-zipfile", "access-pread", "access-mmap",
                                            "access-resident"), required=True)
    parser.add_argument("--mode", choices=("source", "bytecode"), required=True)
    parser.add_argument("--markers", action="store_true")
    parser.add_argument("--profile-import", type=Path, help="separate instrumented import-only diagnostic")
    parser.add_argument("--index", type=Path)
    parser.add_argument("--index-sha256")
    parser.add_argument("--index-verification", choices=("hash", "local"), default="hash")
    parser.add_argument("--native-library", type=Path)
    args = parser.parse_args()
    if not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError("worker requires isolated Python with -I -S -B")
    manifest = json.loads(args.manifest.read_text())
    root = str(args.root.resolve(strict=True))
    sys.path.insert(0, root)
    provider = None
    if args.layout.startswith("shared-"):
        provider = _adapter.SharedZipProvider(root)
        sys.path_hooks.insert(0, provider.path_hook)
    elif args.layout.startswith("persistent-"):
        provider = _persistent.PersistentZipProvider(root)
        sys.meta_path.insert(0, provider)
    elif args.layout.startswith("access-"):
        backend = args.layout.removeprefix("access-")
        factory = (lambda path: _index.IndexedBundleReader(
            path, args.index, index_sha256=args.index_sha256, verify=args.index_verification)
                   ) if args.index is not None else (lambda path: _access.BundleReader(path, backend))
        if args.native_library:
            factory = lambda path: _native.NativeBundleReader(
                path, args.index, index_sha256=args.index_sha256, verify=args.index_verification,
                library=args.native_library)
        provider = _persistent.PersistentZipProvider(
            root, archive_factory=factory,
            resource_factory=_access.BundleResources)
        sys.meta_path.insert(0, provider)
    prefix = manifest["prefix"]
    if any(name.startswith(prefix) for name in sys.modules):
        raise RuntimeError("fixture was imported before measurement")
    profiler = None
    if args.profile_import:
        import cProfile
        profiler = cProfile.Profile()
    if args.markers:
        os.write(2, b"GAIA_WORKLOAD_BEGIN\n")
    cpu_start = time.process_time()
    start = time.perf_counter()
    if profiler is not None:
        profiler.enable()
    try:
        modules = [importlib.import_module(name) for name in manifest["modules"]]
    finally:
        if profiler is not None:
            profiler.disable()
    imported = time.perf_counter()
    payloads = [
        importlib.resources.files(entry["package"]).joinpath(entry["name"]).read_bytes()
        for entry in manifest["resources"]
    ]
    loaded = time.perf_counter()
    checksum = 0
    for iteration in range(manifest["application_rounds"]):
        for ordinal, module in enumerate(modules):
            checksum = (checksum + module.evaluate(iteration + ordinal)) & ((1 << 64) - 1)
    finished = time.perf_counter()
    cpu_elapsed = time.process_time() - cpu_start
    if args.markers:
        os.write(2, b"GAIA_WORKLOAD_END\n")

    # Correctness/origin checks are outside the timed/traced workload.
    if checksum != manifest["application_checksum"]:
        raise RuntimeError("application output differs")
    for entry, data in zip(manifest["resources"], payloads, strict=True):
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise RuntimeError(f"resource mismatch: {entry}")
    loaded_names = {name for name in sys.modules if name.startswith(prefix)}
    expected_names = set(manifest["all_modules"])
    if loaded_names != expected_names:
        raise RuntimeError(f"unexpected module set: {loaded_names ^ expected_names}")
    for name in sorted(loaded_names):
        spec = sys.modules[name].__spec__
        expected_path = manifest["module_paths"][name]
        if args.mode == "bytecode":
            expected_path = expected_path[:-3] + ".pyc"
        expected_origin = root + os.sep + expected_path.replace("/", os.sep)
        if spec.origin != expected_origin:
            raise RuntimeError(f"wrong origin for {name}: {spec.origin!r}")
        if args.layout == "directory":
            kind = (importlib.machinery.SourceFileLoader if args.mode == "source"
                    else importlib.machinery.SourcelessFileLoader)
        elif args.layout.startswith(("persistent-", "access-")):
            kind = _persistent.ModuleLoader
        elif provider is not None:
            kind = _adapter.SharedImporter
        else:
            kind = zipimport.zipimporter
        if not isinstance(spec.loader, kind):
            raise RuntimeError(f"wrong loader for {name}: {type(spec.loader)}")
    missing = manifest["modules"][0].rsplit(".", 1)[0] + ".gaia_missing_module"
    try:
        importlib.import_module(missing)
    except ModuleNotFoundError as error:
        if error.name != missing:
            raise
    else:
        raise RuntimeError("missing module unexpectedly loaded")
    try:
        importlib.resources.files(manifest["resources"][0]["package"]).joinpath(
            "gaia_missing_resource"
        ).read_bytes()
    except FileNotFoundError:
        pass
    else:
        raise RuntimeError("missing resource unexpectedly loaded")
    validation_finished = time.perf_counter()
    if provider is not None:
        if provider.archive_opens != 1:
            raise RuntimeError("shared reader did not use exactly one archive handle")
        if args.layout.startswith(("persistent-", "access-")) and provider.module_reads != len(expected_names):
            raise RuntimeError("persistent provider did not read each module exactly once")
        provider.close()
    # getrusage's high-water mark can include the parent's pre-exec RSS on
    # Linux. VmHWM belongs to this executed address space instead.
    peak_rss = next(int(line.split()[1]) * 1024
                    for line in Path("/proc/self/status").read_text().splitlines()
                    if line.startswith("VmHWM:"))
    metrics_ready = time.perf_counter()
    if profiler is not None:
        profiler.dump_stats(str(args.profile_import))
    print(json.dumps({
        "module_setup_seconds": _module_ready - _worker_entered,
        "request_setup_seconds": start - _module_ready,
        "import_seconds": imported - start,
        "resource_seconds": loaded - imported,
        "application_seconds": finished - loaded,
        "workload_seconds": finished - start,
        "workload_cpu_seconds": cpu_elapsed,
        "validation_seconds": validation_finished - finished,
        "cleanup_seconds": metrics_ready - validation_finished,
        "child_observed_seconds": metrics_ready - _worker_entered,
        "peak_rss_bytes": peak_rss,
        "peak_rss_source": "/proc/self/status VmHWM",
        "reported_ru_maxrss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        "leaf_modules": len(modules),
        "verified_modules": len(loaded_names),
        "verified_resources": len(payloads),
        "resource_bytes": sum(map(len, payloads)),
        "application_checksum": checksum,
        "verified_origin": root,
        "verified_loader": args.layout,
        "mode": args.mode,
        "native_timings": getattr(provider.archive, "native_timings", None) if provider is not None and args.native_library else None,
        "correct": True,
        "shared_archive_opens": provider.archive_opens if provider is not None else None,
        "persistent_module_reads": provider.module_reads if args.layout.startswith(("persistent-", "access-")) else None,
    }))


if __name__ == "__main__":
    main()
