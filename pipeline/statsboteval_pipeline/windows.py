"""Windows registry (contract §6.1): all_time, semesters, trailing_4.

A week belongs to the semester containing its Thursday. SS = Mar 1-Jun 30,
WS = Oct 1-Jan 31 (following year); Feb and Jul-Sep weeks are break weeks and
belong only to all_time/trailing windows. Semester `weeks` list the full
calendar membership; `coverage` is clipped to the axis (the data range).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from typing import NamedTuple

from .contract import (
    AllTimeWindow,
    Coverage,
    SemesterWindow,
    TrailingWindow,
    Window,
    date_to_week,
    week_monday,
)

TRAILING_WEEKS = 4


class _Semester(NamedTuple):
    id: str
    label: str
    start_date: date
    end_date: date


def _semester_of(week: str) -> _Semester | None:
    """The semester owning this week (Thursday rule), or None for break weeks."""
    thursday = week_monday(week) + timedelta(days=3)
    y, m = thursday.year, thursday.month
    if 3 <= m <= 6:
        return _Semester(f"{y}S", f"Summer semester {y}", date(y, 3, 1), date(y, 6, 30))
    if m >= 10:
        return _Semester(f"{y}W", f"Winter semester {y}/{(y + 1) % 100:02d}", date(y, 10, 1), date(y + 1, 1, 31))
    if m == 1:
        return _Semester(f"{y - 1}W", f"Winter semester {y - 1}/{y % 100:02d}", date(y - 1, 10, 1), date(y, 1, 31))
    return None


def _semester_weeks(start: date, end: date) -> list[str]:
    """Full membership: every week whose Thursday lies within [start, end]."""
    out: list[str] = []
    monday = week_monday(date_to_week(start))
    while monday <= end:
        if start <= monday + timedelta(days=3) <= end:
            out.append(date_to_week(monday))
        monday += timedelta(days=7)
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
        windows.append(
            SemesterWindow(
                kind="semester",
                id=sem.id,
                label=sem.label,
                start_date=sem.start_date,
                end_date=sem.end_date,
                weeks=weeks,
                coverage=Coverage(from_=covered[0], through=covered[-1]),
            )
        )

    trailing = list(axis[-TRAILING_WEEKS:])
    windows.append(
        TrailingWindow(
            kind="trailing",
            id="trailing_4",
            label="Last Avl. 4 weeks",
            weeks=trailing,
            coverage=Coverage(from_=trailing[0], through=trailing[-1]),
        )
    )
    return windows
