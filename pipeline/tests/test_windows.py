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


def test_slice_names_its_semester_and_holds_its_closing_weeks() -> None:
    axis = weeks_range("2025-W09", "2025-W30")  # runs past the end of 2025S
    w = window(build_windows(axis), "2025S.last4")
    assert isinstance(w, SemesterSliceWindow)
    assert w.parent_window_id == "2025S"
    assert w.label == "Previous 4 weeks · SS 2025"
    assert w.short_label == "Previous 4 weeks"
    assert w.weeks == ["2025-W23", "2025-W24", "2025-W25", "2025-W26"]
    assert (w.coverage.from_, w.coverage.through) == ("2025-W23", "2025-W26")
    assert window(build_windows(axis), "2025S.last1").label == "Last available week · SS 2025"


def test_labels_do_not_depend_on_whether_the_term_is_still_running() -> None:
    # D-56 said "Latest" mid-term and "Final" afterwards; D-57 dropped the branch because
    # both phrasings below are true readings of either state, and the picker already marks
    # the semester itself "(in progress)". Same week-set, same words.
    running = build_windows(weeks_range("2025-W09", "2025-W20"))
    ended = build_windows(weeks_range("2025-W09", "2025-W30"))
    assert window(running, "2025S.last4").label == window(ended, "2025S.last4").label
    assert window(running, "2025S.last1").label == window(ended, "2025S.last1").label


def test_winter_slice_label_spans_the_new_year() -> None:
    axis = weeks_range("2025-W38", "2026-W07")
    assert window(build_windows(axis), "2025W.last1").label == "Last available week · WS 2025/26"


def test_short_slice_states_the_count_it_actually_holds() -> None:
    # Three teaching weeks in, "4 weeks" would be a promise the window cannot keep — the
    # exact failure that got trailing_4 renamed to "Last Avl. 4 weeks" instead of fixed.
    axis = weeks_range("2025-W09", "2025-W12")  # 2025S covered: W10, W11, W12
    w = window(build_windows(axis), "2025S.last4")
    assert w.label == "Previous 3 weeks · SS 2025"
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


def test_only_the_anchor_semester_is_sliced() -> None:
    # D-57: every semester stays selectable, but only the newest carries slices. The two
    # slice windows sit at the end of the registry, which is also their display order under
    # the picker's "Recent" heading — wider first.
    axis = weeks_range("2025-W09", "2026-W12")
    ids = [w.id for w in build_windows(axis)]
    assert ids == ["all_time", "2025S", "2025W", "2026S", "2026S.last4", "2026S.last1"]


@pytest.mark.parametrize(
    ("axis_end", "anchor", "last_week", "first_of_four"),
    [
        # The rollover table from the D-56 plan, re-pinned against anchor-only emission.
        # These are the moments the anchor moves, and the reason it must not be read off
        # the axis tail: on 2026-W39 the calendar says WS has begun, but no teaching week
        # has been extracted yet, so "recent" still belongs to the summer term.
        ("2026-W30", "2026S", "2026-W26", "2026-W23"),  # deep in the July/August break
        ("2026-W39", "2026S", "2026-W26", "2026-W23"),  # WS 2026 opens, no covered week yet
        ("2026-W41", "2026W", "2026-W41", "2026-W40"),  # first covered WS weeks: only two
        ("2026-W47", "2026W", "2026-W47", "2026-W44"),  # term running, a full four
    ],
)
def test_the_anchor_follows_the_data_not_the_calendar(
    axis_end: str, anchor: str, last_week: str, first_of_four: str
) -> None:
    windows = build_windows(weeks_range("2025-W09", axis_end))
    slices = [w for w in windows if w.kind == "semester_slice"]
    assert [w.id for w in slices] == [f"{anchor}.last4", f"{anchor}.last1"]
    assert all(w.parent_window_id == anchor for w in slices)
    assert window(windows, f"{anchor}.last1").weeks == [last_week]
    assert window(windows, f"{anchor}.last4").weeks[0] == first_of_four


def test_empty_axis_rejected() -> None:
    with pytest.raises(ValueError):
        build_windows([])
