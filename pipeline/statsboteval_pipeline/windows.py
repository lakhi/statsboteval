"""Windows registry (contract §6.1): all_time, semesters, semester slices.

A week belongs to the semester containing its Thursday. SS = Mar 1-Jun 30,
WS = Oct 1-Jan 31 (following year); Feb and Jul-Sep weeks are break weeks and
belong only to all_time. Semester `weeks` list the full calendar membership;
`coverage` is clipped to the axis (the data range).

Each semester also publishes two slices of its own closing stretch (D-56): the last
covered week and the last up-to-`SLICE_WEEKS` covered weeks. These replace the old
axis-anchored `trailing_4`, which advanced with extraction whether or not anyone was in
class — across a break it drifted into weeks holding almost nothing.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from typing import NamedTuple

from .contract import (
    AllTimeWindow,
    Coverage,
    SemesterSliceWindow,
    SemesterWindow,
    Window,
    date_to_week,
    week_monday,
)

SLICE_WEEKS = 4


class _Semester(NamedTuple):
    id: str
    label: str
    short: str
    start_date: date
    end_date: date


def _semester_of(week: str) -> _Semester | None:
    """The semester owning this week (Thursday rule), or None for break weeks."""
    thursday = week_monday(week) + timedelta(days=3)
    y, m = thursday.year, thursday.month
    if 3 <= m <= 6:
        return _Semester(f"{y}S", f"Summer semester {y}", f"SS {y}", date(y, 3, 1), date(y, 6, 30))
    if m >= 10:
        return _winter(y)
    if m == 1:
        return _winter(y - 1)
    return None


def _winter(y: int) -> _Semester:
    """Both winter branches build the same tuple; two spellings of "2025/26" would drift."""
    spanning = f"{y}/{(y + 1) % 100:02d}"
    return _Semester(f"{y}W", f"Winter semester {spanning}", f"WS {spanning}", date(y, 10, 1), date(y + 1, 1, 31))


def _semester_weeks(start: date, end: date) -> list[str]:
    """Full membership: every week whose Thursday lies within [start, end]."""
    out: list[str] = []
    monday = week_monday(date_to_week(start))
    while monday <= end:
        if start <= monday + timedelta(days=3) <= end:
            out.append(date_to_week(monday))
        monday += timedelta(days=7)
    return out


def _slices(semester: SemesterWindow, covered: Sequence[str], short: str) -> list[SemesterSliceWindow]:
    """The semester's closing stretch, as one-week and up-to-SLICE_WEEKS windows.

    `running` decides the whole vocabulary: while a semester is in progress these weeks
    answer "how is it going", and once it has ended the same week-set answers "how did the
    term close". One fixed word cannot be right in both states.

    The multi-week label states the count it *actually* holds. Early in a term there are
    fewer than SLICE_WEEKS weeks to take, and saying "4 weeks" over two of them is exactly
    the failure that made the old trailing window need renaming to "Last Avl. 4 weeks"
    instead of fixing.
    """
    running = covered[-1] < semester.weeks[-1]
    word = "Latest" if running else "Final"
    out: list[SemesterSliceWindow] = []

    def slice_for(weeks: Sequence[str], suffix: str, short_label: str) -> SemesterSliceWindow:
        return SemesterSliceWindow(
            kind="semester_slice",
            id=f"{semester.id}.{suffix}",
            # "Latest week · SS 2026" (owner's wording): self-contained for the places that
            # print a window name into a sentence — card captions, empty states, the header.
            label=f"{short_label} · {short}",
            short_label=short_label,
            parent_window_id=semester.id,
            weeks=list(weeks),
            # Indexed against full membership, never `covered` — see contract._check_windows.
            semester_weeks=[
                semester.weeks.index(weeks[0]) + 1,
                semester.weeks.index(weeks[-1]) + 1,
            ],
            coverage=Coverage(from_=weeks[0], through=weeks[-1]),
        )

    # Widest first: the picker renders registry order, and a group reads whole -> narrower.
    if len(covered) >= 2:
        multi = covered[-SLICE_WEEKS:]
        out.append(slice_for(multi, f"last{SLICE_WEEKS}", f"{word} {len(multi)} weeks"))
    # At one covered week the multi-week slice would be a second name for this same week,
    # so it is omitted above rather than published as a duplicate under a different id.
    out.append(slice_for(covered[-1:], "last1", f"{word} week"))
    return out


def build_windows(axis: Sequence[str]) -> list[Window]:
    """Registry for a dense, chronological, complete-week axis (aggregate's invariant)."""
    if not axis:
        raise ValueError("axis is empty; no windows to build")

    windows: list[Window] = [
        AllTimeWindow(
            kind="all_time",
            id="all_time",
            label="All time",
            short_label="All time",
            coverage=Coverage(from_=axis[0], through=axis[-1]),
        )
    ]

    seen: set[str] = set()
    for week in axis:
        sem = _semester_of(week)
        if sem is None or sem.id in seen:
            continue
        seen.add(sem.id)
        weeks = _semester_weeks(sem.start_date, sem.end_date)
        covered = [w for w in axis if w in set(weeks)]
        semester = SemesterWindow(
            kind="semester",
            id=sem.id,
            label=sem.label,
            short_label="Whole semester",
            start_date=sem.start_date,
            end_date=sem.end_date,
            weeks=weeks,
            coverage=Coverage(from_=covered[0], through=covered[-1]),
        )
        windows.append(semester)
        windows.extend(_slices(semester, covered, sem.short))
    return windows
