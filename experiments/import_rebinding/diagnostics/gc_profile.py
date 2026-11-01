#!/usr/bin/env python3
"""Separate intrusive GC attribution; not part of the timing matrix."""
import argparse
import fcntl
import gc
import importlib.util
import os
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser()
    for name in ("corpus", "native", "work", "result", "lock"):
        p.add_argument("--"+name, type=Path, required=True)
    p.add_argument("--mode", required=True)
    args = p.parse_args()
    os.environ["GAIA_IMPORT_NATIVE"] = str(args.native.resolve())
    sys.path.insert(0, str(HERE))
    import producer
    original = producer.Session

    class ProfiledSession(original):
        def request(self, *a, **kw):
            events = []; started = {}

            def callback(phase, info):
                now = time.perf_counter_ns(); gen = info["generation"]
                if phase == "start":
                    started[gen] = now
                else:
                    events.append({**info, "ns": now - started.pop(gen)})

            gc.callbacks.append(callback)
            try:
                response, stats = super().request(*a, **kw)
            finally:
                gc.callbacks.remove(callback)
            stats["gc_events"] = events
            return response, stats

    producer.Session = ProfiledSession
    spec = importlib.util.spec_from_file_location("rebinding_runner", HERE / "run.py")
    runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
    with args.lock.open("a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        runner.worker(args)


if __name__ == "__main__":
    main()
