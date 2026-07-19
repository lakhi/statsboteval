"""GL5: run-weekly orchestration (stubbed source/publisher — no network, no real data)."""

import json
from pathlib import Path

import pytest

import statsboteval_pipeline.cli as cli
import statsboteval_pipeline.classify.step as classify_step_module
import statsboteval_pipeline.extract as extract_module
import statsboteval_pipeline.language as language_module
from statsboteval_pipeline.corpus import open_corpus
from statsboteval_pipeline.fixtures import seed_synthetic
from statsboteval_pipeline.publish import PublishGuardError


class FakeSource:
    def close(self) -> None:
        pass


@pytest.fixture()
def corpus(tmp_path: Path) -> Path:
    path = tmp_path / "corpus.duckdb"
    con = open_corpus(path)
    seed_synthetic(con, weeks=4, seed=7)
    con.close()
    return path


@pytest.fixture()
def env_file(tmp_path: Path) -> Path:
    env = tmp_path / "fake.env"
    env.write_text(
        "STATSBOT_DB_HOST=localhost\nSTATSBOT_DB_NAME=fake\nSTATSBOT_DB_USER=fake\n"
        "STATSBOT_DB_PASSWORD=fake\nPSEUDONYM_PEPPER=synthetic-test-pepper\n"
    )
    return env


