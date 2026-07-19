"""Batch classification runner — the `statsboteval-v1` producer (D-30/D-33).

Selects messages lacking labels for the target version, batches them (≤50,
Bergmann's validated size), runs the deductive pass plus the method/software
theme passes per batch, and writes each batch's labels in one transaction.
Idempotent by `(history_id, label_version)`: a mid-run failure leaves completed
batches persisted and a re-run labels only the remainder. The emergent-theme
assignment pass (Task 12) reuses the same batching with a different domain.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol, TypeVar

import duckdb

from statsboteval_pipeline.classify.codebook import Category, Codebook
from statsboteval_pipeline.classify.parse import ClassifierParseError, parse_deductive, parse_themes
from statsboteval_pipeline.classify.prompts import BATCH_LIMIT, build_deductive_prompt, build_theme_prompt
from statsboteval_pipeline.labels import LabelRow, write_labels

THEME_PASSES: tuple[tuple[str, str], ...] = (
    ("method_theme", "statistics methods"),
    ("software_theme", "data analysis software"),
)

# The model occasionally deviates from the table contract (off-list labels,
# commentary cells) despite the prompt; strictness stays — a deviation is never
# written — but we re-ask with the parser's complaint appended before giving up.
PARSE_ATTEMPTS = 3

_T = TypeVar("_T")


class CompletionClient(Protocol):
    def complete(self, prompt: str) -> str: ...


def _complete_parsed(client: CompletionClient, prompt: str, parse: Callable[[str], _T]) -> _T:
    """Call the model and parse strictly, re-asking with the parse error on deviation."""
    attempt_prompt = prompt
    for attempt in range(1, PARSE_ATTEMPTS + 1):
        try:
            return parse(client.complete(attempt_prompt))
        except ClassifierParseError as error:
            if attempt == PARSE_ATTEMPTS:
                raise
            attempt_prompt = (
                f"{prompt}\n\nYour previous response was rejected by a strict parser with this error:\n"
                f"{error}\n"
                "Output ONLY the requested Markdown table, following the format rules above exactly."
            )
    raise AssertionError("unreachable")


def classify_corpus(
    con: duckdb.DuckDBPyConnection,
    client: CompletionClient,
    codebook: Codebook,
    *,
    label_version: str,
    model_tag: str,
    batch_size: int = BATCH_LIMIT,
    category_groups: Sequence[Sequence[Category]] | None = None,
) -> int:
    """Label every not-yet-labeled message under `label_version`; returns how many."""
    groups: list[Sequence[Category]] = list(category_groups) if category_groups else [codebook.categories]
    pending = con.execute(
        "SELECT m.history_id, m.sent FROM messages m "
        "WHERE NOT EXISTS (SELECT 1 FROM labels l WHERE l.history_id = m.history_id AND l.label_version = ?) "
        "ORDER BY m.history_id",
        [label_version],
    ).fetchall()
    labeled = 0
    for start in range(0, len(pending), batch_size):
        chunk = pending[start : start + batch_size]
        ids = [row[0] for row in chunk]
        texts = [row[1] for row in chunk]
        rows: list[LabelRow] = []
        for group in groups:
            prompt = build_deductive_prompt(codebook, texts, categories=group)
            names = [c.name for c in group]
            matrix = _complete_parsed(client, prompt, lambda out: parse_deductive(out, names, len(texts)))
            for history_id, coded in zip(ids, matrix, strict=True):
                rows.extend(
                    LabelRow(history_id, label_version, "deductive", cat.code, coded[cat.name], model_tag)
                    for cat in group
                )
        for domain, noun in THEME_PASSES:
            themes = codebook.method_themes if domain == "method_theme" else codebook.software_themes
            assigned = _complete_parsed(
                client, build_theme_prompt(themes, texts, noun), lambda out: parse_themes(out, themes, len(texts))
            )
            for history_id, labels in zip(ids, assigned, strict=True):
                rows.extend(LabelRow(history_id, label_version, domain, theme, 1, model_tag) for theme in labels)
        # One transaction per batch: the idempotency query sees a batch entirely or not at all.
        con.execute("BEGIN TRANSACTION")
        try:
            write_labels(con, rows)
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise
        labeled += len(chunk)
    return labeled
