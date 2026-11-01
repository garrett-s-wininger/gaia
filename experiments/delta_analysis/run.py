#!/usr/bin/env python3
"""Validated, randomized source-edit traces. Preparation and oracles are untimed."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import random
import resource
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
MODES = ("cached_library", "retained_native", "delta")
REQUIRED = {"grimp": "3.17", "import-linter": "2.15"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def tree_identity(root, files):
    rows = [{"path": str(p.relative_to(root)), "bytes": p.stat().st_size,
             "sha256": digest(p.read_bytes())} for p in sorted(files)]
    return {"files": len(rows), "bytes": sum(r["bytes"] for r in rows),
            "manifest_sha256": digest(json.dumps(rows, sort_keys=True).encode()), "manifest": rows}


def inputs(corpus):
    distributions = {}
    for name, required in REQUIRED.items():
        dist = importlib.metadata.distribution(name)
        if dist.version != required:
            raise RuntimeError(f"{name} must be {required}, got {dist.version}")
        root = Path(dist.locate_file(""))
        files = [Path(dist.locate_file(p)) for p in dist.files if str(p).endswith((".py", ".so"))]
        distributions[name] = {"version": dist.version, **tree_identity(root, files)}
    return {"corpus": tree_identity(corpus, corpus.rglob("*.py")),
            "implementation": tree_identity(HERE, HERE.glob("*.py")),
            "distributions": distributions,
            "python": {"version": sys.version, "executable": sys.executable,
                       "resolved": str(Path(sys.executable).resolve()),
                       "sha256": digest(Path(sys.executable).read_bytes())}}


def trace(project):
    archive = "django/utils/archive.py"; location = "django/utils/deprecation.py"
    hashable = "django/utils/hashable.py"; probe = "django/utils/gaia_probe.py"; peer = "django/utils/gaia_peer.py"
    originals = {p: (project / p).read_text() for p in (archive, location, hashable)}
    assert not (project / probe).exists() and not (project / peer).exists()
    return [
        ("initial", "initial", {}, None),
        ("unchanged", "unchanged", {}, None),
        ("location_shift", "location", {location: "\n" + originals[location]}, None),
        ("body_only", "body", {hashable: originals[hashable] + "\n# Gaia edit probe: no import change.\n"}, None),
        ("add_dependency", "edge", {hashable: originals[hashable] + "\nfrom django.db import models as _gaia_models\n"}, None),
        ("retarget_dependency", "edge", {hashable: originals[hashable] + "\nfrom django import template as _gaia_models\n"}, None),
        ("remove_dependency", "edge", {hashable: originals[hashable]}, None),
        ("missing_module_reference", "edge", {archive: originals[archive] + "\nfrom django.utils import gaia_probe\n"}, None),
        ("module_appears", "membership", {probe: "from django.db import models\n"}, None),
        ("cycle_with_exit", "membership", {probe: "from django.utils import gaia_peer\nfrom django.db import models\n",
                                             peer: "from django.utils import gaia_probe\n"}, None),
        ("cycle_loses_exit", "edge", {probe: "from django.utils import gaia_peer\n"}, None),
        ("cycle_regains_exit", "edge", {peer: "from django.utils import gaia_probe\nfrom django.db import models\n"}, None),
        ("module_disappears", "membership", {peer: None}, None),
        ("restore_branch", "membership", {**originals, probe: None}, None),
        ("rule_target_change", "configuration", {}, "django.template"),
        ("unchanged_after_rule_change", "unchanged", {}, None),
    ]


def worker(args):
    from engine import ROOTS, Session, graph_rows, verify
    import grimp
    project = args.work / "project"; project.mkdir(parents=True)
    prep = time.perf_counter_ns()
    for path in args.corpus.rglob("*.py"):
        dest = project / "django" / path.relative_to(args.corpus)
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path, dest)
    prepared_ns = time.perf_counter_ns() - prep
    sys.path.insert(0, str(project))
    session = Session(project, args.mode)
    observations = []; held = None; held_digest = None
    for label, category, changes, target in trace(project):
        response, stats = session.request(changes, expected=session.generation, target=target)
        # All validation and logical state accounting are outside event clocks.
        checked_at = time.perf_counter_ns()
        oracle = grimp.build_graph("django", cache_dir=None)
        checked = verify(response, oracle, ROOTS)
        if graph_rows(session.graph) != graph_rows(oracle):
            raise AssertionError((label, "producer graph/locations differ"))
        if held is None:
            held, held_digest = response, digest(response.encode())
        if digest(held.encode()) != held_digest:
            raise AssertionError("old published response changed")
        value = json.loads(response)
        if category == "body" and args.mode != "cached_library":
            assert stats["scanned_modules"] == 1 and stats["edge_delta"] == 0
            assert not any(stats["counts"].values()), stats
        if category == "location":
            assert stats["counts"]["diagnostics_refreshed"] > 0
        if category == "configuration" and args.mode != "cached_library":
            assert stats["counts"]["native_reachability"] == 0
        validation_ns = time.perf_counter_ns() - checked_at
        logical_state = {"native_modules": len(session.graph.modules),
                         "native_edges": session.graph.count_imports(),
                         "retained_import_records": sum(map(len, session.producer.records.values())) if session.producer else 0,
                         "navigation_entries": sum(map(len, session.consumer.navigation.values())),
                         "diagnostic_witness_edges": sum(map(len, session.consumer.diagnostics.values()))}
        if args.mode == "delta":
            logical_state.update({"extra_adjacency_entries": sum(map(len, session.consumer.adjacency.out.values())) * 2,
                                  "proof_distances": sum(len(p.distance) for p in session.consumer.proofs.values()),
                                  "proof_parent_entries": sum(len(p.parent) for p in session.consumer.proofs.values())})
        observations.append({"event": label, "category": category, "stats": stats,
                             "validation": checked, "validation_ns": validation_ns,
                             "response_bytes": len(response.encode()), "response_sha256": digest(response.encode()),
                             "generation": value["generation"], "target": value["target"],
                             "state": logical_state,
                             "edit_identities": {p: digest(body.encode()) if body is not None else None for p, body in changes.items()}})
    dump(args.result, {"mode": args.mode, "prepared_ns": prepared_ns, "events": observations,
                       "process_maxrss_kib_including_oracles": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True, help="Directory containing Django's __init__.py")
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--lock", type=Path)
    parser.add_argument("--blocks", type=int, default=7)
    parser.add_argument("--seed", type=int, default=7321)
    parser.add_argument("--mode", choices=MODES)
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()
    args.corpus = args.corpus.resolve(); args.work = args.work.resolve()
    if args.mode:
        worker(args); return
    if not args.output or not args.lock or args.blocks < 1:
        parser.error("--output, --lock, and positive --blocks are required")
    args.output = args.output.resolve()
    if args.output.exists() or args.work.exists():
        parser.error("work/output must be fresh directories")
    args.output.mkdir(parents=True); args.work.mkdir(parents=True)
    frozen = inputs(args.corpus)
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "7321"}
    test = subprocess.run([sys.executable, str(HERE / "test_engine.py")], env=env, text=True, capture_output=True, check=True)
    cache_boundary = subprocess.run([sys.executable, str(HERE / "cache_boundary.py")], env=env, text=True, capture_output=True, check=True)
    dump(args.output / "cache-boundary.json", json.loads(cache_boundary.stdout))
    rng = random.Random(args.seed); runs = []; orders = []
    started = datetime.now(timezone.utc).isoformat()
    args.lock.parent.mkdir(parents=True, exist_ok=True)
    for block in range(args.blocks):
        order = list(MODES); rng.shuffle(order); orders.append(order)
        for mode in order:
            case = args.work / f"b{block}-{mode}"; result = args.work / f"b{block}-{mode}.json"
            cmd = [sys.executable, str(HERE / "run.py"), "--corpus", str(args.corpus), "--work", str(case),
                   "--mode", mode, "--result", str(result)]
            wait_start = time.perf_counter_ns()
            with args.lock.open("a") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                acquired = time.perf_counter_ns()
                subprocess.run(cmd, env=env, check=True)
                elapsed = time.perf_counter_ns() - acquired
            row = json.loads(result.read_text()); row.update({"block": block, "process_ns": elapsed,
                                                             "lock_wait_ns": acquired - wait_start})
            runs.append(row)
            print(f"block {block + 1}/{args.blocks} {mode}: {sum(e['stats']['ns'] for e in row['events']) / 1e6:.2f} ms of event spans", flush=True)
    if inputs(args.corpus) != frozen:
        raise AssertionError("frozen inputs changed")
    raw = {"schema_version": 1, "started_utc": started, "blocks": args.blocks, "seed": args.seed,
           "orders": orders, "runs": runs}
    dump(args.output / "results.json", raw)
    artifact = args.output / "results.json"
    dump(args.output / "raw-identity.json", {"artifacts": [{"file": artifact.name, "bytes": artifact.stat().st_size,
                                                           "sha256": digest(artifact.read_bytes())}]})
    dump(args.output / "provenance.json", {"inputs": frozen, "corpus_path": str(args.corpus),
         "platform": platform.platform(), "machine": platform.machine(), "cpu_count": os.cpu_count(),
         "cpuinfo_sha256": digest(Path("/proc/cpuinfo").read_bytes()),
         "environment_sha256": digest(json.dumps(env, sort_keys=True).encode()),
         "installed_versions": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
         "lock": str(args.lock), "python_hash_seed": env["PYTHONHASHSEED"], "argv": sys.argv,
         "input_identity_scope": "Django .py bytes, local experiment .py files, Grimp/Import Linter .py and .so bytes, interpreter. Not a hermetic SDK identity."})
    dump(args.output / "validation.json", {"passed": True, "traces": len(runs),
         "responses_checked": sum(len(r["events"]) for r in runs), "random_graph_update_batches": 3000,
         "fresh_native_graph_all_edges_locations_and_lazy_flags_equal": True,
         "fresh_real_linter_diagnostic_sets_and_minimum_witness_lengths_equal": True,
         "all_witness_edges_and_locations_current": True, "old_response_bytes_retained": True,
         "stale_generation_rejection_and_syntax_failure_rollback_tested": True,
         "source_and_selected_tool_identities_verified_after": True,
         "tests": test.stdout + test.stderr,
         "limits": "Static imports under pinned Grimp semantics; no full Python execution, type or symbol semantics. Equal-length witness tie-breaking may differ. Single serialized client with declared file edits; no watcher, concurrent publication or general transaction recovery."})


if __name__ == "__main__":
    main()
