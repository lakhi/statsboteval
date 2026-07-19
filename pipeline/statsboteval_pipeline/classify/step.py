"""Operator glue: settings + codebook + client -> one classification run.

Kept as its own tiny module so `run-weekly` can chain classification (D-38)
while tests stub this single entry point — the pieces it wires are each
unit-tested on their own (codebook, prompts, parse, client, runner).
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from statsboteval_pipeline.classify.client import ClassifierClient, Effort
from statsboteval_pipeline.classify.codebook import DEDUCTIVE_CATEGORY_NAMES, load_codebook
from statsboteval_pipeline.classify.config import ClassifierSettings
from statsboteval_pipeline.classify.generate import generate_candidates
from statsboteval_pipeline.classify.runner import assign_emergent_themes, classify_corpus
from statsboteval_pipeline.classify.synthesize import synthesize_to_draft
from statsboteval_pipeline.themes import ThemeEntry, ThemeSetError, reviewed_theme_labels


def _effort(settings: ClassifierSettings) -> Effort:
    effort = settings.classifier_reasoning_effort
    if effort not in ("minimal", "low", "medium", "high"):
        raise ValueError(f"CLASSIFIER_REASONING_EFFORT must be minimal/low/medium/high, got {effort!r}")
    return effort  # type: ignore[return-value]  # narrowed by the check above


def run_classification(con: duckdb.DuckDBPyConnection, *, env_file: Path) -> int:
    """Classify every not-yet-labeled message; returns how many were labeled."""
    settings = ClassifierSettings(_env_file=env_file)  # type: ignore[call-arg]
    if not settings.bergmann_prompts_dir:
        raise ValueError(
            "BERGMANN_PROMPTS_DIR is not set — point it at the materialized codebook "
            "directory (see .env.example), or pass --skip-classify"
        )
    codebook = load_codebook(Path(settings.bergmann_prompts_dir), expected_categories=DEDUCTIVE_CATEGORY_NAMES)
    return classify_corpus(
        con,
        ClassifierClient(settings),
        codebook,
        label_version=settings.classifier_label_version,
        model_tag=settings.classifier_model_tag,
        reasoning_effort=_effort(settings),
    )


def run_theme_generation(
    con: duckdb.DuckDBPyConnection, *, env_file: Path, draft_path: Path
) -> tuple[int, list[ThemeEntry]]:
    """Stage 1 + 2 of the emergent pass: candidates, then the draft for review."""
    settings = ClassifierSettings(_env_file=env_file)  # type: ignore[call-arg]
    set_version = settings.classifier_theme_set_version
    client = ClassifierClient(settings)
    effort = _effort(settings)
    processed = generate_candidates(con, client, run_id=set_version, reasoning_effort=effort)
    entries = synthesize_to_draft(
        con, client, run_id=set_version, draft_path=draft_path, set_version=set_version, reasoning_effort=effort
    )
    return processed, entries


def run_theme_assignment(con: duckdb.DuckDBPyConnection, *, env_file: Path) -> int:
    """Assign the configured reviewed theme set; refuses a missing/unreviewed set."""
    settings = ClassifierSettings(_env_file=env_file)  # type: ignore[call-arg]
    set_version = settings.classifier_theme_set_version
    themes = reviewed_theme_labels(con, set_version)  # raises ThemeSetError if unreviewed
    if themes is None:
        raise ThemeSetError(f"theme set {set_version!r} does not exist; run generate-themes + freeze-themes first")
    return assign_emergent_themes(
        con,
        ClassifierClient(settings),
        themes,
        label_version=settings.classifier_label_version,
        model_tag=settings.classifier_model_tag,
        theme_set_version=set_version,
        reasoning_effort=_effort(settings),
    )
