"""Orchestrator tests with mocked Ollama (create/search + safety flows)."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from laia.orchestrator.pipeline import Orchestrator
from laia.schemas.assistant import CommandName
from laia.schemas.events import EventCreate
from laia.services.calendar import CalendarService
from laia.services.conversation import ConversationStore
from tests.fakes import (
    FakeOllama,
    classify,
    confirm,
    create_slots,
    delete_slots,
    get_slots,
    search_slots,
    update_slots,
)


@pytest.fixture
def store() -> ConversationStore:
    return ConversationStore(ttl_minutes=15)


@pytest.mark.asyncio
async def test_create_event_happy_path(session: AsyncSession, store: ConversationStore) -> None:
    fake = FakeOllama(
        [
            classify(CommandName.CREATE_EVENT),
            create_slots(
                title="Dentist appointment",
                date_expression="July 14 2026",
                time_expression="2pm",
                duration_minutes=60,
            ),
        ]
    )
    orch = Orchestrator(session, ollama=fake, store=store)  # type: ignore[arg-type]
    response = await orch.handle(message="Schedule dentist next Tuesday at 2pm")
    assert response.action is not None
    assert response.action.command == "create_event"
    assert "Dentist" in response.reply
    assert response.pending is None


@pytest.mark.asyncio
async def test_create_asks_for_missing_time(session: AsyncSession, store: ConversationStore) -> None:
    fake = FakeOllama(
        [
            classify(CommandName.CREATE_EVENT),
            create_slots(
                title="Dentist",
                date_expression="next Tuesday",
                time_expression=None,
                all_day=False,
            ),
        ]
    )
    orch = Orchestrator(session, ollama=fake, store=store)  # type: ignore[arg-type]
    response = await orch.handle(message="Schedule dentist next Tuesday")
    assert response.action is None
    assert response.pending is not None
    assert response.pending.type == "slot_clarification"


@pytest.mark.asyncio
async def test_create_missing_title_sets_pending_and_follow_up_creates(
    session: AsyncSession, store: ConversationStore
) -> None:
    fake = FakeOllama(
        [
            classify(CommandName.CREATE_EVENT),
            create_slots(
                title=None,
                date_expression="July 14 2026",
                time_expression="2pm",
                duration_minutes=60,
            ),
        ]
    )
    orch = Orchestrator(session, ollama=fake, store=store)  # type: ignore[arg-type]
    first = await orch.handle(message="Create a dentist appointment next Tuesday at 2pm")
    assert first.action is None
    assert first.pending is not None
    assert first.pending.type == "slot_clarification"
    assert "call this event" in first.reply.lower()

    # Title follow-up should not need another Ollama call.
    second = await orch.handle(
        message="Dentist Appointment",
        conversation_id=first.conversation_id,
    )
    assert second.action is not None
    assert second.action.command == "create_event"
    assert "Dentist Appointment" in second.reply
    assert second.pending is None


@pytest.mark.asyncio
async def test_create_missing_time_follow_up_without_llm(
    session: AsyncSession, store: ConversationStore
) -> None:
    fake = FakeOllama(
        [
            classify(CommandName.CREATE_EVENT),
            create_slots(
                title="Dentist",
                date_expression="July 14 2026",
                time_expression=None,
                all_day=False,
                needs_clarification=True,
                clarification_question="What time should I schedule that for?",
            ),
        ]
    )
    orch = Orchestrator(session, ollama=fake, store=store)  # type: ignore[arg-type]
    first = await orch.handle(message="Schedule dentist on July 14")
    assert first.pending is not None
    assert first.pending.type == "slot_clarification"

    second = await orch.handle(message="2pm", conversation_id=first.conversation_id)
    assert second.action is not None
    assert second.action.command == "create_event"
    assert fake.responses == []


@pytest.mark.asyncio
async def test_create_multi_day_all_day_follow_up(
    session: AsyncSession, store: ConversationStore
) -> None:
    fake = FakeOllama(
        [
            classify(CommandName.CREATE_EVENT),
            create_slots(
                title="Camping trip",
                date_expression="07/17 through 07/20",
                time_expression=None,
                all_day=False,
                needs_clarification=True,
                clarification_question="What time would you like to start and end?",
            ),
        ]
    )
    orch = Orchestrator(session, ollama=fake, store=store)  # type: ignore[arg-type]
    first = await orch.handle(message="Camping trip 07/17 through 07/20")
    assert first.pending is not None
    assert first.pending.type == "slot_clarification"

    second = await orch.handle(message="All day", conversation_id=first.conversation_id)
    assert second.action is not None
    assert second.action.command == "create_event"
    assert "Camping" in second.reply
    assert second.pending is None
    assert fake.responses == []


@pytest.mark.asyncio
async def test_create_multi_day_timed_follow_up_overwrites_bad_time(
    session: AsyncSession, store: ConversationStore
) -> None:
    fake = FakeOllama(
        [
            classify(CommandName.CREATE_EVENT),
            create_slots(
                title="Camping trip",
                date_expression="07/17 through 07/20",
                time_expression="not a real time",
                all_day=False,
            ),
        ]
    )
    orch = Orchestrator(session, ollama=fake, store=store)  # type: ignore[arg-type]
    first = await orch.handle(message="Camping 07/17 through 07/20 at not a real time")
    assert first.action is None
    assert first.pending is not None
    assert first.pending.type == "slot_clarification"

    second = await orch.handle(message="3pm to 1pm", conversation_id=first.conversation_id)
    assert second.action is not None
    assert second.action.command == "create_event"
    assert second.pending is None
    assert fake.responses == []


@pytest.mark.asyncio
async def test_create_slot_clarification_cancel(
    session: AsyncSession, store: ConversationStore
) -> None:
    fake = FakeOllama(
        [
            classify(CommandName.CREATE_EVENT),
            create_slots(
                title="Camping trip",
                date_expression="07/17 through 07/20",
                time_expression=None,
                all_day=False,
                needs_clarification=True,
                clarification_question="What time?",
            ),
        ]
    )
    orch = Orchestrator(session, ollama=fake, store=store)  # type: ignore[arg-type]
    first = await orch.handle(message="Camping 07/17 through 07/20")
    assert first.pending is not None

    second = await orch.handle(message="Nevermind", conversation_id=first.conversation_id)
    assert second.action is None
    assert second.pending is None
    assert "cancel" in second.reply.lower()
    assert fake.responses == []


@pytest.mark.asyncio
async def test_create_multi_day_start_end_times_without_llm(
    session: AsyncSession, store: ConversationStore
) -> None:
    fake = FakeOllama(
        [
            classify(CommandName.CREATE_EVENT),
            create_slots(
                title="Camping trip",
                date_expression="07/17 through 07/20",
                time_expression=None,
                all_day=False,
                needs_clarification=True,
                clarification_question="What time?",
            ),
        ]
    )
    orch = Orchestrator(session, ollama=fake, store=store)  # type: ignore[arg-type]
    first = await orch.handle(message="Camping 07/17 through 07/20")
    second = await orch.handle(
        message="3pm to 1pm",
        conversation_id=first.conversation_id,
    )
    assert second.action is not None
    assert second.action.command == "create_event"
    assert fake.responses == []


@pytest.mark.asyncio
async def test_search_events(session: AsyncSession, store: ConversationStore) -> None:
    cal = CalendarService(session)
    await cal.create_event(
        EventCreate(
            title="Gym",
            start_at=__import__("datetime").datetime(2026, 7, 14, 18, 0, tzinfo=__import__("zoneinfo").ZoneInfo("America/Chicago")),
            end_at=__import__("datetime").datetime(2026, 7, 14, 19, 0, tzinfo=__import__("zoneinfo").ZoneInfo("America/Chicago")),
            timezone="America/Chicago",
        )
    )
    await session.commit()

    fake = FakeOllama(
        [
            classify(CommandName.SEARCH_EVENTS),
            search_slots(query="gym"),
        ]
    )
    orch = Orchestrator(session, ollama=fake, store=store)  # type: ignore[arg-type]
    response = await orch.handle(message="Find my gym sessions")
    assert response.action is not None
    assert response.action.command == "search_events"
    assert response.action.result["total"] == 1


@pytest.mark.asyncio
async def test_search_events_by_same_day_range(session: AsyncSession, store: ConversationStore) -> None:
    cal = CalendarService(session)
    await cal.create_event(
        EventCreate(
            title="Dental appt",
            start_at=__import__("datetime").datetime(2026, 7, 14, 13, 0, tzinfo=__import__("zoneinfo").ZoneInfo("America/Chicago")),
            end_at=__import__("datetime").datetime(2026, 7, 14, 14, 0, tzinfo=__import__("zoneinfo").ZoneInfo("America/Chicago")),
            timezone="America/Chicago",
        )
    )
    await session.commit()

    fake = FakeOllama(
        [
            classify(CommandName.SEARCH_EVENTS),
            search_slots(
                start_date_expression="July 14",
                end_date_expression="July 14",
            ),
        ]
    )
    orch = Orchestrator(session, ollama=fake, store=store)  # type: ignore[arg-type]
    response = await orch.handle(message="What do I have on July 14?")
    assert response.action is not None
    assert response.action.command == "search_events"
    assert response.action.result["total"] == 1


@pytest.mark.asyncio
async def test_search_events_ignores_noisy_query(session: AsyncSession, store: ConversationStore) -> None:
    cal = CalendarService(session)
    await cal.create_event(
        EventCreate(
            title="Weight training",
            start_at=__import__("datetime").datetime(2026, 7, 14, 10, 0, tzinfo=__import__("zoneinfo").ZoneInfo("America/Chicago")),
            end_at=__import__("datetime").datetime(2026, 7, 14, 11, 0, tzinfo=__import__("zoneinfo").ZoneInfo("America/Chicago")),
            timezone="America/Chicago",
        )
    )
    await session.commit()

    fake = FakeOllama(
        [
            classify(CommandName.SEARCH_EVENTS),
            search_slots(
                query="events",
                start_date_expression="July 14",
                end_date_expression="July 14",
            ),
        ]
    )
    orch = Orchestrator(session, ollama=fake, store=store)  # type: ignore[arg-type]
    response = await orch.handle(message="Show me events occurring on Tuesday 07/14/26")
    assert response.action is not None
    assert response.action.result["total"] == 1


@pytest.mark.asyncio
async def test_multi_intent_no_action(session: AsyncSession, store: ConversationStore) -> None:
    fake = FakeOllama([classify(CommandName.MULTI_INTENT)])
    orch = Orchestrator(session, ollama=fake, store=store)  # type: ignore[arg-type]
    response = await orch.handle(message="Cancel gym and move dentist to Friday")
    assert response.action is None
    assert response.pending is None
    assert "one calendar" in response.reply.lower()


@pytest.mark.asyncio
async def test_delete_requires_confirmation(session: AsyncSession, store: ConversationStore) -> None:
    cal = CalendarService(session)
    event = await cal.create_event(
        EventCreate(
            title="Dentist",
            start_at=__import__("datetime").datetime(2026, 7, 14, 14, 0, tzinfo=__import__("zoneinfo").ZoneInfo("America/Chicago")),
            end_at=__import__("datetime").datetime(2026, 7, 14, 15, 0, tzinfo=__import__("zoneinfo").ZoneInfo("America/Chicago")),
            timezone="America/Chicago",
        )
    )
    await session.commit()

    fake = FakeOllama(
        [
            classify(CommandName.DELETE_EVENT),
            delete_slots(query="dentist"),
            confirm(confirmed=True),
        ]
    )
    orch = Orchestrator(session, ollama=fake, store=store)  # type: ignore[arg-type]
    first = await orch.handle(message="Delete my dentist appointment")
    assert first.action is None
    assert first.pending is not None
    assert first.pending.type == "confirmation"

    second = await orch.handle(message="yes", conversation_id=first.conversation_id)
    assert second.action is not None
    assert second.action.command == "delete_event"
    assert second.action.result["id"] == str(event.id)


@pytest.mark.asyncio
async def test_delete_cancelled(session: AsyncSession, store: ConversationStore) -> None:
    cal = CalendarService(session)
    await cal.create_event(
        EventCreate(
            title="Dentist",
            start_at=__import__("datetime").datetime(2026, 7, 14, 14, 0, tzinfo=__import__("zoneinfo").ZoneInfo("America/Chicago")),
            end_at=__import__("datetime").datetime(2026, 7, 14, 15, 0, tzinfo=__import__("zoneinfo").ZoneInfo("America/Chicago")),
            timezone="America/Chicago",
        )
    )
    await session.commit()

    fake = FakeOllama(
        [
            classify(CommandName.DELETE_EVENT),
            delete_slots(query="dentist"),
            confirm(confirmed=False),
        ]
    )
    orch = Orchestrator(session, ollama=fake, store=store)  # type: ignore[arg-type]
    first = await orch.handle(message="Delete dentist")
    second = await orch.handle(message="no", conversation_id=first.conversation_id)
    assert second.action is None
    assert "cancelled" in second.reply.lower()
    items, total = await cal.search_events(query="dentist")
    assert total == 1


@pytest.mark.asyncio
async def test_get_disambiguation(session: AsyncSession, store: ConversationStore) -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    cal = CalendarService(session)
    tz = ZoneInfo("America/Chicago")
    await cal.create_event(
        EventCreate(
            title="Dentist",
            start_at=datetime(2026, 7, 14, 14, 0, tzinfo=tz),
            end_at=datetime(2026, 7, 14, 15, 0, tzinfo=tz),
            timezone="America/Chicago",
        )
    )
    await cal.create_event(
        EventCreate(
            title="Dentist",
            start_at=datetime(2026, 8, 3, 10, 0, tzinfo=tz),
            end_at=datetime(2026, 8, 3, 11, 0, tzinfo=tz),
            timezone="America/Chicago",
        )
    )
    await session.commit()

    fake = FakeOllama(
        [
            classify(CommandName.GET_EVENT),
            get_slots(query="dentist"),
        ]
    )
    orch = Orchestrator(session, ollama=fake, store=store)  # type: ignore[arg-type]
    response = await orch.handle(message="Show my dentist appointment")
    assert response.pending is not None
    assert response.pending.type == "disambiguation"
    assert response.pending.options is not None
    assert len(response.pending.options) == 2


@pytest.mark.asyncio
async def test_update_with_relative_shift(session: AsyncSession, store: ConversationStore) -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    cal = CalendarService(session)
    tz = ZoneInfo("America/Chicago")
    event = await cal.create_event(
        EventCreate(
            title="Dentist",
            start_at=datetime(2026, 7, 14, 14, 0, tzinfo=tz),
            end_at=datetime(2026, 7, 14, 15, 0, tzinfo=tz),
            timezone="America/Chicago",
        )
    )
    await session.commit()

    fake = FakeOllama(
        [
            classify(CommandName.UPDATE_EVENT),
            update_slots(query="dentist"),
            update_slots(relative_shift_minutes=60),
        ]
    )
    orch = Orchestrator(session, ollama=fake, store=store)  # type: ignore[arg-type]
    response = await orch.handle(message="Move my dentist appointment an hour later")
    assert response.action is not None
    assert response.action.command == "update_event"
    updated = await cal.get_event(event.id)
    local = updated.start_at.astimezone(tz)
    assert local.hour == 15


@pytest.mark.asyncio
async def test_none_command(session: AsyncSession, store: ConversationStore) -> None:
    fake = FakeOllama([classify(CommandName.NONE)])
    orch = Orchestrator(session, ollama=fake, store=store)  # type: ignore[arg-type]
    response = await orch.handle(message="What's the capital of France?")
    assert response.action is None
    assert response.pending is None
