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


def test_language_labels_come_from_the_real_heuristic(seeded: duckdb.DuckDBPyConnection) -> None:
    from statsboteval_pipeline.language import LABEL_VERSION

    codes = seeded.execute(
        "SELECT DISTINCT code FROM labels WHERE domain = 'language' AND label_version = ?", [LABEL_VERSION]
    ).fetchall()
    # Detection runs inside seed_synthetic, so a synthetic corpus is language-labelled the
    # same way a real one is — the Language tab was rendering 100% undetermined before T-6.
    assert {c for (c,) in codes} == {"de", "en", "undetermined"}


# --- planted between-semester shifts (T-6) --------------------------------------------
#
# These assert the *generator*: that a two-semester corpus really carries the shifts
# Trends is meant to find. Without them a change here could quietly flatten the corpus and
# the tab would render empty everywhere, with every trends test still green because they
# all drive build_trends directly. The end-to-end proof that the shifts survive
# aggregation and the publish guard is the run-synthetic test in test_cli.py — one
# expensive corpus for the whole suite, since labelling dominates the cost.

TWO_SEMESTER_ANCHOR = date(2026, 7, 1)  # a 38-week axis back from here covers 2025W + 2026S


@pytest.fixture(scope="module")
def two_semesters(tmp_path_factory: pytest.TempPathFactory) -> duckdb.DuckDBPyConnection:
    con = open_corpus(tmp_path_factory.mktemp("long") / "corpus.duckdb")
    seed_synthetic(con, weeks=38, seed=42, anchor=TWO_SEMESTER_ANCHOR, n_students=12)
    return con


def by_semester(con: duckdb.DuckDBPyConnection, expression: str) -> dict[str, float]:
    """`expression` averaged over messages, split by the semester of the message's week."""
    from statsboteval_pipeline.contract import date_to_week
    from statsboteval_pipeline.windows import _semester_of

    rows = con.execute(f"SELECT created_at, {expression} FROM messages").fetchall()
    buckets: dict[str, list[float]] = {}
    for created_at, value in rows:
        semester = _semester_of(date_to_week(created_at.date()))
        if semester is not None:
            buckets.setdefault(semester.id, []).append(float(value))
    return {sid: sum(values) / len(values) for sid, values in buckets.items()}


def test_the_axis_spans_two_semesters(two_semesters: duckdb.DuckDBPyConnection) -> None:
    # Everything below depends on this: one semester means no phase 1 and no planting.
    assert set(by_semester(two_semesters, "1")) == {"2025W", "2026S"}


def test_language_shift_is_planted(two_semesters: duckdb.DuckDBPyConnection) -> None:
    from statsboteval_pipeline.language import LABEL_VERSION

    # Read the detector's own verdict rather than pattern-matching the sentences: the
    # first attempt matched on a leading "W" and counted "What does ..." as German.
    german = by_semester(
        two_semesters,
        "CASE WHEN EXISTS (SELECT 1 FROM labels l WHERE l.history_id = messages.history_id "
        f"AND l.label_version = '{LABEL_VERSION}' AND l.domain = 'language' AND l.code = 'de') "
        "THEN 1 ELSE 0 END",
    )
    assert german["2025W"] - german["2026S"] > 0.15  # planted 0.7 -> 0.35, before undetermined


def test_engagement_shift_is_planted(two_semesters: duckdb.DuckDBPyConnection) -> None:
    per_session = two_semesters.execute(
        "SELECT min(created_at), count(*) FROM messages GROUP BY pseudonym, session_started"
    ).fetchall()
    from statsboteval_pipeline.contract import date_to_week
    from statsboteval_pipeline.windows import _semester_of

    sizes: dict[str, list[int]] = {}
    for started, size in per_session:
        semester = _semester_of(date_to_week(started.date()))
        if semester is not None:
            sizes.setdefault(semester.id, []).append(size)
    assert sum(sizes["2026S"]) / len(sizes["2026S"]) > sum(sizes["2025W"]) / len(sizes["2025W"]) + 2


def test_topic_shift_is_planted(two_semesters: duckdb.DuckDBPyConnection) -> None:
    from statsboteval_pipeline.fixtures import _METHOD_THEMES, seed_synthetic_labels
    from statsboteval_pipeline.labels import CURRENT_LABEL_VERSION

    seed_synthetic_labels(two_semesters, seed=42)
    share = by_semester(
        two_semesters,
        "CASE WHEN EXISTS (SELECT 1 FROM labels l WHERE l.history_id = messages.history_id "
        f"AND l.label_version = '{CURRENT_LABEL_VERSION}' AND l.domain = 'method_theme' "
        f"AND l.code = '{_METHOD_THEMES[0]}') THEN 1 ELSE 0 END",
    )
    assert share["2026S"] - share["2025W"] > 0.20  # planted 0.35 -> 0.65
    # Only the first method theme moves; the others stay flat, so the fixture also
    # exercises candidates that correctly publish nothing.
    flat = by_semester(
        two_semesters,
        "CASE WHEN EXISTS (SELECT 1 FROM labels l WHERE l.history_id = messages.history_id "
        f"AND l.label_version = '{CURRENT_LABEL_VERSION}' AND l.domain = 'method_theme' "
        f"AND l.code = '{_METHOD_THEMES[1]}') THEN 1 ELSE 0 END",
    )
    assert abs(flat["2026S"] - flat["2025W"]) < 0.05


def test_planting_is_inert_on_a_one_semester_axis(seeded: duckdb.DuckDBPyConnection) -> None:
    # The 8-week corpus every Phase A test is written against must be untouched by T-6.
    from statsboteval_pipeline.fixtures import _phase_by_week

    assert set(_phase_by_week(fixture_weeks(ANCHOR, 8)).values()) == {0}
    counts = seeded.execute("SELECT count(*) FROM messages GROUP BY pseudonym, session_started").fetchall()
    assert all(1 <= c[0] <= 10 for c in counts)  # the pre-T-6 range, unchanged


def test_students_registered_before_activity(seeded: duckdb.DuckDBPyConnection) -> None:
    bad = seeded.execute(
        """
        SELECT count(*) FROM messages m JOIN students s USING (pseudonym)
        WHERE m.created_at < s.registered_at
        """
    ).fetchone()[0]
    assert bad == 0
