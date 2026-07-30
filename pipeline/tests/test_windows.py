"""GL1: windows registry — all_time, semesters (Thursday rule), trailing_4.

Expected week memberships are hand-computed from the 2025/26 calendar:
2025S = W10..W26 (W09 Thu = Feb 27 -> break; W27 Thu = Jul 3 -> break),
2025W = 2025-W40..2026-W05 (W39 Thu = Sep 25 -> break; 2026-W06 Thu = Feb 5 -> break).
"""

from datetime import date

import pytest

from statsboteval_pipeline.contract import SemesterWindow, TrailingWindow, weeks_range
from statsboteval_pipeline.windows import build_windows


def window(windows: list, wid: str):
    matches = [w for w in windows if w.id == wid]
    assert len(matches) == 1, f"expected exactly one window {wid!r}, got {len(matches)}"
    return matches[0]


def test_all_time_covers_whole_axis() -> None:
    axis = weeks_range("2025-W09", "2025-W12")
    w = window(build_windows(axis), "all_time")
    assert w.kind == "all_time"
    assert w.label == "All time"
    assert (w.coverage.from_, w.coverage.through) == ("2025-W09", "2025-W12")


def test_semester_full_membership_but_clipped_coverage() -> None:
    # Axis ends mid-semester: weeks list the full semester, coverage only the data range.
    axis = weeks_range("2025-W09", "2025-W12")
    w = window(build_windows(axis), "2025S")
    assert isinstance(w, SemesterWindow)
    assert w.label == "Summer semester 2025"
    assert (w.start_date, w.end_date) == (date(2025, 3, 1), date(2025, 6, 30))
    assert w.weeks == weeks_range("2025-W10", "2025-W26")
    assert (w.coverage.from_, w.coverage.through) == ("2025-W10", "2025-W12")


def test_summer_semester_exact_membership() -> None:
    axis = weeks_range("2025-W01", "2025-W40")
    w = window(build_windows(axis), "2025S")
    assert w.weeks[0] == "2025-W10"  # week of Mar 1 (Sat) has Thu Feb 27 -> break
    assert w.weeks[-1] == "2025-W26"  # W27 Monday Jun 30 but Thu Jul 3 -> break


def test_winter_semester_straddles_new_year() -> None:
    axis = weeks_range("2025-W38", "2026-W07")
    w = window(build_windows(axis), "2025W")
    assert w.label == "Winter semester 2025/26"
    assert (w.start_date, w.end_date) == (date(2025, 10, 1), date(2026, 1, 31))
    assert w.weeks == weeks_range("2025-W40", "2026-W05")
    # New-Year week: Thursday Jan 1 2026 -> belongs to the winter semester.
    assert "2026-W01" in w.weeks
    # Axis extends past both semester ends, so coverage is the full membership.
    assert (w.coverage.from_, w.coverage.through) == ("2025-W40", "2026-W05")


def test_break_only_axis_has_no_semesters() -> None:
    axis = weeks_range("2025-W31", "2025-W33")  # August: break weeks
    windows = build_windows(axis)
    assert [w.kind for w in windows] == ["all_time", "trailing"]


def test_trailing_is_last_four_axis_weeks() -> None:
    axis = weeks_range("2025-W20", "2026-W02")
    w = window(build_windows(axis), "trailing_4")
    assert isinstance(w, TrailingWindow)
    assert w.label == "Last Avl. 4 weeks"
    assert w.weeks == ["2025-W51", "2025-W52", "2026-W01", "2026-W02"]
    assert (w.coverage.from_, w.coverage.through) == ("2025-W51", "2026-W02")


def test_trailing_clamps_to_short_axis() -> None:
    axis = weeks_range("2025-W31", "2025-W33")
    w = window(build_windows(axis), "trailing_4")
    assert w.weeks == axis


def test_window_order_all_time_then_semesters_then_trailing() -> None:
    axis = weeks_range("2025-W09", "2026-W12")
    ids = [w.id for w in build_windows(axis)]
    assert ids == ["all_time", "2025S", "2025W", "2026S", "trailing_4"]


def test_empty_axis_rejected() -> None:
    with pytest.raises(ValueError):
        build_windows([])
