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


def test_all_day_multi_day_span_in_single_date_field() -> None:
    result = resolve_event_bounds(
        date_expression="07/17 through 07/20",
        all_day=True,
        timezone=TZ,
        now=NOW,
    )
    assert result.all_day is True
    assert result.start_at.date().isoformat() == "2026-07-17"
    assert result.end_at.date().isoformat() == "2026-07-21"


def test_all_day_phrase_in_time_expression() -> None:
    result = resolve_event_bounds(
        date_expression="07/17 through 07/20",
        time_expression="All day",
        timezone=TZ,
        now=NOW,
    )
    assert result.all_day is True
    assert result.start_at.date().isoformat() == "2026-07-17"
    assert result.end_at.date().isoformat() == "2026-07-21"


def test_timed_multi_day_span_fields() -> None:
    result = resolve_event_bounds(
        date_expression="07/17 through 07/20",
        time_expression="3pm to 1pm",
        timezone=TZ,
        now=NOW,
    )
    assert result.all_day is False
    assert result.start_at.isoformat().startswith("2026-07-17T15:00:00")
    assert result.end_at.isoformat().startswith("2026-07-20T13:00:00")


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
        end_date_expression="next Monday",
        timezone=TZ,
        now=NOW,
    )
    assert start is not None
    assert end is not None
    assert end >= start
    assert start.isoformat().startswith("2026-07-10T00:00:00")
    assert end.date().isoformat() == "2026-07-13"
    assert end.hour == 23 and end.minute == 59


def test_search_range_same_day_is_full_local_day() -> None:
    start, end = resolve_range(
        start_date_expression="July 14",
        end_date_expression="July 14",
        timezone=TZ,
        now=NOW,
    )
    assert start is not None and end is not None
    assert start.isoformat().startswith("2026-07-14T00:00:00")
    assert end.date().isoformat() == "2026-07-14"
    assert end.hour == 23 and end.minute == 59
    assert end > start


def test_search_range_end_only_includes_that_day() -> None:
    start, end = resolve_range(
        start_date_expression=None,
        end_date_expression="Friday",
        timezone=TZ,
        now=NOW,
    )
    assert start is None
    assert end is not None
    assert end.date().isoformat() == "2026-07-10"
    assert end.hour == 23 and end.minute == 59


def test_search_range_start_only_is_start_of_day() -> None:
    start, end = resolve_range(
        start_date_expression="tomorrow",
        end_date_expression=None,
        timezone=TZ,
        now=NOW,
    )
    assert end is None
    assert start is not None
    assert start.isoformat().startswith("2026-07-10T00:00:00")


def test_search_range_next_week_is_rolling_window() -> None:
    start, end = resolve_range(
        start_date_expression="next week",
        end_date_expression="next week",
        timezone=TZ,
        now=NOW,
    )
    assert start is not None and end is not None
    assert start.isoformat().startswith("2026-07-09T00:00:00")
    assert end.date().isoformat() == "2026-07-15"
    assert end.hour == 23 and end.minute == 59


def test_search_range_this_week_is_monday_through_sunday() -> None:
    start, end = resolve_range(
        start_date_expression="this week",
        end_date_expression="this week",
        timezone=TZ,
        now=NOW,
    )
    assert start is not None and end is not None
    assert start.isoformat().startswith("2026-07-06T00:00:00")
    assert end.date().isoformat() == "2026-07-12"


def test_search_range_this_month_is_full_calendar_month() -> None:
    start, end = resolve_range(
        start_date_expression="this month",
        end_date_expression="this month",
        timezone=TZ,
        now=NOW,
    )
    assert start is not None and end is not None
    assert start.isoformat().startswith("2026-07-01T00:00:00")
    assert end.date().isoformat() == "2026-07-31"
    assert end.hour == 23 and end.minute == 59


def test_search_range_next_month_is_full_next_calendar_month() -> None:
    start, end = resolve_range(
        start_date_expression="next month",
        end_date_expression="next month",
        timezone=TZ,
        now=NOW,
    )
    assert start is not None and end is not None
    assert start.isoformat().startswith("2026-08-01T00:00:00")
    assert end.date().isoformat() == "2026-08-31"
