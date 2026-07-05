from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

from .conftest import FIXTURE_PATH, FakeSource


def test_serves_dashboard_bundle_behind_api_routes(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<html><body>dashboard-bundle</body></html>")
    client = TestClient(
        create_app(
            settings=Settings(dashboard_dist=tmp_path),
            source=FakeSource(FIXTURE_PATH.read_bytes()),
        )
    )
    assert "dashboard-bundle" in client.get("/").text  # D-26: same app serves the bundle
    assert client.get("/healthz").json() == {"status": "ok"}  # API routes still win
    assert client.get("/api/v1/aggregates").status_code == 200


def test_no_dist_configured_means_api_only(tmp_path: Path) -> None:
    client = TestClient(create_app(settings=Settings(), source=FakeSource(None)))
    assert client.get("/").status_code == 404
    assert client.get("/healthz").status_code == 200
