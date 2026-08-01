"""Phase B Task 14: topics aggregation (labels -> contract, floored; by_status per D-39)."""

import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import jsonschema
import pytest

from statsboteval_pipeline.aggregate import build_aggregates
from statsboteval_pipeline.contract import dump_doc
from statsboteval_pipeline.corpus import open_corpus
from statsboteval_pipeline.labels import LabelRow, write_labels

SCHEMA = json.loads((Path(__file__).resolve().parents[2] / "schema" / "aggregates.schema.json").read_text())

# Wednesday of 2025-W14 (Vienna) -> last complete week is 2025-W13.
NOW = datetime(2025, 4, 2, 6, 0, tzinfo=timezone.utc)
VERSION = "statsboteval-v1"


def ms(iso: str) -> int:
    return int(datetime.fromisoformat(iso).replace(tzinfo=timezone.utc).timestamp() * 1000)


def insert_message(con: duckdb.DuckDBPyConnection, history_id: int, pseudonym: str, created: str) -> None:
    con.execute(
        "INSERT INTO messages VALUES (?, ?, ?, ?, 'SYNTHETIC q', 'SYNTHETIC a', 100, 50)",
        [history_id, pseudonym, ms(created), datetime.fromisoformat(created)],
    )


def label(con: duckdb.DuckDBPyConnection, history_id: int, domain: str, code: str, value: int = 1) -> None:
    write_labels(con, [LabelRow(history_id, VERSION, domain, code, value, "stub@2026")])


