"""bergmann-v1 label importer from the public Stage-2 `full_dataset.csv` (D-22, D-30).

The dataset is public research data but contains chat text, so the CSV stays a
git-ignored local file (D-16); only labels derived from it enter the corpus.
Provenance follows the `group` column: the 300-row `Master_sample` is the
human-consensus ground truth, everything else is the team's GPT-5 coding.

Deviation from the original Task 10 wording, found at implementation: the
public `full_dataset.csv` carries only the 13 deductive categories — no
method/software theme codings — so the import is deductive-only. Themes are
not MCC-validated anyway (Bergmann validated them by expert similarity).

Join check (D-35 semantics): `started` is a client epoch-ms value — effectively
a row fingerprint. Where imported IDs already exist in the corpus, `started`
must match exactly or the import refuses to write anything.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from statsboteval_pipeline.labels import LabelRow, write_labels

LABEL_VERSION = "bergmann-v1"
HUMAN_CONSENSUS_GROUP = "Master_sample"

# The CSV's R-style dotted column names → our label codes (matches codebook.category_code
# of the manuscript names; "Prior.Content" is the dataset's short form).
CSV_COLUMN_TO_CODE: dict[str, str] = {
    "Statistics.Interaction": "statistics_interaction",
    "Specific.Method": "specific_method",
    "Data.Analysis.Software": "data_analysis_software",
    "Multiple.Choice": "multiple_choice",
    "Capability.Request": "capability_request",
    "Declarative.Statement": "declarative_statement",
    "Question.Posed": "question_posed",
    "Instruction.Given": "instruction_given",
    "Prior.Content": "reference_to_a_prior_content",
    "English.Input": "english_input",
    "German.Input": "german_input",
    "Politeness.Expression": "politeness_expression",
    "Greeting.Expression": "greeting_expression",
}

_REQUIRED = ("ID", "group", "started", *CSV_COLUMN_TO_CODE)


def import_bergmann_v1(con: duckdb.DuckDBPyConnection, csv_path: Path) -> int:
    """Import the coded dataset as `bergmann-v1`; returns the number of messages labeled."""
    # The published file is cp1252-encoded (bergmann-framework.md); latin-1 reads every byte
    # and only the unqueried `sent` column is affected by the 0x80–0x9F difference.
    source = f"read_csv('{csv_path}', encoding='latin-1', header=true)"
    present = {row[0] for row in con.execute(f"DESCRIBE SELECT * FROM {source}").fetchall()}
    missing = [column for column in _REQUIRED if column not in present]
    if missing:
        raise ValueError(f"dataset CSV is missing required column(s): {missing}")

    mismatches = con.execute(
        f'SELECT count(*) FROM {source} c JOIN messages m ON m.history_id = c."ID" '
        "WHERE m.session_started != c.started"
    ).fetchone()
    if mismatches is not None and mismatches[0]:
        raise ValueError(
            f"join check failed: {mismatches[0]} row(s) whose `started` disagrees with the corpus "
            "— refusing to import against a corpus that does not match the dataset"
        )

    columns = ", ".join(f'"{name}"' for name in CSV_COLUMN_TO_CODE)
    data = con.execute(f'SELECT "ID", "group", {columns} FROM {source} ORDER BY "ID"').fetchall()
    rows: list[LabelRow] = []
    for record in data:
        history_id, group, *values = record
        provenance = "human_consensus" if group == HUMAN_CONSENSUS_GROUP else "gpt5"
        for code, value in zip(CSV_COLUMN_TO_CODE.values(), values, strict=True):
            if value not in (0, 1):
                raise ValueError(f"non-binary value {value!r} for {code} at ID {history_id}")
            rows.append(LabelRow(history_id, LABEL_VERSION, "deductive", code, value, provenance))
    write_labels(con, rows)
    return len(data)
