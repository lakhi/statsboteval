"""Phase B Task 11: per-category MCC validation vs bergmann-v1 (hand-computed expectations)."""

import math
from pathlib import Path

import duckdb
import pytest

from statsboteval_pipeline.corpus import open_corpus
from statsboteval_pipeline.labels import LabelRow, write_labels
from statsboteval_pipeline.validate import format_validation_report, validate_against_bergmann


def seed(
    con: duckdb.DuckDBPyConnection,
    code: str,
    pairs: list[tuple[int, int, int]],  # (history_id, bergmann_value, ours_value)
    *,
    provenance: str = "human_consensus",
) -> None:
    rows = []
    for history_id, theirs, ours in pairs:
        rows.append(LabelRow(history_id, "bergmann-v1", "deductive", code, theirs, provenance))
        rows.append(LabelRow(history_id, "statsboteval-v1", "deductive", code, ours, "gpt-5-mini@2025-08-07"))
    write_labels(con, rows)


def test_hand_computed_mcc_matches(tmp_path: Path) -> None:
    con = open_corpus(tmp_path / "corpus.duckdb")
    # tp=2 (1,1), tn=1 (0,0), fp=1 (0,1), fn=0 -> MCC = (2*1 - 1*0)/sqrt(3*2*2*1) = 2/sqrt(12)
    seed(con, "synthetic_alpha", [(1, 1, 1), (2, 1, 1), (3, 0, 1), (4, 0, 0)])
    report = validate_against_bergmann(con)
    result = report.per_category["synthetic_alpha"]
    assert (result.tp, result.tn, result.fp, result.fn) == (2, 1, 1, 0)
    assert result.mcc == pytest.approx(2 / math.sqrt(12))
    assert report.n_messages == 4


def test_only_human_consensus_rows_enter(tmp_path: Path) -> None:
    con = open_corpus(tmp_path / "corpus.duckdb")
    seed(con, "synthetic_alpha", [(1, 1, 1), (2, 0, 0)])
    seed(con, "synthetic_alpha", [(3, 1, 0), (4, 0, 1)], provenance="gpt5")  # must be excluded
    report = validate_against_bergmann(con)
    result = report.per_category["synthetic_alpha"]
    assert report.n_messages == 2
    assert (result.tp, result.tn, result.fp, result.fn) == (1, 1, 0, 0)
    assert result.mcc == pytest.approx(1.0)


def test_zero_variance_category_yields_na(tmp_path: Path) -> None:
    con = open_corpus(tmp_path / "corpus.duckdb")
    # All-zero on both sides (Bergmann's Multiple Choice case): denominator 0 -> NA, no crash.
    seed(con, "synthetic_beta", [(1, 0, 0), (2, 0, 0)])
    report = validate_against_bergmann(con)
    assert report.per_category["synthetic_beta"].mcc is None


def test_report_carries_model_tag_and_caveat(tmp_path: Path) -> None:
    con = open_corpus(tmp_path / "corpus.duckdb")
    seed(con, "synthetic_alpha", [(1, 1, 1), (2, 0, 0)])
    report = validate_against_bergmann(con)
    assert report.model_tags == {"gpt-5-mini@2025-08-07"}
    assert "consolidated" in report.caveat  # prompt-structure conflation caveat (D-30)
    text = format_validation_report(report)
    assert "synthetic_alpha" in text
    assert "gpt-5-mini@2025-08-07" in text
    assert "NA" not in text.split("synthetic_alpha")[1].splitlines()[0]


def test_no_overlap_raises_clearly(tmp_path: Path) -> None:
    con = open_corpus(tmp_path / "corpus.duckdb")
    write_labels(con, [LabelRow(1, "bergmann-v1", "deductive", "synthetic_alpha", 1, "human_consensus")])
    with pytest.raises(ValueError, match="statsboteval-v1"):
        validate_against_bergmann(con)


def test_na_rendered_in_report(tmp_path: Path) -> None:
    con = open_corpus(tmp_path / "corpus.duckdb")
    seed(con, "synthetic_beta", [(1, 0, 0)])
    text = format_validation_report(validate_against_bergmann(con))
    assert "NA" in text
