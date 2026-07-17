"""Pydantic schemas for assistant chat and LLM structured output."""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class CommandName(StrEnum):
    CREATE_EVENT = "create_event"
    SEARCH_EVENTS = "search_events"
    GET_EVENT = "get_event"
    UPDATE_EVENT = "update_event"
    DELETE_EVENT = "delete_event"
    NONE = "none"
    MULTI_INTENT = "multi_intent"
    UNCLEAR = "unclear"


class ClassificationResult(BaseModel):
    command: CommandName


class CreateEventSlots(BaseModel):
    title: str | None = None
    description: str | None = None
    location: str | None = None
    date_expression: str | None = None
    time_expression: str | None = None
    end_date_expression: str | None = None
    end_time_expression: str | None = None
    duration_minutes: int | None = None
    timezone: str | None = None
    all_day: bool | None = None
    needs_clarification: bool = False
    clarification_question: str | None = None


class SearchEventsSlots(BaseModel):
    query: str | None = None
    start_date_expression: str | None = None
    end_date_expression: str | None = None
    timezone: str | None = None
    needs_clarification: bool = False
    clarification_question: str | None = None


class GetEventSlots(BaseModel):
    query: str | None = None
    date_expression: str | None = None
    timezone: str | None = None
    needs_clarification: bool = False
    clarification_question: str | None = None


class UpdateEventSlots(BaseModel):
    query: str | None = None
    date_expression: str | None = None
    title: str | None = None
    description: str | None = None
    location: str | None = None
    new_date_expression: str | None = None
    new_time_expression: str | None = None
    new_end_date_expression: str | None = None
    new_end_time_expression: str | None = None
    duration_minutes: int | None = None
    relative_shift_minutes: int | None = None
    timezone: str | None = None
    all_day: bool | None = None
    clear_description: bool = False
    clear_location: bool = False
    needs_clarification: bool = False
    clarification_question: str | None = None


class DeleteEventSlots(BaseModel):
    query: str | None = None
    date_expression: str | None = None
    timezone: str | None = None
    needs_clarification: bool = False
    clarification_question: str | None = None


class ConfirmationReply(BaseModel):
    confirmed: bool | None = None
    selected_option_id: str | None = None
    needs_clarification: bool = False
    clarification_question: str | None = None


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str = Field(..., min_length=1)


class PendingDisambiguationOption(BaseModel):
    id: str
    label: str


class PendingState(BaseModel):
    type: Literal["disambiguation", "confirmation", "slot_clarification"]
    command: str | None = None
    options: list[PendingDisambiguationOption] | None = None
    target_event_id: str | None = None
    clarification_question: str | None = None


class ActionResult(BaseModel):
    command: str
    result: dict[str, Any]


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    action: ActionResult | None = None
    pending: PendingState | None = None


class EventSnapshot(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    location: str | None
    start_at: str
    end_at: str
    timezone: str
    all_day: bool
