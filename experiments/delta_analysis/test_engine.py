"""Independent dynamic shortest-path checks and real parser/linter boundary tests."""
from collections import deque
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest

import grimp
from cache_boundary import observe
from engine import Adjacency, ROOTS, Session, ShortestProof, graph_rows, verify


def bfs(nodes, edges, root):
    distance = {root: 0}; q = deque([root])
    while q:
        v = q.popleft()
        for u, w in edges:
            if w == v and u not in distance:
                distance[u] = distance[v] + 1; q.append(u)
    return distance


class ProofTests(unittest.TestCase):
    def assert_proof(self, proof, nodes, edges):
        expected = bfs(nodes, edges, proof.root)
        self.assertEqual(proof.distance, expected)
        for u in nodes - {proof.root}:
            path = proof.path(u)
            if u in expected:
                self.assertEqual(len(path) - 1, expected[u])
                self.assertTrue(all(e in edges for e in zip(path, path[1:])))
            else:
                self.assertEqual(path, ())

    def test_cycles_alternatives_and_random_batches(self):
        rng = random.Random(712)
        for _ in range(100):
            nodes = {f"n{i}" for i in range(rng.randrange(2, 15))}
            edges = {(u, v) for u in sorted(nodes) for v in sorted(nodes) if rng.random() < .16}
            graph = Adjacency(nodes, edges); proof = ShortestProof(graph, "n0")
            self.assert_proof(proof, nodes, edges)
            for _ in range(30):
                deleted = {e for e in sorted(edges) if rng.random() < .15}
                added = {(rng.choice(sorted(nodes)), rng.choice(sorted(nodes))) for _ in range(3)} - (edges - deleted)
                deleted -= added  # An unchanged edge need not be invalidated.
                bad = proof.invalidate(deleted)
                edges = (edges - deleted) | added; graph.apply(deleted, added, nodes)
                proof.repair(bad, added)
                self.assert_proof(proof, nodes, edges)

    def test_disconnected_cycle_loses_its_own_support(self):
        nodes = {"root", "a", "b", "c"}; edges = {("a", "b"), ("b", "a"), ("b", "root"), ("c", "a")}
        graph = Adjacency(nodes, edges); proof = ShortestProof(graph, "root")
        deleted = {("b", "root")}; bad = proof.invalidate(deleted)
        graph.apply(deleted, set(), nodes); edges -= deleted; proof.repair(bad, set())
        self.assertEqual(proof.distance, {"root": 0})
        added = {("a", "root")}; graph.apply(set(), added, nodes); edges |= added
        proof.repair(set(), added); self.assert_proof(proof, nodes, edges)
        deleted = {e for e in edges if "b" in e}; bad = proof.invalidate(deleted)
        nodes.remove("b"); edges -= deleted; graph.apply(deleted, set(), nodes)
        proof.repair(bad, set()); self.assert_proof(proof, nodes, edges)


class SourceTests(unittest.TestCase):
    def test_pinned_library_cache_membership_boundary(self):
        observe()

    def test_native_parser_deltas_locations_membership_and_generation(self):
        files = {
            "django/__init__.py": "", "django/db/__init__.py": "", "django/db/models.py": "x = 1\n",
            "django/template/__init__.py": "", "django/utils/__init__.py": "",
            "django/utils/functional.py": "", "django/utils/a.py": "from django.utils import later\n",
            "django/utils/b.py": "from django.utils import a\n",
        }
        for mode in ("cached_library", "retained_native", "delta"):
            with tempfile.TemporaryDirectory() as work:
                root = Path(work); sys.path.insert(0, work)
                try:
                    for name, body in files.items():
                        p = root / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(body)
                    session = Session(root, mode)
                    steps = [{}, {"django/utils/later.py": "from django.db import models\n"},
                             {"django/utils/later.py": "\nfrom django.db import models\n"},
                             {"django/utils/a.py": "from django.utils import b, later\n"},
                             {"django/utils/later.py": "from django.utils import a\n"},
                             {"django/utils/later.py": None}, {"django/utils/a.py": "x = 3\n"}]
                    held = None
                    for step in steps:
                        response, stats = session.request(step, expected=session.generation)
                        fresh = grimp.build_graph("django", cache_dir=None)
                        try:
                            verify(response, fresh, ROOTS)
                        except Exception as error:
                            raise AssertionError((mode, step, stats)) from error
                        self.assertEqual(graph_rows(session.graph), graph_rows(fresh))
                        if held is None:
                            held = response
                            self.assertEqual(json.loads(held)["diagnostics"], {})
                    before = session.generation
                    with self.assertRaises(ValueError):
                        session.request({"django/utils/a.py": "bad = 4\n"}, expected=before-1)
                    self.assertEqual(session.generation, before)
                    with self.assertRaises(Exception):
                        session.request({"django/utils/a.py": "def broken(\n"}, expected=before)
                    response, stats = session.request({}, expected=before)
                    self.assertEqual(session.generation, before)
                    verify(response, grimp.build_graph("django", cache_dir=None), ROOTS)
                    self.assertEqual(json.loads(held)["diagnostics"], {})
                    response, _ = session.request({}, expected=before, target=ROOTS[1])
                    verify(response, grimp.build_graph("django", cache_dir=None), ROOTS)
                finally:
                    sys.path.remove(work)


if __name__ == "__main__":
    unittest.main()
