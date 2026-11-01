"""Derive pass attribution and paired policy comparisons from frozen observations."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def main(directory):
    raw = json.loads((directory / "results.json").read_text())
    profiles = []
    for item in raw["profiles"]:
        path = directory / Path(item["trace"]).name
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["trace_sha256"]:
            raise ValueError("profile identity differs")
        times, counts = Counter(), Counter()
        for event in json.loads(path.read_text())["traceEvents"]:
            if event["name"] == "RunPass":
                name = event.get("args", {}).get("detail", "unknown")
                times[name] += event["dur"]
                counts[name] += 1
        profiles.append({"edit": item["edit"], "policy": item["policy"],
                         "legacy_pass_events_inclusive": [{"name": name, "ms": us / 1000, "count": counts[name]}
                                                          for name, us in times.most_common(12)]})
    pairs = []
    for edit in raw["edits"]:
        rows = [r for r in raw["observations"] if r["edit"] == edit]
        for candidate in raw["policies"]:
            for control in raw["policies"]:
                if candidate == control:
                    continue
                controls = {r["block"]: r for r in rows if r["policy"] == control}
                candidates = [r for r in rows if r["policy"] == candidate]
                pairs.append({"edit": edit, "candidate": candidate, "control": control, "pairs": len(candidates),
                              "wins": {key: sum(r[key] < controls[r["block"]][key] for r in candidates)
                                       for key in ("compile_ns", "cycle_ns", "long_demand_sum_ns")}})
    result = {"raw_sha256": hashlib.sha256((directory / "results.json").read_bytes()).hexdigest(),
              "analysis_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "profiles": profiles, "paired_comparisons": pairs,
              "scope": "Pass events are inclusive diagnostics; sum neither wrappers and children nor different runs. No crossover extrapolation is made."}
    (directory / "attribution.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    main(parser.parse_args().directory)
