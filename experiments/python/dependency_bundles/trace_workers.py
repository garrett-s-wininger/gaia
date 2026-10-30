#!/usr/bin/env python3
"""Run the saved consumers under ONE outer `strace -ff` invocation.

Separating timing from tracing avoids mixing instrumentation overhead into the
results. The PID map lets the summarizer attach each child trace to its case.
"""

import argparse
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--trace-prefix", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.results.read_text())
    mapping = {"run_id": data["run_id"], "workers": []}
    for index, case in enumerate(data["cases"]):
        child = subprocess.Popen(case["command"] + ["--markers"], stdout=subprocess.PIPE,
                                 text=True)
        stdout, _ = child.communicate(timeout=120)
        if child.returncode:
            raise subprocess.CalledProcessError(child.returncode, child.args, output=stdout)
        verified = json.loads(stdout)
        if not verified["correct"] or verified["application_checksum"] != case["samples"][0]["application_checksum"]:
            raise RuntimeError("traced consumer did not reproduce the measured workload")
        mapping["workers"].append({"case_index": index, "pid": child.pid})
        print(f"traced {case['modules']} {case['mode']} {case['layout']}", flush=True)
    Path(str(args.trace_prefix) + ".workers.json").write_text(json.dumps(mapping, indent=2) + "\n")


if __name__ == "__main__":
    main()
