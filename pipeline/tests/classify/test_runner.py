"""Phase B Task 9: batch classification runner (idempotent, resumable)."""

import re
from pathlib import Path

import duckdb
import pytest

from statsboteval_pipeline.classify.codebook import Codebook, synthetic_codebook
from statsboteval_pipeline.classify.runner import classify_corpus
from statsboteval_pipeline.corpus import open_corpus
from statsboteval_pipeline.labels import read_labels

VERSION = "statsboteval-v1"
MODEL_TAG = "stub-model@2026-01-01"


def seed_corpus(path: Path, n_messages: int) -> duckdb.DuckDBPyConnection:
    con = open_corpus(path)
    con.execute("INSERT INTO students VALUES ('syn-0001', '2025-03-03 10:00:00')")
    for i in range(1, n_messages + 1):
        con.execute(
            "INSERT INTO messages VALUES (?, 'syn-0001', 1700000000000, '2025-03-10 10:00:00', ?, 'reply', 10, 20)",
            [i, f"synthetic message {i}"],
        )
    return con


class StubClient:
    """Deterministic canned tables: deductive all-1s; first message of each batch gets theme[0]."""

    def __init__(self, codebook: Codebook, fail_on_call: int | None = None) -> None:
        self.codebook = codebook
        self.fail_on_call = fail_on_call
        self.calls = 0
        self.efforts: list[str] = []

    def complete(self, prompt: str, *, reasoning_effort: str = "minimal") -> str:
        self.calls += 1
        self.efforts.append(reasoning_effort)
        if self.fail_on_call is not None and self.calls == self.fail_on_call:
            raise RuntimeError("boom (stubbed transport failure)")
        n = len(re.findall(r"^Message \d+:$", prompt, re.MULTILINE))
        if "Codebook:" in prompt:
            names = [c.name for c in self.codebook.categories]
            header = f"| Message | {' | '.join(names)} |\n|{'---|' * (len(names) + 1)}\n"
            rows = "\n".join(f"| {i} | {' | '.join('1' for _ in names)} |" for i in range(1, n + 1))
            return header + rows
        rows = "\n".join(f"| {i} | {'1' if i == 1 else 'none'} |" for i in range(1, n + 1))
        return f"| Message | Labels |\n|---|---|\n{rows}"


def test_full_run_writes_all_domains_with_provenance(tmp_path: Path) -> None:
    cb = synthetic_codebook()
    con = seed_corpus(tmp_path / "corpus.duckdb", 3)
    labeled = classify_corpus(con, StubClient(cb), cb, label_version=VERSION, model_tag=MODEL_TAG)
    assert labeled == 3
    rows = read_labels(con, VERSION)
    deductive = [r for r in rows if r.domain == "deductive"]
    assert len(deductive) == 3 * len(cb.categories)  # explicit 0/1 per category per message
    assert {r.provenance for r in rows} == {MODEL_TAG}
    assert {r.code for r in deductive} == {c.code for c in cb.categories}
    method = [r for r in rows if r.domain == "method_theme"]
    software = [r for r in rows if r.domain == "software_theme"]
    assert [(r.history_id, r.code, r.value) for r in method] == [(1, cb.method_themes[0], 1)]
    assert [(r.history_id, r.code, r.value) for r in software] == [(1, cb.software_themes[0], 1)]


def test_second_run_is_idempotent(tmp_path: Path) -> None:
    cb = synthetic_codebook()
    con = seed_corpus(tmp_path / "corpus.duckdb", 3)
    client = StubClient(cb)
    assert classify_corpus(con, client, cb, label_version=VERSION, model_tag=MODEL_TAG) == 3
    calls_after_first = client.calls
    assert classify_corpus(con, client, cb, label_version=VERSION, model_tag=MODEL_TAG) == 0
    assert client.calls == calls_after_first  # no API calls on a fully-labeled corpus


