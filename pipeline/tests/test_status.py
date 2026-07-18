"""Phase B Task 21: student-status dimension (synthetic rosters only)."""

import shutil
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pytest

from statsboteval_pipeline.corpus import MIGRATIONS_DIR, open_corpus
from statsboteval_pipeline.erase import erase_student
from statsboteval_pipeline.extract import pseudonymize, verify_pepper
from statsboteval_pipeline.status import (
    ImportResult,
    StatusRow,
    import_status_csv,
    read_status,
    resolve_status,
    semester_start,
)

PEPPER = "test-pepper"


def write_csv(path: Path, rows: list[str]) -> Path:
    path.write_text("\n".join(["uid,status,ma_start_semester,source", *rows]) + "\n", encoding="utf-8")
    return path


def fresh_corpus(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    con = open_corpus(tmp_path / "corpus.duckdb")
    verify_pepper(con, PEPPER)
    return con


def vienna_ms(iso: str) -> int:
    # Session `started` is epoch ms; build from a UTC instant for determinism.
    return int(datetime.fromisoformat(iso).replace(tzinfo=timezone.utc).timestamp() * 1000)


def test_migration_004_applies_on_existing_corpus(tmp_path: Path) -> None:
    old_dir = tmp_path / "old_migrations"
    old_dir.mkdir()
    for name in ("001_corpus_init.sql", "002_extract_meta.sql", "003_labels.sql"):
        shutil.copy(MIGRATIONS_DIR / name, old_dir / name)
    path = tmp_path / "corpus.duckdb"
    con = open_corpus(path, migrations_dir=old_dir)
    con.execute("INSERT INTO students VALUES ('syn-0001', '2025-03-03 10:00:00')")
    con.close()

    con = open_corpus(path)  # 004 applies now
    applied = [row[0] for row in con.execute("SELECT name FROM _migrations ORDER BY name").fetchall()]
    assert "004_student_status.sql" in applied
    assert con.execute("SELECT count(*) FROM student_status").fetchone()[0] == 0


def test_import_hmacs_uids_with_extract_normalization(tmp_path: Path) -> None:
    con = fresh_corpus(tmp_path)
    csv = write_csv(tmp_path / "status.csv", ['  Alice@UNI ,master,,"master-mar25"'])
    result = import_status_csv(con, csv, pepper=PEPPER)
    assert result == ImportResult(imported=1, unmatched_corpus_students=0)
    rows = read_status(con)
    # Same pseudonym the extract would produce for the normalized uid: parity guaranteed.
    assert rows == {
        pseudonymize("alice@uni", PEPPER): StatusRow(pseudonymize("  Alice@UNI ", PEPPER), "master", None, "master-mar25")
    }


def test_reimport_is_upsert_and_reports_roster_drift(tmp_path: Path) -> None:
    con = fresh_corpus(tmp_path)
    con.execute("INSERT INTO students VALUES (?, '2025-03-03 10:00:00')", [pseudonymize("bob", PEPPER)])
    con.execute("INSERT INTO students VALUES (?, '2025-03-03 10:00:00')", [pseudonymize("carol", PEPPER)])
    csv = write_csv(tmp_path / "status.csv", ["bob,bachelor,,bachelor-apr25"])
    assert import_status_csv(con, csv, pepper=PEPPER) == ImportResult(1, 1)  # carol unmatched
    csv2 = write_csv(tmp_path / "status.csv", ["bob,bachelor,2025W,bachelor-apr25"])
    assert import_status_csv(con, csv2, pepper=PEPPER) == ImportResult(1, 1)  # upsert, not duplicate
    assert read_status(con)[pseudonymize("bob", PEPPER)].ma_start_semester == "2025W"


def test_wrong_pepper_fails_loudly(tmp_path: Path) -> None:
    con = fresh_corpus(tmp_path)
    csv = write_csv(tmp_path / "status.csv", ["bob,master,,list"])
    with pytest.raises(Exception, match="PSEUDONYM_PEPPER"):
        import_status_csv(con, csv, pepper="a-different-pepper")


@pytest.mark.parametrize(
    "line,message",
    [
        ("bob,phd,,list", "unknown status"),
        ("bob,master,2025W,list", "only valid with status 'bachelor'"),
        ("bob,bachelor,2025X,list", "malformed semester id"),
        ("bob,bachelor,,", "empty source"),
        (",master,,list", "empty uid"),
    ],
)
def test_malformed_rows_raise(tmp_path: Path, line: str, message: str) -> None:
    con = fresh_corpus(tmp_path)
    with pytest.raises(ValueError, match=message):
        import_status_csv(con, write_csv(tmp_path / "status.csv", [line]), pepper=PEPPER)


def test_duplicate_uid_after_normalization_raises(tmp_path: Path) -> None:
    con = fresh_corpus(tmp_path)
    csv = write_csv(tmp_path / "status.csv", ["bob,master,,list", " BOB ,bachelor,,list"])
    with pytest.raises(ValueError, match="duplicate uid"):
        import_status_csv(con, csv, pepper=PEPPER)


def test_semester_start_boundaries() -> None:
    assert semester_start("2025W").isoformat() == "2025-10-01"
    assert semester_start("2026S").isoformat() == "2026-03-01"


def test_transitioner_resolution_across_boundary_incl_break_months() -> None:
    row = StatusRow("p", "bachelor", "2025W", "list")
    assert resolve_status(row, vienna_ms("2025-06-15 10:00")) == "bachelor"  # SS before transition
    assert resolve_status(row, vienna_ms("2025-08-20 10:00")) == "bachelor"  # break month, still BA
    assert resolve_status(row, vienna_ms("2025-10-01 10:00")) == "master"  # first day of WS
    assert resolve_status(row, vienna_ms("2026-02-10 10:00")) == "master"  # after WS ends, stays MA


def test_non_transitioner_and_unknown_resolution() -> None:
    assert resolve_status(StatusRow("p", "staff", None, "doktorat"), vienna_ms("2025-06-15 10:00")) == "staff"
    assert resolve_status(None, vienna_ms("2025-06-15 10:00")) == "unknown"


def test_erasure_covers_student_status(tmp_path: Path) -> None:
    con = fresh_corpus(tmp_path)
    pseudonym = pseudonymize("bob", PEPPER)
    con.execute("INSERT INTO students VALUES (?, '2025-03-03 10:00:00')", [pseudonym])
    import_status_csv(con, write_csv(tmp_path / "status.csv", ["bob,master,,list"]), pepper=PEPPER)
    deleted = erase_student(con, "bob", pepper=PEPPER, log_path=tmp_path / "erasure.log")
    assert deleted is not None
    assert deleted["student_status"] == 1
    assert read_status(con) == {}
