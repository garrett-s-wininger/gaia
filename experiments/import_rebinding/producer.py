"""Retain native-parser references; index their membership observations.

All arms use the same locally extended Grimp scanner. The full upstream graph
builder (unmodified wheel) is the independent oracle in tests and measurements.
"""
from collections import defaultdict
import importlib.util
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "delta_analysis"))
import engine
from grimp.application.config import settings
from grimp.application.usecases import _assemble_graph, _find_packages
from grimp.domain.valueobjects import DirectImport, Module

spec = importlib.util.spec_from_file_location("_rustgrimp", os.environ["GAIA_IMPORT_NATIVE"])
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)

MODES = ("full_rescan", "scoped_native", "rebind")


def scan(files, found, references=False):
    if not files:
        return {}
    rows = native.scan_for_imports(module_files=tuple(files), found_packages=found,
                                  include_external_packages=False, exclude_type_checking_imports=False,
                                  file_system=native.RealBasicFileSystem(), retain_references=references)
    return {module.name: imports for module, imports in rows.items()}


def candidates(name):
    # Exactly Grimp 3.17's internal resolver: exact name, then ONE parent.
    # A missing exact name is an observation even when the parent is present.
    return (name, name.rsplit(".", 1)[0]) if "." in name else (name,)


def bind(references, nodes):
    result = set()
    for ref in references:
        target = next((n for n in candidates(ref.imported.name) if n in nodes), None)
        if target is not None:
            result.add(DirectImport(importer=ref.importer, imported=Module(target), line_number=ref.line_number,
                                    line_contents=ref.line_contents, is_lazy=ref.is_lazy))
    return result


class Producer(engine.Producer):
    def __init__(self, mode):
        self.mode = mode
        self.references = {}; self.watchers = defaultdict(set); self.keys = {}
        self.reset_counts()
        start = time.perf_counter_ns()
        self.found = _find_packages(settings.FILE_SYSTEM, ["django"])
        self.files = {mf.module.name: mf for p in self.found for mf in p.module_files}
        self.nodes = self.node_set(self.found, self.files)
        self.counts["discovery_ns"] = time.perf_counter_ns() - start
        start = time.perf_counter_ns()
        rows = scan(list(self.files.values()), self.found, references=mode != "full_rescan")
        self.counts["native_scan_ns"] = time.perf_counter_ns() - start
        self.counts["parsed_modules"] = len(self.files)
        if mode == "full_rescan":
            self.records = rows
        else:
            self.counts["reference_extractions"] = len(self.files)
            start = time.perf_counter_ns()
            self.records = {n: bind(refs, self.nodes) for n, refs in rows.items()}
            self.counts["references_bound"] = sum(map(len, rows.values()))
            self.counts["binding_ns"] = time.perf_counter_ns() - start
            self.update_references(rows, set())
        self.graph = _assemble_graph(self.found, {Module(n): r for n, r in self.records.items()})

    def reset_counts(self):
        self.counts = dict.fromkeys(("parsed_modules", "reference_extractions", "affected_unchanged_modules",
                                    "references_bound", "membership_names_changed", "discovery_ns",
                                    "native_scan_ns", "binding_ns"), 0)

    @staticmethod
    def node_set(found, files):
        return set(files) | {n for p in found for n in p.namespace_packages}

    def update_references(self, rows, removed):
        for n in set(rows) | removed:
            for key in self.keys.pop(n, ()):
                self.watchers[key].remove(n)
                if not self.watchers[key]:
                    del self.watchers[key]
            self.references.pop(n, None)
        for n, refs in rows.items():
            keys = {key for ref in refs for key in candidates(ref.imported.name)}
            self.keys[n] = keys
            if self.mode == "rebind":
                self.references[n] = refs
            for key in keys:
                self.watchers[key].add(n)

    def prepare(self, changed_modules, membership):
        start = time.perf_counter_ns()
        found = _find_packages(settings.FILE_SYSTEM, ["django"]) if membership else self.found
        files = {mf.module.name: mf for p in found for mf in p.module_files} if membership else self.files
        nodes = self.node_set(found, files)
        self.counts["discovery_ns"] = time.perf_counter_ns() - start
        names_changed = nodes ^ self.nodes
        self.counts["membership_names_changed"] = len(names_changed)
        removed = set(self.files) - set(files)
        edits = (set(changed_modules) | (set(files) - set(self.files))) & set(files)
        updates = {}
        if self.mode == "full_rescan":
            selected = set(files) if membership else edits
            start = time.perf_counter_ns()
            rows = scan([files[n] for n in sorted(selected)], found)
            self.counts["native_scan_ns"] = time.perf_counter_ns() - start
            self.counts["parsed_modules"] = len(selected)
        else:
            affected = set().union(*(self.watchers.get(n, set()) for n in names_changed)) if names_changed else set()
            affected = (affected & set(files)) - edits
            self.counts["affected_unchanged_modules"] = len(affected)
            start = time.perf_counter_ns()
            updates = scan([files[n] for n in sorted(edits)], found, references=True)
            self.counts["native_scan_ns"] = time.perf_counter_ns() - start
            self.counts["parsed_modules"] = len(edits)
            self.counts["reference_extractions"] = len(edits)
            start = time.perf_counter_ns()
            rows = {n: bind(refs, nodes) for n, refs in updates.items()}
            self.counts["references_bound"] = sum(map(len, updates.values()))
            if self.mode == "rebind":
                for n in affected:
                    rows[n] = bind(self.references[n], nodes)
                    self.counts["references_bound"] += len(self.references[n])
            self.counts["binding_ns"] = time.perf_counter_ns() - start
            if self.mode == "scoped_native":
                start = time.perf_counter_ns()
                rows.update(scan([files[n] for n in sorted(affected)], found))
                self.counts["native_scan_ns"] += time.perf_counter_ns() - start
                self.counts["parsed_modules"] += len(affected)
        changed = {n for n in set(rows) | removed if self.records.get(n) != rows.get(n)}
        before = {n: self.records.get(n, set()) for n in changed}
        after = {n: rows.get(n, set()) for n in changed}
        old_edges, new_edges = self.edges(before), self.edges(after)
        batch = engine.Batch(rows, nodes, changed, old_edges - new_edges, new_edges - old_edges,
                             self.counts["parsed_modules"], membership)
        batch.reference_updates = updates; batch.removed_references = removed
        return batch, found, files

    def commit(self, batch, found, files):
        super().commit(batch, found, files)
        if self.mode != "full_rescan" and hasattr(batch, "reference_updates"):
            self.update_references(batch.reference_updates, batch.removed_references)
        self.nodes = batch.nodes

    def state(self):
        return {"references": sum(map(len, self.references.values())), "watched_names": len(self.watchers),
                "watcher_memberships": sum(map(len, self.watchers.values())),
                "reference_source_text_bytes": sum(len(r.line_contents.encode()) for refs in self.references.values() for r in refs)}


class Session(engine.Session):
    """Reuse the prior native consumer and request clock without changing its source.

    Factory substitution is confined to a serialized request in one worker.
    This is an experiment adapter, not a concurrent extension API.
    """
    def __init__(self, project, mode):
        assert mode in MODES
        self.producer_mode = mode
        super().__init__(project, "retained_native")

    def request(self, *args, **kwargs):
        original = engine.Producer
        engine.Producer = lambda: Producer(self.producer_mode)
        if self.producer:
            self.producer.reset_counts()
        try:
            response, stats = super().request(*args, **kwargs)
        finally:
            engine.Producer = original
        stats["producer_counts"] = dict(self.producer.counts)
        return response, stats
