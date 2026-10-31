"""Small partial source-operation algebra; snapshots remain authoritative."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Entry:
    kind: str
    body: bytes
    executable: bool = False

    def __post_init__(self):
        if self.kind not in ('file', 'link') or (self.kind == 'link' and self.executable):
            raise ValueError('unsupported entry')


@dataclass(frozen=True)
class Edit:
    path: str
    before: Entry | None
    after: Entry | None


def valid(snapshot):
    for path, entry in snapshot.items():
        if not path or path.startswith('/') or '\x00' in path or any(p in ('', '.', '..') for p in path.split('/')):
            raise ValueError('invalid path')
        if not isinstance(entry, Entry):
            raise ValueError('invalid entry')
        parent = path
        while '/' in parent:
            parent = parent.rsplit('/', 1)[0]
            if parent in snapshot:
                raise ValueError('ancestor collision')
    return snapshot


def apply(snapshot, patch):
    valid(snapshot)
    result = dict(snapshot)
    for edit in patch:
        if result.get(edit.path) != edit.before:
            raise ValueError('patch context mismatch')
        if edit.after is None:
            result.pop(edit.path, None)
        else:
            result[edit.path] = edit.after
        valid(result)
    return result


def inverse(patch):
    return tuple(Edit(e.path, e.after, e.before) for e in reversed(patch))


def compose(first, second):
    # Composition retains intermediate contexts, including invalid-prefix checks.
    return tuple(first) + tuple(second)


def commute(first, second):
    """Prove only path-independent swaps; absence/type/domain checks stay live."""
    for a in first:
        for b in second:
            if a.path == b.path or a.path.startswith(b.path + '/') or b.path.startswith(a.path + '/'):
                return None
    return tuple(second), tuple(first)


def join_facts(left, right):
    return frozenset(left) | frozenset(right)


def alternatives(facts, generation, key):
    return frozenset(value for gen, name, value in facts if gen == generation and name == key)


class Target:
    """Coordination boundary; a converged request set does not publish a head."""
    def __init__(self):
        self.generation = 0
        self.head = None

    def publish(self, expected_generation, head):
        if expected_generation != self.generation:
            return False
        self.head = head
        self.generation += 1
        return True
