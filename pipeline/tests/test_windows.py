"""GL1: windows registry — all_time, semesters (Thursday rule), semester slices.

Expected week memberships are hand-computed from the 2025/26 calendar:
2025S = W10..W26 (W09 Thu = Feb 27 -> break; W27 Thu = Jul 3 -> break),
2025W = 2025-W40..2026-W05 (W39 Thu = Sep 25 -> break; 2026-W06 Thu = Feb 5 -> break).
"""

from datetime import date

import pytest

from statsboteval_pipeline.contract import SemesterSliceWindow, SemesterWindow, weeks_range
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


def test_break_only_axis_has_no_semesters_and_therefore_no_slices() -> None:
    # August. Since D-56 "recent" is a slice of a semester, so an axis holding no teaching
    # week offers nothing but all_time — the honest answer, and a change from trailing_4,
    # which always published *something* even when it was four empty break weeks.
    axis = weeks_range("2025-W31", "2025-W33")
    windows = build_windows(axis)
    assert [w.kind for w in windows] == ["all_time"]


# --- semester slices (D-56) -----------------------------------------------------------


def test_completed_semester_slices_read_as_final() -> None:
    axis = weeks_range("2025-W09", "2025-W30")  # runs past the end of 2025S
    w = window(build_windows(axis), "2025S.last4")
    assert isinstance(w, SemesterSliceWindow)
    assert w.parent_window_id == "2025S"
    assert w.label == "Final 4 weeks · SS 2025"
    assert w.short_label == "Final 4 weeks"
    assert w.weeks == ["2025-W23", "2025-W24", "2025-W25", "2025-W26"]
    assert (w.coverage.from_, w.coverage.through) == ("2025-W23", "2025-W26")
    assert window(build_windows(axis), "2025S.last1").label == "Final week · SS 2025"


def test_running_semester_slices_read_as_latest() -> None:
    # Same week-set, different question: a term in progress is "how is it going", a term
    # that has ended is "how did it close". One fixed word cannot be right in both states.
    axis = weeks_range("2025-W09", "2025-W20")
    assert window(build_windows(axis), "2025S.last4").label == "Latest 4 weeks · SS 2025"
    assert window(build_windows(axis), "2025S.last1").label == "Latest week · SS 2025"


def test_winter_slice_label_spans_the_new_year() -> None:
    axis = weeks_range("2025-W38", "2026-W07")
    assert window(build_windows(axis), "2025W.last1").label == "Final week · WS 2025/26"


def test_short_slice_states_the_count_it_actually_holds() -> None:
    # Three teaching weeks in, "4 weeks" would be a promise the window cannot keep — the
    # exact failure that got trailing_4 renamed to "Last Avl. 4 weeks" instead of fixed.
    axis = weeks_range("2025-W09", "2025-W12")  # 2025S covered: W10, W11, W12
    w = window(build_windows(axis), "2025S.last4")
    assert w.label == "Latest 3 weeks · SS 2025"
    assert w.weeks == ["2025-W10", "2025-W11", "2025-W12"]


def test_single_covered_week_publishes_no_multi_week_slice() -> None:
    # It would hold exactly the same week as .last1 under a second id and a label claiming
    # more than one week.
    axis = weeks_range("2025-W09", "2025-W10")
    ids = [w.id for w in build_windows(axis)]
    assert "2025S.last4" not in ids
    assert ids == ["all_time", "2025S", "2025S.last1"]


def test_semester_weeks_index_full_membership_not_coverage() -> None:
    # The axis starts at W12, so 2025S's first two member weeks (W10, W11) are
    # unpublishable. The slice still has to report the teaching weeks it really spans:
    # indexing against covered weeks would call W12 "week 1" and slide every cross-semester
    # alignment left by two (the D-54 invariant).
    axis = weeks_range("2025-W12", "2025-W15")
    w = window(build_windows(axis), "2025S.last1")
    assert w.weeks == ["2025-W15"]
    assert w.semester_weeks == [6, 6]  # W10 is teaching week 1, so W15 is week 6
    assert window(build_windows(axis), "2025S.last4").semester_weeks == [3, 6]


def test_every_semester_gets_its_own_slices() -> None:
    axis = weeks_range("2025-W09", "2026-W12")
    ids = [w.id for w in build_windows(axis)]
    assert ids == [
        "all_time",
        "2025S", "2025S.last4", "2025S.last1",
        "2025W", "2025W.last4", "2025W.last1",
        "2026S", "2026S.last4", "2026S.last1",
    ]


def test_empty_axis_rejected() -> None:
    with pytest.raises(ValueError):
        build_windows([])
