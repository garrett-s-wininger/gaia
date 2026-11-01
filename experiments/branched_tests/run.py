"""Versioned, private test requests using native Django/SQLite/fork controls."""
import argparse
from datetime import date, datetime, timezone
import fcntl
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import random
import select
import shutil
import signal
import statistics
import subprocess
import sys
import time

from case_support import fixture_suffix, probe_source, root_conftest

HERE = Path(__file__).resolve().parent
MODES = ('stock_fresh', 'stock_reuse', 'exec_seed', 'warm_seed', 'fork_seed')
SERVERS = ('warm_seed', 'fork_seed')
PREPARED = ('exec_seed', 'warm_seed', 'fork_seed')
NORMAL = 'todo/tests/test_gaia_boundary.py::test_generation_and_resources'
FAULT = 'todo/tests/test_gaia_boundary.py::test_committed_effects'
ATOMIC = 'todo/tests/test_utils.py::test_locked_atomic_transaction'
MOVE = 'todo/tests/test_views.py::test_move_task_to_another_list_in_users_group'
DENIED = 'todo/tests/test_views.py::test_cannot_move_task_to_list_outside_users_groups'
TRACE = [
    ('initial', 'original', '0', '', ATOMIC),
    ('permission', 'original', '0', '', MOVE),
    ('failure', 'original', '0', 'fail', None),
    ('after_failure', 'original', '0', '', DENIED),
    ('termination', 'original', '0', 'kill', None),
    ('after_termination', 'original', '0', '', ATOMIC),
    ('source_edit', 'inclusive', '0', '', ATOMIC),
    ('source_repeat', 'inclusive', '0', '', MOVE),
    ('settings_edit', 'inclusive', '1', '', DENIED),
    ('restore', 'original', '0', '', ATOMIC),
]


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest(root):
    return {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and '.pytest_cache' not in p.parts}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def dependency_manifest():
    result = {}
    for dist in importlib.metadata.distributions():
        files = {str(f): sha(Path(dist.locate_file(f))) for f in dist.files or []
                 if str(f).endswith(('.py', '.so', 'METADATA', 'RECORD')) and Path(dist.locate_file(f)).is_file()}
        result[dist.metadata['Name']] = {'version': dist.version, 'files': len(files), 'digest': digest(files)}
    return result


def read_reply(proc, log):
    ready, _, _ = select.select([proc.stdout], [], [], 60)
    if not ready:
        os.killpg(proc.pid, signal.SIGKILL); proc.wait()
        raise RuntimeError('worker response timeout: ' + str(log))
    line = proc.stdout.readline()
    if not line:
        proc.wait(timeout=60)
        if proc.returncode == -signal.SIGKILL:
            return {'exit': proc.returncode, 'killed': True}
        raise RuntimeError('worker exited without response: ' + log.read_text())
    try:
        return json.loads(line)
    except json.JSONDecodeError as error:
        raise RuntimeError('invalid worker response: ' + line + log.read_text()) from error


def communicate(proc, message=None):
    try:
        return proc.communicate(message, timeout=60)
    except subprocess.TimeoutExpired as error:
        os.killpg(proc.pid, signal.SIGKILL); proc.communicate()
        raise RuntimeError('worker exceeded 60 second operation deadline') from error


