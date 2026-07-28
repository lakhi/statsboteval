"""Settings -> runner wiring (D-45).

The regression this guards is the one D-45 found: `run_classification` called
`classify_corpus` without a batch size, so the tuned value could never reach a
real run no matter what the operator configured. Both API-calling passes are
checked; the runner itself is tested in test_runner.py.
"""

from pathlib import Path
from typing import Any

import pytest

import statsboteval_pipeline.classify.step as step
from statsboteval_pipeline.classify.codebook import synthetic_codebook
from statsboteval_pipeline.corpus import open_corpus


@pytest.fixture()
def env_file(tmp_path: Path) -> Path:
    env = tmp_path / "azure.env"
    env.write_text(
        "AZURE_OPENAI_ENDPOINT=https://example.invalid/\nAZURE_OPENAI_API_KEY=fake\n"
        f"BERGMANN_PROMPTS_DIR={tmp_path}\nCLASSIFIER_BATCH_SIZE=7\n"
    )
    return env


def test_run_classification_threads_the_configured_batch_size(
    tmp_path: Path, env_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, Any] = {}
    monkeypatch.setattr(step, "load_codebook", lambda path, *, expected_categories: synthetic_codebook())
    monkeypatch.setattr(step, "ClassifierClient", lambda settings: object())
    monkeypatch.setattr(step, "classify_corpus", lambda *args, **kwargs: (seen.update(kwargs), 0)[1])
    step.run_classification(open_corpus(tmp_path / "corpus.duckdb"), env_file=env_file)
    assert seen["batch_size"] == 7
    assert seen["reasoning_effort"] == "low"  # the neighbouring setting stays wired too


def test_run_theme_assignment_threads_the_configured_batch_size(
    tmp_path: Path, env_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, Any] = {}
    monkeypatch.setattr(step, "ClassifierClient", lambda settings: object())
    monkeypatch.setattr(step, "assign_emergent_themes", lambda *args, **kwargs: (seen.update(kwargs), 0)[1])
    con = open_corpus(tmp_path / "corpus.duckdb")
    con.execute("INSERT INTO theme_sets VALUES ('statsboteval-themes-v1', 'a theme', 'd', now(), now())")
    step.run_theme_assignment(con, env_file=env_file)
    assert seen["batch_size"] == 7
