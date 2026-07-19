"""Stage 2 of the emergent-theme pass (D-33): candidate codes → draft themes.

One LLM call over the distinct candidate-code list — codes only, no chat text
is re-sent. The result lands in a git-ignored draft file for the operator to
review; nothing enters `theme_sets` until `freeze-themes` (themes.py).
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from statsboteval_pipeline.classify.client import Effort
from statsboteval_pipeline.classify.generate import candidate_frequencies
from statsboteval_pipeline.classify.prompts import build_synthesis_prompt
from statsboteval_pipeline.classify.runner import CompletionClient, _complete_parsed
from statsboteval_pipeline.themes import ThemeEntry, parse_theme_table, write_draft


def synthesize_themes(
    con: duckdb.DuckDBPyConnection,
    client: CompletionClient,
    *,
    run_id: str,
    reasoning_effort: Effort = "minimal",
) -> list[ThemeEntry]:
    frequencies = candidate_frequencies(con, run_id)
    if not frequencies:
        raise ValueError(f"no candidate codes for run {run_id!r}; run generation first")
    return _complete_parsed(
        client, build_synthesis_prompt(frequencies), parse_theme_table, base_effort=reasoning_effort
    )


def synthesize_to_draft(
    con: duckdb.DuckDBPyConnection,
    client: CompletionClient,
    *,
    run_id: str,
    draft_path: Path,
    set_version: str,
    reasoning_effort: Effort = "minimal",
) -> list[ThemeEntry]:
    entries = synthesize_themes(con, client, run_id=run_id, reasoning_effort=reasoning_effort)
    write_draft(entries, draft_path, set_version=set_version)
    return entries
