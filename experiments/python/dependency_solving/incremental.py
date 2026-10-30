"""Experimental dirty-criterion scheduler for the pinned resolvelib 1.2.1 core.

Resolve-loop/control-flow adaptations derive from resolvelib; see
LICENSE.resolvelib. Candidate validation, backjumping, optimistic rollback,
result construction and full state copies remain the upstream implementation.

Only this experiment's stable lexical preference is supported. A generic
provider with state-dependent priorities needs additional invalidation semantics.
"""
from collections import Counter, OrderedDict
import heapq

from pip._vendor.resolvelib import __version__
from pip._vendor.resolvelib.resolvers.resolution import Resolution, _build_result
from pip._vendor.resolvelib.resolvers.criterion import Criterion
from pip._vendor.resolvelib.resolvers.exceptions import RequirementsConflicted, ResolutionImpossible, ResolutionTooDeep
from pip._vendor.resolvelib.structs import State


class IncrementalResolution(Resolution):
    def __init__(self, provider, reporter, *, audit=False):
        if __version__ != "1.2.1":
            raise RuntimeError("incremental adapter requires the pinned resolvelib 1.2.1 internals")
        if provider.session.heuristic:
            raise ValueError("incremental queue currently requires stable lexical preference")
        super().__init__(provider, reporter)
        self.work = Counter()
        self.pending, self.queued, self.heap = set(), set(), []
        self.changed = set()
        self.audit = audit

    def _audit_queue(self):
        # Test-only full-scan oracle; deliberately disabled in measurements.
        expected = {name for name, criterion in self.state.criteria.items()
                    if not self._is_current_pin_satisfying(name, criterion)}
        if expected != self.pending or set(self.heap) != self.queued or len(self.heap) != len(self.queued):
            raise AssertionError("incremental queue differs from full criterion scan")
        if not self.pending.issubset(self.queued):
            raise AssertionError("pending criteria missing from heap")

    def _push_new_state(self):
        self.work["state_copies"] += 1
        base = self._states[-1]
        self.work["map_entries_copied"] += len(base.mapping) + len(base.criteria)
        super()._push_new_state()

    def _save_state(self):
        if self._save_states is None:
            self.work["optimistic_state_saves"] += 1
            self.work["map_entries_copied"] += sum(len(s.mapping) + len(s.criteria) for s in self._states)
        super()._save_state()

    def _rollback_states(self):
        self.work["optimistic_rollbacks"] += 1
        super()._rollback_states()

    def _mark_pending(self, name):
        self.pending.add(name)
        if name not in self.queued:
            heapq.heappush(self.heap, name)
            self.queued.add(name)
            self.work["queue_pushes"] += 1

    def _refresh(self, name):
        self.work["criterion_checks"] += 1
        satisfied = self._is_current_pin_satisfying(name, self.state.criteria[name])
        if satisfied:
            self.pending.discard(name)
        else:
            self._mark_pending(name)
        return satisfied

    def _rebuild(self):
        # Backjump/rollback can swap whole saved states; conservatively rebuild.
        self.work["queue_rebuilds"] += 1
        self.pending.clear(); self.queued.clear(); self.heap.clear()
        for name in self.state.criteria:
            self._refresh(name)

    def _next_pending(self):
        while self.heap:
            name = heapq.heappop(self.heap)
            self.queued.remove(name)
            self.work["queue_pops"] += 1
            if name in self.pending:
                return name
            self.work["stale_queue_pops"] += 1
        raise RuntimeError("pending criterion missing from queue")

    def _get_updated_criteria(self, candidate):
        # Preserve upstream copy-on-attempt and dependency insertion order.
        criteria = self.state.criteria.copy()
        self.work["candidate_criteria_copies"] += 1
        self.work["map_entries_copied"] += len(self.state.criteria)
        changed = set()
        for requirement in self._p.get_dependencies(candidate=candidate):
            self._add_to_criteria(criteria, requirement, parent=candidate)
            changed.add(self._p.identify(requirement))
        # Failed attempts never publish their changed-key set or temporary map.
        self.changed = changed
        return criteria

    def _prune_parent_information(self, parents):
        self.work["information_pruning_scans"] += 1
        changed = set()
        for name, criterion in self.state.criteria.items():
            information = [i for i in criterion.information
                           if i.parent is None or self._p.identify(i.parent) not in parents]
            if len(information) != len(criterion.information):
                self.state.criteria[name] = Criterion(criterion.candidates, information, criterion.incompatibilities)
                changed.add(name)
        return changed

    def resolve(self, requirements, max_rounds):
        if self._states:
            raise RuntimeError("already resolved")
        self._r.starting()
        self._states = [State(mapping=OrderedDict(), criteria={}, backtrack_causes=[])]
        for requirement in requirements:
            try:
                self._add_to_criteria(self.state.criteria, requirement, parent=None)
            except RequirementsConflicted as error:
                raise ResolutionImpossible(error.criterion.information) from error
        self._push_new_state()
        self._rebuild()
        optimistic_rounds_cutoff = None
        optimistic_backjumping_start_round = None
        for round_index in range(max_rounds):
            self._r.starting_round(index=round_index)
            # Preserve upstream optimistic-backjump budget and restoration.
            if self._optimistic_backjumping_ratio and self._save_states is not None:
                if optimistic_backjumping_start_round is None:
                    optimistic_backjumping_start_round = round_index
                    optimistic_rounds_cutoff = int((max_rounds-round_index)*self._optimistic_backjumping_ratio)
                    if optimistic_rounds_cutoff <= 0:
                        self._rollback_states(); self._rebuild()
                        continue
                elif round_index-optimistic_backjumping_start_round >= optimistic_rounds_cutoff:
                    self._rollback_states(); self._rebuild()
                    continue
            if self.audit:
                self._audit_queue()
            if not self.pending:
                self._r.ending(state=self.state)
                return self.state
            name = self._next_pending()
            failure = self._attempt_to_pin_criterion(name)
            if failure:
                causes = self._extract_causes(failure)
                self._r.resolving_conflicts(causes=causes)
                self.work["backjumps"] += 1
                try:
                    success = self._backjump(causes)
                except ResolutionImpossible:
                    if self._optimistic_backjumping_ratio and self._save_states:
                        failed_optimistic_backjumping = True
                    else:
                        raise
                else:
                    failed_optimistic_backjumping = bool(not success and self._optimistic_backjumping_ratio and self._save_states)
                if failed_optimistic_backjumping and self._save_states:
                    self._rollback_states()
                else:
                    self.state.backtrack_causes[:] = causes
                    if not success:
                        raise ResolutionImpossible(self.state.backtrack_causes)
                self._rebuild()
            else:
                # Upstream just validated this candidate against the old criterion.
                # A self-dependency may have changed it; refresh that case below.
                self.pending.discard(name)
                invalidated = set()
                for changed in self.changed:
                    was_satisfied = changed != name and changed in self.state.mapping and changed not in self.pending
                    if not self._refresh(changed) and was_satisfied:
                        invalidated.add(changed)
                if invalidated:
                    for changed in self._prune_parent_information(invalidated):
                        self._refresh(changed)
                self._push_new_state()
            self._r.ending_round(index=round_index, state=self.state)
        raise ResolutionTooDeep(max_rounds)


class IncrementalResolver:
    def __init__(self, provider, reporter):
        self.provider, self.reporter, self.work = provider, reporter, {}

    def resolve(self, requirements, max_rounds=100):
        resolution = IncrementalResolution(self.provider, self.reporter)
        try:
            state = resolution.resolve(requirements, max_rounds)
            return _build_result(state)
        finally:
            self.work = dict(resolution.work)
