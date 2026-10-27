from fastapi.testclient import TestClient

from app.main import app


def test_00_1_healthz_returns_ok():
    response = TestClient(app).get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
