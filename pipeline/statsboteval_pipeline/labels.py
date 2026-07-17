"""Typed access to the versioned labels table (migration 003, D-07).

All label versions share one tidy table; readers select a single version and
never mix them (the aggregates document publishes which version it used via
`label_versions`).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import NamedTuple

import duckdb


class LabelRow(NamedTuple):
    history_id: int
    label_version: str
    domain: str
    code: str
    value: int
    provenance: str


def write_labels(con: duckdb.DuckDBPyConnection, rows: Iterable[LabelRow]) -> None:
    """Bulk upsert on the primary key — re-running a labeling pass never duplicates."""
    con.executemany(
        "INSERT OR REPLACE INTO labels (history_id, label_version, domain, code, value, provenance) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [tuple(row) for row in rows],
    )


def read_labels(con: duckdb.DuckDBPyConnection, label_version: str) -> list[LabelRow]:
    rows = con.execute(
        "SELECT history_id, label_version, domain, code, value, provenance "
        "FROM labels WHERE label_version = ? ORDER BY history_id, domain, code",
        [label_version],
    ).fetchall()
    return [LabelRow(*row) for row in rows]


def label_versions_present(con: duckdb.DuckDBPyConnection) -> set[str]:
    return {row[0] for row in con.execute("SELECT DISTINCT label_version FROM labels").fetchall()}
