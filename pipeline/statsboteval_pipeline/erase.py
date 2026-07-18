"""Student erasure (consent addendum; runbook: docs/runbooks/erasure.md).

Recompute the pseudonym from the uid, delete the student's rows everywhere,
log completion locally. Republishing afterwards is the CLI's job (erase-student
chains re-aggregate -> guard -> upload); this module only touches the corpus.
"""

from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from .extract import _PEPPER_KEY, PepperMismatchError, pseudonymize


def _require_pepper_match(con: duckdb.DuckDBPyConnection, pepper: str) -> None:
    """Unlike ingest, erasure never adopts a fingerprint: no match, no deletion."""
    row = con.execute("SELECT value FROM meta WHERE key = ?", [_PEPPER_KEY]).fetchone()
    if row is None:
        raise ValueError("corpus has no pepper fingerprint; nothing was ever ingested to erase from")
    if row[0] != hashlib.sha256(pepper.encode()).hexdigest():
        raise PepperMismatchError(
            "PSEUDONYM_PEPPER does not match this corpus; the recomputed pseudonym would "
            "miss the student's rows and the erasure would silently do nothing. Restore the "
            "original pepper (password-manager backup, D-34)."
        )


def erase_student(con: duckdb.DuckDBPyConnection, uid: str, *, pepper: str, log_path: Path) -> dict[str, int] | None:
    """Delete every row of the student behind `uid`. Returns per-table counts, or None if unknown."""
    _require_pepper_match(con, pepper)
    pseudonym = pseudonymize(uid, pepper)
    deleted = {}
    for table, sql in (
        ("labels", "DELETE FROM labels WHERE history_id IN (SELECT history_id FROM messages WHERE pseudonym = ?)"),
        ("messages", "DELETE FROM messages WHERE pseudonym = ?"),
        ("student_status", "DELETE FROM student_status WHERE pseudonym = ?"),
        ("students", "DELETE FROM students WHERE pseudonym = ?"),
    ):
        row = con.execute(sql, [pseudonym]).fetchone()
        deleted[table] = int(row[0]) if row else 0
    if sum(deleted.values()) == 0:
        print(f"warning: no rows for the given uid (pseudonym {pseudonym[:16]}…); nothing erased", file=sys.stderr)
        return None
    log_path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    counts = " ".join(f"{table}={n}" for table, n in deleted.items())
    with log_path.open("a") as f:
        f.write(f"{stamp} erased pseudonym {pseudonym[:16]}… {counts}\n")
    return deleted
