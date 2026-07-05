import json

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

from .conftest import FIXTURE_PATH, FakeSource


def client_with(source: FakeSource, **settings_overrides) -> TestClient:
    return TestClient(create_app(settings=Settings(**settings_overrides), source=source))


def test_serves_latest_document_verbatim() -> None:
    payload = FIXTURE_PATH.read_bytes()
    client = client_with(FakeSource(payload))
    response = client.get("/api/v1/aggregates")
    assert response.status_code == 200
    assert response.json() == json.loads(payload)  # contract §1: served verbatim, never reshaped


def test_cache_honored_within_ttl() -> None:
    source = FakeSource(FIXTURE_PATH.read_bytes())
    client = client_with(source, cache_ttl_seconds=300)
    client.get("/api/v1/aggregates")
    client.get("/api/v1/aggregates")
    assert source.calls == 1


def test_zero_ttl_refetches() -> None:
    source = FakeSource(FIXTURE_PATH.read_bytes())
    client = client_with(source, cache_ttl_seconds=0)
    client.get("/api/v1/aggregates")
    client.get("/api/v1/aggregates")
    assert source.calls == 2


def test_missing_blob_returns_503() -> None:
    client = client_with(FakeSource(None))
    assert client.get("/api/v1/aggregates").status_code == 503


def test_invalid_document_returns_500_not_served() -> None:
    doc = json.loads(FIXTURE_PATH.read_text())
    del doc["schema_version"]  # schema tripwire must reject
    client = client_with(FakeSource(json.dumps(doc).encode()))
    response = client.get("/api/v1/aggregates")
    assert response.status_code == 500
    assert "validation" in response.json()["detail"]
