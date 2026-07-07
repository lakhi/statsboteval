from pathlib import Path

from statsboteval_pipeline.corpus import open_corpus


def table_names(con) -> set[str]:
    return {row[0] for row in con.execute("SELECT table_name FROM duckdb_tables()").fetchall()}


def test_fresh_corpus_has_schema(tmp_path: Path) -> None:
    con = open_corpus(tmp_path / "corpus.duckdb")
    assert {"students", "messages"} <= table_names(con)
    applied = [row[0] for row in con.execute("SELECT name FROM _migrations ORDER BY name").fetchall()]
    assert applied == ["001_corpus_init.sql", "002_extract_meta.sql"]


def test_reopen_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "corpus.duckdb"
    open_corpus(path).close()
    con = open_corpus(path)
    assert con.execute("SELECT count(*) FROM _migrations").fetchone()[0] == 2


def test_migrations_apply_in_order(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "001_a.sql").write_text("CREATE TABLE a (x INTEGER);")
    (migrations / "002_b.sql").write_text("INSERT INTO a VALUES (1);")  # only valid if 001 ran first
    con = open_corpus(tmp_path / "c.duckdb", migrations_dir=migrations)
    assert con.execute("SELECT count(*) FROM a").fetchone()[0] == 1
    applied = [row[0] for row in con.execute("SELECT name FROM _migrations ORDER BY name").fetchall()]
    assert applied == ["001_a.sql", "002_b.sql"]
