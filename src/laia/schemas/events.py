"""Pydantic schemas for the events API."""

from __future__ import annotations

import uuid
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _validate_iana_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Invalid IANA timezone: {value}") from exc
    return value


class EventCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    location: str | None = Field(default=None, max_length=500)
    start_at: datetime
    end_at: datetime
    timezone: str
    all_day: bool = False

    @field_validator("timezone")
    @classmethod
    def timezone_must_be_iana(cls, value: str) -> str:
        return _validate_iana_timezone(value)

    @model_validator(mode="after")
    def end_after_start(self) -> EventCreate:
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be greater than start_at")
        return self


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    location: str | None = Field(default=None, max_length=500)
    start_at: datetime | None = None
    end_at: datetime | None = None
    timezone: str | None = None
    all_day: bool | None = None

    @field_validator("timezone")
    @classmethod
    def timezone_must_be_iana(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _validate_iana_timezone(value)


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    location: str | None
    start_at: datetime
    end_at: datetime
    timezone: str
    all_day: bool
    created_at: datetime
    updated_at: datetime


class EventList(BaseModel):
    items: list[EventRead]
    total: int
