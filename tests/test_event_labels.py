"""Unit tests for assistant event label formatting."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from laia.orchestrator.pipeline import format_event_label

TZ = "America/Chicago"
ZONE = ZoneInfo(TZ)


def test_timed_same_day_shows_start_and_end_time() -> None:
    label = format_event_label(
        title="Office meeting",
        start_at=datetime(2026, 7, 16, 15, 0, tzinfo=ZONE),
        end_at=datetime(2026, 7, 16, 16, 0, tzinfo=ZONE),
        timezone=TZ,
        all_day=False,
    )
    assert label == "Office meeting - July 16, 3:00 PM – 4:00 PM"


def test_timed_multi_day_shows_both_dates() -> None:
    label = format_event_label(
        title="Camping Trip",
        start_at=datetime(2026, 7, 17, 6, 0, tzinfo=ZONE),
        end_at=datetime(2026, 7, 20, 13, 0, tzinfo=ZONE),
        timezone=TZ,
        all_day=False,
    )
    assert label == "Camping Trip - July 17, 6:00 AM – July 20, 1:00 PM"


def test_all_day_single_day() -> None:
    label = format_event_label(
        title="Holiday",
        start_at=datetime(2026, 7, 17, 0, 0, tzinfo=ZONE),
        end_at=datetime(2026, 7, 18, 0, 0, tzinfo=ZONE),
        timezone=TZ,
        all_day=True,
    )
    assert label == "Holiday - July 17 (all day)"


def test_all_day_multi_day_uses_inclusive_end() -> None:
    # Stored as exclusive end midnight on Jul 21 for inclusive Jul 17–20.
    label = format_event_label(
        title="Camping Trip",
        start_at=datetime(2026, 7, 17, 0, 0, tzinfo=ZONE),
        end_at=datetime(2026, 7, 21, 0, 0, tzinfo=ZONE),
        timezone=TZ,
        all_day=True,
    )
    assert label == "Camping Trip - July 17 – July 20 (all day)"
