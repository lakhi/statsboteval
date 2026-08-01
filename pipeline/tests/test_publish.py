import json
import shutil
import socket
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import jsonschema
import pytest
from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient

from statsboteval_pipeline.contract import dump_doc
from statsboteval_pipeline.export_schema import SCHEMA_PATH
from statsboteval_pipeline.publish import (
    PublishGuardError,
    _assert_floor_respected,
    _assert_no_recoverable_partition,
    _assert_suppressed_bare,
    guard,
    publish,
)

from .factories import make_synthetic_aggregates, sample_trends_entry

# Azurite's documented well-known dev-storage account key (public, not a secret;
# matches the SDK's DEVSTORE_ACCOUNT_KEY constant).
AZURITE_KEY = "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw=="


def test_guard_accepts_valid_document() -> None:
    doc = make_synthetic_aggregates()
    assert guard(doc) == dump_doc(doc)


def test_guard_walk_rejects_suppressed_with_payload() -> None:
    dumped = dump_doc(make_synthetic_aggregates())
    cell = dumped["sections"]["temporal_usage"]["weekly"]["messages"]["series"][1]["cell"]
    assert cell == {"status": "suppressed"}  # factories week 2 is the suppressed one
    cell["value"] = 7  # the leak the guard exists to catch
    with pytest.raises(PublishGuardError, match="suppressed"):
        _assert_suppressed_bare(dumped)


def with_findings(dumped: dict) -> dict:
    """Attach a populated findings array to a window in a dumped document.

    Injected rather than fixtured: this axis produces no findings at all now that semester
    slices are excluded from the trends pass (D-56), and a factory that published some
    would assert something the pipeline cannot do. The guard walks dumped dicts and does
    not care where they came from, which is exactly what makes this safe.
    """
    dumped["sections"]["trends"]["per_window"]["2025S"] = dump_doc(sample_trends_entry())
    return dumped


def test_guard_walk_rejects_a_sub_floor_finding() -> None:
    dumped = with_findings(dump_doc(make_synthetic_aggregates()))
    finding = dumped["sections"]["trends"]["per_window"]["2025S"]["findings"][0]
    finding["baseline"]["n_students"] = 2  # floor is 3
    with pytest.raises(PublishGuardError, match=r"2025S.*n_students=2"):
        _assert_floor_respected(dumped, 3)


def test_guard_walk_accepts_findings_that_clear_the_floor() -> None:
    _assert_floor_respected(with_findings(dump_doc(make_synthetic_aggregates())), 3)


def test_guard_walk_rejects_a_sub_floor_summary() -> None:
    # The walk is generic, not trends-specific: the same statement covers the histogram
    # summaries that _summary() floors, and any section that publishes an n_students later.
    dumped = dump_doc(make_synthetic_aggregates())
    dumped["sections"]["sessions"]["per_window"]["all_time"]["messages_per_session"]["summary"]["n_students"] = 1
    with pytest.raises(PublishGuardError, match="n_students=1"):
        _assert_floor_respected(dumped, 3)


def test_guard_walk_names_the_path_to_the_offending_cell() -> None:
    dumped = with_findings(dump_doc(make_synthetic_aggregates()))
    dumped["sections"]["trends"]["per_window"]["2025S"]["findings"][1]["current"]["n_students"] = 2
    with pytest.raises(PublishGuardError) as exc:
        _assert_floor_respected(dumped, 3)
    # An operator hitting this at publish time needs the coordinates, not just the fact.
    assert "sections.trends.per_window.2025S.findings[1].current" in str(exc.value)


def with_level_split(dumped: dict, measure: str, cells: list[dict], total: int) -> dict:
    """Give all_time a program-level split with hand-chosen cells.

    Injected rather than fixtured, the same reasoning `with_findings` uses: the factory
    publishes no by_status at all, and the guard walks dumped dicts without caring where
    they came from. Hand-built is also the point — `_joint_partition_floor` makes this
    shape unbuildable by the pipeline, so the only way to prove the guard catches it is to
    forge one, which is exactly the hand-edited-document case the guard is the backstop for.
    """
    window = dumped["sections"]["usage_context"]["per_window"]["all_time"]
    window["totals"][measure] = {"status": "ok", "value": total}
    window["by_status"] = {
        level: {"active_students": {"status": "ok", "value": 9}, "messages": {"status": "ok", "value": 9},
                measure: cell}
        for level, cell in zip(("bachelor", "master", "staff"), cells)
    }
    return dumped