@pytest.fixture()
def stages(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []
    monkeypatch.setattr(extract_module, "connect_source", lambda settings: FakeSource())
    monkeypatch.setattr(extract_module, "extract_new_rows", lambda con, source, pepper: (calls.append("extract"), 0)[1])
    monkeypatch.setattr(language_module, "detect_languages", lambda con: (calls.append("detect"), 0)[1])
    monkeypatch.setattr(
        classify_step_module, "run_classification", lambda con, *, env_file: (calls.append("classify"), 0)[1]
    )
    real_build = cli.build_aggregates

    def recording_build(*args, **kwargs):
        calls.append("aggregate")
        return real_build(*args, **kwargs)

    monkeypatch.setattr(cli, "build_aggregates", recording_build)
    return calls


def test_run_weekly_stage_order_and_provenance(corpus: Path, env_file: Path, stages: list[str], tmp_path: Path) -> None:
    out = tmp_path / "aggregates.json"
    assert cli.main(["run-weekly", "--corpus", str(corpus), "--env-file", str(env_file), "--out", str(out)]) == 0
    assert stages == ["extract", "detect", "classify", "aggregate"]
    doc = json.loads(out.read_text())
    assert doc["data_provenance"] == "production"
    # No classification labels exist (stubbed classify) -> topics + its version key stay absent.
    assert doc["label_versions"] == {"language": "lang-heuristic-v1"}
    assert "topics" not in doc["sections"]


def test_run_weekly_guard_failure_blocks_upload(
    corpus: Path, env_file: Path, stages: list[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    uploaded: list[str] = []
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "UseDevelopmentStorage=true")
    monkeypatch.setattr(cli, "publish", lambda doc, **kw: uploaded.append("publish"))

    def failing_render(doc):
        raise PublishGuardError("synthetic guard failure")

    monkeypatch.setattr(cli, "render", failing_render)
    with pytest.raises(PublishGuardError):
        cli.main(["run-weekly", "--corpus", str(corpus), "--env-file", str(env_file), "--upload"])
    assert uploaded == []  # guard fired before any upload


def test_run_weekly_upload_uses_publisher(
    corpus: Path, env_file: Path, stages: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    published: list[dict] = []
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "UseDevelopmentStorage=true")

    def fake_publish(doc, *, connection_string, **kw):
        published.append({"provenance": doc.data_provenance, "conn": connection_string})
        return "v1/aggregates_x.json", "v1/latest.json"

    monkeypatch.setattr(cli, "publish", fake_publish)
    assert cli.main(["run-weekly", "--corpus", str(corpus), "--env-file", str(env_file), "--upload"]) == 0
    assert published == [{"provenance": "production", "conn": "UseDevelopmentStorage=true"}]


def test_run_weekly_skip_extract(corpus: Path, env_file: Path, stages: list[str], tmp_path: Path) -> None:
    out = tmp_path / "aggregates.json"
    args = ["run-weekly", "--corpus", str(corpus), "--env-file", str(env_file), "--skip-extract", "--out", str(out)]
    assert cli.main(args) == 0
    assert stages == ["detect", "classify", "aggregate"]  # no source connection attempted
    assert json.loads(out.read_text())["data_provenance"] == "production"


def test_run_weekly_skip_classify(corpus: Path, env_file: Path, stages: list[str], tmp_path: Path) -> None:
    out = tmp_path / "aggregates.json"
    args = ["run-weekly", "--corpus", str(corpus), "--env-file", str(env_file), "--skip-classify", "--out", str(out)]
    assert cli.main(args) == 0
    assert stages == ["extract", "detect", "aggregate"]  # classification bypassed (D-38 escape hatch)
    assert json.loads(out.read_text())["data_provenance"] == "production"


def test_run_synthetic_with_labels_publishes_topics(tmp_path: Path) -> None:
    out = tmp_path / "aggregates.json"
    corpus = tmp_path / "fresh.duckdb"
    assert cli.main(["run-synthetic", "--corpus", str(corpus), "--with-labels", "--out", str(out)]) == 0
    doc = json.loads(out.read_text())
    assert doc["data_provenance"] == "synthetic"
    assert doc["label_versions"]["classification"] == "statsboteval-v1"
    topics = doc["sections"]["topics"]
    assert topics["theme_set_version"] == "statsboteval-themes-v1"
    entry = topics["per_window"]["all_time"]
    assert entry["deductive"]["items"] and entry["emergent_themes"]["items"]
    assert set(entry["by_status"]) <= {"bachelor", "master", "staff", "unknown"}
    assert len(entry["by_status"]) >= 2


def test_validate_subcommand_prints_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from statsboteval_pipeline.labels import LabelRow, write_labels

    corpus = tmp_path / "corpus.duckdb"
    con = open_corpus(corpus)
    write_labels(
        con,
        [
            LabelRow(1, "bergmann-v1", "deductive", "synthetic_alpha", 1, "human_consensus"),
            LabelRow(1, "statsboteval-v1", "deductive", "synthetic_alpha", 1, "stub@x"),
        ],
    )
    con.close()
    assert cli.main(["validate", "--corpus", str(corpus)]) == 0
    printed = capsys.readouterr().out
    assert "Validation vs bergmann-v1" in printed
    assert "synthetic_alpha" in printed


def test_run_weekly_axis_start_is_forwarded(
    corpus: Path, env_file: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(extract_module, "connect_source", lambda settings: FakeSource())
    monkeypatch.setattr(extract_module, "extract_new_rows", lambda con, source, pepper: 0)
    monkeypatch.setattr(language_module, "detect_languages", lambda con: 0)
    seen: dict = {}
    real_build = cli.build_aggregates

    def capturing_build(*args, **kwargs):
        seen.update(kwargs)
        return real_build(*args, **kwargs)

    monkeypatch.setattr(cli, "build_aggregates", capturing_build)
    out = tmp_path / "aggregates.json"
    args = ["run-weekly", "--corpus", str(corpus), "--env-file", str(env_file), "--skip-classify", "--out", str(out)]
    assert cli.main(args) == 0
    assert str(seen["axis_start"]) == "2025-03-01"  # the D-36 owner default


def _freeze_test_set(corpus: Path, set_version: str = "statsboteval-themes-v1") -> None:
    from datetime import datetime, timezone

    from statsboteval_pipeline.themes import ThemeEntry, freeze_theme_set

    con = open_corpus(corpus)
    entries = [ThemeEntry(f"synthetic theme {i}", "synthetic description") for i in range(3)]
    freeze_theme_set(con, entries, set_version, now=datetime(2026, 7, 19, tzinfo=timezone.utc))
    con.close()


def test_run_weekly_chains_assignment_once_a_set_is_frozen(
    corpus: Path, env_file: Path, stages: list[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _freeze_test_set(corpus)
    monkeypatch.setattr(
        classify_step_module, "run_theme_assignment", lambda con, *, env_file: (stages.append("assign"), 0)[1]
    )
    out = tmp_path / "aggregates.json"
    assert cli.main(["run-weekly", "--corpus", str(corpus), "--env-file", str(env_file), "--out", str(out)]) == 0
    assert stages == ["extract", "detect", "classify", "assign", "aggregate"]
    # Assignment ran but wrote no labels (stub) -> theme_set_version stays absent.
    assert "topics" not in json.loads(out.read_text())["sections"]


def test_run_weekly_skip_classify_skips_assignment_too(
    corpus: Path, env_file: Path, stages: list[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _freeze_test_set(corpus)
    monkeypatch.setattr(
        classify_step_module, "run_theme_assignment", lambda con, *, env_file: (stages.append("assign"), 0)[1]
    )
    args = ["run-weekly", "--corpus", str(corpus), "--env-file", str(env_file), "--skip-classify"]
    assert cli.main(args) == 0
    assert stages == ["extract", "detect", "aggregate"]


def test_run_weekly_aggregates_carry_theme_set_version_with_emergent_labels(
    corpus: Path, env_file: Path, stages: list[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from statsboteval_pipeline.labels import LabelRow, write_labels

    _freeze_test_set(corpus)
    con = open_corpus(corpus)
    ids = [row[0] for row in con.execute("SELECT history_id FROM messages LIMIT 5").fetchall()]
    write_labels(
        con,
        [LabelRow(i, "statsboteval-v1", "emergent_theme", "synthetic theme 0", 1, "stub@x#set") for i in ids],
    )
    con.close()
    monkeypatch.setattr(classify_step_module, "run_theme_assignment", lambda con, *, env_file: 0)
    out = tmp_path / "aggregates.json"
    assert cli.main(["run-weekly", "--corpus", str(corpus), "--env-file", str(env_file), "--out", str(out)]) == 0
    topics = json.loads(out.read_text())["sections"]["topics"]
    assert topics["theme_set_version"] == "statsboteval-themes-v1"


def test_freeze_themes_cli_loads_reviewed_draft(corpus: Path, env_file: Path, tmp_path: Path) -> None:
    from statsboteval_pipeline.themes import reviewed_theme_labels

    draft = tmp_path / "draft.md"
    draft.write_text(
        "| Theme | Description |\n|---|---|\n"
        "| synthetic a | d |\n| synthetic b | d |\n| synthetic c | d |\n"
    )
    args = ["freeze-themes", "--corpus", str(corpus), "--env-file", str(env_file), "--draft", str(draft)]
    assert cli.main(args) == 0
    con = open_corpus(corpus)
    assert reviewed_theme_labels(con, "statsboteval-themes-v1") == ["synthetic a", "synthetic b", "synthetic c"]
    con.close()


def test_assign_themes_refuses_missing_or_unreviewed_set(corpus: Path, tmp_path: Path) -> None:
    from statsboteval_pipeline.classify.step import run_theme_assignment
    from statsboteval_pipeline.themes import ThemeSetError

    env = tmp_path / "azure.env"
    env.write_text("AZURE_OPENAI_ENDPOINT=https://example.invalid/\nAZURE_OPENAI_API_KEY=fake\n")
    con = open_corpus(corpus)
    with pytest.raises(ThemeSetError, match="does not exist"):
        run_theme_assignment(con, env_file=env)
    con.execute("INSERT INTO theme_sets VALUES ('statsboteval-themes-v1', 'a theme', 'd', now(), NULL)")
    with pytest.raises(ThemeSetError, match="not reviewed"):
        run_theme_assignment(con, env_file=env)
    con.close()
