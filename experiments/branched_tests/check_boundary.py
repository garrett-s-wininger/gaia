"""Distinguish private heap branches from warm reuse after successful effects."""
import argparse
import json
from pathlib import Path
import shutil

from run import Session, NORMAL, read_reply, write_json


def operation(session, index, test):
    branch = session.work / f'probe-{index}'
    branch.mkdir()
    shutil.copyfile(session.seed / 'test.sqlite3', branch / 'test.sqlite3')
    shutil.copytree(session.seed / 'media', branch / 'media')
    request = {'generation': session.generation, 'branch': str(branch), 'database': str(branch / 'test.sqlite3'),
               'fault': '', 'tests': [test]}
    session.server.stdin.write(json.dumps(request) + '\n'); session.server.stdin.flush()
    result = read_reply(session.server, session.server_log)
    return result


def main():
    p = argparse.ArgumentParser(); p.add_argument('--app', type=Path, required=True)
    p.add_argument('--work', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(); args.work.mkdir(parents=True, exist_ok=False)
    results = {}
    for mode in ('warm_seed', 'fork_seed'):
        session = Session(mode, args.app.resolve(), args.work.resolve()/mode, 'diagnostic-immutable-environment')
        try:
            session.configure('original', '0')
            dirty = operation(session, 0, 'todo/tests/test_gaia_boundary.py::test_successful_effects')
            assert dirty['exit'] == 0, dirty
            after = operation(session, 1, NORMAL)
            assert after['exit'] == (1 if mode == 'warm_seed' else 0), after
            if mode == 'warm_seed':
                assert '_gaia_leaked_heap' in after['log'], after
                session.stop(); session.restarts += 1; session.start_server(make_seed=False)
                recovered = operation(session, 2, NORMAL)
                assert recovered['exit'] == 0, recovered
            else:
                recovered = None
            # An unannounced edit must fail admission before the next request.
            session.models.write_text(session.original + '\n# unannounced edit\n')
            try:
                session.configure('original', '0')
            except AssertionError as e:
                assert 'unannounced' in str(e)
            else:
                raise AssertionError('unannounced change was reused')
            results[mode] = {'successful_mutating_request': dirty, 'following_request': after,
                             'after_explicit_restart': recovered, 'unannounced_source_edit_rejected': True}
        finally:
            session.stop()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, results)
    shutil.rmtree(args.work)
    print('Passed: fork discards successful heap mutations; warm worker needs an explicit restart; source admission rejects unannounced changes.')


if __name__ == '__main__':
    main()
