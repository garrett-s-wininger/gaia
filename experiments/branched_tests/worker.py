"""Real pytest operations in fresh, warm, and normally finalized fork children."""
import atexit
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import random
import sys
import threading
import time

ALLOWED_WRITE = None


def audit(event, args):
    if event in ("socket.connect", "socket.bind", "socket.getaddrinfo"):
        raise RuntimeError("network outside the local test contract")
    if ALLOWED_WRITE is None:
        return
    path = None
    if event == "open" and isinstance(args[0], (str, bytes)):
        mode, flags = args[1], args[2]
        if (isinstance(mode, str) and any(c in mode for c in "wax+")) or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC):
            path = args[0]
    elif event in ("os.remove", "os.rmdir", "os.mkdir"):
        path = args[0]
    elif event in ("os.rename", "os.link", "os.symlink"):
        for p in args[:2]:
            if isinstance(p, (str, bytes)) and not Path(os.fsdecode(p)).resolve().is_relative_to(ALLOWED_WRITE):
                raise RuntimeError("unadmitted mutation: " + os.fsdecode(p))
    if path is not None and not Path(os.fsdecode(path)).resolve().is_relative_to(ALLOWED_WRITE):
        raise RuntimeError("unadmitted write: " + os.fsdecode(path))


def memory(pid="self"):
    fields = {}
    for line in Path(f"/proc/{pid}/smaps_rollup").read_text().splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            if key in ("Rss", "Pss", "Private_Dirty", "Shared_Clean", "Shared_Dirty"):
                fields[key + "_bytes"] = int(value.split()[0]) * 1024
    return fields


def admit():
    from django.db import connections
    connections.close_all()
    if threading.active_count() != 1 or len(list(Path("/proc/self/task").iterdir())) != 1:
        raise RuntimeError("template must be single threaded")
    opened = []
    for p in Path("/proc/self/fd").iterdir():
        if int(p.name) > 2:
            try:
                opened.append(os.readlink(p))
            except FileNotFoundError:
                pass
    if opened:
        raise RuntimeError("template owns unbound descriptors: " + repr(opened))


def prepare(config):
    start = time.perf_counter_ns()
    sys.path.insert(0, config["app"])
    os.environ.update(config["environment"])
    sys.addaudithook(audit)
    import django
    django.setup()
    import pytest
    from django.db import connections
    from django.conf import settings
    if config.get("reset_database"):
        from django.core.management import call_command
        call_command("flush", verbosity=0, interactive=False)
    if config.get("make_seed"):
        from django.core.management import call_command
        from django.contrib.auth import get_user_model
        call_command("migrate", verbosity=0, interactive=False, run_syncdb=True)
        spec = importlib.util.spec_from_file_location("gaia_seed_fixture", Path(config["app"]) / "todo/tests/conftest.py")
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        module._gaia_seed(get_user_model())
        from case_support import verify_fixture
        verify_fixture()
    connections.close_all()
    # Retain the real URL/template/import initialization, with no test result.
    from django.urls import get_resolver
    tuple(get_resolver().url_patterns)
    admit()
    return {"ready": True, "prepare_ns": time.perf_counter_ns()-start, "memory": memory(), "pid": os.getpid()}


class Reports:
    def __init__(self):
        self.reports = []

    def pytest_runtest_logreport(self, report):
        self.reports.append({"nodeid": report.nodeid, "when": report.when, "outcome": report.outcome})


def execute(config, request, finalizer=False):
    global ALLOWED_WRITE
    if request["generation"] != config["generation"]:
        raise ValueError("stale template generation")
    branch = Path(request["branch"]).resolve()
    if not branch.is_relative_to(Path(config["work"]).resolve()):
        raise ValueError("unowned branch path")
    if Path(request["database"]).resolve() != branch / "test.sqlite3":
        raise ValueError("database must be bound inside this branch")
    os.environ.update(GAIA_DB_PATH=request["database"], GAIA_MEDIA_ROOT=str(branch / "media"),
                      GAIA_PROBE=str(branch / "probe.json"), GAIA_FAULT=request["fault"])
    from django.conf import settings
    from django.db import connections
    from django.test.utils import override_settings
    connections.close_all()
    connections["default"].settings_dict["NAME"] = request["database"]
    connections["default"].settings_dict["TEST"]["NAME"] = request["database"]
    settings.DATABASES["default"]["NAME"] = request["database"]
    ALLOWED_WRITE = branch
    random.seed()
    if finalizer:
        atexit.register((branch / "finalized").write_text, "normal Python finalization")
    import pytest
    reports = Reports(); log = io.StringIO(); start = time.perf_counter_ns()
    args = ["-q", "-s", "-p", "pytest_django.plugin", "-p", "pytest_mock", "-p", "no:cacheprovider",
            "--basetemp", str(branch / "pytest-temp"), "--log-file", str(branch / "pytest.log"),
            "--rootdir", config["app"]]
    if config["mode"] == "stock_reuse":
        args.append("--reuse-db")
    args += [str(Path(config["app"]) / p) for p in request["tests"]]
    with override_settings(MEDIA_ROOT=str(branch / "media")), contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        code = int(pytest.main(args, plugins=[reports]))
    connections.close_all()
    elapsed = time.perf_counter_ns()-start
    # Pytest can flush transaction-test state; report assertions establish the
    # committed effects before that teardown. Parent discards private state.
    reply = {"exit": code, "reports": reports.reports, "pytest_ns": elapsed,
             "log": log.getvalue(), "memory": memory(), "pid": os.getpid()}
    if config["mode"] == "fork_seed":
        reply["parent_memory"] = memory(os.getppid())
    ALLOWED_WRITE = None if not finalizer else branch
    return reply


def emit(value):
    print(json.dumps(value, separators=(",", ":")), flush=True)


def main():
    config = json.loads(Path(sys.argv[1]).read_text())
    ready = prepare(config)
    if config["mode"] == "prepare_only":
        emit(ready); return 0
    if config["mode"] in ("stock_fresh", "stock_reuse", "exec_seed"):
        request = json.loads(sys.stdin.readline())
        reply = execute(config, request, finalizer=True); reply["prepare_ns"] = ready["prepare_ns"]
        emit(reply); return reply["exit"]
    emit(ready)
    for line in sys.stdin:
        request = json.loads(line)
        if request == {"stop": True}:
            return 0
        if request["generation"] != config["generation"]:
            emit({"rejected": "stale generation"}); continue
        if config["mode"] == "warm_seed":
            emit(execute(config, request)); continue
        fork_start = time.perf_counter_ns()
        admit(); rd, wr = os.pipe(); pid = os.fork()
        if pid == 0:
            os.close(rd); os.close(0)
            try:
                reply = execute(config, request, finalizer=True); code = reply["exit"]
            except Exception as error:
                reply = {"error": repr(error), "exit": 2}; code = 2
            with os.fdopen(wr, "w") as stream:
                stream.write(json.dumps(reply))
            # Normal interpreter finalization; do not use os._exit.
            return code
        os.close(wr)
        with os.fdopen(rd) as stream:
            payload = stream.read()
        payload_received = time.perf_counter_ns()
        _, status, usage = os.wait4(pid, 0)
        reply = json.loads(payload) if payload else {"exit": os.waitstatus_to_exitcode(status), "killed": True}
        reply.update(child_status=os.waitstatus_to_exitcode(status), child_maxrss_kib=usage.ru_maxrss,
                     execution_protocol_ns=payload_received-fork_start,
                     finalization_wait_ns=time.perf_counter_ns()-payload_received)
        emit(reply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