def test_guard_rejects_a_lone_suppressed_level_cell() -> None:
    """One withheld level beside a published total is arithmetic, not privacy (D-59)."""
    dumped = with_level_split(
        dump_doc(make_synthetic_aggregates()),
        "new_registrations",
        [{"status": "ok", "value": 40}, {"status": "ok", "value": 58}, {"status": "suppressed"}],
        100,
    )
    with pytest.raises(PublishGuardError) as exc:
        _assert_no_recoverable_partition(dumped)
    # The operator needs the number that escaped, not just the fact that one did.
    assert "recoverable as 100 - 98 = 2" in str(exc.value)


def test_guard_allows_two_suppressed_level_cells() -> None:
    """Two unknowns share the remainder, so neither is individually recoverable."""
    dumped = with_level_split(
        dump_doc(make_synthetic_aggregates()),
        "new_registrations",
        [{"status": "ok", "value": 40}, {"status": "suppressed"}, {"status": "suppressed"}],
        100,
    )
    _assert_no_recoverable_partition(dumped)


def test_guard_ignores_a_measure_the_levels_do_not_partition() -> None:
    """active_students double-counts transitioners, so its remainder is not a value."""
    dumped = with_level_split(
        dump_doc(make_synthetic_aggregates()),
        "active_students",
        [{"status": "ok", "value": 40}, {"status": "ok", "value": 58}, {"status": "suppressed"}],
        100,
    )
    _assert_no_recoverable_partition(dumped)


def test_guard_accepts_a_measured_zero() -> None:
    # ok(0) carries no n_students at all (a measured zero is not identifying), so the
    # universal walk must not read a zero *value* as a zero student count.
    dumped = dump_doc(make_synthetic_aggregates())
    assert dumped["sections"]["language"]["weekly"]["messages_by_language"]["other"]["series"][0]["cell"] == {
        "status": "ok",
        "value": 0,
    }
    _assert_floor_respected(dumped, 3)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def azurite() -> Iterator[str]:
    if shutil.which("npx") is None:
        pytest.skip("npx unavailable; skipping Azurite integration tests")
    port = _free_port()
    proc = subprocess.Popen(
        [
            "npx", "--yes", "--package", "azurite", "azurite-blob",
            "--blobHost", "127.0.0.1", "--blobPort", str(port), "--inMemoryPersistence", "--silent",
            "--skipApiVersionCheck",  # SDK may speak a newer API version than Azurite validates
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                socket.create_connection(("127.0.0.1", port), timeout=1).close()
                break
            except OSError:
                if proc.poll() is not None:
                    pytest.skip("azurite failed to start")
                time.sleep(0.3)
        else:
            pytest.skip("azurite did not open its port in time")
        yield (
            "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;"
            f"AccountKey={AZURITE_KEY};BlobEndpoint=http://127.0.0.1:{port}/devstoreaccount1;"
        )
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_publish_protocol(azurite: str) -> None:
    doc = make_synthetic_aggregates()
    immutable, latest = publish(doc, connection_string=azurite)
    assert immutable == "v1/aggregates_2025-W14_20250407T050000Z.json"
    assert latest == "v1/latest.json"

    container = BlobServiceClient.from_connection_string(azurite).get_container_client("aggregates")
    immutable_bytes = container.download_blob(immutable).readall()
    latest_bytes = container.download_blob(latest).readall()
    assert immutable_bytes == latest_bytes  # §9: latest is a full identical copy
    assert json.loads(immutable_bytes) == dump_doc(doc)

    with pytest.raises(ResourceExistsError):  # §9: the versioned blob is immutable
        publish(doc, connection_string=azurite)


def test_cli_writes_valid_document(tmp_path: Path) -> None:
    from statsboteval_pipeline.cli import main

    out = tmp_path / "aggregates.json"
    assert main(["run-synthetic", "--corpus", str(tmp_path / "c.duckdb"), "--out", str(out)]) == 0
    data = json.loads(out.read_text())
    jsonschema.validate(data, json.loads(SCHEMA_PATH.read_text()))
    assert data["data_provenance"] == "synthetic"


def test_cli_refuses_existing_corpus(tmp_path: Path) -> None:
    from statsboteval_pipeline.cli import main

    (tmp_path / "c.duckdb").touch()
    with pytest.raises(SystemExit):
        main(["run-synthetic", "--corpus", str(tmp_path / "c.duckdb")])
