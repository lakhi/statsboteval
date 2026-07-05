"""Local DuckDB corpus (D-17): one file on the encrypted disk, plain numbered migrations."""

from __future__ import annotations

from pathlib import Path

import duckdb

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"


def open_corpus(path: Path, migrations_dir: Path = MIGRATIONS_DIR) -> duckdb.DuckDBPyConnection:
    """Open (or create) the corpus file and apply any pending migrations, in name order."""
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE IF NOT EXISTS _migrations (name TEXT PRIMARY KEY, applied_at TIMESTAMP DEFAULT now())")
    applied = {row[0] for row in con.execute("SELECT name FROM _migrations").fetchall()}
    for migration in sorted(migrations_dir.glob("[0-9]*.sql")):
        if migration.name not in applied:
            con.execute(migration.read_text())
            con.execute("INSERT INTO _migrations (name) VALUES (?)", [migration.name])
    return con
