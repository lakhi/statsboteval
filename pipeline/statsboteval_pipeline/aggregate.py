"""Weekly aggregation + privacy floor -> the contract document.

The floor (contract invariant 1) is applied in exactly one place: floored_count().
No other code may turn corpus numbers into cells. ISO-week bucketing happens in
Python after UTC->Europe/Vienna conversion — calendar knowledge lives here, not
in SQL (matching the contract's semester principle).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

import duckdb

from .contract import (
    Aggregates,
    AllTimeWindow,
    Footnote,
    OkCell,
    Sections,
    SuppressedCell,
    SCHEMA_VERSION,
    TemporalUsage,
    TemporalUsageWeekly,
    WeeklyEntry,
    WeeklySeries,
    date_to_week,
    ok,
    suppressed,
    week_monday,
    week_sunday,
    weeks_range,
)

VIENNA = ZoneInfo("Europe/Vienna")

# Footnote catalog texts are pinned in docs/aggregates-contract.md §6.2.
FOOTNOTES = {
    "chat_fragmentation": Footnote(
        text="The credit-limit UI nudges students toward starting new chats; "
        "conversation counts may overstate distinct dialogues."
    ),
}


def floored_count(value: int, n_students: int, floor_n: int) -> OkCell | SuppressedCell:
    """The one and only construction path from corpus numbers to a published cell."""
    if value < 0 or n_students < 0 or floor_n < 1:
        raise ValueError(f"invalid floor inputs: value={value} n_students={n_students} floor_n={floor_n}")
    if value > 0 and n_students == 0:
        raise ValueError(f"incoherent cell: value={value} with no contributing students")
    if n_students == 0 or n_students >= floor_n:
        return ok(value)
    return suppressed()


def _week_of(created_at_utc_naive: datetime) -> str:
    local = created_at_utc_naive.replace(tzinfo=timezone.utc).astimezone(VIENNA)
    return date_to_week(local.date())


def build_aggregates(
    con: duckdb.DuckDBPyConnection,
    *,
    floor_n: int,
    now: datetime,
    provenance: Literal["synthetic", "production"],
    pipeline_version: str,
) -> Aggregates:
    rows = con.execute("SELECT pseudonym, session_started, created_at FROM messages").fetchall()
    if not rows:
        raise ValueError("corpus has no messages; nothing to aggregate")

    msg_count: Counter[str] = Counter()
    msg_students: dict[str, set[str]] = defaultdict(set)
    session_first: dict[tuple[str, int], datetime] = {}
    for pseudonym, session_started, created_at in rows:
        week = _week_of(created_at)
        msg_count[week] += 1
        msg_students[week].add(pseudonym)
        key = (pseudonym, session_started)
        if key not in session_first or created_at < session_first[key]:
            session_first[key] = created_at

    # A session belongs to the week of its first message ((pseudonym, started) key, D-08).
    session_count: Counter[str] = Counter()
    session_students: dict[str, set[str]] = defaultdict(set)
    for (pseudonym, _), first_at in session_first.items():
        week = _week_of(first_at)
        session_count[week] += 1
        session_students[week].add(pseudonym)

    # Axis: complete ISO weeks only (invariant 3). data_through_week = the last week
    # fully elapsed before `now` (extract time) in Vienna. Trailing quiet weeks were
    # measured (extraction covered them, found nothing) -> they publish as ok(0);
    # clipping them off would misencode a measured zero as "absent" (invariant 2).
    now_week_monday = week_monday(date_to_week(now.astimezone(VIENNA).date()))
    through = date_to_week(now_week_monday - timedelta(days=7))
    first = min(msg_count, key=week_monday)
    if week_monday(first) > week_monday(through):
        raise ValueError("all corpus data lies in the current, incomplete week; nothing publishable")
    axis = weeks_range(first, through)

    def series(counts: Counter[str], students: dict[str, set[str]]) -> list[WeeklyEntry]:
        return [
            WeeklyEntry(week=w, cell=floored_count(counts.get(w, 0), len(students.get(w, set())), floor_n))
            for w in axis
        ]

    active_entries = [
        WeeklyEntry(
            week=w,
            cell=floored_count(len(msg_students.get(w, set())), len(msg_students.get(w, set())), floor_n),
        )
        for w in axis
    ]

    return Aggregates(
        schema_version=SCHEMA_VERSION,
        generated_at=now.astimezone(timezone.utc),
        data_through_week=through,
        data_through_date=week_sunday(through),
        first_week=first,
        privacy_floor_n=floor_n,
        label_versions={},
        timezone="Europe/Vienna",
        data_provenance=provenance,
        pipeline_version=pipeline_version,
        windows=[
            AllTimeWindow(
                kind="all_time",
                id="all_time",
                label="All time",
                coverage={"from": first, "through": through},  # type: ignore[arg-type]
            )
        ],
        footnotes=FOOTNOTES,
        sections=Sections(
            temporal_usage=TemporalUsage(
                weekly=TemporalUsageWeekly(
                    messages=WeeklySeries(series=series(msg_count, msg_students)),
                    sessions=WeeklySeries(
                        series=series(session_count, session_students),
                        footnote_ids=["chat_fragmentation"],
                    ),
                    active_students=WeeklySeries(series=active_entries),
                ),
                per_window={},
            )
        ),
    )
