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
    assert doc["label_versions"] == {"language": "lang-heuristic-v1"}
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
    assert cells(doc, "messages") == {
        "2025-W12": {"status": "ok", "value": 3},
        "2025-W13": {"status": "ok", "value": 0},
    }


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


# ---- GL4: full Phase A section set -----------------------------------------
# Hand corpus #2: everything below is hand-computed. Vienna is UTC+1 in March
# (DST starts Mar 30), so 09:00 UTC = 10:00 local. Axis: W10..W11 under
# NOW2 = Wednesday of 2025-W12.

NOW2 = datetime(2025, 3, 19, 6, 0, tzinfo=timezone.utc)


def insert_full(con: duckdb.DuckDBPyConnection, rows: list[tuple]) -> None:
    """rows: (history_id, pseudonym, session_started, created_at, completion_tokens)"""
    con.executemany(
        "INSERT INTO messages VALUES (?, ?, ?, ?, 'SYNTHETIC q', 'SYNTHETIC a', 100, ?)",
        rows,
    )


@pytest.fixture()
def con2(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    from statsboteval_pipeline.labels import LabelRow, write_labels

    c = open_corpus(tmp_path / "corpus.duckdb")
    c.executemany(
        "INSERT INTO students VALUES (?, ?)",
        [
            ("syn-0001", datetime(2025, 3, 3, 8, 0)),  # W10
            ("syn-0002", datetime(2025, 3, 4, 8, 0)),  # W10
            ("syn-0003", datetime(2025, 2, 10, 8, 0)),  # W07: before the axis
            ("syn-0004", datetime(2025, 3, 12, 8, 0)),  # W11, never messages
            ("syn-0000", datetime(2025, 2, 1, 8, 0)),  # pilot-phase student
        ],
    )
    insert_full(
        c,
        [
            # W10, all Monday Mar 3 09:xx UTC -> local (dow=1, hour=10)
            (1, "syn-0001", 1000, datetime(2025, 3, 3, 9, 0), 50),
            (2, "syn-0001", 1000, datetime(2025, 3, 3, 9, 5), 120),  # session A: 2 msgs, 5 min
            (3, "syn-0002", 2000, datetime(2025, 3, 3, 9, 10), 80),
            (4, "syn-0002", 2000, datetime(2025, 3, 3, 9, 40), 90),
            (5, "syn-0002", 2000, datetime(2025, 3, 3, 9, 55), 260),  # session C: 3 msgs, 45 min
            (6, "syn-0003", 3000, datetime(2025, 3, 3, 9, 20), 700),  # session E: 1 msg, 0 min
            # W11
            (7, "syn-0001", 4000, datetime(2025, 3, 10, 8, 0), 300),  # session B: local (1, 9)
            (8, "syn-0003", 5000, datetime(2025, 3, 11, 19, 0), 1200),  # session F: local (2, 20)
            # pilot-phase message, excluded once axis_start = 2025-03-01
            (100, "syn-0000", 500, datetime(2025, 2, 10, 10, 0), 10),
        ],
    )
    codes = {1: "de", 2: "en", 3: "de", 4: "de", 5: "undetermined", 6: "other", 7: "en"}  # 8, 100 unlabeled
    write_labels(
        c,
        [LabelRow(hid, "lang-heuristic-v1", "language", code, 1, "lingua-py") for hid, code in codes.items()],
    )
    return c


def build2(con: duckdb.DuckDBPyConnection, floor_n: int) -> dict:
    from datetime import date

    doc = build_aggregates(
        con,
        floor_n=floor_n,
        now=NOW2,
        provenance="synthetic",
        pipeline_version="0.1.0",
        axis_start=date(2025, 3, 1),
    )
    dumped = dump_doc(doc)
    jsonschema.validate(dumped, SCHEMA)
    return dumped


def test_axis_start_clips_pilot_traffic(con2: duckdb.DuckDBPyConnection) -> None:
    doc = build2(con2, floor_n=1)
    assert doc["first_week"] == "2025-W10"
    assert doc["data_through_week"] == "2025-W11"
    # Without axis_start the pilot message pulls the axis back to February.
    unclipped = dump_doc(build_aggregates(con2, floor_n=1, now=NOW2, provenance="synthetic", pipeline_version="0.1.0"))
    assert unclipped["first_week"] == "2025-W07"
    assert cells(unclipped, "messages")["2025-W07"] == {"status": "ok", "value": 1}


def test_windows_registry_in_document(con2: duckdb.DuckDBPyConnection) -> None:
    doc = build2(con2, floor_n=3)
    assert [w["id"] for w in doc["windows"]] == ["all_time", "2025S", "trailing_4"]
    sem = doc["windows"][1]
    assert sem["coverage"] == {"from": "2025-W10", "through": "2025-W11"}
    assert len(sem["weeks"]) == 17  # full 2025S membership, W10..W26
    for name in ("temporal_usage", "usage_context", "sessions", "tokens", "language"):
        assert set(doc["sections"][name]["per_window"]) == {"all_time", "2025S", "trailing_4"}, name


def test_heatmap_vienna_local(con2: duckdb.DuckDBPyConnection) -> None:
    doc = build2(con2, floor_n=3)
    grid = {
        (c["dow"], c["hour"]): c["cell"]
        for c in doc["sections"]["temporal_usage"]["per_window"]["all_time"]["activity_heatmap"]["cells"]
    }
    assert len(grid) == 168
    assert grid[(1, 10)] == {"status": "ok", "value": 6}  # 6 msgs, 3 students, 09:xx UTC -> 10 local
    assert grid[(1, 9)] == {"status": "suppressed"}  # 1 msg (syn-0001)
    assert grid[(2, 20)] == {"status": "suppressed"}  # 1 msg (syn-0003)
    assert grid[(1, 8)] == {"status": "ok", "value": 0}  # measured zero stays ok(0)


def test_usage_context_totals_and_registrations(con2: duckdb.DuckDBPyConnection) -> None:
    doc = build2(con2, floor_n=1)
    weekly = {e["week"]: e["cell"] for e in doc["sections"]["usage_context"]["weekly"]["registrations"]["series"]}
    assert weekly == {"2025-W10": {"status": "ok", "value": 2}, "2025-W11": {"status": "ok", "value": 1}}
    totals = doc["sections"]["usage_context"]["per_window"]["all_time"]["totals"]
    assert totals == {
        "active_students": {"status": "ok", "value": 3},
        "messages": {"status": "ok", "value": 8},
        "sessions": {"status": "ok", "value": 5},
        # syn-0003 registered in W07, outside the axis: not a new registration here.
        "new_registrations": {"status": "ok", "value": 3},
    }
    suppressed_doc = build2(con2, floor_n=3)
    weekly3 = {
        e["week"]: e["cell"] for e in suppressed_doc["sections"]["usage_context"]["weekly"]["registrations"]["series"]
    }
    assert weekly3 == {"2025-W10": {"status": "suppressed"}, "2025-W11": {"status": "suppressed"}}


def test_user_classes_bergmann_rules(con2: duckdb.DuckDBPyConnection) -> None:
    doc = build2(con2, floor_n=1)
    classes = doc["sections"]["usage_context"]["per_window"]["all_time"]["user_classes"]
    # syn-0002: one calendar day, 45 min -> one_time. syn-0001 span 8d, syn-0003 span 9d,
    # neither reaches span >= 30 for monthly -> both sporadic.
    assert classes["one_time"] == {"status": "ok", "value": 1}
    assert classes["monthly"] == {"status": "ok", "value": 0}
    assert classes["sporadic"] == {"status": "ok", "value": 2}
    assert classes["footnote_ids"] == ["user_class_definitions"]
    classes3 = build2(con2, floor_n=3)["sections"]["usage_context"]["per_window"]["all_time"]["user_classes"]
    assert classes3["one_time"] == {"status": "suppressed"}
    assert classes3["monthly"] == {"status": "ok", "value": 0}
    assert classes3["sporadic"] == {"status": "suppressed"}


def test_sessions_histograms(con2: duckdb.DuckDBPyConnection) -> None:
    win = build2(con2, floor_n=1)["sections"]["sessions"]["per_window"]["all_time"]
    mps = win["messages_per_session"]
    assert mps["unit"] == "sessions"
    assert [(b["lo"], b["hi"], b["cell"]["value"]) for b in mps["bins"]] == [
        (1, 1, 3),
        (2, 3, 2),
        (4, 7, 0),
        (8, None, 0),
    ]
    assert mps["n_total"] == {"status": "ok", "value": 5}
    assert mps["summary"] == {
        "status": "ok",
        "n_students": 3,
        "median": 1.0,
        "p25": 1.0,
        "p75": 2.0,
        "mean": 1.6,
        "sd": 0.9,
    }
    assert mps["footnote_ids"] == ["chat_fragmentation"]
    dur = win["session_duration_minutes"]
    # durations: A=5, C=45, E=B=F=0 minutes
    assert [(b["lo"], b["hi"], b["cell"]["value"]) for b in dur["bins"]] == [
        (0, 1, 3),
        (2, 5, 1),
        (6, 15, 0),
        (16, 30, 0),
        (31, None, 1),
    ]
    # Resumed chats make duration means meaningless (multi-day "sessions"):
    # robust stats only — no mean/sd keys at all in the dumped document.
    assert dur["summary"] == {
        "status": "ok",
        "n_students": 3,
        "median": 0.0,
        "p25": 0.0,
        "p75": 5.0,
    }
    assert dur["footnote_ids"] == ["chat_fragmentation", "duration_definition"]


def test_sessions_histogram_floor_per_bin(con2: duckdb.DuckDBPyConnection) -> None:
    mps = build2(con2, floor_n=3)["sections"]["sessions"]["per_window"]["all_time"]["messages_per_session"]
    by_lo = {b["lo"]: b["cell"] for b in mps["bins"]}
    assert by_lo[1] == {"status": "suppressed"}  # 3 sessions but only 2 students
    assert by_lo[2] == {"status": "suppressed"}  # 2 students
    assert by_lo[4] == {"status": "ok", "value": 0}
    assert mps["n_total"] == {"status": "ok", "value": 5}  # 3 students overall
    assert mps["summary"]["status"] == "ok"  # 3 contributing students >= floor


def test_tokens_histogram(con2: duckdb.DuckDBPyConnection) -> None:
    tok = build2(con2, floor_n=1)["sections"]["tokens"]["per_window"]["all_time"]["completion_tokens_per_message"]
    assert tok["unit"] == "messages"
    assert [(b["lo"], b["hi"], b["cell"]["value"]) for b in tok["bins"]] == [
        (0, 100, 3),
        (101, 250, 1),
        (251, 500, 2),
        (501, 1000, 1),
        (1001, None, 1),
    ]
    assert tok["summary"] == {
        "status": "ok",
        "n_students": 3,
        "median": 190.0,
        "p25": 85.0,
        "p75": 500.0,
        "mean": 350.0,
        "sd": 403.4,
    }


def test_language_section_joins_labels(con2: duckdb.DuckDBPyConnection) -> None:
    doc = build2(con2, floor_n=1)
    lang = doc["sections"]["language"]
    weekly = {
        code: {e["week"]: e["cell"]["value"] for e in lang["weekly"]["messages_by_language"][code]["series"]}
        for code in ("de", "en", "other", "undetermined")
    }
    assert weekly["de"] == {"2025-W10": 3, "2025-W11": 0}
    assert weekly["en"] == {"2025-W10": 1, "2025-W11": 1}
    assert weekly["other"] == {"2025-W10": 1, "2025-W11": 0}
    assert weekly["undetermined"] == {"2025-W10": 1, "2025-W11": 1}  # W11: msg 8 has no label
    assert lang["weekly"]["messages_by_language"]["footnote_ids"] == ["language_heuristic"]
    assert lang["per_window"]["all_time"]["totals"] == {
        "de": {"status": "ok", "value": 3},
        "en": {"status": "ok", "value": 2},
        "other": {"status": "ok", "value": 1},
        "undetermined": {"status": "ok", "value": 2},
    }
    assert doc["label_versions"] == {"language": "lang-heuristic-v1"}


def test_semester_window_matches_all_time_here(con2: duckdb.DuckDBPyConnection) -> None:
    # All data lies inside 2025S, so the semester rollup equals the all-time rollup.
    doc = build2(con2, floor_n=1)
    uc = doc["sections"]["usage_context"]["per_window"]
    assert uc["2025S"] == uc["all_time"]
    assert uc["trailing_4"] == uc["all_time"]  # trailing_4 clamps to the 2-week axis
