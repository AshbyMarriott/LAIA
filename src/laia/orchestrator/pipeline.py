"""Two-call NL orchestrator: classify → slot-fill → validate → act."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from laia.config import Settings, get_settings
from laia.models.event import Event
from laia.orchestrator import prompts
from laia.schemas.assistant import (
    ActionResult,
    ChatResponse,
    ClassificationResult,
    CommandName,
    ConfirmationReply,
    CreateEventSlots,
    DeleteEventSlots,
    GetEventSlots,
    PendingDisambiguationOption,
    PendingState,
    SearchEventsSlots,
    UpdateEventSlots,
)
from laia.schemas.events import EventCreate, EventRead, EventUpdate
from laia.schemas.single_call import SingleCallResult
from laia.services.calendar import CalendarService, EventNotFoundError
from laia.services.conversation import ConversationState, ConversationStore, get_conversation_store
from laia.services.dates import (
    DateResolutionError,
    apply_relative_shift,
    resolve_event_bounds,
    resolve_range,
)
from laia.services.ollama import OllamaClient, OllamaError, get_ollama_client

logger = logging.getLogger(__name__)


def _format_event_label(event: Event) -> str:
    local = event.start_at.astimezone(ZoneInfo(event.timezone))
    if event.all_day:
        return f"{event.title} - {local.date().isoformat()} (all day)"
    hour = local.strftime("%I").lstrip("0") or "12"
    return f"{event.title} - {local.strftime('%B')} {local.day}, {hour}:{local.strftime('%M %p')}"


def _event_to_snapshot(event: Event) -> dict[str, Any]:
    return EventRead.model_validate(event).model_dump(mode="json")


def _reply_created(event: Event) -> str:
    return f"Created event: {_format_event_label(event)}."


def _reply_updated(event: Event) -> str:
    return f"Updated event: {_format_event_label(event)}."


class Orchestrator:
    def __init__(
        self,
        session: AsyncSession,
        *,
        ollama: OllamaClient | None = None,
        store: ConversationStore | None = None,
        settings: Settings | None = None,
        pipeline: str = "two_call",
    ) -> None:
        self.settings = settings or get_settings()
        self.calendar = CalendarService(session)
        self.ollama = ollama or get_ollama_client(self.settings)
        self.store = store or get_conversation_store()
        self.pipeline = pipeline

    async def handle(self, *, message: str, conversation_id: str | None = None) -> ChatResponse:
        state = self.store.get_or_create(conversation_id)
        text = message.strip()

        try:
            if state.pending_type == "confirmation":
                return await self._handle_confirmation(state, text)
            if state.pending_type == "disambiguation":
                return await self._handle_disambiguation(state, text)
            if state.pending_type == "slot_clarification":
                return await self._handle_slot_clarification(state, text)

            if self.pipeline == "single_call":
                return await self._handle_single_call(state, text)

            classification = await self.ollama.structured(
                system=prompts.CLASSIFY_SYSTEM,
                user=prompts.classify_user_prompt(text),
                schema=ClassificationResult,
            )
            command = classification.command
            logger.info("classified command=%s conversation_id=%s", command, state.conversation_id)
            return await self._dispatch(state, text, command)
        except OllamaError as exc:
            logger.exception("ollama error")
            return self._response(state, f"The local model is unavailable right now: {exc}")
        except Exception:
            logger.exception("orchestrator failure")
            return self._response(state, "Something went wrong while handling that request.")

    async def _dispatch(
        self, state: ConversationState, text: str, command: CommandName
    ) -> ChatResponse:
        if command == CommandName.NONE:
            return self._response(
                state,
                "I can help with calendar requests: create, find, update, or delete an event.",
            )
        if command == CommandName.MULTI_INTENT:
            return self._response(
                state,
                "I can handle one calendar change at a time. Which one should I do first?",
            )
        if command == CommandName.UNCLEAR:
            return self._response(
                state,
                "I'm not sure what you'd like to do. Try asking me to create, find, update, or delete an event.",
            )
        if command == CommandName.CREATE_EVENT:
            return await self._create_event(state, text)
        if command == CommandName.SEARCH_EVENTS:
            return await self._search_events(state, text)
        if command == CommandName.GET_EVENT:
            return await self._get_event(state, text)
        if command == CommandName.UPDATE_EVENT:
            return await self._update_event(state, text)
        if command == CommandName.DELETE_EVENT:
            return await self._delete_event(state, text)
        return self._response(state, "I couldn't process that request.")

    async def _handle_single_call(self, state: ConversationState, text: str) -> ChatResponse:
        """Bakeoff path: one structured call with command + args."""
        result = await self.ollama.structured(
            system=prompts.SINGLE_CALL_SYSTEM,
            user=prompts.slots_user_prompt(text),
            schema=SingleCallResult,
        )
        command = result.command
        logger.info("single_call command=%s conversation_id=%s", command, state.conversation_id)

        if command in {CommandName.NONE, CommandName.MULTI_INTENT, CommandName.UNCLEAR}:
            return await self._dispatch(state, text, command)

        schema_map = {
            CommandName.CREATE_EVENT: CreateEventSlots,
            CommandName.SEARCH_EVENTS: SearchEventsSlots,
            CommandName.GET_EVENT: GetEventSlots,
            CommandName.UPDATE_EVENT: UpdateEventSlots,
            CommandName.DELETE_EVENT: DeleteEventSlots,
        }
        slot_schema = schema_map[command]
        fixed_slots = slot_schema.model_validate(result.args)

        class _Fixed:
            def __init__(self, inner: OllamaClient, fixed: Any) -> None:
                self._inner = inner
                self._fixed = fixed
                self._used = False

            async def structured(self, **kwargs: Any) -> Any:
                if not self._used:
                    self._used = True
                    return self._fixed
                return await self._inner.structured(**kwargs)

        original = self.ollama
        self.ollama = _Fixed(original, fixed_slots)  # type: ignore[assignment]
        try:
            return await self._dispatch(state, text, command)
        finally:
            self.ollama = original

    def _response(
        self,
        state: ConversationState,
        reply: str,
        *,
        action: ActionResult | None = None,
        pending: PendingState | None = None,
    ) -> ChatResponse:
        return ChatResponse(
            conversation_id=state.conversation_id,
            reply=reply,
            action=action,
            pending=pending,
        )

    def _ask_create_clarification(
        self,
        state: ConversationState,
        slots: CreateEventSlots,
        question: str,
    ) -> ChatResponse:
        self.store.set_pending(
            state.conversation_id,
            pending_type="slot_clarification",
            command=CommandName.CREATE_EVENT.value,
            pending_slots=slots.model_dump(),
        )
        return self._response(
            state,
            question,
            pending=PendingState(
                type="slot_clarification",
                command="create_event",
                clarification_question=question,
            ),
        )

    async def _finalize_create_from_slots(
        self,
        state: ConversationState,
        slots: CreateEventSlots,
    ) -> ChatResponse:
        if not slots.title:
            return self._ask_create_clarification(
                state,
                slots,
                "What should I call this event?",
            )

        all_day = bool(slots.all_day)
        try:
            bounds = resolve_event_bounds(
                date_expression=slots.date_expression,
                time_expression=slots.time_expression,
                end_date_expression=slots.end_date_expression,
                end_time_expression=slots.end_time_expression,
                duration_minutes=slots.duration_minutes,
                all_day=all_day,
                timezone=slots.timezone or self.settings.laia_timezone,
                default_duration_minutes=self.settings.default_event_duration_minutes,
            )
        except DateResolutionError as exc:
            return self._ask_create_clarification(state, slots, str(exc))

        event = await self.calendar.create_event(
            EventCreate(
                title=slots.title,
                description=slots.description,
                location=slots.location,
                start_at=bounds.start_at,
                end_at=bounds.end_at,
                timezone=bounds.timezone,
                all_day=bounds.all_day,
            )
        )
        self.store.clear_pending(state.conversation_id)
        return self._response(
            state,
            _reply_created(event),
            action=ActionResult(command="create_event", result={"id": str(event.id)}),
        )

    async def _create_event(self, state: ConversationState, message: str) -> ChatResponse:
        slots = await self.ollama.structured(
            system=prompts.CREATE_SLOTS_SYSTEM,
            user=prompts.slots_user_prompt(message),
            schema=CreateEventSlots,
        )
        if slots.needs_clarification:
            question = slots.clarification_question or "What time should I schedule that for?"
            return self._ask_create_clarification(state, slots, question)

        return await self._finalize_create_from_slots(state, slots)

    async def _search_events(self, state: ConversationState, message: str) -> ChatResponse:
        slots = await self.ollama.structured(
            system=prompts.SEARCH_SLOTS_SYSTEM,
            user=prompts.slots_user_prompt(message),
            schema=SearchEventsSlots,
        )
        if slots.needs_clarification:
            question = slots.clarification_question or "What should I search for?"
            return self._response(state, question)

        try:
            start, end = resolve_range(
                start_date_expression=slots.start_date_expression,
                end_date_expression=slots.end_date_expression,
                timezone=slots.timezone or self.settings.laia_timezone,
            )
        except DateResolutionError as exc:
            return self._response(state, str(exc))

        items, total = await self.calendar.search_events(query=slots.query, start=start, end=end, limit=10)
        if total == 0:
            return self._response(
                state,
                "I couldn't find any matching events.",
                action=ActionResult(command="search_events", result={"total": 0, "items": []}),
            )

        lines = [f"Found {total} event(s):"]
        for event in items:
            lines.append(f"- {_format_event_label(event)} [{event.id}]")
        return self._response(
            state,
            "\n".join(lines),
            action=ActionResult(
                command="search_events",
                result={
                    "total": total,
                    "items": [{"id": str(e.id), "title": e.title} for e in items],
                },
            ),
        )

    async def _resolve_candidates(
        self,
        *,
        query: str | None,
        date_expression: str | None,
        timezone: str | None,
    ) -> list[Event]:
        start = end = None
        if date_expression:
            try:
                start, end = resolve_range(
                    start_date_expression=date_expression,
                    end_date_expression=date_expression,
                    timezone=timezone or self.settings.laia_timezone,
                )
                # Expand single-day expression to full local day.
                if start is not None and end is not None and start.date() == end.date():
                    tz = ZoneInfo(timezone or self.settings.laia_timezone)
                    start = datetime.combine(start.date(), datetime.min.time(), tzinfo=tz)
                    end = datetime.combine(start.date(), datetime.max.time(), tzinfo=tz)
            except DateResolutionError:
                start = end = None
        items, _ = await self.calendar.search_events(query=query, start=start, end=end, limit=10)
        return items

    async def _get_event(self, state: ConversationState, message: str) -> ChatResponse:
        slots = await self.ollama.structured(
            system=prompts.GET_SLOTS_SYSTEM,
            user=prompts.slots_user_prompt(message),
            schema=GetEventSlots,
        )
        candidates = await self._resolve_candidates(
            query=slots.query,
            date_expression=slots.date_expression,
            timezone=slots.timezone,
        )
        if not candidates:
            return self._response(state, "I couldn't find an event matching that.")
        if len(candidates) > 1:
            return self._ask_disambiguation(state, CommandName.GET_EVENT.value, candidates)
        event = candidates[0]
        details = (
            f"{_format_event_label(event)}\n"
            f"Location: {event.location or '—'}\n"
            f"Description: {event.description or '—'}"
        )
        return self._response(
            state,
            details,
            action=ActionResult(command="get_event", result={"id": str(event.id)}),
        )

    async def _update_event(self, state: ConversationState, message: str) -> ChatResponse:
        # Stage 1: locate target unless already resolved in pending snapshot flow.
        locate = await self.ollama.structured(
            system=prompts.UPDATE_SLOTS_SYSTEM,
            user=prompts.slots_user_prompt(message),
            schema=UpdateEventSlots,
        )
        candidates = await self._resolve_candidates(
            query=locate.query,
            date_expression=locate.date_expression,
            timezone=locate.timezone,
        )
        if not candidates:
            return self._response(state, "I couldn't find an event to update.")
        if len(candidates) > 1:
            return self._ask_disambiguation(
                state,
                CommandName.UPDATE_EVENT.value,
                candidates,
                pending_slots=locate.model_dump(),
            )

        return await self._apply_update(state, candidates[0], message, locate)

    async def _apply_update(
        self,
        state: ConversationState,
        event: Event,
        message: str,
        prior_slots: UpdateEventSlots | None = None,
    ) -> ChatResponse:
        snapshot = _event_to_snapshot(event)
        slots = await self.ollama.structured(
            system=prompts.UPDATE_SLOTS_SYSTEM,
            user=prompts.slots_user_prompt(message, context={"current_event": snapshot}),
            schema=UpdateEventSlots,
        )
        # Prefer patch fields from the context-aware call; fall back to prior locate slots.
        if prior_slots is not None:
            merged = prior_slots.model_dump()
            for key, value in slots.model_dump(exclude_unset=True).items():
                if value is not None and value != [] and value is not False:
                    merged[key] = value
            slots = UpdateEventSlots.model_validate(merged)

        patch: dict[str, Any] = {}
        if slots.title:
            patch["title"] = slots.title
        if slots.description is not None or slots.clear_description:
            patch["description"] = None if slots.clear_description else slots.description
        if slots.location is not None or slots.clear_location:
            patch["location"] = None if slots.clear_location else slots.location
        if slots.all_day is not None:
            patch["all_day"] = slots.all_day
        if slots.timezone:
            patch["timezone"] = slots.timezone

        start_at = event.start_at
        end_at = event.end_at
        tz_name = slots.timezone or event.timezone

        if slots.relative_shift_minutes:
            start_at, end_at = apply_relative_shift(start_at, end_at, slots.relative_shift_minutes)
            patch["start_at"] = start_at
            patch["end_at"] = end_at
        elif slots.new_date_expression or slots.new_time_expression or slots.new_end_time_expression:
            try:
                bounds = resolve_event_bounds(
                    date_expression=slots.new_date_expression
                    or event.start_at.astimezone(ZoneInfo(tz_name)).date().isoformat(),
                    time_expression=slots.new_time_expression,
                    end_date_expression=slots.new_end_date_expression,
                    end_time_expression=slots.new_end_time_expression,
                    duration_minutes=slots.duration_minutes
                    or int((event.end_at - event.start_at).total_seconds() // 60),
                    all_day=bool(slots.all_day) if slots.all_day is not None else event.all_day,
                    timezone=tz_name,
                    default_duration_minutes=self.settings.default_event_duration_minutes,
                )
            except DateResolutionError as exc:
                return self._response(state, str(exc))
            # If only shifting date with no new time and not all-day, preserve local clock time.
            if (
                slots.new_date_expression
                and not slots.new_time_expression
                and not (slots.all_day or event.all_day)
            ):
                local = event.start_at.astimezone(ZoneInfo(tz_name))
                try:
                    bounds = resolve_event_bounds(
                        date_expression=slots.new_date_expression,
                        time_expression=local.strftime("%H:%M"),
                        duration_minutes=int((event.end_at - event.start_at).total_seconds() // 60),
                        timezone=tz_name,
                    )
                except DateResolutionError as exc:
                    return self._response(state, str(exc))
            patch["start_at"] = bounds.start_at
            patch["end_at"] = bounds.end_at
            patch["all_day"] = bounds.all_day
            patch["timezone"] = bounds.timezone

        if not patch:
            return self._response(state, "I couldn't tell what to change. What should I update?")

        updated = await self.calendar.update_event(event.id, EventUpdate.model_validate(patch))
        self.store.clear_pending(state.conversation_id)
        return self._response(
            state,
            _reply_updated(updated),
            action=ActionResult(command="update_event", result={"id": str(updated.id)}),
        )

    async def _delete_event(self, state: ConversationState, message: str) -> ChatResponse:
        slots = await self.ollama.structured(
            system=prompts.DELETE_SLOTS_SYSTEM,
            user=prompts.slots_user_prompt(message),
            schema=DeleteEventSlots,
        )
        candidates = await self._resolve_candidates(
            query=slots.query,
            date_expression=slots.date_expression,
            timezone=slots.timezone,
        )
        if not candidates:
            return self._response(state, "I couldn't find an event to delete.")
        if len(candidates) > 1:
            return self._ask_disambiguation(state, CommandName.DELETE_EVENT.value, candidates)

        event = candidates[0]
        self.store.set_pending(
            state.conversation_id,
            pending_type="confirmation",
            command=CommandName.DELETE_EVENT.value,
            target_event_id=str(event.id),
            event_snapshot=_event_to_snapshot(event),
        )
        label = _format_event_label(event)
        return self._response(
            state,
            f"Delete '{label}'? Reply yes or no.",
            pending=PendingState(
                type="confirmation",
                command="delete_event",
                target_event_id=str(event.id),
            ),
        )

    def _ask_disambiguation(
        self,
        state: ConversationState,
        command: str,
        candidates: list[Event],
        pending_slots: dict[str, Any] | None = None,
    ) -> ChatResponse:
        options = [
            PendingDisambiguationOption(id=str(event.id), label=_format_event_label(event))
            for event in candidates
        ]
        self.store.set_pending(
            state.conversation_id,
            pending_type="disambiguation",
            command=command,
            candidate_event_ids=[str(e.id) for e in candidates],
            pending_slots=pending_slots,
            options=[opt.model_dump() for opt in options],
        )
        lines = ["I found multiple matching events. Which one did you mean?"]
        for idx, opt in enumerate(options, start=1):
            lines.append(f"{idx}. {opt.label}")
        return self._response(
            state,
            "\n".join(lines),
            pending=PendingState(type="disambiguation", command=command, options=options),
        )

    async def _handle_confirmation(self, state: ConversationState, message: str) -> ChatResponse:
        reply = await self.ollama.structured(
            system=prompts.CONFIRMATION_SYSTEM,
            user=prompts.slots_user_prompt(
                message,
                context={"pending": "confirmation", "command": state.command, "target": state.target_event_id},
            ),
            schema=ConfirmationReply,
        )
        lowered = message.strip().lower()
        confirmed = reply.confirmed
        if confirmed is None:
            if lowered in {"y", "yes", "yeah", "yep", "confirm", "do it", "delete"}:
                confirmed = True
            elif lowered in {"n", "no", "nope", "cancel", "stop"}:
                confirmed = False

        if confirmed is None or reply.needs_clarification:
            return self._response(
                state,
                "Please reply yes or no.",
                pending=PendingState(
                    type="confirmation",
                    command=state.command,
                    target_event_id=state.target_event_id,
                ),
            )

        if not confirmed:
            self.store.clear_pending(state.conversation_id)
            return self._response(state, "Okay, I cancelled that.")

        if state.command == CommandName.DELETE_EVENT.value and state.target_event_id:
            try:
                await self.calendar.delete_event(uuid.UUID(state.target_event_id))
            except EventNotFoundError:
                self.store.clear_pending(state.conversation_id)
                return self._response(state, "That event no longer exists.")
            event_id = state.target_event_id
            self.store.clear_pending(state.conversation_id)
            return self._response(
                state,
                "Deleted the event.",
                action=ActionResult(command="delete_event", result={"id": event_id}),
            )

        self.store.clear_pending(state.conversation_id)
        return self._response(state, "Okay.")

    async def _handle_disambiguation(self, state: ConversationState, message: str) -> ChatResponse:
        reply = await self.ollama.structured(
            system=prompts.CONFIRMATION_SYSTEM,
            user=prompts.slots_user_prompt(
                message,
                context={"pending": "disambiguation", "options": state.options},
            ),
            schema=ConfirmationReply,
        )
        selected_id = reply.selected_option_id
        if not selected_id:
            # Allow "1" / "2" style answers.
            stripped = message.strip()
            if stripped.isdigit():
                idx = int(stripped) - 1
                if 0 <= idx < len(state.candidate_event_ids):
                    selected_id = state.candidate_event_ids[idx]
            else:
                lowered = stripped.lower()
                for opt in state.options:
                    if lowered in opt.get("label", "").lower() or lowered == opt.get("id", "").lower():
                        selected_id = opt["id"]
                        break

        if not selected_id or selected_id not in state.candidate_event_ids:
            return self._response(
                state,
                "Please choose one of the listed options by number or name.",
                pending=PendingState(
                    type="disambiguation",
                    command=state.command,
                    options=[PendingDisambiguationOption(**o) for o in state.options],
                ),
            )

        command = state.command
        pending_slots = state.pending_slots
        try:
            event = await self.calendar.get_event(uuid.UUID(selected_id))
        except EventNotFoundError:
            self.store.clear_pending(state.conversation_id)
            return self._response(state, "That event no longer exists.")

        if command == CommandName.GET_EVENT.value:
            self.store.clear_pending(state.conversation_id)
            details = (
                f"{_format_event_label(event)}\n"
                f"Location: {event.location or '—'}\n"
                f"Description: {event.description or '—'}"
            )
            return self._response(
                state,
                details,
                action=ActionResult(command="get_event", result={"id": str(event.id)}),
            )

        if command == CommandName.DELETE_EVENT.value:
            self.store.set_pending(
                state.conversation_id,
                pending_type="confirmation",
                command=CommandName.DELETE_EVENT.value,
                target_event_id=str(event.id),
                event_snapshot=_event_to_snapshot(event),
            )
            return self._response(
                state,
                f"Delete '{_format_event_label(event)}'? Reply yes or no.",
                pending=PendingState(
                    type="confirmation",
                    command="delete_event",
                    target_event_id=str(event.id),
                ),
            )

        if command == CommandName.UPDATE_EVENT.value:
            prior = UpdateEventSlots.model_validate(pending_slots or {})
            # Re-run patch extraction with selected event context using original pending slots message context.
            return await self._apply_update(state, event, message, prior)

        self.store.clear_pending(state.conversation_id)
        return self._response(state, "Okay.")

    async def _handle_slot_clarification(self, state: ConversationState, message: str) -> ChatResponse:
        # Treat the follow-up as completing the original create (MVP: create only).
        if state.command == CommandName.CREATE_EVENT.value:
            prior = CreateEventSlots.model_validate(state.pending_slots or {})
            text = message.strip().strip('"').strip("'")

            # If we asked for a title, accept the reply as the title without another LLM call.
            # This keeps follow-ups working when the model is slow/unavailable.
            if not prior.title and text:
                merged = prior.model_dump()
                merged["title"] = text
                merged["needs_clarification"] = False
                return await self._finalize_create_from_slots(
                    state,
                    CreateEventSlots.model_validate(merged),
                )

            # If we have a title/date but no time, accept a short time reply without another LLM call.
            if (
                prior.title
                and prior.date_expression
                and not prior.time_expression
                and not prior.all_day
                and text
                and len(text) <= 40
            ):
                merged = prior.model_dump()
                merged["time_expression"] = text
                merged["needs_clarification"] = False
                return await self._finalize_create_from_slots(
                    state,
                    CreateEventSlots.model_validate(merged),
                )

            # Merge: if user only provides a time, keep prior date/title.
            follow = await self.ollama.structured(
                system=prompts.CREATE_SLOTS_SYSTEM,
                user=prompts.slots_user_prompt(
                    message,
                    context={"previous_slots": prior.model_dump()},
                ),
                schema=CreateEventSlots,
            )
            merged = prior.model_dump()
            for key, value in follow.model_dump().items():
                if value is not None and value != "" and value is not False:
                    merged[key] = value
            merged["needs_clarification"] = False
            return await self._finalize_create_from_slots(
                state,
                CreateEventSlots.model_validate(merged),
            )
        # Fallback: clear and reprocess as a fresh message.
        self.store.clear_pending(state.conversation_id)
        return await self.handle(message=message, conversation_id=state.conversation_id)
