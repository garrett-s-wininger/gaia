"""Bounded file/environment observation language plus three graph evaluators.

This is not a C preprocessor. Lookup candidates are explicit ordered names;
negative observations are retained until the first selected candidate.
"""
from collections import defaultdict, deque
from dataclasses import dataclass
import hashlib


@dataclass(frozen=True)
class Spec:
    lookups: tuple[tuple[str, ...], ...] = ()
    env: tuple[str, ...] = ()
    directories: tuple[str, ...] = ()
    deps: tuple[str, ...] = ()
    env_lookup: str | None = None


def sha(body):
    return hashlib.sha256(body).hexdigest()


def observe(spec, files, env):
    observations = set()
    values = set()
    lookups = list(spec.lookups)
    if spec.env_lookup:
        observations.add(('env', spec.env_lookup))
        lookups.append((env.get(spec.env_lookup, 'default') + '/selected.h',))
    for candidates in lookups:
        selected = False
        for name in candidates:
            observations.add(('file', name))
            if name in files:
                values.add(('file', name, sha(files[name])))
                selected = True
                break
        if not selected:
            values.add(('missing', repr(candidates), ''))
    for key in spec.env:
        observations.add(('env', key))
        values.add(('env', key, env.get(key, '<absent>')))
    for directory in spec.directories:
        observations.add(('dir', directory))
        prefix = directory.rstrip('/') + '/' if directory else ''
        members = sorted({name[len(prefix):].split('/', 1)[0] for name in files if name.startswith(prefix)})
        values.add(('dir', directory, sha(repr(members).encode())))
    return frozenset(values), frozenset(observations)


def reverse(specs):
    result = defaultdict(set)
    for name, spec in specs.items():
        for dep in spec.deps:
            if dep not in specs:
                raise ValueError('unknown node dependency: ' + dep)
            result[dep].add(name)
    return result


def closure_nodes(specs, root):
    seen = set()
    pending = [root]
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        pending.extend(specs[name].deps)
    return seen


def full_oracle(specs, files, env):
    local = {name: observe(spec, files, env)[0] for name, spec in specs.items()}
    return {root: frozenset(value for name in closure_nodes(specs, root) for value in local[name]) for root in specs}


class Engine:
    mode = 'full'
    def __init__(self, specs, files, env):
        self.specs = dict(specs)
        self.files = dict(files)
        self.env = dict(env)
        self.local = {}
        self.observations = {}
        self.watch = defaultdict(set)
        self.rev = reverse(self.specs)
        for name in self.specs:
            self._observe(name)
        self.outputs = full_oracle(self.specs, self.files, self.env)
        self.reachable = None
        if self.mode == 'relational':
            self._relations()

    def _observe(self, name):
        for token in self.observations.get(name, ()):
            self.watch[token].discard(name)
        self.local[name], self.observations[name] = observe(self.specs[name], self.files, self.env)
        for token in self.observations[name]:
            self.watch[token].add(name)

    def _relations(self):
        # Materialized root/node relation. Topology changes rebuild this closure;
        # data updates reuse it. This is not a Differential Dataflow engine.
        relation = {(name, name) for name in self.specs}
        delta = set(relation)
        while delta:
            next_delta = {(root, dep) for root, node in delta for dep in self.specs[node].deps} - relation
            relation |= next_delta
            delta = next_delta
        self.reachable = defaultdict(set)
        for root, node in relation:
            self.reachable[root].add(node)

    def update(self, files=None, env=None, specs=None):
        files, env, specs = files or {}, env or {}, specs or {}
        before = dict(self.outputs)
        tokens = {('file', name) for name in files} | {('env', key) for key in env}
        for name in files:
            parts = name.split('/')
            tokens.update(('dir', '/'.join(parts[:i])) for i in range(len(parts)))
        dirty = set(specs)
        for token in tokens:
            dirty.update(self.watch.get(token, ()))
        old_reverse = self.rev
        for name, body in files.items():
            if body is None:
                self.files.pop(name, None)
            else:
                self.files[name] = body
        for key, value in env.items():
            if value is None:
                self.env.pop(key, None)
            else:
                self.env[key] = value
        self.specs.update(specs)
        if specs:
            self.rev = reverse(self.specs)
        affected = set(dirty)
        queue = deque(dirty)
        while queue:
            node = queue.popleft()
            for parent in old_reverse.get(node, set()) | self.rev.get(node, set()):
                if parent not in affected:
                    affected.add(parent)
                    queue.append(parent)
        if self.mode == 'full':
            for name in self.specs:
                self._observe(name)
            self.outputs = full_oracle(self.specs, self.files, self.env)
            evaluated = len(self.specs)
        else:
            for name in dirty:
                self._observe(name)
            if self.mode == 'relational':
                if specs:
                    self._relations()
                for root in affected:
                    self.outputs[root] = frozenset(value for name in self.reachable[root] for value in self.local[name])
            else:
                values = {name: self.local[name] for name in affected}
                changed = True
                while changed:
                    changed = False
                    for name in sorted(affected):
                        new = self.local[name] | frozenset(value for dep in self.specs[name].deps for value in (values[dep] if dep in affected else self.outputs[dep]))
                        if values[name] != new:
                            values[name] = new
                            changed = True
                self.outputs = {**self.outputs, **values}
            evaluated = len(affected)
        changed_outputs = {name for name in self.specs if before.get(name, frozenset()) != self.outputs[name]}
        return {'observed_nodes': len(self.specs) if self.mode == 'full' else len(dirty), 'evaluated_nodes': evaluated,
                'selected_tests': sorted(n for n in changed_outputs if n.startswith('test:')),
                'selected_editor_queries': sorted(n for n in changed_outputs if n.startswith('editor:')),
                'changed_outputs': sorted(changed_outputs)}


class Frontier(Engine):
    mode = 'frontier'


class Relational(Engine):
    mode = 'relational'
