"""Stage 1 of the emergent-theme pass (D-33): candidate codes per message.

Mirrors the runner's discipline — ≤50-message batches, strict parse with the
corrective-retry/effort ladder, one transaction per batch, heartbeat — but
writes to `theme_candidates` (local forever, never published). Idempotent per
(history_id, run_id): a message with zero codes gets a code='' marker row so
the anti-join resume never re-processes it.
"""

from __future__ import annotations

import duckdb

from statsboteval_pipeline.classify.client import Effort
from statsboteval_pipeline.classify.parse import parse_candidates
from statsboteval_pipeline.classify.prompts import BATCH_LIMIT, build_candidate_prompt
from statsboteval_pipeline.classify.runner import CompletionClient, _complete_parsed


def generate_candidates(
    con: duckdb.DuckDBPyConnection,
    client: CompletionClient,
    *,
    run_id: str,
    batch_size: int = BATCH_LIMIT,
    reasoning_effort: Effort = "minimal",
) -> int:
    """Generate candidate codes for every not-yet-processed message; returns how many."""
    pending = con.execute(
        "SELECT m.history_id, m.sent FROM messages m "
        "WHERE NOT EXISTS (SELECT 1 FROM theme_candidates c WHERE c.history_id = m.history_id AND c.run_id = ?) "
        "ORDER BY m.history_id",
        [run_id],
    ).fetchall()
    processed = 0
    for start in range(0, len(pending), batch_size):
        chunk = pending[start : start + batch_size]
        ids = [row[0] for row in chunk]
        texts = [row[1] for row in chunk]
        per_message = _complete_parsed(
            client,
            build_candidate_prompt(texts),
            lambda out: parse_candidates(out, len(texts)),
            base_effort=reasoning_effort,
        )
        rows: list[tuple[int, str, str]] = []
        for history_id, codes in zip(ids, per_message, strict=True):
            rows.extend((history_id, run_id, code) for code in (codes or [""]))
        con.execute("BEGIN TRANSACTION")
        try:
            con.executemany("INSERT OR REPLACE INTO theme_candidates VALUES (?, ?, ?)", rows)
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise
        processed += len(chunk)
        print(f"generated candidates for {processed}/{len(pending)} pending messages", flush=True)
    return processed


def candidate_frequencies(con: duckdb.DuckDBPyConnection, run_id: str) -> list[tuple[str, int]]:
    """Distinct candidate codes with counts, most frequent first ('' markers excluded)."""
    return [
        (code, count)
        for code, count in con.execute(
            "SELECT code, count(*) FROM theme_candidates WHERE run_id = ? AND code <> '' "
            "GROUP BY code ORDER BY count(*) DESC, code",
            [run_id],
        ).fetchall()
    ]
