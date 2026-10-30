"""Reversible map histories for the pinned incremental resolver experiment.

Saved maps are constant-size version handles into one mutable store. Switching
versions undoes/redoes only intervening mutations, including insertion order.
Criterion values remain upstream immutable-by-convention replacement objects.
Resolver control flow derives from resolvelib; see LICENSE.resolvelib.
"""
from collections.abc import Mapping, MutableMapping

from incremental import IncrementalResolution
from pip._vendor.resolvelib.resolvers.resolution import Resolution, _build_result
from pip._vendor.resolvelib.structs import State


_MISSING = object()


class Version:
    __slots__ = ('parent', 'depth', 'key', 'before', 'after')

    def __init__(self, parent=None, key=None, before=None, after=None):
        self.parent = parent
        self.depth = parent.depth + 1 if parent else 0
        self.key, self.before, self.after = key, before, after


class Store:
    def __init__(self, work):
        self.work = work
        self.entries = {}
        self.end = object()
        self.first = self.last = self.end
        self.current = Version()

    def replace(self, key, entry):
        """Apply an exact entry (value, previous key, next key), or absence."""
        if key in self.entries:
            _, previous, following = self.entries.pop(key)
            if previous is self.end:self.first = following
            else:self.entries[previous][2] = following
            if following is self.end:self.last = previous
            else:self.entries[following][1] = previous
        if entry is not _MISSING:
            value, previous, following = entry
            self.entries[key] = [value, previous, following]
            if previous is self.end:self.first = key
            else:self.entries[previous][2] = key
            if following is self.end:self.last = key
            else:self.entries[following][1] = key

    def checkout(self, target):
        current = self.current
        forward = []
        while current is not target:
            if current.depth >= target.depth:
                self.replace(current.key, current.before)
                self.work['trail_undos'] += 1
                current = current.parent
            else:
                forward.append(target)
                target = target.parent
        for version in reversed(forward):
            self.replace(version.key, version.after)
            self.work['trail_redos'] += 1
            current = version
        self.current = current


class TrailMap(MutableMapping):
    def __init__(self, work, source=()):
        self.store = Store(work)
        self.version = self.store.current
        self.update(source)

    def _entries(self):
        self.store.checkout(self.version)
        return self.store.entries

    def __getitem__(self, key):
        return self._entries()[key][0]

    def __len__(self):
        return len(self._entries())

    def __iter__(self):
        self._entries()
        key = self.store.first
        while key is not self.store.end:
            # Reactivate for callers that read another saved map mid-iteration.
            entries = self._entries()
            following = entries[key][2]
            yield key
            key = following

    def _write(self, key, value):
        entries = self._entries()
        before = tuple(entries[key]) if key in entries else _MISSING
        if value is _MISSING:
            if before is _MISSING:raise KeyError(key)
            after = _MISSING
        elif before is _MISSING:
            after = (value, self.store.last, self.store.end)
        else:
            after = (value, before[1], before[2])
        self.store.replace(key, after)
        self.version = Version(self.version, key, before, after)
        self.store.current = self.version
        self.store.work['trail_mutations'] += 1

    def __setitem__(self, key, value):self._write(key, value)
    def __delitem__(self, key):self._write(key, _MISSING)

    def popitem(self):
        self._entries()
        if self.store.last is self.store.end:raise KeyError('empty map')
        key = self.store.last
        value = self[key]
        del self[key]
        return key, value

    def copy(self):
        result = object.__new__(TrailMap)
        result.store, result.version = self.store, self.version
        self.store.work['map_version_handles'] += 1
        return result


class Overlay(Mapping):
    """Candidate-local replacements; no mutation or copy of the base map."""
    def __init__(self, base):self.base, self.delta = base, {}
    def __getitem__(self, key):
        return self.delta[key] if key in self.delta else self.base[key]
    def __setitem__(self, key, value):self.delta[key] = value
    def __iter__(self):
        yield from self.base
        yield from (k for k in self.delta if k not in self.base)
    def __len__(self):return len(self.base) + sum(k not in self.base for k in self.delta)


class TrailResolution(IncrementalResolution):
    def _push_new_state(self):
        base = self._states[-1]
        if not isinstance(base.mapping, TrailMap):
            base = State(TrailMap(self.work, base.mapping), TrailMap(self.work, base.criteria), base.backtrack_causes)
            self._states[-1] = base
        self.work['decision_checkpoints'] += 1
        self.work['backtrack_cause_entries_copied'] += len(base.backtrack_causes)
        self._states.append(State(base.mapping.copy(), base.criteria.copy(), base.backtrack_causes[:]))

    def _save_state(self):
        if self._save_states is None:
            self.work['optimistic_state_saves'] += 1
            self.work['optimistic_state_handles'] += len(self._states)
            self.work['backtrack_cause_entries_copied'] += sum(len(s.backtrack_causes) for s in self._states)
        # Upstream copy() calls create version handles, not full map snapshots.
        Resolution._save_state(self)

    def _get_updated_criteria(self, candidate):
        criteria = Overlay(self.state.criteria)
        self.work['candidate_overlays'] += 1
        for requirement in self._p.get_dependencies(candidate=candidate):
            self._add_to_criteria(criteria, requirement, parent=candidate)
        self.changed = set(criteria.delta)
        self.work['candidate_delta_entries'] += len(criteria.delta)
        return criteria.delta


class TrailResolver:
    def __init__(self, provider, reporter):
        self.provider, self.reporter, self.work = provider, reporter, {}

    def resolve(self, requirements, max_rounds=100):
        resolution = TrailResolution(self.provider, self.reporter)
        try:return _build_result(resolution.resolve(requirements, max_rounds))
        finally:self.work = dict(resolution.work)
