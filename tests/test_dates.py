"""Unit tests for deterministic date resolution."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from laia.services.dates import DateResolutionError, resolve_event_bounds, resolve_range

TZ = "America/Chicago"
NOW = datetime(2026, 7, 9, 10, 0, tzinfo=ZoneInfo(TZ))


def test_resolve_absolute_with_time() -> None:
    result = resolve_event_bounds(
        date_expression="July 14 2026",
        time_expression="2pm",
        timezone=TZ,
        now=NOW,
    )
    assert result.all_day is False
    assert result.start_at.hour == 14
    assert result.end_at.hour == 15


def test_resolve_relative_tomorrow() -> None:
    result = resolve_event_bounds(
        date_expression="tomorrow",
        time_expression="9am",
        duration_minutes=30,
        timezone=TZ,
        now=NOW,
    )
    assert result.start_at.date().isoformat() == "2026-07-10"
    assert result.start_at.hour == 9
    assert (result.end_at - result.start_at).total_seconds() == 1800


def test_missing_time_raises() -> None:
    with pytest.raises(DateResolutionError, match="Time is missing"):
        resolve_event_bounds(
            date_expression="next Tuesday",
            timezone=TZ,
            now=NOW,
        )


def test_all_day_bounds() -> None:
    result = resolve_event_bounds(
        date_expression="August 1 2026",
        all_day=True,
        timezone=TZ,
        now=NOW,
    )
    assert result.all_day is True
    assert result.start_at.isoformat().startswith("2026-08-01T00:00:00")
    assert result.end_at.isoformat().startswith("2026-08-02T00:00:00")


def test_in_two_hours() -> None:
    result = resolve_event_bounds(
        date_expression="today",
        time_expression="in two hours",
        duration_minutes=60,
        timezone=TZ,
        now=NOW,
    )
    assert result.start_at.hour == 12


def test_search_range() -> None:
    start, end = resolve_range(
        start_date_expression="tomorrow",
        end_date_expression="next Friday",
        timezone=TZ,
        now=NOW,
    )
    assert start is not None
    assert end is not None
    assert end >= start
