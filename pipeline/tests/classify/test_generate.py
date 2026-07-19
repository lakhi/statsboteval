"""Phase B Stage 2 (Task 12): candidate-code generation — idempotent, strict, resumable."""

import re
from pathlib import Path

import duckdb
import pytest

from statsboteval_pipeline.classify.generate import candidate_frequencies, generate_candidates
from statsboteval_pipeline.classify.parse import ClassifierParseError
from statsboteval_pipeline.corpus import open_corpus

RUN = "statsboteval-themes-v1"


def seed_corpus(path: Path, n_messages: int) -> duckdb.DuckDBPyConnection:
    con = open_corpus(path)
    con.execute("INSERT INTO students VALUES ('syn-0001', '2025-03-03 10:00:00')")
    for i in range(1, n_messages + 1):
        con.execute(
            "INSERT INTO messages VALUES (?, 'syn-0001', 1700000000000, '2025-03-10 10:00:00', ?, 'reply', 10, 20)",
            [i, f"synthetic message {i}"],
        )
    return con


class CandidateStub:
    """Odd messages get two codes (one messily cased); even messages get none."""

    def __init__(self, fail_on_call: int | None = None) -> None:
        self.fail_on_call = fail_on_call
        self.calls = 0
        self.efforts: list[str] = []

    def complete(self, prompt: str, *, reasoning_effort: str = "minimal") -> str:
        self.calls += 1
        self.efforts.append(reasoning_effort)
        if self.fail_on_call is not None and self.calls == self.fail_on_call:
            raise RuntimeError("boom (stubbed transport failure)")
        n = len(re.findall(r"^Message \d+:$", prompt, re.MULTILINE))
        rows = "\n".join(
            f"| {i} | {'Topic  ALPHA ; topic alpha; topic beta' if i % 2 else 'none'} |" for i in range(1, n + 1)
        )
        return f"| Message | Codes |\n|---|---|\n{rows}"


def candidates(con: duckdb.DuckDBPyConnection) -> list[tuple[int, str]]:
    return con.execute("SELECT history_id, code FROM theme_candidates WHERE run_id = ? ORDER BY 1, 2", [RUN]).fetchall()


def test_candidates_written_normalized_with_none_markers(tmp_path: Path) -> None:
    con = seed_corpus(tmp_path / "corpus.duckdb", 3)
    assert generate_candidates(con, CandidateStub(), run_id=RUN) == 3
    # Messy casing/whitespace normalized, duplicates dropped; "none" -> '' marker.
    assert candidates(con) == [(1, "topic alpha"), (1, "topic beta"), (2, ""), (3, "topic alpha"), (3, "topic beta")]


def test_second_run_is_idempotent_even_for_none_messages(tmp_path: Path) -> None:
    con = seed_corpus(tmp_path / "corpus.duckdb", 3)
    client = CandidateStub()
    assert generate_candidates(con, client, run_id=RUN) == 3
    calls_after_first = client.calls
    assert generate_candidates(con, client, run_id=RUN) == 0
    assert client.calls == calls_after_first  # the '' markers keep no-code messages done


def test_mid_run_failure_keeps_prior_batches_and_resume_completes(tmp_path: Path) -> None:
    con = seed_corpus(tmp_path / "corpus.duckdb", 4)
    with pytest.raises(RuntimeError, match="boom"):
        generate_candidates(con, CandidateStub(fail_on_call=2), run_id=RUN, batch_size=2)
    assert {history_id for history_id, _ in candidates(con)} == {1, 2}
    assert generate_candidates(con, CandidateStub(), run_id=RUN, batch_size=2) == 2
    assert {history_id for history_id, _ in candidates(con)} == {1, 2, 3, 4}


class MalformedOnceStub(CandidateStub):
    def complete(self, prompt: str, *, reasoning_effort: str = "minimal") -> str:
        out = super().complete(prompt, reasoning_effort=reasoning_effort)
        return "sorry, here is prose instead of a table" if self.calls == 1 else out


def test_parse_error_triggers_corrective_retry(tmp_path: Path) -> None:
    con = seed_corpus(tmp_path / "corpus.duckdb", 2)
    client = MalformedOnceStub()
    assert generate_candidates(con, client, run_id=RUN) == 2
    assert client.efforts == ["minimal", "low"]  # same escalation ladder as the runner


class QuotedTextStub(CandidateStub):
    def complete(self, prompt: str, *, reasoning_effort: str = "minimal") -> str:
        super().complete(prompt, reasoning_effort=reasoning_effort)
        long_code = "a verbatim quote of the whole student message pasted straight into the code cell"
        return f"| Message | Codes |\n|---|---|\n| 1 | {long_code} |\n| 2 | ok |"


def test_overlong_code_is_rejected_and_never_written(tmp_path: Path) -> None:
    con = seed_corpus(tmp_path / "corpus.duckdb", 2)
    with pytest.raises(ClassifierParseError, match="exceeds"):
        generate_candidates(con, QuotedTextStub(), run_id=RUN)
    assert candidates(con) == []


def test_candidate_frequencies_excludes_markers_and_sorts(tmp_path: Path) -> None:
    con = seed_corpus(tmp_path / "corpus.duckdb", 5)
    generate_candidates(con, CandidateStub(), run_id=RUN)
    assert candidate_frequencies(con, RUN) == [("topic alpha", 3), ("topic beta", 3)]
    assert candidate_frequencies(con, "other-run") == []
