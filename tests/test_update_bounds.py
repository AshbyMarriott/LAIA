"""Unit tests for update date/time bound resolution."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from laia.orchestrator.pipeline import _resolve_update_bounds
from laia.services.calendar import CalendarService

TZ = "America/Chicago"
ZONE = ZoneInfo(TZ)


def _event(*, start: datetime, end: datetime, all_day: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        start_at=start,
        end_at=end,
        timezone=TZ,
        all_day=all_day,
    )


def test_all_day_end_only_preserves_start() -> None:
    # Camping Jul 17–23 stored with exclusive end Jul 24.
    event = _event(
        start=datetime(2026, 7, 17, 0, 0, tzinfo=ZONE),
        end=datetime(2026, 7, 24, 0, 0, tzinfo=ZONE),
        all_day=True,
    )
    bounds = _resolve_update_bounds(
        event,  # type: ignore[arg-type]
        tz_name=TZ,
        all_day=True,
        new_date_expression=None,
        new_time_expression=None,
        new_end_date_expression="July 20th",
        new_end_time_expression=None,
        duration_minutes=None,
        default_duration_minutes=60,
    )
    assert bounds.all_day is True
    assert bounds.start_at.date().isoformat() == "2026-07-17"
    assert bounds.end_at.date().isoformat() == "2026-07-21"  # exclusive


def test_all_day_start_only_preserves_end() -> None:
    event = _event(
        start=datetime(2026, 7, 17, 0, 0, tzinfo=ZONE),
        end=datetime(2026, 7, 24, 0, 0, tzinfo=ZONE),
        all_day=True,
    )
    bounds = _resolve_update_bounds(
        event,  # type: ignore[arg-type]
        tz_name=TZ,
        all_day=True,
        new_date_expression="July 18",
        new_time_expression=None,
        new_end_date_expression=None,
        new_end_time_expression=None,
        duration_minutes=None,
        default_duration_minutes=60,
    )
    assert bounds.start_at.date().isoformat() == "2026-07-18"
    assert bounds.end_at.date().isoformat() == "2026-07-24"  # exclusive through Jul 23


def test_timed_end_only_preserves_start_clock() -> None:
    event = _event(
        start=datetime(2026, 7, 17, 6, 0, tzinfo=ZONE),
        end=datetime(2026, 7, 20, 13, 0, tzinfo=ZONE),
    )
    bounds = _resolve_update_bounds(
        event,  # type: ignore[arg-type]
        tz_name=TZ,
        all_day=False,
        new_date_expression=None,
        new_time_expression=None,
        new_end_date_expression="July 19",
        new_end_time_expression="1pm",
        duration_minutes=None,
        default_duration_minutes=60,
    )
    assert bounds.start_at.isoformat().startswith("2026-07-17T06:00:00")
    assert bounds.end_at.isoformat().startswith("2026-07-19T13:00:00")


def test_normalize_bounds_keeps_exclusive_midnight_end() -> None:
    start = datetime(2026, 7, 17, 0, 0, tzinfo=ZONE)
    exclusive_end = datetime(2026, 7, 21, 0, 0, tzinfo=ZONE)
    out_start, out_end = CalendarService._normalize_bounds(
        start_at=start,
        end_at=exclusive_end,
        timezone=TZ,
        all_day=True,
    )
    assert out_start == start
    assert out_end == exclusive_end


def test_normalize_bounds_still_expands_inclusive_daytime_end() -> None:
    start = datetime(2026, 8, 1, 12, 0, tzinfo=ZONE)
    end = datetime(2026, 8, 1, 18, 0, tzinfo=ZONE)
    out_start, out_end = CalendarService._normalize_bounds(
        start_at=start,
        end_at=end,
        timezone=TZ,
        all_day=True,
    )
    assert out_start == datetime(2026, 8, 1, 0, 0, tzinfo=ZONE)
    assert out_end == datetime(2026, 8, 2, 0, 0, tzinfo=ZONE)
