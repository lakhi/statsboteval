"""GL2 (= Phase B Task 4): versioned labels table + typed helpers."""

import shutil
from pathlib import Path

from statsboteval_pipeline.corpus import MIGRATIONS_DIR, open_corpus
from statsboteval_pipeline.labels import LabelRow, label_versions_present, read_labels, write_labels


def some_rows() -> list[LabelRow]:
    return [
        LabelRow(1, "lang-heuristic-v1", "language", "de", 1, "lingua-py"),
        LabelRow(2, "lang-heuristic-v1", "language", "undetermined", 1, "lingua-py"),
        LabelRow(1, "bergmann-v1", "deductive", "statistics_interaction", 0, "human_consensus"),
    ]


def test_migration_003_applies_on_existing_corpus(tmp_path: Path) -> None:
    # Build a corpus as it existed before this change (001+002 only), with data in it.
    old_dir = tmp_path / "old_migrations"
    old_dir.mkdir()
    for name in ("001_corpus_init.sql", "002_extract_meta.sql"):
        shutil.copy(MIGRATIONS_DIR / name, old_dir / name)
    path = tmp_path / "corpus.duckdb"
    con = open_corpus(path, migrations_dir=old_dir)
    con.execute("INSERT INTO students VALUES ('syn-0001', '2025-03-03 10:00:00')")
    con.close()

    con = open_corpus(path)  # real migrations dir: 003 applies now
    applied = [row[0] for row in con.execute("SELECT name FROM _migrations ORDER BY name").fetchall()]
    assert applied == [
        "001_corpus_init.sql",
        "002_extract_meta.sql",
        "003_labels.sql",
        "004_student_status.sql",
        "005_theme_sets.sql",
    ]
    assert con.execute("SELECT count(*) FROM students").fetchone()[0] == 1  # data survived
    assert con.execute("SELECT count(*) FROM labels").fetchone()[0] == 0


def test_write_read_round_trip(tmp_path: Path) -> None:
    con = open_corpus(tmp_path / "corpus.duckdb")
    write_labels(con, some_rows())
    got = read_labels(con, "lang-heuristic-v1")
    assert got == [
        LabelRow(1, "lang-heuristic-v1", "language", "de", 1, "lingua-py"),
        LabelRow(2, "lang-heuristic-v1", "language", "undetermined", 1, "lingua-py"),
    ]
    assert all(isinstance(r, LabelRow) for r in got)


def test_versions_coexist_without_collision(tmp_path: Path) -> None:
    con = open_corpus(tmp_path / "corpus.duckdb")
    write_labels(con, some_rows())
    assert label_versions_present(con) == {"lang-heuristic-v1", "bergmann-v1"}
    # Same (history_id, domain, code) under a second version is a distinct row.
    write_labels(con, [LabelRow(1, "statsboteval-v1", "deductive", "statistics_interaction", 1, "gpt5")])
    assert len(read_labels(con, "bergmann-v1")) == 1
    assert len(read_labels(con, "statsboteval-v1")) == 1


def test_rewrite_same_key_is_upsert_not_duplicate(tmp_path: Path) -> None:
    con = open_corpus(tmp_path / "corpus.duckdb")
    write_labels(con, some_rows())
    write_labels(con, [LabelRow(1, "lang-heuristic-v1", "language", "de", 1, "lingua-py-rerun")])
    got = [r for r in read_labels(con, "lang-heuristic-v1") if r.history_id == 1]
    assert got == [LabelRow(1, "lang-heuristic-v1", "language", "de", 1, "lingua-py-rerun")]


def test_label_versions_present_empty(tmp_path: Path) -> None:
    con = open_corpus(tmp_path / "corpus.duckdb")
    assert label_versions_present(con) == set()
