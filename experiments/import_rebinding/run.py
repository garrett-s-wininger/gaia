#!/usr/bin/env python3
"""Source-edit responses with full, scoped-native and retained-reference producers."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
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
PRIOR = HERE.parent / "delta_analysis"
spec = importlib.util.spec_from_file_location("prior_runner", PRIOR / "run.py")
prior = importlib.util.module_from_spec(spec); spec.loader.exec_module(prior)
MODES = ("full_rescan", "scoped_native", "rebind")
dump, digest = prior.dump, prior.digest


def identity(args):
    return {"prior_inputs": prior.inputs(args.corpus),
            "implementation": prior.tree_identity(HERE, [*HERE.glob("*.py"), HERE / "native.patch"]),
            "native": {"path": str(args.native), "bytes": args.native.stat().st_size,
                       "sha256": digest(args.native.read_bytes())}}


def trace(project):
    events = prior.trace(project)
    shadow = "django/utils/translation/gettext_lazy.py"
    assert not (project / shadow).exists()
    return events + [
        ("popular_name_shadowed", "wide_membership", {shadow: "from django.db import models\n"}, None),
        ("popular_name_restored", "wide_membership", {shadow: None}, None),
    ]


def worker(args):
    from producer import Session, engine
    import grimp
    project = args.work / "project"; project.mkdir(parents=True)
    prep = time.perf_counter_ns()
    for path in args.corpus.rglob("*.py"):
        dest = project / "django" / path.relative_to(args.corpus)
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path, dest)
    prep = time.perf_counter_ns() - prep
    sys.path.insert(0, str(project)); session = Session(project, args.mode)
    rows = []; held = None
    for label, category, changes, target in trace(project):
        response, stats = session.request(changes, expected=session.generation, target=target)
        start = time.perf_counter_ns()
        fresh = grimp.build_graph("django", cache_dir=None)
        checked = engine.verify(response, fresh, engine.ROOTS)
        assert engine.graph_rows(session.graph) == engine.graph_rows(fresh), label
        if held is None:
            held = response; held_hash = digest(held.encode())
        assert digest(held.encode()) == held_hash
        if category == "body":
            assert not any(stats["counts"].values()), stats
        if category == "configuration":
            assert stats["counts"]["native_reachability"] == 0
        validation_ns = time.perf_counter_ns() - start
        value = json.loads(response)
        rows.append({"event": label, "category": category, "stats": stats, "validation": checked,
                     "validation_ns": validation_ns, "generation": value["generation"], "target": value["target"],
                     "response_sha256": digest(response.encode()), "response_bytes": len(response.encode()),
                     "state": {**session.producer.state(), "native_modules": len(session.graph.modules),
                               "native_edges": session.graph.count_imports(),
                               "resolved_records": sum(map(len, session.producer.records.values()))},
                     "edit_identities": {p: digest(body.encode()) if body is not None else None for p, body in changes.items()}})
    dump(args.result, {"mode": args.mode, "prepared_ns": prep, "events": rows,
                       "maxrss_kib_including_oracles": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--corpus", type=Path, required=True)
    p.add_argument("--native", type=Path, required=True)
    p.add_argument("--work", type=Path, required=True)
    p.add_argument("--output", type=Path)
    p.add_argument("--lock", type=Path)
    p.add_argument("--blocks", type=int, default=7)
    p.add_argument("--seed", type=int, default=4913)
    p.add_argument("--mode", choices=MODES)
    p.add_argument("--result", type=Path)
    args = p.parse_args()
    for key in ("corpus", "native", "work", "output", "lock"):
        value = getattr(args, key)
        if value:
            setattr(args, key, value.resolve())
    os.environ["GAIA_IMPORT_NATIVE"] = str(args.native)
    if args.mode:
        worker(args); return
    if not args.output or not args.lock or args.blocks < 1 or args.output.exists() or args.work.exists():
        p.error("need fresh work/output, lock, positive blocks")
    args.work.mkdir(parents=True); args.output.mkdir(parents=True)
    frozen = identity(args)
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "4913"}
    tests = subprocess.run([sys.executable, str(HERE / "test_rebinding.py")], env=env, capture_output=True, text=True, check=True)
    rng = random.Random(args.seed); runs = []; orders = []
    started = datetime.now(timezone.utc).isoformat()
    args.lock.parent.mkdir(parents=True, exist_ok=True)
    for block in range(args.blocks):
        order = list(MODES); rng.shuffle(order); orders.append(order)
        for mode in order:
            case = args.work / f"b{block}-{mode}"; result = args.work / f"b{block}-{mode}.json"
            cmd = [sys.executable, str(HERE / "run.py"), "--corpus", str(args.corpus), "--native", str(args.native),
                   "--work", str(case), "--mode", mode, "--result", str(result)]
            waiting = time.perf_counter_ns()
            with args.lock.open("a") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX); acquired = time.perf_counter_ns()
                subprocess.run(cmd, env=env, check=True)
                elapsed = time.perf_counter_ns() - acquired
            row = json.loads(result.read_text()); row.update({"block": block, "process_ns": elapsed,
                                                             "lock_wait_ns": acquired - waiting})
            runs.append(row)
            print(f"block {block+1}/{args.blocks} {mode}: {sum(e['stats']['ns'] for e in row['events'])/1e6:.2f} ms event spans", flush=True)
    assert identity(args) == frozen, "frozen inputs changed"
    dump(args.output / "results.json", {"started_utc": started, "seed": args.seed, "blocks": args.blocks,
                                       "orders": orders, "runs": runs})
    path = args.output / "results.json"
    dump(args.output / "raw-identity.json", {"artifacts": [{"file": path.name, "bytes": path.stat().st_size,
                                                           "sha256": digest(path.read_bytes())}]})
    dump(args.output / "provenance.json", {"inputs": frozen, "platform": platform.platform(),
         "cpu_count": os.cpu_count(), "python_hash_seed": env["PYTHONHASHSEED"],
         "environment_sha256": digest(json.dumps(env, sort_keys=True).encode()), "argv": sys.argv,
         "lock": str(args.lock), "scope": "Selected source/library/native binary identities; not a hermetic SDK."})
    dump(args.output / "validation.json", {"passed": True, "responses_checked": sum(len(r["events"]) for r in runs),
         "traces": len(runs), "fresh_unmodified_grimp_graph_edges_and_all_metadata_equal": True,
         "fresh_full_linter_violation_sets_minimum_witness_lengths_current_edges_locations_equal": True,
         "random_source_update_batches": 360, "native_syntax_relative_lazy_namespace_fallback_tests": True,
         "stale_generation_and_syntax_failure_rollback_tested": True, "old_response_immutable": True,
         "selected_inputs_verified_after": True, "tests": tests.stdout + tests.stderr,
         "limits": "Fixed single root package and parser options. Static import graphs and single-explanation editor diagnostics; no Python execution/type fidelity, concurrent requests or full CLI output equivalence."})


if __name__ == "__main__":
    main()
