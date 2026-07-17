"""In-memory conversation state with TTL."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from laia.config import get_settings

PendingType = Literal["disambiguation", "confirmation", "slot_clarification"]


@dataclass
class ConversationState:
    conversation_id: str
    pending_type: PendingType | None = None
    command: str | None = None
    candidate_event_ids: list[str] = field(default_factory=list)
    target_event_id: str | None = None
    event_snapshot: dict[str, Any] | None = None
    pending_slots: dict[str, Any] | None = None
    options: list[dict[str, str]] = field(default_factory=list)
    expires_at: float = 0.0

    def is_expired(self, now: float | None = None) -> bool:
        return (now or time.time()) >= self.expires_at


class ConversationStore:
    def __init__(self, ttl_minutes: int | None = None) -> None:
        settings = get_settings()
        self._ttl_seconds = (ttl_minutes or settings.conversation_ttl_minutes) * 60
        self._states: dict[str, ConversationState] = {}
        self._lock = threading.Lock()

    def _purge(self) -> None:
        now = time.time()
        expired = [cid for cid, state in self._states.items() if state.is_expired(now)]
        for cid in expired:
            del self._states[cid]

    def get(self, conversation_id: str) -> ConversationState | None:
        with self._lock:
            self._purge()
            state = self._states.get(conversation_id)
            if state is None or state.is_expired():
                self._states.pop(conversation_id, None)
                return None
            return state

    def get_or_create(self, conversation_id: str | None = None) -> ConversationState:
        with self._lock:
            self._purge()
            if conversation_id and conversation_id in self._states:
                state = self._states[conversation_id]
                if not state.is_expired():
                    state.expires_at = time.time() + self._ttl_seconds
                    return state
            cid = conversation_id or f"conv_{uuid.uuid4().hex[:12]}"
            state = ConversationState(
                conversation_id=cid,
                expires_at=time.time() + self._ttl_seconds,
            )
            self._states[cid] = state
            return state

    def clear_pending(self, conversation_id: str) -> None:
        state = self.get(conversation_id)
        if state is None:
            return
        state.pending_type = None
        state.command = None
        state.candidate_event_ids = []
        state.target_event_id = None
        state.event_snapshot = None
        state.pending_slots = None
        state.options = []
        state.expires_at = time.time() + self._ttl_seconds

    def set_pending(
        self,
        conversation_id: str,
        *,
        pending_type: PendingType,
        command: str | None = None,
        candidate_event_ids: list[str] | None = None,
        target_event_id: str | None = None,
        event_snapshot: dict[str, Any] | None = None,
        pending_slots: dict[str, Any] | None = None,
        options: list[dict[str, str]] | None = None,
    ) -> ConversationState:
        state = self.get_or_create(conversation_id)
        state.pending_type = pending_type
        state.command = command
        state.candidate_event_ids = candidate_event_ids or []
        state.target_event_id = target_event_id
        state.event_snapshot = event_snapshot
        state.pending_slots = pending_slots
        state.options = options or []
        state.expires_at = time.time() + self._ttl_seconds
        return state


_store: ConversationStore | None = None


def get_conversation_store() -> ConversationStore:
    global _store
    if _store is None:
        _store = ConversationStore()
    return _store