def test_mid_run_failure_keeps_prior_batches_and_resume_completes(tmp_path: Path) -> None:
    cb = synthetic_codebook()
    con = seed_corpus(tmp_path / "corpus.duckdb", 4)
    # batch_size=2 -> two batches of 3 calls each; fail on call 4 (first call of batch 2).
    failing = StubClient(cb, fail_on_call=4)
    with pytest.raises(RuntimeError, match="boom"):
        classify_corpus(con, failing, cb, label_version=VERSION, model_tag=MODEL_TAG, batch_size=2)
    done_ids = {r.history_id for r in read_labels(con, VERSION)}
    assert done_ids == {1, 2}  # batch 1 persisted, batch 2 untouched
    assert classify_corpus(con, StubClient(cb), cb, label_version=VERSION, model_tag=MODEL_TAG, batch_size=2) == 2
    assert {r.history_id for r in read_labels(con, VERSION)} == {1, 2, 3, 4}


class OffListOnceClient(StubClient):
    """First theme call emits an off-list label; the corrective retry then behaves."""

    def complete(self, prompt: str, *, reasoning_effort: str = "minimal") -> str:
        out = super().complete(prompt, reasoning_effort=reasoning_effort)
        if "Labels |" in out and "rejected by a strict parser" not in prompt:
            self.bad_calls = getattr(self, "bad_calls", 0) + 1
            return out.replace("| 1 |", "| 1 | not-a-real-theme;", 1)
        return out


class AlwaysOffListClient(StubClient):
    def complete(self, prompt: str, *, reasoning_effort: str = "minimal") -> str:
        out = super().complete(prompt, reasoning_effort=reasoning_effort)
        return out.replace("| 1 |", "| 1 | not-a-real-theme;", 1) if "Labels |" in out else out


def test_parse_error_triggers_corrective_retry(tmp_path: Path) -> None:
    cb = synthetic_codebook()
    con = seed_corpus(tmp_path / "corpus.duckdb", 2)
    client = OffListOnceClient(cb)
    assert classify_corpus(con, client, cb, label_version=VERSION, model_tag=MODEL_TAG) == 2
    assert client.bad_calls == 2  # both theme passes misbehaved once, then recovered
    # Retries escalate reasoning effort: each theme pass ran minimal then low.
    assert client.efforts == ["minimal", "minimal", "low", "minimal", "low"]
    rows = read_labels(con, VERSION)
    assert not [r for r in rows if "not-a-real-theme" in r.code]  # bad label never written
    assert [(r.history_id, r.code) for r in rows if r.domain == "method_theme"] == [(1, cb.method_themes[0])]


def test_persistent_parse_error_still_raises(tmp_path: Path) -> None:
    from statsboteval_pipeline.classify.parse import ClassifierParseError

    cb = synthetic_codebook()
    con = seed_corpus(tmp_path / "corpus.duckdb", 2)
    with pytest.raises(ClassifierParseError, match="not-a-real-theme"):
        classify_corpus(con, AlwaysOffListClient(cb), cb, label_version=VERSION, model_tag=MODEL_TAG)
    assert read_labels(con, VERSION) == []  # nothing persisted from the failing batch


def test_other_versions_do_not_mark_messages_done(tmp_path: Path) -> None:
    cb = synthetic_codebook()
    con = seed_corpus(tmp_path / "corpus.duckdb", 2)
    con.execute(
        "INSERT INTO labels VALUES (1, 'lang-heuristic-v1', 'language', 'de', 1, 'lingua-py')"
    )
    assert classify_corpus(con, StubClient(cb), cb, label_version=VERSION, model_tag=MODEL_TAG) == 2


def test_empty_corpus_is_a_noop(tmp_path: Path) -> None:
    cb = synthetic_codebook()
    con = open_corpus(tmp_path / "corpus.duckdb")
    client = StubClient(cb)
    assert classify_corpus(con, client, cb, label_version=VERSION, model_tag=MODEL_TAG) == 0
    assert client.calls == 0