class Session:
    def __init__(self, mode, source, work, dependencies):
        self.mode, self.work = mode, work
        self.work.mkdir(parents=True)
        self.app = work / 'app'
        shutil.copytree(source, self.app, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
        fixture = self.app / 'todo/tests/conftest.py'
        fixture.write_text(fixture.read_text() + fixture_suffix())
        (self.app / 'conftest.py').write_text(root_conftest())
        (self.app / 'todo/tests/test_gaia_boundary.py').write_text(probe_source())
        for name in ('test_views.py', 'test_utils.py'):
            assert sha(self.app/'todo/tests'/name) == sha(source/'todo/tests'/name)
        self.models = self.app / 'todo/models.py'
        self.original = self.models.read_text()
        assert self.original.count('datetime.date.today() > self.due_date') == 1
        self.context = None
        self.dependencies = dependencies
        self.server = None
        self.server_log = None
        self.preparations = []
        self.generation_count = 0
        self.restarts = 0
        self.stale_rejections = 0
        self.seed_identity = None
        self.reset_database = False

    def start_process(self, config, suffix):
        config_path = self.work / (suffix + '.json')
        write_json(config_path, config)
        log = self.work / (suffix + '.stderr')
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
        with log.open('w') as stream:
            proc = subprocess.Popen([sys.executable, str(HERE / 'worker.py'), str(config_path)],
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stream,
                                    text=True, env=env, cwd=self.app, start_new_session=True)
        return proc, log

    def generation_identity(self, revision, staff):
        return digest({'source': manifest(self.app), 'revision': revision, 'staff': staff,
                       'harness': {p.name: sha(p) for p in HERE.glob('*.py')},
                       'dependencies': self.dependencies, 'day': date.today().isoformat(),
                       'hasher': 'MD5PasswordHasher'})

    def stop(self):
        if self.server is not None:
            if self.server.poll() is None:
                self.server.stdin.write(json.dumps({'stop': True}) + '\n'); self.server.stdin.flush()
            out, _ = communicate(self.server)
            if self.server.returncode not in (0, -signal.SIGKILL):
                raise RuntimeError('server shutdown failed: ' + self.server_log.read_text() + out)
            self.server = None

    def start_server(self, make_seed):
        config = dict(self.config, make_seed=make_seed)
        self.server, self.server_log = self.start_process(config, f'server-{self.generation_count}-{self.restarts}')
        reply = read_reply(self.server, self.server_log)
        assert reply.get('ready'), reply
        self.preparations.append(reply)
        # A wrong identity must be rejected before executing or allocating a branch.
        self.server.stdin.write(json.dumps({'generation': 'stale-' + self.generation}) + '\n')
        self.server.stdin.flush()
        assert read_reply(self.server, self.server_log) == {'rejected': 'stale generation'}
        self.stale_rejections += 1

    def configure(self, revision, staff):
        if self.context == (revision, staff):
            assert self.generation == self.generation_identity(revision, staff), 'unannounced source/config change'
            return False
        self.stop()
        if self.context is not None:
            shutil.rmtree(self.seed)
        self.models.write_text(self.original if revision == 'original' else self.original.replace(
            'datetime.date.today() > self.due_date', 'datetime.date.today() >= self.due_date'))
        self.generation = self.generation_identity(revision, staff)
        self.generation_count += 1
        self.context = (revision, staff)
        self.seed = self.work / f'seed-{self.generation_count}'
        self.seed.mkdir(); (self.seed / 'media').mkdir()
        environment = {'DJANGO_SETTINGS_MODULE': 'gaia_settings', 'GAIA_APP_PATH': str(self.app),
                       'GAIA_DB_PATH': str(self.seed / 'test.sqlite3'), 'GAIA_MEDIA_ROOT': str(self.seed / 'media'),
                       'GAIA_PREPARED': '1' if self.mode in PREPARED else '0',
                       'GAIA_REVISION': revision, 'GAIA_STAFF_ONLY': staff, 'GAIA_FAST_HASHER': '1'}
        self.config = {'mode': self.mode, 'app': str(self.app), 'work': str(self.work),
                       'generation': self.generation, 'environment': environment}
        if self.mode == 'exec_seed':
            proc, log = self.start_process(dict(self.config, mode='prepare_only', make_seed=True), f'prepare-{self.generation_count}')
            out, _ = communicate(proc)
            if proc.returncode:
                raise RuntimeError('seed preparation failed: ' + log.read_text() + out)
            self.preparations.append(json.loads(out))
        elif self.mode in SERVERS:
            self.start_server(make_seed=True)
        self.seed_identity = manifest(self.seed)
        return True

    def request(self, event, index):
        label, revision, staff, fault, test = event
        start = time.perf_counter_ns()
        changed = self.configure(revision, staff)
        configured = time.perf_counter_ns()
        branch = self.work / ('reuse' if self.mode == 'stock_reuse' else f'branch-{index}')
        branch.mkdir(exist_ok=self.mode == 'stock_reuse')
        media = branch / 'media'
        if self.mode in PREPARED:
            shutil.copyfile(self.seed / 'test.sqlite3', branch / 'test.sqlite3')
            shutil.copytree(self.seed / 'media', media)
        else:
            media.mkdir()
        request = {'generation': self.generation, 'branch': str(branch), 'database': str(branch / 'test.sqlite3'),
                   'fault': fault, 'tests': [FAULT] if fault else [test, NORMAL]}
        cloned = time.perf_counter_ns()
        if self.mode in SERVERS:
            self.server.stdin.write(json.dumps(request) + '\n'); self.server.stdin.flush()
            reply = read_reply(self.server, self.server_log)
        else:
            config = dict(self.config, reset_database=self.reset_database,
                          environment=dict(self.config['environment'], GAIA_DB_PATH=request['database'],
                                           GAIA_MEDIA_ROOT=str(media)))
            proc, log = self.start_process(config, f'request-{index}')
            out, _ = communicate(proc, json.dumps(request) + '\n')
            reply = json.loads(out) if out else {'exit': proc.returncode, 'killed': proc.returncode == -9}
            if proc.returncode not in (0, 1, -9):
                raise RuntimeError('fresh worker failed: ' + log.read_text() + out)
            assert reply['exit'] == proc.returncode
        executed = time.perf_counter_ns()
        probe = json.loads((branch / 'probe.json').read_text()) if (branch / 'probe.json').exists() else None
        expected = {'fail': 1, 'kill': -9, '': 0}[fault]
        assert reply.get('exit') == expected, (self.mode, label, reply)
        assert probe is not None, (self.mode, label, reply)
        if fault:
            assert probe == {'committed': True, 'media_written': True, 'heap_mutated': True}
        else:
            assert probe == {'tasks': 6, 'lists': 2, 'users': 3,
                             'attachment': hashlib.sha256(b'prepared attachment\n').hexdigest(),
                             'overdue_today': revision == 'inclusive', 'nonstaff_permitted': staff != '1'}
            assert len(reply['reports']) == 6 and all(r['outcome'] == 'passed' for r in reply['reports']), reply
        finalized = (branch / 'finalized').exists()
        if self.mode != 'warm_seed':
            assert finalized == (fault != 'kill'), (self.mode, label, finalized, reply)
        assert manifest(self.seed) == self.seed_identity, 'template external state was mutated'
        validated = time.perf_counter_ns()
        if self.mode == 'warm_seed' and fault:
            self.stop(); self.restarts += 1
            self.start_server(make_seed=False)
        # Keeping only clean schema is the ordinary pytest --reuse-db control.
        if self.mode == 'stock_reuse':
            # Native transaction-test teardown has flushed ordinary failures.
            # A killed process needs an explicit Django flush on next startup.
            # These method/permission edits do not change the database schema.
            self.reset_database = fault == 'kill'
            if fault == 'fail':
                assert reply['reports'][-1]['when'] == 'teardown' and reply['reports'][-1]['outcome'] == 'passed'
            for path in branch.iterdir():
                if path.name not in ('test.sqlite3', 'test.sqlite3-journal', 'test.sqlite3-wal', 'test.sqlite3-shm'):
                    shutil.rmtree(path) if path.is_dir() else path.unlink()
        else:
            shutil.rmtree(branch)
        elapsed = time.perf_counter_ns() - start
        return {'event': label, 'generation': self.generation, 'changed': changed, 'fault': fault,
                'elapsed_ns': elapsed, 'probe': probe, 'finalized': finalized, 'reply': reply,
                'phases_ns': {'configure_and_identity': configured-start, 'clone_or_bind': cloned-configured,
                              'execute_and_wait': executed-cloned, 'validate': validated-executed,
                              'recover_and_cleanup': start+elapsed-validated}}


def trial(mode, source, work, dependencies):
    start = time.perf_counter_ns()
    session = Session(mode, source, work, dependencies)
    try:
        rows = [session.request(event, index) for index, event in enumerate(TRACE)]
    finally:
        session.stop()
    # Count retained disk state before releasing the session's owned workspace.
    disk_bytes = sum(p.stat().st_size for p in work.rglob('*') if p.is_file())
    shutil.rmtree(work)
    elapsed = time.perf_counter_ns() - start
    return {'mode': mode, 'total_ns': elapsed, 'requests': rows, 'preparations': session.preparations,
            'generations': session.generation_count, 'restarts': session.restarts,
            'stale_rejections': session.stale_rejections, 'disk_bytes_before_disposal': disk_bytes}


def negative_control(work):
    """Demonstrate that a real fork leaves shared SQLite/media writes behind."""
    import sqlite3
    work.mkdir(); db = work / 'shared.sqlite3'; media = work / 'shared.txt'
    con = sqlite3.connect(db); con.execute('create table t (v text)'); con.commit(); con.close()
    media.write_text('before')
    pid = os.fork()
    if pid == 0:
        con = sqlite3.connect(db); con.execute("insert into t values ('committed')"); con.commit(); con.close()
        media.write_text('after')
        os._exit(0)  # Deliberately unsafe diagnostic, not a measured request.
    _, status = os.waitpid(pid, 0)
    assert status == 0
    con = sqlite3.connect(db); rows = con.execute('select v from t').fetchall(); con.close()
    assert rows == [('committed',)] and media.read_text() == 'after'
    shutil.rmtree(work)
    return {'fork_alone_leaks_committed_database_write': True, 'fork_alone_leaks_file_write': True}


def summarize(raw):
    groups = {m: [r for r in raw['trials'] if r['mode'] == m] for m in raw['modes']}
    result = {}
    for mode, rows in groups.items():
        result[mode] = {'trace_ms_median': statistics.median(r['total_ns']/1e6 for r in rows),
                        'trace_ms_min': min(r['total_ns']/1e6 for r in rows),
                        'trace_ms_max': max(r['total_ns']/1e6 for r in rows),
                        'events_ms_median': {event[0]: statistics.median(r['requests'][i]['elapsed_ns']/1e6 for r in rows)
                                             for i, event in enumerate(TRACE)},
                        'max_request_pss_mib': max((q['reply'].get('memory', {}).get('Pss_bytes', 0)/2**20
                                                   for r in rows for q in r['requests']), default=0),
                        'max_request_private_dirty_mib': max((q['reply'].get('memory', {}).get('Private_Dirty_bytes', 0)/2**20
                                                             for r in rows for q in r['requests']), default=0),
                        'max_combined_request_template_pss_mib': max(((q['reply'].get('memory', {}).get('Pss_bytes', 0)
                                                                   + q['reply'].get('parent_memory', {}).get('Pss_bytes', 0))/2**20
                                                                   for r in rows for q in r['requests']), default=0),
                        'max_template_pss_mib': max((p['memory']['Pss_bytes']/2**20 for r in rows for p in r['preparations']), default=0)}
    paired = {}
    if 'fork_seed' in groups:
        for mode, rows in groups.items():
            if mode == 'fork_seed':
                continue
            reductions = [100*(1-a['total_ns']/b['total_ns']) for a, b in zip(groups['fork_seed'], rows)]
            paired[mode] = {'percent_reduction_median': statistics.median(reductions),
                            'percent_reductions_by_block': reductions}
    return {'modes': result, 'fork_vs_controls': paired, 'blocks': raw['blocks'], 'trace_events': len(TRACE),
            'responses': len(raw['trials'])*len(TRACE)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--blocks', type=int, default=7)
    parser.add_argument('--modes', nargs='+', choices=MODES, default=list(MODES))
    parser.add_argument('--lock', type=Path)
    args = parser.parse_args()
    args.app, args.work, args.output = args.app.resolve(), args.work.resolve(), args.output.resolve()
    args.work.mkdir(parents=True, exist_ok=False); args.output.mkdir(parents=True, exist_ok=False)
    packages = dependency_manifest()
    interpreter = {'version': sys.version, 'binary_sha256': sha(Path(sys.executable))}
    dependency_id = digest({'packages': packages, 'interpreter': interpreter})
    source_identity = manifest(args.app)
    inputs = {p.name: sha(p) for p in HERE.glob('*.py')}
    raw = {'schema_version': 1, 'modes': args.modes, 'blocks': args.blocks, 'trials': []}
    validation = negative_control(args.work / 'negative-control')
    lock = args.lock.open('a+') if args.lock else None
    try:
        if lock:
            print('Waiting for cooperative measurement lock', flush=True); fcntl.flock(lock, fcntl.LOCK_EX)
        for block in range(args.blocks):
            modes = list(args.modes); random.Random(87291 + block).shuffle(modes)
            for mode in modes:
                print(f'block {block + 1}/{args.blocks} {mode}', flush=True)
                row = trial(mode, args.app, args.work / f'block-{block}-{mode}', dependency_id)
                row['block'] = block; raw['trials'].append(row)
                write_json(args.output / 'results.json', raw)
    finally:
        if lock:
            fcntl.flock(lock, fcntl.LOCK_UN); lock.close()
    assert inputs == {p.name: sha(p) for p in HERE.glob('*.py')}, 'harness changed during measurement'
    assert source_identity == manifest(args.app), 'upstream input changed during measurement'
    assert packages == dependency_manifest(), 'installed dependency bytes changed during measurement'
    # Same upstream test IDs, phase outcomes and independent probes across controls.
    reference = raw['trials'][0]['requests']
    for row in raw['trials']:
        for got, want in zip(row['requests'], reference):
            assert got['probe'] == want['probe']
            assert got['reply'].get('reports', []) == want['reply'].get('reports', [])
            assert got['reply']['exit'] == want['reply']['exit']
    validation.update({'all_responses_match': True, 'responses': len(raw['trials'])*len(TRACE),
                       'upstream_test_bodies_unchanged': True, 'normal_finalization_verified': True,
                       'failure_and_termination_recovery': True, 'template_artifacts_unchanged': True,
                       'real_source_and_settings_edits_verified': True,
                       'stale_template_rejections': sum(r['stale_rejections'] for r in raw['trials'])})
    write_json(args.output / 'validation.json', validation)
    write_json(args.output / 'summary.json', summarize(raw))
    write_json(args.output / 'raw-identity.json', {'path': 'results.json', 'bytes': (args.output/'results.json').stat().st_size,
                                                'sha256': sha(args.output/'results.json')})
    write_json(args.output / 'provenance.json', {'python': sys.version, 'executable': sys.executable,
               'platform': platform.platform(), 'machine': platform.machine(), 'packages': packages, 'interpreter': interpreter,
               'cpu': subprocess.check_output(['lscpu'], text=True),
               'filesystem': subprocess.check_output(['df', '-T', str(args.work)], text=True),
               'app': str(args.app), 'app_manifest': source_identity, 'harness_sha256': inputs,
               'finished_utc': datetime.now(timezone.utc).isoformat(), 'lock': str(args.lock),
               'clock': 'perf_counter_ns; full trace includes source copy, all preparations, cleanup and shutdown',
               'trace': TRACE, 'random_order_seed_base': 87291})
    print(json.dumps(summarize(raw), indent=2))


if __name__ == '__main__':
    main()
