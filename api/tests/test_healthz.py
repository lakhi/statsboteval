from fastapi.testclient import TestClient

from app.main import create_app

from .conftest import FakeSource


def test_healthz() -> None:
    client = TestClient(create_app(source=FakeSource(None)))
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
