"""Deterministic date/time resolution for natural-language expressions."""

from __future__ import annotations

import re
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

_ALL_DAY_PHRASES = frozenset(
    {
        "all day",
        "all-day",
        "allday",
        "the whole day",
        "whole day",
        "entire day",
        "the entire day",
    }
)

# Multi-day spans stuffed into one field: "07/17 through 07/20", "Friday to Monday".
_DATE_SPAN_SPLIT = re.compile(
    r"\s+(?:through|thru|until|til|to)\s+|\s+[–—]\s+|\s+-\s+",
    re.IGNORECASE,
)

# Timed spans stuffed into one field: "3pm to 1pm", "15:00 - 13:00".
_TIME_SPAN_SPLIT = re.compile(
    r"\s+(?:to|until|til|-|–|—)\s+",
    re.IGNORECASE,
)
_TIME_LIKE = re.compile(
    r"(\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?)|\bnoon\b|\bmidnight\b",
    re.IGNORECASE,
)


def is_all_day_phrase(expression: str | None) -> bool:
    """True when a follow-up or time slot clearly means an all-day event."""
    if not expression:
        return False
    return expression.strip().lower() in _ALL_DAY_PHRASES


def _split_date_span(expression: str) -> tuple[str, str] | None:
    parts = _DATE_SPAN_SPLIT.split(expression.strip(), maxsplit=1)
    if len(parts) != 2:
        return None
    start, end = parts[0].strip(), parts[1].strip()
    if not start or not end:
        return None
    return start, end


def _split_time_span(expression: str) -> tuple[str, str] | None:
    parts = _TIME_SPAN_SPLIT.split(expression.strip(), maxsplit=1)
    if len(parts) != 2:
        return None
    start, end = parts[0].strip(), parts[1].strip()
    if not (start and end and _TIME_LIKE.search(start) and _TIME_LIKE.search(end)):
        return None
    return start, end


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

    # Models often stuff "07/17 through 07/20" or "3pm to 1pm" into one field.
    if date_expression and not end_date_expression:
        span = _split_date_span(date_expression)
        if span:
            date_expression, end_date_expression = span
    if time_expression and not end_time_expression:
        if is_all_day_phrase(time_expression):
            all_day = True
            time_expression = None
        else:
            span = _split_time_span(time_expression)
            if span:
                time_expression, end_time_expression = span

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


_THIS_WEEK_PHRASES = frozenset(
    {
        "this week",
        "the week",
        "current week",
        "this current week",
    }
)
_NEXT_WEEK_PHRASES = frozenset(
    {
        "next week",
        "the next week",
        "in the next week",
        "over the next week",
        "for the next week",
        "coming week",
        "the coming week",
        "in the coming week",
        "upcoming week",
        "the upcoming week",
    }
)
_THIS_MONTH_PHRASES = frozenset(
    {
        "this month",
        "the month",
        "current month",
        "this current month",
        "in this month",
    }
)
_NEXT_MONTH_PHRASES = frozenset(
    {
        "next month",
        "the next month",
        "in the next month",
        "over the next month",
        "for the next month",
        "coming month",
        "the coming month",
        "in the coming month",
    }
)


def _normalize_range_phrase(expression: str) -> str:
    return " ".join(expression.strip().lower().split())


def _try_period_bounds(
    expression: str,
    *,
    base: datetime,
    tz: ZoneInfo,
) -> tuple[datetime, datetime] | None:
    """Expand week/month phrases into inclusive local bounds."""
    text = _normalize_range_phrase(expression)
    today = base.date()

    if text in _THIS_WEEK_PHRASES:
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        return (
            datetime.combine(monday, time.min, tzinfo=tz),
            datetime.combine(sunday, time.max, tzinfo=tz),
        )

    if text in _NEXT_WEEK_PHRASES:
        # Rolling week from today so "events in the next week" includes tomorrow.
        end_day = today + timedelta(days=6)
        return (
            datetime.combine(today, time.min, tzinfo=tz),
            datetime.combine(end_day, time.max, tzinfo=tz),
        )

    if text in _THIS_MONTH_PHRASES:
        first = today.replace(day=1)
        last = end_of_month(today)
        return (
            datetime.combine(first, time.min, tzinfo=tz),
            datetime.combine(last, time.max, tzinfo=tz),
        )

    if text in _NEXT_MONTH_PHRASES:
        first_next = (today.replace(day=1) + relativedelta(months=1))
        last_next = end_of_month(first_next)
        return (
            datetime.combine(first_next, time.min, tzinfo=tz),
            datetime.combine(last_next, time.max, tzinfo=tz),
        )

    return None


def resolve_range(
    *,
    start_date_expression: str | None,
    end_date_expression: str | None,
    timezone: str,
    now: datetime | None = None,
) -> tuple[datetime | None, datetime | None]:
    """Resolve an optional search range into inclusive local calendar-day bounds.

    Date expressions parse to a single instant (often midnight or "now" on that day).
    For search overlap filters, normalize start to local 00:00:00 and end to local
    23:59:59.999999 so same-day queries like start=end="Friday" include timed events.

    Week/month phrases such as "this week" / "this month" expand to a multi-day window.
    """
    tz = _zone(timezone)
    base = now.astimezone(tz) if now is not None else datetime.now(tz=tz)

    start_period = (
        _try_period_bounds(start_date_expression, base=base, tz=tz)
        if start_date_expression
        else None
    )
    end_period = (
        _try_period_bounds(end_date_expression, base=base, tz=tz)
        if end_date_expression
        else None
    )

    if start_period and end_period:
        start, end = start_period[0], end_period[1]
    elif start_period and not end_date_expression:
        start, end = start_period
    elif end_period and not start_date_expression:
        start, end = end_period
    elif start_period and end_date_expression:
        end_instant = _parse_expression(
            end_date_expression, base=base, timezone=timezone, prefer_future=False
        )
        start = start_period[0]
        end = datetime.combine(end_instant.date(), time.max, tzinfo=tz)
    elif end_period and start_date_expression:
        start_instant = _parse_expression(
            start_date_expression, base=base, timezone=timezone, prefer_future=False
        )
        start = datetime.combine(start_instant.date(), time.min, tzinfo=tz)
        end = end_period[1]
    else:
        start = (
            _parse_expression(
                start_date_expression, base=base, timezone=timezone, prefer_future=False
            )
            if start_date_expression
            else None
        )
        end = (
            _parse_expression(
                end_date_expression, base=base, timezone=timezone, prefer_future=False
            )
            if end_date_expression
            else None
        )
        if start is not None:
            start = datetime.combine(start.date(), time.min, tzinfo=tz)
        if end is not None:
            end = datetime.combine(end.date(), time.max, tzinfo=tz)

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
