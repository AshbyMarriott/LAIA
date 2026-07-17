"""Fake Ollama client for deterministic orchestrator tests."""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from laia.schemas.assistant import (
    ClassificationResult,
    CommandName,
    ConfirmationReply,
    CreateEventSlots,
    DeleteEventSlots,
    GetEventSlots,
    SearchEventsSlots,
    UpdateEventSlots,
)

T = TypeVar("T", bound=BaseModel)


class FakeOllama:
    """Queue-based structured-output stub."""

    def __init__(self, responses: list[BaseModel] | None = None) -> None:
        self.responses: list[BaseModel] = list(responses or [])
        self.calls: list[dict[str, Any]] = []

    def enqueue(self, *items: BaseModel) -> None:
        self.responses.extend(items)

    async def structured(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        model: str | None = None,
        temperature: float = 0.0,
    ) -> T:
        self.calls.append({"system": system, "user": user, "schema": schema.__name__})
        if not self.responses:
            raise AssertionError(f"FakeOllama has no queued response for {schema.__name__}")
        item = self.responses.pop(0)
        if not isinstance(item, schema):
            # Allow raw dict coercion
            if isinstance(item, BaseModel):
                raise AssertionError(
                    f"Expected {schema.__name__}, got {type(item).__name__}"
                )
        return item  # type: ignore[return-value]

    async def health(self) -> dict[str, Any]:
        return {"ok": True, "models": ["fake"]}

    async def aclose(self) -> None:
        return None


def classify(command: CommandName) -> ClassificationResult:
    return ClassificationResult(command=command)


def create_slots(**kwargs: Any) -> CreateEventSlots:
    return CreateEventSlots(**kwargs)


def search_slots(**kwargs: Any) -> SearchEventsSlots:
    return SearchEventsSlots(**kwargs)


def get_slots(**kwargs: Any) -> GetEventSlots:
    return GetEventSlots(**kwargs)


def update_slots(**kwargs: Any) -> UpdateEventSlots:
    return UpdateEventSlots(**kwargs)


def delete_slots(**kwargs: Any) -> DeleteEventSlots:
    return DeleteEventSlots(**kwargs)


def confirm(**kwargs: Any) -> ConfirmationReply:
    return ConfirmationReply(**kwargs)
