"""Incremental import facts and target-rooted shortest-path proofs.

Grimp remains the parser/resolver. The alternative consumer maintains the
min-plus fixed point; the control retains Grimp's native graph and real linter.
"""
from collections import defaultdict, deque
from dataclasses import dataclass
import heapq
import importlib
import json
from pathlib import Path
import time

import grimp
from grimp.application.config import settings
from grimp.application.scanning import scan_imports
from grimp.application.usecases import _assemble_graph, _find_packages
from grimp.domain.valueobjects import Module
from importlinter.configuration import configure
from importlinter.contracts.forbidden import ForbiddenContract

configure()
ROOTS = ("django.db.models", "django.template", "django.utils.functional")
SOURCE_PREFIX = "django.utils."


class SingleExplanationGraph:
    """Replace one traversal hook for an editor's one-explanation response.

    The native control uses the singular native shortest-chain API. The delta
    arm substitutes a maintained shortest proof. The unmodified linter, which
    can enumerate multiple explanations, remains the diagnostic-set oracle.
    """
    def __init__(self, graph, proof=None):
        self.graph, self.proof = graph, proof

    def __getattr__(self, name):
        return getattr(self.graph, name)

    def find_shortest_chains(self, *, importer, imported, as_packages):
        assert as_packages is False
        if self.proof is None:
            path = self.graph.find_shortest_chain(importer=importer, imported=imported, as_packages=False)
        else:
            assert self.proof.root == imported
            path = self.proof.path(importer)
        return {path} if path else set()


def contract(graph, sources, target, *, proof=None, full=False):
    """Real ForbiddenContract with a declared single-explanation traversal hook."""
    if not sources:
        return {}
    rule = ForbiddenContract("Utilities must not depend on this module", {"root_packages": ["django"]},
                             {"source_modules": sorted(sources), "forbidden_modules": [target], "as_packages": "false"})
    result = rule.check(graph if full else SingleExplanationGraph(graph, proof), verbose=False)
    if result.warnings or result.ignored_import_count:
        raise AssertionError("unexpected contract options")
    output = {}
    for row in result.metadata["invalid_chains"]:
        chains = row["chains"]
        if not full and len(chains) != 1:
            raise AssertionError("editor response requires one explanation")
        # The full linter can enumerate several edge-disjoint explanations.
        # Its minimum-length chain is an independent oracle for this response.
        selected = min(chains, key=len)
        output[row["downstream_module"]] = tuple(
            (e["importer"], e["imported"], tuple(sorted(e["line_numbers"]))) for e in selected)
    return output


def graph_rows(graph):
    """Independent complete API export, used only for validation."""
    return {u: tuple(sorted((v, tuple(sorted((d["line_number"], d["line_contents"], d["is_lazy"])
                          for d in graph.get_import_details(importer=u, imported=v))))
                           for v in graph.find_modules_directly_imported_by(u))) for u in sorted(graph.modules)}


class Adjacency:
    def __init__(self, nodes, edges):
        self.out = {u: set() for u in nodes}
        self.inc = {u: set() for u in nodes}
        self.apply(set(), edges, nodes)

    def apply(self, deleted, added, nodes):
        for u in nodes:
            self.out.setdefault(u, set()); self.inc.setdefault(u, set())
        for u, v in deleted:
            self.out[u].discard(v); self.inc[v].discard(u)
        for u, v in added:
            self.out[u].add(v); self.inc[v].add(u)
        for u in set(self.out) - set(nodes):
            if self.out[u] or self.inc[u]:
                raise AssertionError("node removal omitted incident edge delta")
            del self.out[u]; del self.inc[u]