@pytest.fixture()
def con(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    c = open_corpus(tmp_path / "corpus.duckdb")
    c.executemany(
        "INSERT INTO students VALUES (?, ?)",
        [(f"syn-{i:04d}", datetime(2025, 1, 1)) for i in range(1, 6)],
    )
    return c


def seed_labeled_corpus(con: duckdb.DuckDBPyConnection) -> None:
    # W11: three students, one message each; W12: one more from syn-0001.
    insert_message(con, 1, "syn-0001", "2025-03-10 10:00:00")
    insert_message(con, 2, "syn-0002", "2025-03-11 10:00:00")
    insert_message(con, 3, "syn-0003", "2025-03-12 10:00:00")
    insert_message(con, 4, "syn-0001", "2025-03-18 10:00:00")
    # deductive: alpha on 1,2,3 (3 students -> ok); beta explicit 0s except msg 4 (1 student -> suppressed)
    for history_id in (1, 2, 3):
        label(con, history_id, "deductive", "synthetic_alpha")
        label(con, history_id, "deductive", "synthetic_beta", 0)
    label(con, 4, "deductive", "synthetic_alpha", 0)
    label(con, 4, "deductive", "synthetic_beta", 1)
    # themes: method on 1,2,3 (ok); software on 4 only (suppressed)
    for history_id in (1, 2, 3):
        label(con, history_id, "method_theme", "synthetic method one")
    label(con, 4, "software_theme", "synthetic software one")


def build(con: duckdb.DuckDBPyConnection, floor_n: int = 3, **kwargs):
    return build_aggregates(
        con, floor_n=floor_n, now=NOW, provenance="synthetic", pipeline_version="0.1.0", **kwargs
    )


def all_time_topics(doc) -> dict:
    return dump_doc(doc)["sections"]["topics"]["per_window"]["all_time"]


def test_hand_computed_topics_with_suppression(con: duckdb.DuckDBPyConnection) -> None:
    seed_labeled_corpus(con)
    doc = build(con, classification_version=VERSION)
    entry = all_time_topics(doc)
    deductive = {item["label"]: item["cell"] for item in entry["deductive"]["items"]}
    assert deductive["synthetic_alpha"] == {"status": "ok", "value": 3}
    assert deductive["synthetic_beta"] == {"status": "suppressed"}  # 1 student < floor 3
    assert entry["deductive"]["n_total"] == {"status": "ok", "value": 4}  # 4 msgs, 3 students
    method = {item["label"]: item["cell"] for item in entry["method_themes"]["items"]}
    assert method["synthetic method one"] == {"status": "ok", "value": 3}
    software = {item["label"]: item["cell"] for item in entry["software_themes"]["items"]}
    assert software["synthetic software one"] == {"status": "suppressed"}
    assert "emergent_themes" not in entry  # none labeled -> omitted (designed state)
    assert "by_status" not in entry  # no status rows -> omitted
    assert doc.label_versions["classification"] == VERSION
    assert entry["deductive"]["footnote_ids"] == ["multi_label", "label_provenance"]
    jsonschema.validate(dump_doc(doc), SCHEMA)


def test_real_category_code_gets_display_label(con: duckdb.DuckDBPyConnection) -> None:
    insert_message(con, 1, "syn-0001", "2025-03-10 10:00:00")
    label(con, 1, "deductive", "statistics_interaction")
    doc = build(con, floor_n=1, classification_version=VERSION)
    labels = [item["label"] for item in all_time_topics(doc)["deductive"]["items"]]
    assert labels == ["Statistics Interaction"]  # public manuscript name, not the slug


def test_no_labels_or_no_version_omits_topics(con: duckdb.DuckDBPyConnection) -> None:
    insert_message(con, 1, "syn-0001", "2025-03-10 10:00:00")
    assert build(con).sections.topics is None
    doc = build(con, classification_version=VERSION)  # version configured, no labels yet
    assert doc.sections.topics is None
    assert "classification" not in doc.label_versions
    jsonschema.validate(dump_doc(doc), SCHEMA)


def status_row(con: duckdb.DuckDBPyConnection, pseudonym: str, status: str, ma_start: str | None = None) -> None:
    con.execute("INSERT INTO student_status VALUES (?, ?, ?, 'synthetic-roster')", [pseudonym, status, ma_start])


def test_transitioner_splits_by_session_date(con: duckdb.DuckDBPyConnection) -> None:
    # syn-0001 transitions at 2025S (Mar 1): February session counts bachelor, March master.
    insert_message(con, 1, "syn-0001", "2025-02-19 10:00:00")
    insert_message(con, 2, "syn-0001", "2025-03-10 10:00:00")
    insert_message(con, 3, "syn-0002", "2025-03-10 11:00:00")
    for history_id in (1, 2, 3):
        label(con, history_id, "deductive", "synthetic_alpha")
    status_row(con, "syn-0001", "bachelor", "2025S")
    status_row(con, "syn-0002", "staff")
    for i in range(3, 6):
        status_row(con, f"syn-{i:04d}", "master")
    entry = all_time_topics(build(con, floor_n=1, classification_version=VERSION))
    by_status = entry["by_status"]
    assert set(by_status) == {"bachelor", "master", "staff"}  # no unknown: all students covered
    assert by_status["bachelor"]["deductive"]["n_total"] == {"status": "ok", "value": 1}
    assert by_status["master"]["deductive"]["n_total"] == {"status": "ok", "value": 1}
    assert by_status["staff"]["deductive"]["n_total"] == {"status": "ok", "value": 1}
    # D-59: no `status_rule` here. A level slice carries the same two ids the cohort-wide
    # group does; the roster rule is the by-level card's business, not every card's.
    assert by_status["master"]["deductive"]["footnote_ids"] == ["multi_label", "label_provenance"]


def test_sub_floor_status_group_suppresses_but_appears(con: duckdb.DuckDBPyConnection) -> None:
    seed_labeled_corpus(con)
    for i in range(1, 4):
        status_row(con, f"syn-{i:04d}", "master")
    # syn-0001 is 1 of 3 masters; no staff rows -> unlabeled students absent from data anyway.
    doc = build(con, classification_version=VERSION)
    by_status = all_time_topics(doc)["by_status"]
    assert set(by_status) == {"master"}
    master = {item["label"]: item["cell"] for item in by_status["master"]["deductive"]["items"]}
    assert master["synthetic_alpha"] == {"status": "ok", "value": 3}
    assert master["synthetic_beta"] == {"status": "suppressed"}
    jsonschema.validate(dump_doc(doc), SCHEMA)


def test_unknown_group_appears_for_uncovered_students(con: duckdb.DuckDBPyConnection) -> None:
    seed_labeled_corpus(con)
    status_row(con, "syn-0001", "master")  # syn-0002/0003 have messages but no status row
    by_status = all_time_topics(build(con, floor_n=1, classification_version=VERSION))["by_status"]
    assert set(by_status) == {"master", "unknown"}


def test_emergent_and_theme_set_version(con: duckdb.DuckDBPyConnection) -> None:
    seed_labeled_corpus(con)
    label(con, 1, "emergent_theme", "synthetic emergent theme")
    doc = build(con, floor_n=1, classification_version=VERSION, theme_set_version="statsboteval-themes-v1")
    dumped = dump_doc(doc)
    assert dumped["sections"]["topics"]["theme_set_version"] == "statsboteval-themes-v1"
    emergent = {i["label"]: i["cell"] for i in all_time_topics(doc)["emergent_themes"]["items"]}
    assert emergent["synthetic emergent theme"] == {"status": "ok", "value": 1}
    jsonschema.validate(dumped, SCHEMA)


def test_emergent_descriptions_published_from_theme_set(con: duckdb.DuckDBPyConnection) -> None:
    # 1.2.0: emergent items carry the frozen set's reviewed description; every
    # other domain publishes none (Bergmann definitions stay unpublished, D-16).
    seed_labeled_corpus(con)
    label(con, 1, "emergent_theme", "synthetic emergent theme")
    con.execute(
        "INSERT INTO theme_sets VALUES ('statsboteval-themes-v1', 'synthetic emergent theme', "
        "'Synthetic description.', now(), now())"
    )
    doc = build(con, floor_n=1, classification_version=VERSION, theme_set_version="statsboteval-themes-v1")
    entry = all_time_topics(doc)
    emergent_items = entry["emergent_themes"]["items"]
    assert [i["description"] for i in emergent_items] == ["Synthetic description."]
    for domain in ("deductive", "method_themes", "software_themes"):
        assert all("description" not in item for item in entry[domain]["items"])
    jsonschema.validate(dump_doc(doc), SCHEMA)
