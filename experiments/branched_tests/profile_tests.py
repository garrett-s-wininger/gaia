"""Profile real upstream tests before selecting a preparation boundary."""
import argparse
import cProfile
import io
import json
import os
from pathlib import Path
import pstats
import sys
import time


def main():
    p = argparse.ArgumentParser(); p.add_argument("--app", type=Path, required=True)
    p.add_argument("--work", type=Path, required=True); a = p.parse_args()
    a.app = a.app.resolve(); a.work = a.work.resolve(); a.work.mkdir(parents=True)
    sys.path.insert(0, str(a.app))
    os.environ.update(GAIA_APP_PATH=str(a.app), GAIA_DB_PATH=str(a.work / "test.sqlite"),
                      GAIA_MEDIA_ROOT=str(a.work / "media"), DJANGO_SETTINGS_MODULE="gaia_settings",
                      PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    import pytest
    profile = cProfile.Profile(); start = time.perf_counter_ns(); profile.enable()
    code = pytest.main(["-q", "-p", "pytest_django.plugin", "-p", "pytest_mock", "--durations=10",
                        str(a.app / "todo/tests/test_views.py")+"::test_todo_setup",
                        str(a.app / "todo/tests/test_views.py")+"::test_move_task_to_another_list_in_users_group",
                        str(a.app / "todo/tests/test_views.py")+"::test_cannot_move_task_to_list_outside_users_groups",
                        str(a.app / "todo/tests/test_utils.py")+"::test_locked_atomic_transaction"])
    profile.disable(); ns = time.perf_counter_ns()-start
    out = io.StringIO(); pstats.Stats(profile,stream=out).strip_dirs().sort_stats("cumulative").print_stats(40)
    (a.work / "profile.txt").write_text(out.getvalue())
    (a.work / "result.json").write_text(json.dumps({"pytest_exit":int(code),"ns":ns},indent=2)+"\n")
    print(out.getvalue())
    raise SystemExit(int(code))


if __name__ == "__main__":
    main()