class ShortestProof:
    """d(root)=0, d(u)=1+min d(v) over u->v; absent distance means infinity.

    A selected witness is a tree rooted at the target. Deleting a selected
    edge invalidates its witness subtree before relaxation. Consequently a
    disconnected cycle cannot sustain a false finite distance.
    """
    def __init__(self, graph, root):
        if root not in graph.out:
            raise ValueError("missing target")
        self.graph, self.root = graph, root
        self.distance, self.parent = {}, {}
        self.children = defaultdict(set)
        changed, self.initial_examined = self.relax([(0, root, "")])
        self.initial_nodes_changed = len(changed)

    def invalidate(self, deleted):
        bad = set(); queue = []
        for u, v in deleted:
            if self.parent.get(u) == v:
                queue.append(u)
        while queue:
            u = queue.pop()
            if u in bad:
                continue
            if u == self.root:
                raise AssertionError("target cannot be invalidated")
            bad.add(u); queue.extend(self.children[u])
        for u in bad:
            p = self.parent.pop(u, None)
            if p is not None:
                self.children[p].discard(u)
            self.distance.pop(u, None)
        for u in bad:
            self.children[u].clear()
        return bad

    def relax(self, queue):
        heapq.heapify(queue); changed = set(); examined = 0
        while queue:
            d, u, via = heapq.heappop(queue)
            old = self.distance.get(u)
            if old is not None and (d > old or (d == old and via >= self.parent.get(u, ""))):
                continue
            if u == self.root and d:
                continue
            previous = self.parent.get(u)
            if previous is not None:
                self.children[previous].discard(u)
            self.distance[u] = d
            if u != self.root:
                self.parent[u] = via; self.children[via].add(u)
            changed.add(u)
            for pred in self.graph.inc[u]:
                examined += 1
                if pred != self.root:
                    heapq.heappush(queue, (d + 1, pred, u))
        return changed, examined

    def repair(self, bad, added):
        seeds = []; seed_edges = 0
        for u in bad:
            for v in self.graph.out.get(u, ()):
                seed_edges += 1
                if v in self.distance:
                    seeds.append((self.distance[v] + 1, u, v))
        for u, v in added:
            seed_edges += 1
            if v in self.distance and u != self.root:
                seeds.append((self.distance[v] + 1, u, v))
        changed, work = self.relax(seeds)
        return bad | changed, work + seed_edges

    def path(self, source):
        if source not in self.distance or source == self.root:
            return ()
        result = [source]
        while result[-1] != self.root:
            result.append(self.parent[result[-1]])
            if len(result) > len(self.distance):
                raise AssertionError("cyclic witness")
        return tuple(result)


@dataclass
class Batch:
    records: dict
    nodes: set
    changed: set
    deleted: set
    added: set
    scanned: int
    membership: bool


class Producer:
    def __init__(self):
        self.found = _find_packages(settings.FILE_SYSTEM, ["django"])
        self.files = {mf.module.name: mf for p in self.found for mf in p.module_files}
        scanned = scan_imports(list(self.files.values()), found_packages=self.found,
                               include_external_packages=False, exclude_type_checking_imports=False)
        self.records = {mf.module.name: imports for mf, imports in scanned.items()}
        self.graph = _assemble_graph(self.found, {Module(n): r for n, r in self.records.items()})

    @staticmethod
    def edges(records):
        return {(u, r.imported.name) for u, rows in records.items() for r in rows}

    def prepare(self, changed_modules, membership):
        found = _find_packages(settings.FILE_SYSTEM, ["django"]) if membership else self.found
        files = {mf.module.name: mf for p in found for mf in p.module_files} if membership else self.files
        selected = list(files.values()) if membership else [files[n] for n in changed_modules]
        scanned = scan_imports(selected, found_packages=found, include_external_packages=False, exclude_type_checking_imports=False)
        rows = {mf.module.name: imports for mf, imports in scanned.items()}
        changed = {n for n in set(rows) | (set(self.records) - set(files)) if self.records.get(n) != rows.get(n)}
        before = {n: self.records.get(n, set()) for n in changed}
        after = {n: rows.get(n, set()) for n in changed}
        old_edges, new_edges = self.edges(before), self.edges(after)
        nodes = set(files) | {n for p in found for n in p.namespace_packages}
        # Scanning succeeds before publication or graph mutation.
        return Batch(rows, nodes, changed, old_edges - new_edges, new_edges - old_edges, len(selected), membership), found, files

    def commit(self, batch, found, files):
        previous_nodes = self.graph.modules
        for n in batch.nodes - previous_nodes:
            self.graph.add_module(n)
        for n in batch.changed:
            if n in previous_nodes:
                for imported in self.graph.find_modules_directly_imported_by(n):
                    self.graph.remove_import(importer=n, imported=imported)
        for n in previous_nodes - batch.nodes:
            self.graph.remove_module(n)
        for n in batch.changed & batch.nodes:
            for r in sorted(batch.records.get(n, set())):
                self.graph.add_import(importer=n, imported=r.imported.name, is_lazy=r.is_lazy,
                                      line_number=r.line_number, line_contents=r.line_contents)
        for n in set(self.records) - batch.nodes:
            del self.records[n]
        self.records.update(batch.records)
        self.found, self.files = found, files


