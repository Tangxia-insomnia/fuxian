"""Per-path state, no join/phi and no mutation of historical value records."""
from dataclasses import dataclass, field
import copy


@dataclass
class StateEnvironment:
    path_id: str
    current: dict = field(default_factory=dict)
    counters: dict = field(default_factory=dict)
    guards: list = field(default_factory=list)
    termination: str | None = None
    invalidated_by: list = field(default_factory=list)

    def fork(self, path_id, guard):
        branch = copy.deepcopy(self)
        branch.path_id = path_id
        branch.guards.append(copy.deepcopy(guard))
        return branch

    def next_version(self, slot):
        number = self.counters.get(slot, -1)+1
        self.counters[slot] = number
        return number

    def invalidate(self, event_id):
        # Unknown effects are a barrier, never silently keep the previous current value.
        for slot in self.current:
            self.current[slot] = None
        self.invalidated_by.append(event_id)
        self.termination = 'UNKNOWN_EFFECT_STOP'

    def snapshot(self):
        return {'path_id':self.path_id, 'current':dict(self.current),
                'guards':copy.deepcopy(self.guards), 'termination':self.termination,
                'invalidated_by':list(self.invalidated_by)}
