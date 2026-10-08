"""Bounded process-local conversations, with nonblocking per-conversation leases."""
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import Lock
from ..services.meal_engine import create_meal


class StoreError(Exception):
    def __init__(self, code):
        self.code = code


@dataclass
class Conversation:
    state: dict = field(default_factory=create_meal)
    history: list = field(default_factory=list)
    cart: list = field(default_factory=list)
    cart_confirmed: bool = False
    cart_mode: bool = False
    revision: int = 0
    busy: bool = False


def history_window(history):
    """Keep whole user/assistant pairs within the existing provider contract."""
    window = list(history[-40:])
    while sum(len(m['content']) for m in window) > 16000:
        del window[:2]
    return window


class ConversationStore:
    def __init__(self, capacity=1000):
        self._entries = {}
        self._lock = Lock()
        self.capacity = capacity

    @contextmanager
    def lease(self, conversation_id):
        with self._lock:
            entry = self._entries.get(conversation_id)
            if entry is None:
                if len(self._entries) >= self.capacity:
                    raise StoreError('CONVERSATION_CAPACITY')
                entry = self._entries[conversation_id] = Conversation()
            if entry.busy:
                raise StoreError('CONVERSATION_BUSY')
            entry.busy = True
        try:
            yield entry
        finally:
            with self._lock:
                entry.busy = False

    def delete(self, conversation_id):
        with self._lock:
            entry = self._entries.get(conversation_id)
            if entry and entry.busy:
                raise StoreError('CONVERSATION_BUSY')
            return self._entries.pop(conversation_id, None) is not None