class Consumer:
    def __init__(self, graph, roots, target, mode):
        self.roots, self.target, self.mode = tuple(roots), target, mode
        self.navigation = {}
        self.diagnostics = {}
        self.owners = defaultdict(set)
        self.counts = {"native_reachability": 0, "native_contract_sources": 0,
                       "proof_nodes_changed": 0, "proof_edges_examined": 0, "diagnostics_refreshed": 0}
        if mode == "delta":
            edges = {(u, v) for u in graph.modules for v in graph.find_modules_directly_imported_by(u)}
            self.adjacency = Adjacency(graph.modules, edges)
            self.proofs = {r: ShortestProof(self.adjacency, r) for r in self.roots}
            self.counts["proof_nodes_changed"] = sum(p.initial_nodes_changed for p in self.proofs.values())
            self.counts["proof_edges_examined"] = sum(p.initial_examined for p in self.proofs.values())
        self.refresh(graph, set(graph.modules), force=True)

    @staticmethod
    def sources(graph):
        return {n for n in graph.modules if n.startswith(SOURCE_PREFIX)}

    def prior_owners(self, nodes):
        return set().union(*(self.owners.get(n, set()) for n in nodes)) if nodes else set()

    def before(self, graph, batch):
        # Both controls preserve diagnostics whose selected proof is unaffected
        # by a deletion or a location-only edit. An added edge might introduce
        # a shorter path, so the native control invalidates its old ancestors.
        dirty = self.prior_owners(batch.changed)
        if self.mode != "delta":
            for u, _ in batch.added:
                if u in graph.modules:
                    dirty |= graph.find_downstream_modules(u) | {u}
                    self.counts["native_reachability"] += 1
            return dirty, None
        bad = {r: p.invalidate(batch.deleted) for r, p in self.proofs.items()}
        return dirty, bad

    def after(self, graph, batch, prepared, target=None):
        dirty, bad = prepared
        if self.mode == "delta":
            self.adjacency.apply(batch.deleted, batch.added, batch.nodes)
            for r, proof in self.proofs.items():
                changed, examined = proof.repair(bad[r], batch.added)
                self.counts["proof_nodes_changed"] += len(changed)
                self.counts["proof_edges_examined"] += examined
                if r == self.target:
                    dirty |= self.prior_owners(changed) | changed
        if target is not None and target != self.target:
            self.target = target; dirty = set(graph.modules)
            force = True
        else:
            force = False
        for source in set(self.diagnostics) - self.sources(graph):
            self.drop(source)
        dirty |= self.sources(graph) - self.known_sources
        changed_edges = batch.deleted | batch.added
        self.refresh(graph, dirty, force, changed_edges)

    def drop(self, source):
        for u, _, _ in self.diagnostics.pop(source, ()):
            self.owners[u].discard(source)

    def refresh(self, graph, dirty, force=False, changed_edges=frozenset()):
        for root in self.roots:
            if root not in graph.modules:
                raise ValueError("missing query target")
            if self.mode == "delta":
                if changed_edges or root not in self.navigation:
                    self.navigation[root] = frozenset(self.proofs[root].distance) - {root}
            else:
                previous = self.navigation.get(root)
                if previous is None or any(u == root or v == root or u in previous or v in previous for u, v in changed_edges):
                    self.navigation[root] = frozenset(graph.find_downstream_modules(root)) - {root}
                    self.counts["native_reachability"] += 1
        sources = self.sources(graph)
        dirty = sources if force else dirty & sources
        if self.mode == "delta":
            current = contract(graph, dirty, self.target, proof=self.proofs[self.target])
        else:
            current = contract(graph, dirty, self.target)
            self.counts["native_contract_sources"] += len(dirty)
        for source in dirty:
            self.drop(source)
            if source in current:
                self.diagnostics[source] = current[source]
                for u, _, _ in current[source]:
                    self.owners[u].add(source)
        self.counts["diagnostics_refreshed"] += len(dirty)
        self.known_sources = sources

    def response(self, generation):
        # Fresh immutable wire result; full consumption has the same shape in
        # every arm. Alternative equal-length valid witnesses are allowed.
        return json.dumps({"generation": generation, "target": self.target,
                           "navigation": {r: sorted(self.navigation[r]) for r in self.roots},
                           "diagnostics": {s: self.diagnostics[s] for s in sorted(self.diagnostics)}}, sort_keys=True)


