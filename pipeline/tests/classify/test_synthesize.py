"""Phase B Stage 2 (Task 12): synthesis — codes only in, reviewable draft out."""

from pathlib import Path

import duckdb
import pytest

from statsboteval_pipeline.classify.parse import ClassifierParseError
from statsboteval_pipeline.classify.prompts import build_synthesis_prompt
from statsboteval_pipeline.classify.synthesize import synthesize_themes, synthesize_to_draft
from statsboteval_pipeline.corpus import open_corpus
from statsboteval_pipeline.themes import ThemeEntry, parse_theme_table

RUN = "statsboteval-themes-v1"
SECRET_TEXT = "SECRET-CHAT-TEXT do not resend"

GOOD_TABLE = (
    "| Theme | Description |\n|---|---|\n"
    "| interpreting output | making sense of results |\n"
    "| choosing a test | which method fits |\n"
    "| software help | using analysis tools |"
)


def seeded_con(path: Path) -> duckdb.DuckDBPyConnection:
    con = open_corpus(path)
    con.execute("INSERT INTO students VALUES ('syn-0001', '2025-03-03 10:00:00')")
    con.execute(
        "INSERT INTO messages VALUES (1, 'syn-0001', 1700000000000, '2025-03-10 10:00:00', ?, 'reply', 10, 20)",
        [SECRET_TEXT],
    )
    con.executemany(
        "INSERT INTO theme_candidates VALUES (1, ?, ?)",
        [(RUN, "topic alpha"), (RUN, "topic beta"), (RUN, "")],
    )
    return con


class RecordingStub:
    def __init__(self, response: str = GOOD_TABLE) -> None:
        self.response = response
        self.prompts: list[str] = []

    def complete(self, prompt: str, *, reasoning_effort: str = "minimal") -> str:
        self.prompts.append(prompt)
        return self.response


def test_synthesis_prompt_contains_codes_only_never_chat_text(tmp_path: Path) -> None:
    con = seeded_con(tmp_path / "corpus.duckdb")
    client = RecordingStub()
    entries = synthesize_themes(con, client, run_id=RUN)
    assert [e.label for e in entries] == ["interpreting output", "choosing a test", "software help"]
    (prompt,) = client.prompts
    assert "topic alpha (1)" in prompt and "topic beta (1)" in prompt
    assert SECRET_TEXT not in prompt  # codes only — no chat text is re-sent (D-33)


def test_draft_file_written_and_round_trips(tmp_path: Path) -> None:
    con = seeded_con(tmp_path / "corpus.duckdb")
    draft = tmp_path / "draft.md"
    entries = synthesize_to_draft(con, RecordingStub(), run_id=RUN, draft_path=draft, set_version=RUN)
    assert parse_theme_table(draft.read_text()) == entries
    assert entries[0] == ThemeEntry("interpreting output", "making sense of results")


def test_no_candidates_refuses(tmp_path: Path) -> None:
    con = open_corpus(tmp_path / "corpus.duckdb")
    with pytest.raises(ValueError, match="no candidate codes"):
        synthesize_themes(con, RecordingStub(), run_id=RUN)


class MalformedOnceStub(RecordingStub):
    def complete(self, prompt: str, *, reasoning_effort: str = "minimal") -> str:
        super().complete(prompt, reasoning_effort=reasoning_effort)
        return "prose, not a table" if len(self.prompts) == 1 else self.response


def test_malformed_synthesis_is_retried_with_parser_feedback(tmp_path: Path) -> None:
    con = seeded_con(tmp_path / "corpus.duckdb")
    client = MalformedOnceStub()
    assert len(synthesize_themes(con, client, run_id=RUN)) == 3
    assert "rejected by a strict parser" in client.prompts[1]


def test_synthesis_prompt_requires_codes() -> None:
    with pytest.raises(ValueError, match="no candidate codes"):
        build_synthesis_prompt([])


def test_off_spec_theme_table_raises_after_retries(tmp_path: Path) -> None:
    con = seeded_con(tmp_path / "corpus.duckdb")
    bad = "| Theme | Description |\n|---|---|\n| dup | a |\n| dup | b |\n| other | c |"
    with pytest.raises(ClassifierParseError, match="duplicate"):
        synthesize_themes(con, RecordingStub(bad), run_id=RUN)
