"""Extract stage (D-33): production MySQL → pseudonymized DuckDB corpus.

Binding rules (CLAUDE.md constraint 5; docs/source-data-dictionary.md):
- The production DB is LIVE and strictly read-only: `connect_source` opens the
  session with `SET SESSION TRANSACTION READ ONLY` (server-enforced) and this
  module issues only the two SELECTs below.
- Timestamps are read with the server-default session timezone — never
  `time_zone='+00:00'` — which reproduces the UTC wall-clock strings Laravel
  wrote (see the data dictionary's "Timestamps & timezone").
- Direct identifiers never touch disk: `uid` is HMAC-pseudonymized in flight;
  names, Matrikelnummer, and the `import` roster table are never selected.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Protocol

import duckdb

from .config import ExtractSettings

if TYPE_CHECKING:
    import pymysql.connections

_PEPPER_KEY = "pepper_sha256"
_LAST_EXTRACTED_AT_KEY = "last_extracted_at"
_BATCH_SIZE = 500

_STUDENTS_SQL = "SELECT uid, created_at FROM students"
_HISTORY_SQL = (
    "SELECT h.id, s.uid, h.started, h.created_at, h.sent, h.received, h.prompt_tokens, h.completion_tokens"
    " FROM history h JOIN students s ON s.id = h.student_id"
    " WHERE h.id > %s ORDER BY h.id"
)


class ExtractError(RuntimeError):
    """A source row violates an assumption; investigate before ingesting."""


class PepperMismatchError(ExtractError):
    """The configured pepper is not the one this corpus was built with (D-34)."""


class SourceConnection(Protocol):
    """PEP-249 duck type: satisfied by pymysql and by the test stub alike."""

    def cursor(self) -> Any: ...


def normalize_uid(uid: str) -> str:
    """Trim + lowercase — without this, casing/whitespace variants silently fork pseudonyms."""
    return uid.strip().lower()


def pseudonymize(uid: str, pepper: str) -> str:
    return hmac.new(pepper.encode(), normalize_uid(uid).encode(), hashlib.sha256).hexdigest()


def verify_pepper(con: duckdb.DuckDBPyConnection, pepper: str) -> None:
    """Store the pepper fingerprint on first ingest; refuse to run on any later mismatch."""
    fingerprint = hashlib.sha256(pepper.encode()).hexdigest()
    row = con.execute("SELECT value FROM meta WHERE key = ?", [_PEPPER_KEY]).fetchone()
    if row is None:
        con.execute("INSERT INTO meta VALUES (?, ?)", [_PEPPER_KEY, fingerprint])
    elif row[0] != fingerprint:
        raise PepperMismatchError(
            "PSEUDONYM_PEPPER does not match the fingerprint this corpus was built with; "
            "a mismatched pepper would silently fork every pseudonym. Restore the original "
            "pepper (password-manager backup, D-34) or re-ingest from scratch."
        )


def record_extraction_time(con: duckdb.DuckDBPyConnection, now: datetime) -> None:
    """Persist when extraction last actually queried the source DB (even a quiet run).

    This is the only trustworthy anchor for "how far does the corpus really reach":
    read_corpus_view derives the published axis boundary from this, not from wall-clock
    `now` at aggregate time, so a later re-aggregate without a fresh extract (e.g.
    erase-student, or iterating on a new tab) can't silently publish weeks past the
    data as if they were measured zeros.
    """
    value = now.astimezone(timezone.utc).isoformat()
    row = con.execute("SELECT 1 FROM meta WHERE key = ?", [_LAST_EXTRACTED_AT_KEY]).fetchone()
    if row is None:
        con.execute("INSERT INTO meta VALUES (?, ?)", [_LAST_EXTRACTED_AT_KEY, value])
    else:
        con.execute("UPDATE meta SET value = ? WHERE key = ?", [value, _LAST_EXTRACTED_AT_KEY])


def read_last_extracted_at(con: duckdb.DuckDBPyConnection) -> datetime | None:
    """The stored extraction watermark, or None if extract_new_rows has never run."""
    row = con.execute("SELECT value FROM meta WHERE key = ?", [_LAST_EXTRACTED_AT_KEY]).fetchone()
    return datetime.fromisoformat(row[0]) if row is not None else None


def connect_source(settings: ExtractSettings) -> pymysql.connections.Connection:
    """Open the production connection: read-only session, server-default timezone."""
    import pymysql

    return pymysql.connect(
        host=settings.statsbot_db_host,
        port=settings.statsbot_db_port,
        user=settings.statsbot_db_user,
        password=settings.statsbot_db_password,
        database=settings.statsbot_db_name,
        charset="utf8mb4",
        connect_timeout=15,
        read_timeout=300,
        init_command="SET SESSION TRANSACTION READ ONLY",
    )


def extract_new_rows(
    con: duckdb.DuckDBPyConnection,
    source: SourceConnection,
    *,
    pepper: str,
    now: datetime | None = None,
) -> int:
    """Ingest source rows above the corpus watermark; return the count of new messages.

    Incremental and idempotent: the watermark is MAX(messages.history_id) and history
    rows arrive in ascending id order, so a mid-run failure leaves a valid resume point.
    """
    verify_pepper(con, pepper)
    row = con.execute("SELECT COALESCE(MAX(history_id), 0) FROM messages").fetchone()
    watermark = int(row[0]) if row is not None else 0

    cur = source.cursor()
    cur.execute(_STUDENTS_SQL)
    students = [
        (pseudonymize(uid, pepper), registered_at)
        for uid, registered_at in cur.fetchall()
        if registered_at is not None  # rare NULL registration time: no honest value to invent
    ]
    if students:
        con.executemany("INSERT OR IGNORE INTO students VALUES (?, ?)", students)

    cur.execute(_HISTORY_SQL, (watermark,))
    total = 0
    while batch := cur.fetchmany(_BATCH_SIZE):
        rows = []
        for history_id, uid, started, created_at, sent, received, prompt_tokens, completion_tokens in batch:
            if created_at is None:
                raise ExtractError(f"history.id={history_id} has NULL created_at; investigate before ingesting")
            rows.append(
                (
                    history_id,
                    pseudonymize(uid, pepper),
                    int(started),
                    created_at,
                    sent,
                    received,
                    prompt_tokens,
                    completion_tokens,
                )
            )
        con.executemany("INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
        total += len(rows)
    record_extraction_time(con, now or datetime.now(timezone.utc))
    return total
