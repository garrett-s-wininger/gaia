#!/usr/bin/env python3
"""Summarize paired traces, keeping startup and membership costs visible."""
import argparse
import json
from pathlib import Path
from statistics import median

MODES = ("cached_library", "retained_native", "delta")


def describe(values):
    return {"min": min(values), "median": median(values), "max": max(values), "samples": len(values)}


def main():
    p = argparse.ArgumentParser(); p.add_argument("output", type=Path); a = p.parse_args()
    raw = json.loads((a.output / "results.json").read_text())
    runs = {(r["block"], r["mode"]): r for r in raw["runs"]}
    blocks = list(range(raw["blocks"])); events = [e["event"] for e in raw["runs"][0]["events"]]
    categories = {e["event"]: e["category"] for e in raw["runs"][0]["events"]}
    rows = {(b, m, e["event"]): e for (b, m), r in runs.items() for e in r["events"]}
    groups = {"all_event_spans": events,
              "after_initial": [e for e in events if categories[e] != "initial"],
              "fixed_namespace_edits": [e for e in events if categories[e] in ("edge", "location", "body")],
              "membership_changes": [e for e in events if categories[e] == "membership"],
              "initial": ["initial"],
              "configuration": [e for e in events if categories[e] == "configuration"],
              "unchanged": [e for e in events if categories[e] == "unchanged"]}
    summary = {"schema_version": 1, "blocks": len(blocks), "events_per_trace": len(events),
               "response_contract": "Three dependency-navigation sets and real forbidden-rule decisions with one shortest current explanation per violation; not the full CLI multi-chain report.",
               "clock": "Sum of request event spans, including edits, producer, consumer and JSON. Validation between events excluded; process startup, module imports and corpus copying excluded. Not an uninterrupted session clock.",
               "groups": {}, "events": {}, "paired_percent_change": {}}
    for group, names in groups.items():
        summary["groups"][group] = {m: describe([sum(rows[b, m, e]["stats"]["ns"] for e in names) / 1e6 for b in blocks]) for m in MODES}
        comparisons = {}
        for candidate, baseline in (("delta", "retained_native"), ("retained_native", "cached_library"), ("delta", "cached_library")):
            comparisons[f"{candidate}_vs_{baseline}"] = describe([
                100 * (sum(rows[b, candidate, e]["stats"]["ns"] for e in names) /
                       sum(rows[b, baseline, e]["stats"]["ns"] for e in names) - 1) for b in blocks])
        summary["paired_percent_change"][group] = comparisons
    for event in events:
        summary["events"][event] = {"category": categories[event], "modes": {}}
        for mode in MODES:
            samples = [rows[b, mode, event] for b in blocks]
            summary["events"][event]["modes"][mode] = {
                "elapsed_ms": describe([s["stats"]["ns"] / 1e6 for s in samples]),
                "producer_ms": describe([s["stats"]["producer_ns"] / 1e6 for s in samples]),
                "consumer_and_output_ms": describe([s["stats"]["consumer_and_output_ns"] / 1e6 for s in samples]),
                "work_counts": {k: describe([s["stats"]["counts"][k] for s in samples]) for k in samples[0]["stats"]["counts"]},
                "scanned_modules": samples[0]["stats"]["scanned_modules"],
                "edge_delta": samples[0]["stats"]["edge_delta"],
                "state": samples[0]["state"], "violations": samples[0]["validation"]["violations"]}
    (a.output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print("group: cached library / retained native / delta (median ms)")
    for group, modes in summary["groups"].items():
        print(group + ": " + " / ".join(f"{modes[m]['median']:.3f}" for m in MODES))
    print("paired delta vs retained percent changes:")
    for group, comparisons in summary["paired_percent_change"].items():
        print(group, comparisons["delta_vs_retained_native"])


if __name__ == "__main__":
    main()
