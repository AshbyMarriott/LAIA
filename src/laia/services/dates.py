"""Deterministic date/time resolution for natural-language expressions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import dateparser
from dateutil.relativedelta import relativedelta


class DateResolutionError(Exception):
    """Raised when a date/time expression cannot be resolved."""


@dataclass(frozen=True)
class ResolvedInterval:
    start_at: datetime
    end_at: datetime
    all_day: bool
    timezone: str


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise DateResolutionError(f"Invalid timezone: {name}") from exc


_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def _try_relative_weekday(expression: str, base: datetime) -> datetime | None:
    """Handle common 'next Friday' / 'this Monday' forms dateparser sometimes misses."""
    text = expression.strip().lower()
    for prefix in ("next ", "this "):
        if text.startswith(prefix):
            day = text[len(prefix) :].strip()
            if day in _WEEKDAYS:
                target = next_weekday(base.date(), _WEEKDAYS[day])
                if prefix == "this ":
                    # "this Friday" means the Friday of the current week if still ahead,
                    # otherwise next week's Friday.
                    days_ahead = (_WEEKDAYS[day] - base.weekday()) % 7
                    target = base.date() + timedelta(days=days_ahead or 7)
                return datetime.combine(target, base.timetz()).replace(
                    hour=base.hour, minute=base.minute, second=0, microsecond=0
                )
    if text in _WEEKDAYS:
        days_ahead = (_WEEKDAYS[text] - base.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        target = base.date() + timedelta(days=days_ahead)
        return datetime.combine(target, time(0, 0), tzinfo=base.tzinfo)
    return None


def _parse_expression(
    expression: str,
    *,
    base: datetime,
    timezone: str,
    prefer_future: bool = True,
) -> datetime:
    tz = _zone(timezone)
    relative = _try_relative_weekday(expression, base)
    if relative is not None:
        return relative.astimezone(tz) if relative.tzinfo else relative.replace(tzinfo=tz)

    settings = {
        "TIMEZONE": timezone,
        "RETURN_AS_TIMEZONE_AWARE": True,
        "RELATIVE_BASE": base,
        "PREFER_DATES_FROM": "future" if prefer_future else "current_period",
        "PREFER_DAY_OF_MONTH": "first",
    }
    parsed = dateparser.parse(expression, settings=settings)
    if parsed is None and not prefer_future:
        # Retry with future preference for phrases like "next Friday".
        settings["PREFER_DATES_FROM"] = "future"
        parsed = dateparser.parse(expression, settings=settings)
    if parsed is None:
        raise DateResolutionError(f"Could not parse date/time expression: {expression!r}")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    else:
        parsed = parsed.astimezone(tz)
    return parsed


def resolve_event_bounds(
    *,
    date_expression: str | None,
    time_expression: str | None = None,
    end_date_expression: str | None = None,
    end_time_expression: str | None = None,
    duration_minutes: int | None = None,
    all_day: bool = False,
    timezone: str,
    now: datetime | None = None,
    default_duration_minutes: int = 60,
) -> ResolvedInterval:
    """Resolve LLM-extracted expressions into validated start/end datetimes."""
    tz = _zone(timezone)
    base = now.astimezone(tz) if now is not None else datetime.now(tz=tz)

    if all_day:
        if not date_expression:
            raise DateResolutionError("All-day events require a date_expression")
        start_local = _parse_expression(date_expression, base=base, timezone=timezone)
        start_day = datetime.combine(start_local.date(), time.min, tzinfo=tz)
        if end_date_expression:
            end_local = _parse_expression(end_date_expression, base=base, timezone=timezone)
            end_day = datetime.combine(end_local.date() + timedelta(days=1), time.min, tzinfo=tz)
        else:
            end_day = start_day + timedelta(days=1)
        if end_day <= start_day:
            raise DateResolutionError("end_at must be greater than start_at")
        return ResolvedInterval(start_at=start_day, end_at=end_day, all_day=True, timezone=timezone)

    if not date_expression and not time_expression:
        raise DateResolutionError("A date or time expression is required")

    if date_expression and time_expression:
        combined = f"{date_expression} {time_expression}"
        start_at = _parse_expression(combined, base=base, timezone=timezone)
    elif date_expression and not time_expression:
        raise DateResolutionError(
            "Time is missing. Provide a time or mark the event as all-day."
        )
    else:
        # time only — assume today / next occurrence relative to now
        assert time_expression is not None
        start_at = _parse_expression(time_expression, base=base, timezone=timezone)
        if start_at < base:
            start_at = start_at + timedelta(days=1)

    if end_date_expression or end_time_expression:
        end_parts = []
        if end_date_expression:
            end_parts.append(end_date_expression)
        elif date_expression:
            end_parts.append(date_expression)
        if end_time_expression:
            end_parts.append(end_time_expression)
        end_at = _parse_expression(" ".join(end_parts), base=base, timezone=timezone)
    else:
        minutes = duration_minutes if duration_minutes is not None else default_duration_minutes
        if minutes <= 0:
            raise DateResolutionError("duration_minutes must be positive")
        end_at = start_at + timedelta(minutes=minutes)

    if end_at <= start_at:
        raise DateResolutionError("end_at must be greater than start_at")

    return ResolvedInterval(start_at=start_at, end_at=end_at, all_day=False, timezone=timezone)


def resolve_range(
    *,
    start_date_expression: str | None,
    end_date_expression: str | None,
    timezone: str,
    now: datetime | None = None,
) -> tuple[datetime | None, datetime | None]:
    """Resolve an optional search range."""
    tz = _zone(timezone)
    base = now.astimezone(tz) if now is not None else datetime.now(tz=tz)
    start = (
        _parse_expression(start_date_expression, base=base, timezone=timezone, prefer_future=False)
        if start_date_expression
        else None
    )
    end = (
        _parse_expression(end_date_expression, base=base, timezone=timezone, prefer_future=False)
        if end_date_expression
        else None
    )
    if start and end and end < start:
        raise DateResolutionError("Search end must not be before start")
    return start, end


def apply_relative_shift(
    start_at: datetime,
    end_at: datetime,
    shift_minutes: int,
) -> tuple[datetime, datetime]:
    delta = timedelta(minutes=shift_minutes)
    return start_at + delta, end_at + delta


def next_weekday(base: date, weekday: int) -> date:
    """Return the next date with the given weekday (Mon=0)."""
    days_ahead = (weekday - base.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return base + timedelta(days=days_ahead)


def end_of_month(base: date) -> date:
    return (base.replace(day=1) + relativedelta(months=1)) - timedelta(days=1)
