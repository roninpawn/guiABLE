from dataclasses import dataclass
from time import monotonic


@dataclass
class _EditGroup:
    operation: str
    edge: int
    size: int


class EditHistory:
    _continuous = ("insert", "backspace", "delete")

    def __init__(self, max_events:int=100, idle_timeout:int=1200,
                 min_group_size:int=3, max_group_size:int=128):

        self._max_events = max(1, int(max_events))
        self._idle_seconds = max(0, int(idle_timeout)) / 1000
        self._min_group_size = max(1, int(min_group_size))
        self._max_group_size = max(1, int(max_group_size))

        self._undo = []
        self._redo = []

        self._group = None
        self._last_edit = 0.0

    def maxEvents(self, count:int=None) -> int:
        if count is not None:
            self._max_events = max(1, int(count))

            if len(self._undo) > self._max_events:
                del self._undo[:-self._max_events]

            if len(self._redo) > self._max_events:
                del self._redo[:-self._max_events]

        return self._max_events

    def idleTimeout(self, milliseconds:int=None) -> int:
        if milliseconds is not None:
            self._idle_seconds = max(0, int(milliseconds)) / 1000

        return round(self._idle_seconds * 1000)

    def minGroupSize(self, size:int=None) -> int:
        if size is not None: self._min_group_size = max(1, int(size))
        return self._min_group_size

    def maxGroupSize(self, size:int=None) -> int:
        if size is not None: self._max_group_size = max(1, int(size))
        return self._max_group_size

    def canUndo(self) -> bool: return bool(self._undo)
    def canRedo(self) -> bool: return bool(self._redo)

    def record(self, snapshot, operation:str, position:int, removed:int=0, inserted:str=""):
        now = monotonic()

        if self._group is not None:
            if self._groupExpired(now) or self._group.size >= self._max_group_size:
                self.breakGroup()

        continuous = self._isContinuous(operation, removed, inserted)

        if not continuous or not self._compatible(operation, position, removed):
            self.breakGroup()
            self._push(self._undo, snapshot)
            self._redo.clear()

            if continuous:
                self._group = _EditGroup(
                    operation,
                    self._nextEdge(operation, position, removed, inserted),
                    self._editSize(removed, inserted)
                )

        else:
            self._group.edge = self._nextEdge(operation, position, removed, inserted)
            self._group.size += self._editSize(removed, inserted)

        self._last_edit = now

        if not continuous: self.breakGroup()

    def undo(self, current_snapshot):
        self.breakGroup()
        if not self._undo: return None

        snapshot = self._undo.pop()
        self._push(self._redo, current_snapshot)
        return snapshot

    def redo(self, current_snapshot):
        self.breakGroup()
        if not self._redo: return None

        snapshot = self._redo.pop()
        self._push(self._undo, current_snapshot)
        return snapshot

    def breakGroup(self):
        self._group = None
        self._last_edit = 0.0

    def clear(self):
        self._undo.clear()
        self._redo.clear()
        self.breakGroup()

    def _groupExpired(self, now:float) -> bool:
        return self._group.size >= self._min_group_size and now - self._last_edit >= self._idle_seconds

    def _compatible(self, operation:str, position:int, removed:int) -> bool:
        if self._group is None or self._group.operation != operation: return False

        if operation == "insert": return position == self._group.edge
        if operation == "backspace": return position + removed == self._group.edge
        if operation == "delete": return position == self._group.edge
        return False

    @classmethod
    def _isContinuous(cls, operation:str, removed:int, inserted:str) -> bool:
        if operation not in cls._continuous: return False
        if operation == "insert": return removed == 0 and len(inserted) == 1
        return removed == 1 and not inserted

    @staticmethod
    def _nextEdge(operation:str, position:int, removed:int, inserted:str) -> int:
        if operation == "insert": return position + len(inserted)
        return position

    @staticmethod
    def _editSize(removed:int, inserted:str) -> int:
        return max(removed, len(inserted), 1)

    def _push(self, stack:list, snapshot):
        if stack and stack[-1] == snapshot: return

        stack.append(snapshot)
        if len(stack) > self._max_events: stack.pop(0)
