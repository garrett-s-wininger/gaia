"""Current-source equivalence and focused namespace invalidation checks."""
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest

from producer import MODES, Session, bind, candidates, engine
import grimp

BASE = {"django/__init__.py": "", "django/db/__init__.py": "", "django/db/models.py": "",
        "django/template/__init__.py": "", "django/utils/__init__.py": "",
        "django/utils/functional.py": ""}


class Workspace:
    def __init__(self, files):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        for name, body in {**BASE, **files}.items():
            path = self.root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(body)

    def __enter__(self):
        sys.path.insert(0, str(self.root)); return self.root

    def __exit__(self, *exc):
        sys.path.remove(str(self.root)); self.temp.cleanup()


def check(session, edits=None):
    response, stats = session.request(edits, expected=session.generation)
    fresh = grimp.build_graph("django", cache_dir=None)
    assert engine.graph_rows(session.graph) == engine.graph_rows(fresh)
    engine.verify(response, fresh, engine.ROOTS)
    if session.producer.mode != "full_rescan":
        # Verify the actual retained relation and its inverse, not just outputs.
        expected = {}
        for importer, refs in session.producer.references.items():
            assert bind(refs, fresh.modules) == session.producer.records[importer]
            assert session.producer.keys[importer] == {name for ref in refs for name in candidates(ref.imported.name)}
        for importer, names in session.producer.keys.items():
            for name in names:
                expected.setdefault(name, set()).add(importer)
        assert expected == session.producer.watchers
    return response, stats


class RebindingTests(unittest.TestCase):
    def test_native_syntax_and_absence_recovery(self):
        source = '''# imports in strings and comments are ignored
text = "import django.imaginary"
from . import later as alias
from ..db import (models as Model,)
from django.utils import *
import django.utils.later; from django.utils import later
def nested():
    from .later import Thing
if TYPE_CHECKING:
    from . import later
else:
    from .. import template
lazy from django.utils import later
'''
        for mode in MODES:
            with Workspace({"django/utils/a.py": source}) as root:
                s = Session(root, mode); check(s)
                _, stats = check(s, {"django/utils/later.py": "from django.db import models\n"})
                if mode == "rebind":
                    self.assertEqual(stats["producer_counts"]["parsed_modules"], 1)
                    self.assertEqual(stats["producer_counts"]["affected_unchanged_modules"], 1)
                check(s, {"django/utils/later.py": None})
                check(s, {"django/utils/a.py": source.replace("later", "different")})
                _, stats = check(s, {"django/utils/later.py": ""})
                if mode != "full_rescan":
                    self.assertEqual(stats["producer_counts"]["affected_unchanged_modules"], 0)

    def test_namespace_packages_parent_fallback_and_file_to_package(self):
        files = {"django/utils/a.py": "from django.utils.ns import absent\nfrom .mod import child\n",
                 "django/utils/ns/first.py": "", "django/utils/mod.py": "from . import functional\n"}
        for mode in MODES:
            with Workspace(files) as root:
                s = Session(root, mode); check(s)
                check(s, {"django/utils/ns/absent.py": "from django.db import models\n"})
                check(s, {"django/utils/ns/absent.py": None, "django/utils/ns/first.py": None})
                check(s, {"django/utils/mod.py": None,
                          "django/utils/mod/__init__.py": "from .. import functional\n",
                          "django/utils/mod/child.py": "from django.db import models\n"})
                check(s, {"django/utils/mod/__init__.py": None, "django/utils/mod/child.py": None,
                          "django/utils/mod.py": "from . import functional\n"})

    def test_parser_failure_and_generation(self):
        for mode in MODES:
            with Workspace({"django/utils/a.py": "from . import missing\n"}) as root:
                s = Session(root, mode); old, _ = check(s); gen = s.generation
                with self.assertRaises(ValueError):
                    s.request({"django/utils/a.py": "x=1\n"}, expected=gen-1)
                with self.assertRaises(Exception):
                    s.request({"django/utils/a.py": "def broken(\n", "django/utils/missing.py": ""}, expected=gen)
                current, _ = check(s)
                self.assertEqual(json.loads(old), json.loads(current))
                self.assertEqual(s.generation, gen)
                check(s, {"django/utils/missing.py": "from django.db import models\n"})

    def test_random_membership_and_import_retargeting(self):
        for mode in MODES:
            with Workspace({"django/utils/a.py": "from . import n0\n"}) as root:
                rng = random.Random(5407); s = Session(root, mode); check(s)
                present = set()
                for _ in range(120):
                    n = rng.randrange(10); path = f"django/utils/n{n}.py"
                    if n in present and rng.random() < .4:
                        edits = {path: None}; present.remove(n)
                    else:
                        target = rng.randrange(10)
                        body = f"from . import n{target}\n"
                        if rng.random() < .35:
                            body += "from django.db import models\n"
                        edits = {path: body}; present.add(n)
                    if rng.random() < .2:
                        edits["django/utils/a.py"] = f"from . import n{rng.randrange(10)}\n"
                    check(s, edits)


if __name__ == "__main__":
    unittest.main()
