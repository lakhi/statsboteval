"""Phase B Stage 2: theme-set storage, draft round-trip, and the freeze gate (D-33)."""

from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pytest

from statsboteval_pipeline.classify.parse import ClassifierParseError
from statsboteval_pipeline.corpus import open_corpus
from statsboteval_pipeline.themes import (
    ThemeEntry,
    ThemeSetError,
    freeze_theme_set,
    parse_theme_table,
    reviewed_theme_labels,
    write_draft,
)

NOW = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)
ENTRIES = [
    ThemeEntry("interpreting output", "making sense of statistical results"),
    ThemeEntry("choosing a test", "which method fits the data"),
    ThemeEntry("software help", "using analysis tools"),
]


@pytest.fixture()
def con(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    return open_corpus(tmp_path / "corpus.duckdb")


def test_draft_round_trips_through_the_parser(tmp_path: Path) -> None:
    draft = tmp_path / "theme-draft-test.md"
    write_draft(ENTRIES, draft, set_version="test-v1")
    text = draft.read_text()
    assert "REVIEW BEFORE FREEZING" in text
    assert parse_theme_table(text) == ENTRIES


@pytest.mark.parametrize(
    ("text", "match"),
    [
        ("no table at all", "no Markdown table"),
        ("| Label | Meaning |\n|---|---|\n| a | b |", "unexpected table header"),
        ("| Theme | Description |\n|---|---|\n| only one | with two missing |", "expected 3-40 themes"),
        ("| Theme | Description |\n|---|---|\n| a | b |\n| a | c |\n| d | e |", "duplicate theme label"),
        ("| Theme | Description |\n|---|---|\n| a | b |\n|  | c |\n| d | e |", "empty theme"),
        ("| Theme | Description |\n|---|---|\n| a | b | extra |\n| c | d |\n| e | f |", "expected 2 columns"),
    ],
)
def test_parse_rejects_structural_deviations(text: str, match: str) -> None:
    with pytest.raises(ClassifierParseError, match=match):
        parse_theme_table(text)


def test_freeze_stamps_reviewed_and_reads_back(con: duckdb.DuckDBPyConnection) -> None:
    assert freeze_theme_set(con, ENTRIES, "test-v1", now=NOW) == 3
    assert reviewed_theme_labels(con, "test-v1") == sorted(e.label for e in ENTRIES)
    assert con.execute("SELECT count(*) FROM theme_sets WHERE reviewed_at IS NULL").fetchone()[0] == 0


def test_frozen_set_is_immutable(con: duckdb.DuckDBPyConnection) -> None:
    freeze_theme_set(con, ENTRIES, "test-v1", now=NOW)
    with pytest.raises(ThemeSetError, match="already exists"):
        freeze_theme_set(con, ENTRIES, "test-v1", now=NOW)


def test_absent_set_reads_as_none(con: duckdb.DuckDBPyConnection) -> None:
    assert reviewed_theme_labels(con, "missing-v1") is None


def test_unreviewed_set_refuses(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("INSERT INTO theme_sets VALUES ('draft-v1', 'a theme', 'desc', ?, NULL)", [NOW])
    with pytest.raises(ThemeSetError, match="not reviewed"):
        reviewed_theme_labels(con, "draft-v1")
