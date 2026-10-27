"""Bounded, conversation-scoped focus for follow-up workflow questions."""
from collections import OrderedDict
from threading import RLock
from time import monotonic


class WorkflowQueryFocus:
    def __init__(self, ttl_seconds=3600, max_sessions=500, clock=monotonic):
        self.ttl_seconds = ttl_seconds
        self.max_sessions = max_sessions
        self.clock = clock
        self._items = OrderedDict()
        self._lock = RLock()

    def get(self, conversation_id):
        with self._lock:
            item = self._items.get(conversation_id)
            if item is None:
                return None
            identifier, accessed = item
            if self.clock() - accessed >= self.ttl_seconds:
                self._items.pop(conversation_id, None)
                return None
            self._items[conversation_id] = (identifier, self.clock())
            self._items.move_to_end(conversation_id)
            return identifier

    def set(self, conversation_id, workflow_id):
        with self._lock:
            self._items[conversation_id] = (workflow_id, self.clock())
            self._items.move_to_end(conversation_id)
            while len(self._items) > self.max_sessions:
                self._items.popitem(last=False)

    def clear(self, conversation_id):
        with self._lock:
            self._items.pop(conversation_id, None)


workflow_query_focus = WorkflowQueryFocus()
