"""Program-level student status: import + usage-time resolution (D-39).

The roster-derived CSV (`uid,status,ma_start_semester,source`) lives outside
the repo tree, beside its source Excel lists (custody rules:
docs/ethics/data-handling.md, program-level section). The importer HMACs uids
in flight with the extract's exact normalization — identifiers never enter the
corpus. Resolution implements the usage-time rule at session level (owner,
2026-07-17): a BA→MA transitioner counts as master from the calendar start of
their Master Beginnsemester (S → Mar 1, W → Oct 1), keyed on the session's
`started` timestamp in Vienna local time, so a session never straddles two
statuses. Students without a status row resolve to 'unknown' (the roster
snapshot is refreshed and re-imported each semester).
"""

from __future__ import annotations

import csv
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import NamedTuple
from zoneinfo import ZoneInfo

import duckdb

from .extract import pseudonymize, verify_pepper

STATUSES = ("bachelor", "master", "staff")
UNKNOWN = "unknown"

_SEMESTER_ID = re.compile(r"^(\d{4})([SW])$")
_VIENNA = ZoneInfo("Europe/Vienna")
_REQUIRED_COLUMNS = {"uid", "status", "ma_start_semester", "source"}


class StatusRow(NamedTuple):
    pseudonym: str
    status: str
    ma_start_semester: str | None
    provenance: str


class ImportResult(NamedTuple):
    imported: int
    unmatched_corpus_students: int  # corpus students without a status row (roster drift)


def semester_start(semester_id: str) -> date:
    match = _SEMESTER_ID.match(semester_id)
    if not match:
        raise ValueError(f"malformed semester id {semester_id!r} (expected e.g. '2025W' or '2026S')")
    year, term = int(match.group(1)), match.group(2)
    return date(year, 3, 1) if term == "S" else date(year, 10, 1)


def import_status_csv(con: duckdb.DuckDBPyConnection, csv_path: Path, *, pepper: str) -> ImportResult:
    """Upsert the roster CSV into `student_status`; returns counts incl. roster drift."""
    verify_pepper(con, pepper)
    if not csv_path.is_file():
        raise ValueError(f"status CSV not found: {csv_path} (check STUDENT_STATUS_CSV in pipeline/.env)")
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = _REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"status CSV missing column(s): {sorted(missing)}")
        rows: dict[str, StatusRow] = {}
        for lineno, record in enumerate(reader, start=2):
            uid = (record["uid"] or "").strip()
            status = (record["status"] or "").strip()
            ma_start = (record["ma_start_semester"] or "").strip() or None
            source = (record["source"] or "").strip()
            if not uid:
                raise ValueError(f"status CSV line {lineno}: empty uid")
            if status not in STATUSES:
                raise ValueError(f"status CSV line {lineno}: unknown status {status!r} (expected one of {STATUSES})")
            if ma_start is not None:
                if status != "bachelor":
                    raise ValueError(
                        f"status CSV line {lineno}: ma_start_semester is only valid with status 'bachelor' "
                        "(a transitioner row carries the pre-transition status)"
                    )
                semester_start(ma_start)  # format check
            if not source:
                raise ValueError(f"status CSV line {lineno}: empty source")
            pseudonym = pseudonymize(uid, pepper)
            if pseudonym in rows:
                raise ValueError(f"status CSV line {lineno}: duplicate uid (after normalization)")
            rows[pseudonym] = StatusRow(pseudonym, status, ma_start, source)
    con.executemany("INSERT OR REPLACE INTO student_status VALUES (?, ?, ?, ?)", [tuple(r) for r in rows.values()])
    unmatched = con.execute(
        "SELECT count(*) FROM students s "
        "WHERE NOT EXISTS (SELECT 1 FROM student_status t WHERE t.pseudonym = s.pseudonym)"
    ).fetchone()
    return ImportResult(len(rows), int(unmatched[0]) if unmatched else 0)


def read_status(con: duckdb.DuckDBPyConnection) -> dict[str, StatusRow]:
    return {
        row[0]: StatusRow(*row)
        for row in con.execute(
            "SELECT pseudonym, status, ma_start_semester, provenance FROM student_status"
        ).fetchall()
    }


def resolve_status(row: StatusRow | None, session_started_ms: int) -> str:
    """Status at usage time, session-level: 'bachelor' | 'master' | 'staff' | 'unknown'."""
    if row is None:
        return UNKNOWN
    if row.ma_start_semester is None:
        return row.status
    session_date = datetime.fromtimestamp(session_started_ms / 1000, tz=timezone.utc).astimezone(_VIENNA).date()
    return "master" if session_date >= semester_start(row.ma_start_semester) else row.status
