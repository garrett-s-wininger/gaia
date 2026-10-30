"""Versioned undo/redo order correctness and solver copy-growth checks."""
from collections import Counter, OrderedDict
from pathlib import Path
import random
import tempfile
import unittest

from fixtures import wheel
from test_incremental import session
from trail import TrailMap
import solver


class TrailTests(unittest.TestCase):
    def test_branching_versions_restore_values_and_insertion_order(self):
        rng = random.Random(20261029)
        work = Counter()
        maps = [(TrailMap(work), OrderedDict())]
        for step in range(1500):
            actual, expected = rng.choice(maps)
            if rng.randrange(4) == 0:
                maps.append((actual.copy(), expected.copy()))
                if len(maps) > 30:maps.pop(rng.randrange(len(maps)))
            else:
                key = rng.randrange(16)
                operation = rng.randrange(4)
                if operation < 2:
                    actual[key] = expected[key] = step
                elif operation == 2:
                    self.assertEqual(actual.pop(key, None), expected.pop(key, None))
                elif expected:
                    self.assertEqual(actual.popitem(), expected.popitem())
            for actual, expected in maps:
                self.assertEqual(list(actual.items()), list(expected.items()))
        self.assertGreater(work['trail_undos'], 0)
        self.assertGreater(work['trail_redos'], 0)

    def test_wide_graph_records_linear_mutations_without_full_map_copies(self):
        with tempfile.TemporaryDirectory() as temp:
            for count in (16, 32, 64):
                root = Path(temp)/str(count)
                wheels = root/'wheels'
                wheel(wheels, 'root', '1.0', [f'leaf-{i:03}==1' for i in range(count)])
                for i in range(count):wheel(wheels, f'leaf-{i:03}', '1.0')
                admission = solver.admit(wheels, root/'snapshot')
                baseline = session(admission, 'incremental').solve(['root'])
                result = session(admission, 'trail').solve(['root'])
                self.assertEqual(result['selected'], baseline['selected'])
                work = result['engine_work']
                self.assertEqual(work.get('map_entries_copied', 0), 0)
                self.assertEqual(work.get('state_copies', 0), 0)
                self.assertEqual(work.get('candidate_criteria_copies', 0), 0)
                self.assertEqual(work['trail_mutations'], 2*(count+1))
                self.assertEqual(work['candidate_delta_entries'], count)
                self.assertEqual(work.get('trail_undos', 0), 0)
                self.assertEqual(work.get('trail_redos', 0), 0)
                self.assertGreater(baseline['engine_work']['map_entries_copied'], count*count)


if __name__ == '__main__':unittest.main()
