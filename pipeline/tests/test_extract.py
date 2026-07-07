"""Extract-stage tests — stubbed source connection, no network, SYNTHETIC data only.

The production DB is live and strictly read-only (CLAUDE.md binding constraint 5);
the stub below asserts the extract never selects direct identifiers or the roster.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime
from pathlib import Path

import duckdb
import pytest

from statsboteval_pipeline.corpus import open_corpus
from statsboteval_pipeline.extract import (
    ExtractError,
    PepperMismatchError,
    extract_new_rows,
    pseudonymize,
)

PEPPER = "test-pepper-not-a-real-secret"


def expected_pseudonym(normalized_uid: str) -> str:
    return hmac.new(PEPPER.encode(), normalized_uid.encode(), hashlib.sha256).hexdigest()


class StubCursor:
    def __init__(self, source: StubSource) -> None:
        self._source = source
        self._results: list[tuple] = []

    def execute(self, sql: str, params: tuple | None = None) -> None:
        self._source.executed.append((sql, params))
        if "FROM students" in sql:
            self._results = list(self._source.students)
        elif "FROM history" in sql:
            assert params is not None, "history query must be watermark-parameterized"
            watermark = params[0]
            self._results = sorted((r for r in self._source.history if r[0] > watermark), key=lambda r: r[0])
        else:  # pragma: no cover - the extract must only run the two known queries
            raise AssertionError(f"unexpected query: {sql}")

    def fetchall(self) -> list[tuple]:
        out, self._results = self._results, []
        return out

    def fetchmany(self, size: int) -> list[tuple]:
        out, self._results = self._results[:size], self._results[size:]
        return out


class StubSource:
    """Minimal PEP-249 stand-in for the production MySQL connection."""

    def __init__(self, students: list[tuple], history: list[tuple]) -> None:
        self.students = students
        self.history = history
        self.executed: list[tuple[str, tuple | None]] = []

    def cursor(self) -> StubCursor:
        return StubCursor(self)


def msg(history_id: int, uid: str = "u:alice", started: int = 1_750_000_000_000) -> tuple:
    return (
        history_id,
        uid,
        started,
        datetime(2026, 5, 4, 10, history_id % 60),
        f"SYNTHETIC question {history_id}",
        f"SYNTHETIC reply {history_id}",
        100 + history_id,
        50,
    )


def fresh_corpus(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    return open_corpus(tmp_path / "corpus.duckdb")


def test_pseudonymize_normalizes_and_is_deterministic() -> None:
    assert pseudonymize("  U:Alice ", PEPPER) == pseudonymize("u:alice", PEPPER)
    assert pseudonymize("u:alice", PEPPER) == expected_pseudonym("u:alice")
    assert pseudonymize("u:alice", "another-pepper") != pseudonymize("u:alice", PEPPER)
    assert len(pseudonymize("u:alice", PEPPER)) == 64  # hex sha256


def test_extract_writes_only_pseudonymized_schema_columns(tmp_path: Path) -> None:
    con = fresh_corpus(tmp_path)
    source = StubSource(
        students=[("u:alice", datetime(2026, 4, 1, 9, 0)), ("  U:Bob ", datetime(2026, 4, 2, 9, 0))],
        history=[msg(1), msg(2, uid="  U:Bob "), msg(3)],
    )
    assert extract_new_rows(con, source, pepper=PEPPER) == 3

    students = dict(con.execute("SELECT pseudonym, registered_at FROM students").fetchall())
    assert set(students) == {expected_pseudonym("u:alice"), expected_pseudonym("u:bob")}
    assert students[expected_pseudonym("u:alice")] == datetime(2026, 4, 1, 9, 0)

    rows = con.execute(
        "SELECT history_id, pseudonym, session_started, created_at, sent, prompt_tokens, completion_tokens "
        "FROM messages ORDER BY history_id"
    ).fetchall()
    assert [r[0] for r in rows] == [1, 2, 3]
    assert rows[1][1] == expected_pseudonym("u:bob")
    assert rows[0][2] == 1_750_000_000_000
    assert rows[0][4] == "SYNTHETIC question 1"

    # The source is only ever asked the two known queries, and none of them touches
    # names, Matrikelnummer, e-mail, or the `import` roster table.
    all_sql = " ".join(sql for sql, _ in source.executed).lower()
    for forbidden in ("firstname", "lastname", "matrikelnummer", "e-mail", "import"):
        assert forbidden not in all_sql
    # ...and no raw uid survives into the corpus.
    dumped = str(con.execute("SELECT * FROM students").fetchall()) + str(con.execute("SELECT * FROM messages").fetchall())
    assert "u:alice" not in dumped and "U:Bob" not in dumped


def test_watermark_makes_reruns_incremental(tmp_path: Path) -> None:
    con = fresh_corpus(tmp_path)
    source = StubSource(students=[("u:alice", datetime(2026, 4, 1))], history=[msg(1), msg(2)])
    assert extract_new_rows(con, source, pepper=PEPPER) == 2
    source.history += [msg(3), msg(4)]
    assert extract_new_rows(con, source, pepper=PEPPER) == 2
    ids = [r[0] for r in con.execute("SELECT history_id FROM messages ORDER BY history_id").fetchall()]
    assert ids == [1, 2, 3, 4]


def test_empty_delta_is_a_noop(tmp_path: Path) -> None:
    con = fresh_corpus(tmp_path)
    source = StubSource(students=[("u:alice", datetime(2026, 4, 1))], history=[msg(1)])
    assert extract_new_rows(con, source, pepper=PEPPER) == 1
    assert extract_new_rows(con, source, pepper=PEPPER) == 0
    assert con.execute("SELECT count(*) FROM messages").fetchone()[0] == 1


def test_pepper_mismatch_fails_before_touching_the_source(tmp_path: Path) -> None:
    con = fresh_corpus(tmp_path)
    source = StubSource(students=[("u:alice", datetime(2026, 4, 1))], history=[msg(1)])
    extract_new_rows(con, source, pepper=PEPPER)
    queries_before = len(source.executed)
    with pytest.raises(PepperMismatchError):
        extract_new_rows(con, source, pepper="rotated-pepper")
    assert len(source.executed) == queries_before  # refused before any source query
    assert con.execute("SELECT count(*) FROM messages").fetchone()[0] == 1  # ...and before any write


def test_student_without_registration_time_is_skipped(tmp_path: Path) -> None:
    con = fresh_corpus(tmp_path)
    source = StubSource(students=[("u:alice", None)], history=[msg(1)])
    assert extract_new_rows(con, source, pepper=PEPPER) == 1
    assert con.execute("SELECT count(*) FROM students").fetchone()[0] == 0
    assert con.execute("SELECT count(*) FROM messages").fetchone()[0] == 1


def test_null_message_timestamp_fails_loudly(tmp_path: Path) -> None:
    con = fresh_corpus(tmp_path)
    bad = (7, "u:alice", 1_750_000_000_000, None, "SYNTHETIC q", "SYNTHETIC r", 100, 50)
    source = StubSource(students=[("u:alice", datetime(2026, 4, 1))], history=[bad])
    with pytest.raises(ExtractError, match="history.id=7"):
        extract_new_rows(con, source, pepper=PEPPER)


_LIVE_VARS = ("STATSBOT_DB_HOST", "STATSBOT_DB_NAME", "STATSBOT_DB_USER", "STATSBOT_DB_PASSWORD")


@pytest.mark.skipif(
    not all(os.environ.get(v) for v in _LIVE_VARS),
    reason="live smoke needs STATSBOT_DB_* exported (never set in CI; VPN required)",
)
def test_live_smoke_connects_read_only() -> None:
    from statsboteval_pipeline.config import ExtractSettings
    from statsboteval_pipeline.extract import connect_source

    settings = ExtractSettings(_env_file=None, pseudonym_pepper="smoke-only-never-ingests")
    conn = connect_source(settings)
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM history")
        assert cur.fetchall()[0][0] >= 0
    finally:
        conn.close()