class Session:
    def __init__(self, project, mode, roots=ROOTS, target=ROOTS[0]):
        self.project, self.mode, self.roots, self.target = Path(project), mode, roots, target
        self.generation = 0; self.producer = None; self.consumer = None
        self.cache = self.project.parent / ("cache-" + mode)
        self.cache_epoch = 0

    @staticmethod
    def module(relative):
        parts = list(Path(relative).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        return ".".join(parts)

    def request(self, changes=None, expected=None, target=None):
        if expected is not None and expected != self.generation:
            raise ValueError("stale generation")
        changes = changes or {}; target = target or self.target
        if target not in self.roots:
            raise ValueError("target outside registered query context")
        start = time.perf_counter_ns(); initial = self.producer is None and self.consumer is None
        old = {}; changed_modules = set(); membership = False
        for relative, body in changes.items():
            path = self.project / relative
            if not path.resolve().is_relative_to(self.project.resolve()) or path.suffix != ".py":
                raise ValueError("invalid update path")
            old[relative] = path.read_bytes() if path.exists() else None
            data = body.encode() if body is not None else None
            if data == old[relative]:
                continue
            changed_modules.add(self.module(relative)); membership |= data is None or old[relative] is None
            if data is None:
                path.unlink()
            else:
                path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
        importlib.invalidate_caches()
        written_ns = time.perf_counter_ns() - start; phase = time.perf_counter_ns()
        scanned = 0; changed_facts = 0; edge_delta = 0
        before = dict(self.consumer.counts) if self.consumer else {}
        try:
            if self.mode == "cached_library":
                if initial or changed_modules:
                    if membership:
                        self.cache_epoch += 1
                    graph = grimp.build_graph("django", cache_dir=str(self.cache / str(self.cache_epoch)))
                    self.graph = graph
                producer_ns = time.perf_counter_ns() - phase; phase = time.perf_counter_ns()
                if initial or changed_modules or target != self.target:
                    self.consumer = Consumer(self.graph, self.roots, target, "native")
                    # A cached library build rechecks all derived results.
                    before = {}
            else:
                if initial:
                    self.producer = Producer(); self.graph = self.producer.graph
                    scanned = len(self.producer.files)
                    producer_ns = time.perf_counter_ns() - phase; phase = time.perf_counter_ns()
                    self.consumer = Consumer(self.graph, self.roots, target, "delta" if self.mode == "delta" else "native")
                else:
                    if changed_modules:
                        batch, found, files = self.producer.prepare(changed_modules, membership)
                    else:
                        batch = Batch({}, self.graph.modules, set(), set(), set(), 0, False)
                        found, files = self.producer.found, self.producer.files
                    producer_ns = time.perf_counter_ns() - phase; phase = time.perf_counter_ns()
                    # Native graph mutation and maintenance count as consumer
                    # work here, identically for the two retained arms.
                    prepared = self.consumer.before(self.graph, batch)
                    self.producer.commit(batch, found, files)
                    self.consumer.after(self.graph, batch, prepared, target)
                    scanned = batch.scanned; changed_facts = len(batch.changed)
                    edge_delta = len(batch.deleted) + len(batch.added)
        except Exception:
            # Scanner syntax failures happen before mutation/publication.
            for relative, body in old.items():
                path = self.project / relative
                if body is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(body)
            raise
        self.generation += int(initial or bool(changed_modules) or target != self.target)
        self.target = target
        response = self.consumer.response(self.generation)
        finished = time.perf_counter_ns()
        ns = finished - start
        counts = {k: v - before.get(k, 0) for k, v in self.consumer.counts.items()}
        return response, {"ns": ns, "write_ns": written_ns, "producer_ns": producer_ns,
                          "consumer_and_output_ns": finished - phase,
                          "scanned_modules": scanned if self.mode != "cached_library" else None,
                          "changed_importer_facts": changed_facts if self.mode != "cached_library" else None,
                          "edge_delta": edge_delta if self.mode != "cached_library" else None,
                          "membership_rescan": membership, "counts": counts}


def verify(response, oracle_graph, roots):
    """Exact result sets, minimum path length, current valid witness/locations.

    Native graph construction can choose a different equally short witness;
    no equality of that tie-breaking order is required or claimed.
    """
    value = json.loads(response); target = value["target"]
    expected = contract(oracle_graph, Consumer.sources(oracle_graph), target, full=True)
    if set(value["diagnostics"]) != set(expected):
        raise AssertionError(f"diagnostic set differs: {set(value['diagnostics'])} != {set(expected)}")
    for root in roots:
        if set(value["navigation"][root]) != oracle_graph.find_downstream_modules(root) - {root}:
            raise AssertionError("navigation differs: " + root)
    for source, path in value["diagnostics"].items():
        if len(path) != len(expected[source]) or not path or path[0][0] != source or path[-1][1] != target:
            raise AssertionError("nonminimum or malformed witness")
        for i, (u, v, lines) in enumerate(path):
            if not oracle_graph.direct_import_exists(importer=u, imported=v) or (i and path[i-1][1] != u):
                raise AssertionError("invalid witness edge")
            actual_lines = sorted(d["line_number"] for d in oracle_graph.get_import_details(importer=u, imported=v))
            if lines != actual_lines:
                raise AssertionError("stale source location")
    return {"navigation_nodes": sum(len(v) for v in value["navigation"].values()),
            "violations": len(expected), "witness_edges": sum(len(v) for v in value["diagnostics"].values())}
