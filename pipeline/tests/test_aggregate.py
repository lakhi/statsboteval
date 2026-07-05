import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import jsonschema
import pytest

from statsboteval_pipeline.aggregate import build_aggregates
from statsboteval_pipeline.contract import dump_doc
from statsboteval_pipeline.corpus import open_corpus

SCHEMA = json.loads((Path(__file__).resolve().parents[2] / "schema" / "aggregates.schema.json").read_text())

# Wednesday of 2025-W14 (Vienna) -> last complete week is 2025-W13.
NOW = datetime(2025, 4, 2, 6, 0, tzinfo=timezone.utc)


def insert(con: duckdb.DuckDBPyConnection, rows: list[tuple]) -> None:
    """rows: (history_id, pseudonym, session_started, created_at_utc_naive)"""
    con.executemany(
        "INSERT INTO messages VALUES (?, ?, ?, ?, 'SYNTHETIC q', 'SYNTHETIC a', 100, 50)",
        rows,
    )


@pytest.fixture()
def con(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    c = open_corpus(tmp_path / "corpus.duckdb")
    c.executemany(
        "INSERT INTO students VALUES (?, ?)",
        [(f"syn-{i:04d}", datetime(2025, 1, 1)) for i in range(1, 6)],
    )
    return c


def hand_corpus(con: duckdb.DuckDBPyConnection) -> None:
    # W11 (Mon 2025-03-10): 3 students, 3 sessions, 5 messages -> all ok.
    insert(
        con,
        [
            (1, "syn-0001", 1000, datetime(2025, 3, 10, 10, 0)),
            (2, "syn-0001", 1000, datetime(2025, 3, 10, 10, 5)),
            (3, "syn-0002", 2000, datetime(2025, 3, 11, 11, 0)),
            (4, "syn-0002", 2000, datetime(2025, 3, 11, 11, 9)),
            (5, "syn-0003", 3000, datetime(2025, 3, 12, 9, 0)),
        ],
    )
    # W12: 2 students, 4 messages, 2 sessions -> suppressed at N=3.
    insert(
        con,
        [
            (6, "syn-0004", 4000, datetime(2025, 3, 18, 10, 0)),
            (7, "syn-0004", 4000, datetime(2025, 3, 18, 10, 3)),
            (8, "syn-0004", 4000, datetime(2025, 3, 18, 10, 6)),
            (9, "syn-0005", 5000, datetime(2025, 3, 19, 15, 0)),
        ],
    )
    # W13: nothing -> ok(0) everywhere.


def cells(doc: dict, series: str) -> dict[str, dict]:
    weekly = doc["sections"]["temporal_usage"]["weekly"][series]["series"]
    return {entry["week"]: entry["cell"] for entry in weekly}


def test_hand_computed_document(con: duckdb.DuckDBPyConnection) -> None:
    hand_corpus(con)
    doc = dump_doc(build_aggregates(con, floor_n=3, now=NOW, provenance="synthetic", pipeline_version="0.1.0"))

    assert doc["first_week"] == "2025-W11"
    assert doc["data_through_week"] == "2025-W13"
    assert doc["data_through_date"] == "2025-03-30"
    assert doc["privacy_floor_n"] == 3
    assert doc["label_versions"] == {}
    assert doc["windows"][0]["id"] == "all_time"
    assert doc["windows"][0]["coverage"] == {"from": "2025-W11", "through": "2025-W13"}

    assert cells(doc, "messages") == {
        "2025-W11": {"status": "ok", "value": 5},
        "2025-W12": {"status": "suppressed"},
        "2025-W13": {"status": "ok", "value": 0},
    }
    assert cells(doc, "sessions") == {
        "2025-W11": {"status": "ok", "value": 3},
        "2025-W12": {"status": "suppressed"},
        "2025-W13": {"status": "ok", "value": 0},
    }
    assert cells(doc, "active_students") == {
        "2025-W11": {"status": "ok", "value": 3},
        "2025-W12": {"status": "suppressed"},
        "2025-W13": {"status": "ok", "value": 0},
    }
    assert doc["sections"]["temporal_usage"]["weekly"]["sessions"]["footnote_ids"] == ["chat_fragmentation"]
    assert "chat_fragmentation" in doc["footnotes"]

    jsonschema.validate(doc, SCHEMA)


def test_session_counted_in_week_of_first_message(con: duckdb.DuckDBPyConnection) -> None:
    # One session: first message Sunday of W11, second message Monday of W12.
    insert(
        con,
        [
            (1, "syn-0001", 1000, datetime(2025, 3, 16, 12, 0)),
            (2, "syn-0001", 1000, datetime(2025, 3, 17, 12, 0)),
            (3, "syn-0002", 2000, datetime(2025, 3, 10, 8, 0)),
            (4, "syn-0003", 3000, datetime(2025, 3, 11, 8, 0)),
            (5, "syn-0002", 6000, datetime(2025, 3, 18, 8, 0)),
            (6, "syn-0003", 7000, datetime(2025, 3, 19, 8, 0)),
        ],
    )
    doc = dump_doc(build_aggregates(con, floor_n=3, now=NOW, provenance="synthetic", pipeline_version="0.1.0"))
    # W11 sessions: 3 (incl. the spanning one, by first message); W12 sessions: 2, not 3.
    assert cells(doc, "sessions")["2025-W11"] == {"status": "ok", "value": 3}
    assert cells(doc, "sessions")["2025-W12"] == {"status": "suppressed"}  # 2 session-owning students
    assert cells(doc, "messages")["2025-W11"] == {"status": "ok", "value": 3}  # ids 1,3,4 (id 2 is W12)
    assert cells(doc, "messages")["2025-W12"] == {"status": "ok", "value": 3}  # 3 students >= N


def test_vienna_timezone_bucketing(con: duckdb.DuckDBPyConnection) -> None:
    # 23:30 UTC Sunday of W11 = 00:30 Monday Vienna (UTC+1 on 2025-03-16) -> W12.
    insert(
        con,
        [
            (1, "syn-0001", 1000, datetime(2025, 3, 16, 23, 30)),
            (2, "syn-0002", 2000, datetime(2025, 3, 17, 8, 0)),
            (3, "syn-0003", 3000, datetime(2025, 3, 17, 9, 0)),
        ],
    )
    doc = dump_doc(build_aggregates(con, floor_n=3, now=NOW, provenance="synthetic", pipeline_version="0.1.0"))
    assert doc["first_week"] == "2025-W12"
    assert cells(doc, "messages") == {"2025-W12": {"status": "ok", "value": 3}, "2025-W13": {"status": "ok", "value": 0}}


def test_incomplete_current_week_excluded(con: duckdb.DuckDBPyConnection) -> None:
    hand_corpus(con)
    # Data in W14 (the week containing NOW) must not appear (contract invariant 3).
    insert(con, [(100, "syn-0001", 9000, datetime(2025, 3, 31, 10, 0))])
    doc = dump_doc(build_aggregates(con, floor_n=3, now=NOW, provenance="synthetic", pipeline_version="0.1.0"))
    assert doc["data_through_week"] == "2025-W13"
    assert "2025-W14" not in cells(doc, "messages")


def test_empty_corpus_rejected(con: duckdb.DuckDBPyConnection) -> None:
    with pytest.raises(ValueError, match="no messages"):
        build_aggregates(con, floor_n=3, now=NOW, provenance="synthetic", pipeline_version="0.1.0")
