"""Operator glue: settings + codebook + client -> one classification run.

Kept as its own tiny module so `run-weekly` can chain classification (D-38)
while tests stub this single entry point — the pieces it wires are each
unit-tested on their own (codebook, prompts, parse, client, runner).
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from statsboteval_pipeline.classify.client import ClassifierClient
from statsboteval_pipeline.classify.codebook import DEDUCTIVE_CATEGORY_NAMES, load_codebook
from statsboteval_pipeline.classify.config import ClassifierSettings
from statsboteval_pipeline.classify.runner import classify_corpus


def run_classification(con: duckdb.DuckDBPyConnection, *, env_file: Path) -> int:
    """Classify every not-yet-labeled message; returns how many were labeled."""
    settings = ClassifierSettings(_env_file=env_file)  # type: ignore[call-arg]
    if not settings.bergmann_prompts_dir:
        raise ValueError(
            "BERGMANN_PROMPTS_DIR is not set — point it at the materialized codebook "
            "directory (see .env.example), or pass --skip-classify"
        )
    codebook = load_codebook(Path(settings.bergmann_prompts_dir), expected_categories=DEDUCTIVE_CATEGORY_NAMES)
    client = ClassifierClient(settings)
    return classify_corpus(
        con,
        client,
        codebook,
        label_version=settings.classifier_label_version,
        model_tag=settings.classifier_model_tag,
    )
