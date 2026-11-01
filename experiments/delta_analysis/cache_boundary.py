"""Reproduce a cached resolution boundary in the pinned Grimp version."""
import importlib
import json
from pathlib import Path
import sys
import tempfile

import grimp


def observe():
    with tempfile.TemporaryDirectory() as work:
        root = Path(work)
        files = {"django/__init__.py": "", "django/utils/__init__.py": "",
                 "django/db/__init__.py": "", "django/db/models.py": "",
                 "django/utils/a.py": "from django.utils import later\n"}
        for name, body in files.items():
            p = root / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(body)
        sys.path.insert(0, work)
        try:
            importlib.invalidate_caches()
            first = grimp.build_graph("django", cache_dir=str(root / "cache"))
            (root / "django/utils/later.py").write_text("from django.db import models\n")
            importlib.invalidate_caches()
            cached = grimp.build_graph("django", cache_dir=str(root / "cache"))
            fresh = grimp.build_graph("django", cache_dir=None)
            rotated = grimp.build_graph("django", cache_dir=str(root / "cache-next"))
            dependencies = lambda g: sorted(g.find_modules_directly_imported_by("django.utils.a"))
            result = {"initial_dependencies": dependencies(first),
                      "cached_after_module_appears": dependencies(cached),
                      "fresh_after_module_appears": dependencies(fresh),
                      "rotated_cache_after_module_appears": dependencies(rotated)}
            assert result["cached_after_module_appears"] != result["fresh_after_module_appears"], result
            assert result["rotated_cache_after_module_appears"] == result["fresh_after_module_appears"], result
            return result
        finally:
            sys.path.remove(work)


if __name__ == "__main__":
    print(json.dumps(observe(), indent=2))
