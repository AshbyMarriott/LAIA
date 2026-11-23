"""Unit tests for create-slot clarification title vs time detection."""

from __future__ import annotations

from laia.orchestrator.pipeline import _is_title_clarification
from laia.schemas.assistant import CreateEventSlots


def test_is_title_clarification_for_call_this_event_question() -> None:
    slots = CreateEventSlots(
        title=None,
        date_expression="July 14 2026",
        time_expression="2pm",
        clarification_question="What should I call this event?",
    )
    assert _is_title_clarification(slots) is True


def test_is_title_clarification_false_for_start_end_time_question() -> None:
    slots = CreateEventSlots(
        title=None,
        date_expression="07/17",
        end_date_expression="07/20",
        time_expression=None,
        needs_clarification=True,
        clarification_question="What time would you like to start and end?",
    )
    assert _is_title_clarification(slots) is False


def test_is_title_clarification_when_title_only_missing_slot() -> None:
    slots = CreateEventSlots(
        title=None,
        date_expression="July 14 2026",
        time_expression="2pm",
        clarification_question=None,
    )
    assert _is_title_clarification(slots) is True


def test_is_title_clarification_false_when_title_already_set() -> None:
    slots = CreateEventSlots(
        title="Camping",
        date_expression="July 14 2026",
        clarification_question="What should I call this event?",
    )
    assert _is_title_clarification(slots) is False
