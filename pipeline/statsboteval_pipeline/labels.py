"""Typed access to the versioned labels table (migration 003, D-07).

All label versions share one tidy table; readers select a single version and
never mix them (the aggregates document publishes which version it used via
`label_versions`).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import NamedTuple

import duckdb

# The label version this pipeline currently produces and publishes — the single
# source of truth for every default (settings, CLI flags, synthetic fixtures), so
# minting the next version is one edit rather than a hunt through string literals.
# `statsboteval-v2` since 2026-07-28 (D-45): avg MCC .823 vs v1's .714. Older
# versions stay in the table by design; bumping this never deletes them, and the
# rollback is to point the settings/flags back at the previous string.
CURRENT_LABEL_VERSION = "statsboteval-v2"


class LabelRow(NamedTuple):
    history_id: int
    label_version: str
    domain: str
    code: str
    value: int
    provenance: str


def write_labels(con: duckdb.DuckDBPyConnection, rows: Iterable[LabelRow]) -> None:
    """Bulk upsert on the primary key — re-running a labeling pass never duplicates.

    Staged through a temp table rather than `executemany("INSERT OR REPLACE ...")`:
    DuckDB runs the latter one statement at a time, doing a primary-key probe per row,
    which measured at ~1.5 ms/row — 90 s to write one classification pass over the real
    corpus, and growing linearly with it. Loading a PK-less staging table and merging in a
    single statement lets the columnar engine do the work it is good at.
    """
    # Last-wins on duplicate keys, matching what row-by-row INSERT OR REPLACE did. The
    # merge below cannot do it: DuckDB refuses to update the same row twice in one
    # statement, so a duplicate would turn a silent overwrite into a hard failure.
    deduped = {row[:4]: tuple(row) for row in rows}
    if not deduped:
        return
    con.execute("CREATE OR REPLACE TEMP TABLE _labels_in AS SELECT * FROM labels LIMIT 0")
    try:
        con.executemany("INSERT INTO _labels_in VALUES (?, ?, ?, ?, ?, ?)", list(deduped.values()))
        con.execute(
            "INSERT OR REPLACE INTO labels (history_id, label_version, domain, code, value, provenance) "
            "SELECT history_id, label_version, domain, code, value, provenance FROM _labels_in"
        )
    finally:
        con.execute("DROP TABLE IF EXISTS _labels_in")


def read_labels(con: duckdb.DuckDBPyConnection, label_version: str) -> list[LabelRow]:
    rows = con.execute(
        "SELECT history_id, label_version, domain, code, value, provenance "
        "FROM labels WHERE label_version = ? ORDER BY history_id, domain, code",
        [label_version],
    ).fetchall()
    return [LabelRow(*row) for row in rows]


def label_versions_present(con: duckdb.DuckDBPyConnection) -> set[str]:
    return {row[0] for row in con.execute("SELECT DISTINCT label_version FROM labels").fetchall()}
