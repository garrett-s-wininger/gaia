"""Current source plus explicitly historical native test-execution evidence."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def source_snapshot(root):
    root = Path(root)
    files = {}
    for area in ('src', 'tests'):
        for path in sorted((root/area).rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix not in ('.pyc', '.pyo'):
                files[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ('pyproject.toml', 'setup.cfg', 'pytest.ini', 'conftest.py'):
        path = root/name
        if path.exists():
            files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def generation(root, context):
    return digest({'files': source_snapshot(root), 'context': context})


def symbols(source):
    """Python's parser supplies lexical body spans, not runtime call edges."""
    tree = ast.parse(source)
    result = {}
    class Visitor(ast.NodeVisitor):
        def __init__(self):
            self.scope = []
        def visit_ClassDef(self, node):
            self.scope.append(node.name); self.generic_visit(node); self.scope.pop()
        def visit_FunctionDef(self, node):
            self.scope.append(node.name)
            name = '.'.join(self.scope)
            result[name] = {'line': node.lineno, 'body_line': node.body[0].lineno,
                            'end_line': node.end_lineno,
                            'body_identity': digest(ast.dump(node, include_attributes=False))}
            self.generic_visit(node); self.scope.pop()
        visit_AsyncFunctionDef = visit_FunctionDef
    Visitor().visit(tree)
    return result


def observed_symbols(definitions, lines):
    # Credit a covered line to the innermost function body containing it.
    found = set()
    ordered = sorted(definitions.items(), key=lambda item: item[1]['end_line']-item[1]['body_line'])
    for line in lines:
        for name, info in ordered:
            if info['body_line'] <= line <= info['end_line']:
                found.add(name); break
    return sorted(found)


class EvidenceStore:
    def __init__(self, root, context, path=None):
        self.root, self.context = Path(root).resolve(), context
        self.runs = []
        if path and Path(path).exists():
            data = json.loads(Path(path).read_text())
            if data['context'] != context:
                raise ValueError('evidence context differs')
            self.runs = data['runs']

    def current(self):
        return generation(self.root, self.context)

    def publish(self, run):
        if run['context'] != self.context or run['generation'] != self.current():
            raise ValueError('refusing result from a different source/configuration generation')
        if not run['unchanged_during_run']:
            raise ValueError('source changed while validation ran')
        self.runs.append(run)

    def save(self, path):
        Path(path).write_text(json.dumps({'schema_version': 1, 'context': self.context, 'runs': self.runs}, sort_keys=True)+'\n')

    def inspect(self, filename, symbol, expected=None, focus='', limit=20):
        current = self.current()
        if expected is not None and expected != current:
            raise ValueError('stale query generation')
        path = (self.root/filename).resolve()
        if not path.is_relative_to(self.root/'src') or not filename.startswith('src/'):
            raise ValueError('source path outside admitted project')
        text = path.read_text()
        try:
            definitions = symbols(text)
        except SyntaxError as e:
            return {'generation': current, 'status': 'incomplete-source', 'line': e.lineno,
                    'observations': [], 'complete_impact_set': False}
        if symbol not in definitions:
            return {'generation': current, 'status': 'absent', 'observations': [], 'complete_impact_set': False}
        info = definitions[symbol]
        observations = []
        key = filename+'::'+symbol
        # One latest observation per test, with the generation that produced it.
        seen = set()
        for run in reversed(self.runs):
            for nodeid, facts in run.get('observed', {}).items():
                if nodeid in seen or key not in facts:
                    continue
                seen.add(nodeid)
                old = run['functions'][key]
                observations.append({'test': nodeid, 'observed_generation': run['generation'],
                                     'status': 'current' if run['generation'] == current else 'historical',
                                     'same_function_ast': old['body_identity'] == info['body_identity'],
                                     'observed_line': old['line'],
                                     'outcome': run['outcomes'].get(nodeid, 'unknown')})
        observations.sort(key=lambda x:(x['status'] != 'current', bool(focus) and focus.lower() not in x['test'].lower(), x['test']))
        lines = text.splitlines()
        if self.current() != current:
            raise ValueError('source changed during inspection')
        return {'generation': current, 'status': 'current-source', 'file': filename, 'symbol': symbol,
                'source_sha256': hashlib.sha256(text.encode()).hexdigest(), **info,
                'excerpt': '\n'.join(lines[info['line']-1:min(info['end_line'],info['line']+79)]),
                'excerpt_truncated': info['end_line'] >= info['line']+80,
                'observations': observations[:limit], 'observation_count':len(observations),
                'current_count':sum(o['status']=='current' for o in observations),
                'observations_truncated':len(observations)>limit, 'complete_impact_set': False,
                'meaning': 'Execution observed under these test contexts in this lexical function body. Deferred callbacks can be attributed here. Not a complete impact or bug-detection proof.'}

    def search(self, query, limit=30):
        before = self.current()
        cmd = ['rg', '--json', '-i', '-F', '--glob', '*.py', '--', query, 'src', 'tests']
        run = subprocess.run(cmd, cwd=self.root, text=True, capture_output=True, check=False)
        if run.returncode not in (0,1):
            raise RuntimeError(run.stderr)
        matches = []
        for line in run.stdout.splitlines():
            entry=json.loads(line)
            if entry['type']=='match':
                d=entry['data']; matches.append({'file':d['path']['text'], 'line':d['line_number'], 'text':d['lines']['text'].rstrip()})
        if self.current() != before:
            raise ValueError('source changed during search')
        return {'generation':before, 'origin':'ripgrep literal search', 'matches':matches[:limit],
                'total_matches':len(matches), 'truncated':len(matches)>limit}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True);p.add_argument('--store',type=Path,required=True)
    p.add_argument('--context',required=True)
    sub=p.add_subparsers(dest='command',required=True)
    search=sub.add_parser('search');search.add_argument('query')
    inspect=sub.add_parser('inspect');inspect.add_argument('file');inspect.add_argument('symbol')
    inspect.add_argument('--focus',default='');inspect.add_argument('--limit',type=int,default=20)
    a=p.parse_args();store=EvidenceStore(a.root,a.context,a.store)
    response=store.search(a.query) if a.command=='search' else store.inspect(a.file,a.symbol,focus=a.focus,limit=a.limit)
    print(json.dumps(response,indent=2))


if __name__=='__main__':main()
