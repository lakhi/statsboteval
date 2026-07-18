"""Phase B Task 10: bergmann-v1 importer (synthetic CSV only — the real dataset is git-ignored)."""

from pathlib import Path

import duckdb
import pytest

from statsboteval_pipeline.corpus import open_corpus
from statsboteval_pipeline.import_bergmann import CSV_COLUMN_TO_CODE, import_bergmann_v1
from statsboteval_pipeline.labels import LabelRow, read_labels, write_labels

CATEGORY_COLUMNS = list(CSV_COLUMN_TO_CODE)


def write_csv(path: Path, rows: list[dict[str, object]]) -> Path:
    header = ["ID", "group", "started", "prompt_tokens", *CATEGORY_COLUMNS]
    lines = [",".join(f'"{h}"' for h in header)]
    for row in rows:
        lines.append(",".join(str(row.get(h, 0)) if h not in ("group",) else f'"{row[h]}"' for h in header))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def csv_row(message_id: int, group: str, **categories: int) -> dict[str, object]:
    row: dict[str, object] = {"ID": message_id, "group": group, "started": 1_700_000_000_000 + message_id, "prompt_tokens": 10}
    row.update(categories)
    return row


def test_import_writes_deductive_rows_with_provenance_split(tmp_path: Path) -> None:
    con = open_corpus(tmp_path / "corpus.duckdb")
    csv = write_csv(
        tmp_path / "synthetic.csv",
        [
            csv_row(1, "Master_sample", **{"Statistics.Interaction": 1}),
            csv_row(2, "Bachelor", **{"Prior.Content": 1}),
        ],
    )
    assert import_bergmann_v1(con, csv) == 2
    rows = read_labels(con, "bergmann-v1")
    assert len(rows) == 2 * len(CATEGORY_COLUMNS)  # explicit 0/1 per category
    by_id = {(r.history_id, r.code): r for r in rows}
    assert by_id[(1, "statistics_interaction")].value == 1
    assert by_id[(1, "statistics_interaction")].provenance == "human_consensus"
    assert by_id[(2, "reference_to_a_prior_content")].value == 1
    assert by_id[(2, "reference_to_a_prior_content")].provenance == "gpt5"
    assert by_id[(2, "statistics_interaction")].value == 0


def test_reimport_is_idempotent_and_does_not_touch_other_versions(tmp_path: Path) -> None:
    con = open_corpus(tmp_path / "corpus.duckdb")
    write_labels(con, [LabelRow(1, "statsboteval-v1", "deductive", "statistics_interaction", 1, "stub@x")])
    csv = write_csv(tmp_path / "synthetic.csv", [csv_row(1, "Master_sample")])
    assert import_bergmann_v1(con, csv) == 1
    assert import_bergmann_v1(con, csv) == 1  # upsert, not duplicate
    assert len(read_labels(con, "bergmann-v1")) == len(CATEGORY_COLUMNS)
    ours = read_labels(con, "statsboteval-v1")
    assert ours == [LabelRow(1, "statsboteval-v1", "deductive", "statistics_interaction", 1, "stub@x")]


def test_missing_category_column_raises(tmp_path: Path) -> None:
    con = open_corpus(tmp_path / "corpus.duckdb")
    csv = write_csv(tmp_path / "synthetic.csv", [csv_row(1, "Master_sample")])
    text = csv.read_text(encoding="utf-8").replace('"Declarative.Statement",', "")
    broken = tmp_path / "broken.csv"
    # Drop the value column too so rows stay aligned.
    lines = text.splitlines()
    broken.write_text("\n".join(line.rsplit(",", 1)[0] for line in lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Declarative.Statement"):
        import_bergmann_v1(con, broken)


def test_non_binary_value_raises(tmp_path: Path) -> None:
    con = open_corpus(tmp_path / "corpus.duckdb")
    csv = write_csv(tmp_path / "synthetic.csv", [csv_row(1, "Master_sample", **{"Multiple.Choice": 7})])
    with pytest.raises(ValueError, match="[Nn]on-binary"):
        import_bergmann_v1(con, csv)


def seed_message(con: duckdb.DuckDBPyConnection, history_id: int, started: int) -> None:
    con.execute("INSERT OR IGNORE INTO students VALUES ('syn-0001', '2025-03-03 10:00:00')")
    con.execute(
        "INSERT INTO messages VALUES (?, 'syn-0001', ?, '2025-03-10 10:00:00', 'synthetic', 'reply', 10, 20)",
        [history_id, started],
    )


def test_join_check_passes_on_matching_corpus_rows(tmp_path: Path) -> None:
    con = open_corpus(tmp_path / "corpus.duckdb")
    seed_message(con, 1, started=1_700_000_000_001)  # matches csv_row's started for id 1
    csv = write_csv(tmp_path / "synthetic.csv", [csv_row(1, "Master_sample")])
    assert import_bergmann_v1(con, csv) == 1


def test_join_check_mismatch_raises_before_any_write(tmp_path: Path) -> None:
    con = open_corpus(tmp_path / "corpus.duckdb")
    seed_message(con, 1, started=999)  # corpus disagrees with the CSV fingerprint
    csv = write_csv(tmp_path / "synthetic.csv", [csv_row(1, "Master_sample")])
    with pytest.raises(ValueError, match="join check"):
        import_bergmann_v1(con, csv)
    assert read_labels(con, "bergmann-v1") == []
