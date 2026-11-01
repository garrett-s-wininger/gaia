#!/usr/bin/env python3
import json
from pathlib import Path
from statistics import median
import sys

MODES = ("full_rescan", "scoped_native", "rebind")


def stats(values):
    return {"min": min(values), "median": median(values), "max": max(values), "samples": len(values)}


def main():
    output = Path(sys.argv[1]); raw = json.loads((output / "results.json").read_text())
    rows = {(r["block"], r["mode"], e["event"]): e for r in raw["runs"] for e in r["events"]}
    events = [e["event"] for e in raw["runs"][0]["events"]]
    cats = {e["event"]: e["category"] for e in raw["runs"][0]["events"]}
    blocks = range(raw["blocks"])
    groups = {"all": events, "original_16": events[:16], "after_initial": events[1:],
              "initial": events[:1], "local_membership": [e for e in events if cats[e] == "membership"],
              "wide_membership": [e for e in events if cats[e] == "wide_membership"],
              "fixed_membership_edits": [e for e in events if cats[e] in ("body", "location", "edge")]}
    summary = {"blocks": raw["blocks"], "events_per_trace": len(events), "groups": {}, "events": {},
               "clock": "Sum of request spans, including edits, discovery, parser/reference work, graph mutation, native consumer and full JSON; validation between events excluded."}
    for name, names in groups.items():
        totals = {m: [sum(rows[b,m,e]["stats"]["ns"] for e in names) / 1e6 for b in blocks] for m in MODES}
        summary["groups"][name] = {"elapsed_ms": {m: stats(v) for m,v in totals.items()}, "paired_percent_change": {}}
        for c,b in (("rebind","full_rescan"), ("scoped_native","full_rescan"), ("rebind","scoped_native")):
            summary["groups"][name]["paired_percent_change"][c+"_vs_"+b] = stats([100*(v/w-1) for v,w in zip(totals[c],totals[b])])
        print(name, " / ".join(f"{median(totals[m]):.3f}" for m in MODES),
              "rebind vs scoped", summary["groups"][name]["paired_percent_change"]["rebind_vs_scoped_native"])
    for e in events:
        summary["events"][e] = {"category": cats[e], "modes": {}}
        for m in MODES:
            samples = [rows[b,m,e] for b in blocks]
            summary["events"][e]["modes"][m] = {"elapsed_ms": stats([s["stats"]["ns"]/1e6 for s in samples]),
               "producer_ms": stats([s["stats"]["producer_ns"]/1e6 for s in samples]),
               "consumer_and_output_ms": stats([s["stats"]["consumer_and_output_ns"]/1e6 for s in samples]),
               "producer_counts": {k: stats([s["stats"]["producer_counts"][k] for s in samples]) for k in samples[0]["stats"]["producer_counts"]},
               "state": samples[0]["state"], "edge_delta": samples[0]["stats"]["edge_delta"]}
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True)+"\n")


if __name__ == "__main__":
    main()
