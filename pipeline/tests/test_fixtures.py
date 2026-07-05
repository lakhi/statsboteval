from datetime import date
from pathlib import Path

import duckdb
import pytest

from statsboteval_pipeline.corpus import open_corpus
from statsboteval_pipeline.fixtures import fixture_weeks, seed_synthetic

ANCHOR = date(2025, 4, 16)  # fixed anchor => fully deterministic axis for tests


@pytest.fixture()
def seeded(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    con = open_corpus(tmp_path / "corpus.duckdb")
    seed_synthetic(con, weeks=8, seed=42, anchor=ANCHOR)
    return con


def dump(con: duckdb.DuckDBPyConnection) -> tuple:
    return (
        con.execute("SELECT * FROM students ORDER BY pseudonym").fetchall(),
        con.execute("SELECT * FROM messages ORDER BY history_id").fetchall(),
    )


def message_weeks(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """week id -> distinct active students, from raw created_at (generator avoids tz-boundary spill)."""
    from statsboteval_pipeline.contract import date_to_week

    rows = con.execute("SELECT created_at, pseudonym FROM messages").fetchall()
    out: dict[str, set[str]] = {}
    for created_at, pseudonym in rows:
        out.setdefault(date_to_week(created_at.date()), set()).add(pseudonym)
    return {week: len(students) for week, students in out.items()}


def test_deterministic(tmp_path: Path) -> None:
    a = open_corpus(tmp_path / "a.duckdb")
    b = open_corpus(tmp_path / "b.duckdb")
    seed_synthetic(a, weeks=8, seed=42, anchor=ANCHOR)
    seed_synthetic(b, weeks=8, seed=42, anchor=ANCHOR)
    assert dump(a) == dump(b)


def test_axis_is_the_last_complete_weeks(seeded: duckdb.DuckDBPyConnection) -> None:
    weeks = fixture_weeks(ANCHOR, 8)
    assert len(weeks) == 8
    assert weeks[-1] == "2025-W15"  # last complete week before the anchor's week (W16)
    assert set(message_weeks(seeded)) <= set(weeks)  # no spill outside the axis


def test_zero_week_exists(seeded: duckdb.DuckDBPyConnection) -> None:
    weeks = fixture_weeks(ANCHOR, 8)
    assert set(weeks) - set(message_weeks(seeded)), "expected at least one week with no messages"


def test_suppression_week_exists(seeded: duckdb.DuckDBPyConnection) -> None:
    assert any(1 <= n <= 2 for n in message_weeks(seeded).values()), "expected a 1-2 student week"


def test_sessions_have_1_to_10_messages(seeded: duckdb.DuckDBPyConnection) -> None:
    counts = seeded.execute(
        "SELECT count(*) FROM messages GROUP BY pseudonym, session_started"
    ).fetchall()
    assert counts and all(1 <= c[0] <= 10 for c in counts)


def test_all_text_is_labeled_synthetic(seeded: duckdb.DuckDBPyConnection) -> None:
    bad = seeded.execute(
        "SELECT count(*) FROM messages WHERE sent NOT LIKE 'SYNTHETIC%' OR received NOT LIKE 'SYNTHETIC%'"
    ).fetchone()[0]
    assert bad == 0


def test_students_registered_before_activity(seeded: duckdb.DuckDBPyConnection) -> None:
    bad = seeded.execute(
        """
        SELECT count(*) FROM messages m JOIN students s USING (pseudonym)
        WHERE m.created_at < s.registered_at
        """
    ).fetchone()[0]
    assert bad == 0
