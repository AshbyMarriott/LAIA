"""Conversation store unit tests."""

from __future__ import annotations

import time

from laia.services.conversation import ConversationStore


def test_ttl_expiry() -> None:
    store = ConversationStore(ttl_minutes=0)  # expires immediately after set with 0 minutes
    # Use internal seconds override for a short TTL
    store._ttl_seconds = 1
    state = store.get_or_create()
    cid = state.conversation_id
    store.set_pending(cid, pending_type="confirmation", command="delete_event", target_event_id="x")
    assert store.get(cid) is not None
    time.sleep(1.1)
    assert store.get(cid) is None


def test_clear_pending() -> None:
    store = ConversationStore(ttl_minutes=15)
    state = store.get_or_create()
    store.set_pending(
        state.conversation_id,
        pending_type="disambiguation",
        command="get_event",
        candidate_event_ids=["a", "b"],
    )
    store.clear_pending(state.conversation_id)
    refreshed = store.get(state.conversation_id)
    assert refreshed is not None
    assert refreshed.pending_type is None
    assert refreshed.candidate_event_ids == []
