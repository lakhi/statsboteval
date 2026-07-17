"""GL6 (= Phase B Task 17): student erasure — synthetic corpus, fake publisher."""

from datetime import datetime
from pathlib import Path

import duckdb
import pytest

from statsboteval_pipeline.aggregate import build_aggregates
from statsboteval_pipeline.corpus import open_corpus
from statsboteval_pipeline.erase import erase_student
from statsboteval_pipeline.extract import PepperMismatchError, pseudonymize, verify_pepper
from statsboteval_pipeline.labels import LabelRow, write_labels

PEPPER = "synthetic-test-pepper"
NOW = datetime.fromisoformat("2025-03-19T06:00:00+00:00")


@pytest.fixture()
def con(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    c = open_corpus(tmp_path / "corpus.duckdb")
    verify_pepper(c, PEPPER)  # simulate first real ingest: fingerprint stored
    target, other = pseudonymize("a1234567", PEPPER), pseudonymize("b7654321", PEPPER)
    c.executemany(
        "INSERT INTO students VALUES (?, ?)",
        [(target, datetime(2025, 3, 3, 8, 0)), (other, datetime(2025, 3, 3, 9, 0))],
    )
    c.executemany(
        "INSERT INTO messages VALUES (?, ?, ?, ?, 'SYNTHETIC q', 'SYNTHETIC a', 100, 50)",
        [
            (1, target, 1000, datetime(2025, 3, 3, 10, 0)),
            (2, target, 1000, datetime(2025, 3, 3, 10, 5)),
            (3, other, 2000, datetime(2025, 3, 4, 11, 0)),
        ],
    )
    write_labels(
        c,
        [
            LabelRow(1, "lang-heuristic-v1", "language", "de", 1, "lingua-py"),
            LabelRow(2, "lang-heuristic-v1", "language", "en", 1, "lingua-py"),
            LabelRow(3, "lang-heuristic-v1", "language", "de", 1, "lingua-py"),
        ],
    )
    return c


def counts(con: duckdb.DuckDBPyConnection) -> tuple[int, int, int]:
    return tuple(  # type: ignore[return-value]
        con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("students", "messages", "labels")
    )


def test_erasure_removes_exactly_the_target(con: duckdb.DuckDBPyConnection, tmp_path: Path) -> None:
    log = tmp_path / "erasure.log"
    deleted = erase_student(con, "A1234567 ", pepper=PEPPER, log_path=log)  # normalization applies
    assert deleted == {"labels": 2, "messages": 2, "students": 1}
    assert counts(con) == (1, 1, 1)  # the other student is untouched
    other = pseudonymize("b7654321", PEPPER)
    assert con.execute("SELECT pseudonym FROM students").fetchone()[0] == other


def test_reaggregation_no_longer_reflects_erased_student(con: duckdb.DuckDBPyConnection, tmp_path: Path) -> None:
    before = build_aggregates(con, floor_n=1, now=NOW, provenance="synthetic", pipeline_version="0.1.0")
    erase_student(con, "a1234567", pepper=PEPPER, log_path=tmp_path / "erasure.log")
    after = build_aggregates(con, floor_n=1, now=NOW, provenance="synthetic", pipeline_version="0.1.0")
    totals = after.sections.usage_context.per_window["all_time"].totals
    assert totals.active_students.value == 1
    assert totals.messages.value == 1
    assert before.sections.usage_context.per_window["all_time"].totals.messages.value == 3


def test_unknown_uid_is_warned_noop(con: duckdb.DuckDBPyConnection, tmp_path: Path, capsys) -> None:
    log = tmp_path / "erasure.log"
    assert erase_student(con, "nobody999", pepper=PEPPER, log_path=log) is None
    assert counts(con) == (2, 3, 3)
    assert "no rows" in capsys.readouterr().err
    assert not log.exists()  # nothing erased -> nothing logged


def test_log_line_appended(con: duckdb.DuckDBPyConnection, tmp_path: Path) -> None:
    log = tmp_path / "erasure.log"
    erase_student(con, "a1234567", pepper=PEPPER, log_path=log)
    lines = log.read_text().splitlines()
    assert len(lines) == 1
    assert "students=1" in lines[0] and "messages=2" in lines[0] and "labels=2" in lines[0]
    assert "a1234567" not in lines[0]  # the identifier itself never lands in the log


def test_wrong_pepper_refuses(con: duckdb.DuckDBPyConnection, tmp_path: Path) -> None:
    with pytest.raises(PepperMismatchError):
        erase_student(con, "a1234567", pepper="wrong-pepper", log_path=tmp_path / "erasure.log")


def test_missing_fingerprint_refuses(tmp_path: Path) -> None:
    con = open_corpus(tmp_path / "fresh.duckdb")  # no ingest ever ran
    with pytest.raises(ValueError, match="fingerprint"):
        erase_student(con, "a1234567", pepper=PEPPER, log_path=tmp_path / "erasure.log")
