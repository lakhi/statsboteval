"""GL5: run-weekly orchestration (stubbed source/publisher — no network, no real data)."""

import json
from pathlib import Path

import pytest

import statsboteval_pipeline.cli as cli
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
    real_build = cli.build_aggregates

    def recording_build(*args, **kwargs):
        calls.append("aggregate")
        return real_build(*args, **kwargs)

    monkeypatch.setattr(cli, "build_aggregates", recording_build)
    return calls


def test_run_weekly_stage_order_and_provenance(corpus: Path, env_file: Path, stages: list[str], tmp_path: Path) -> None:
    out = tmp_path / "aggregates.json"
    assert cli.main(["run-weekly", "--corpus", str(corpus), "--env-file", str(env_file), "--out", str(out)]) == 0
    assert stages == ["extract", "detect", "aggregate"]
    doc = json.loads(out.read_text())
    assert doc["data_provenance"] == "production"
    assert doc["label_versions"] == {"language": "lang-heuristic-v1"}


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
    assert cli.main(["run-weekly", "--corpus", str(corpus), "--env-file", str(env_file), "--out", str(out)]) == 0
    assert str(seen["axis_start"]) == "2025-03-01"  # the D-36 owner default
