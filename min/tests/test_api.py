# min/tests/test_api.py — T3: API Endpoints integration tests

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from main import app
    return TestClient(app)


def test_health_ok(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"ok": True}


def test_get_config(client):
    res = client.get("/config")
    assert res.status_code == 200
    data = res.json()
    assert "model" in data


def test_list_providers(client):
    res = client.get("/providers")
    assert res.status_code == 200
    data = res.json()
    assert "providers" in data
    assert isinstance(data["providers"], list)


def test_project_current(client):
    res = client.get("/project/current")
    assert res.status_code == 200
    assert "path" in res.json()


def test_project_files(client):
    res = client.get("/project/files")
    assert res.status_code == 200
    assert "files" in res.json()


def test_create_session(client):
    res = client.post("/session")
    assert res.status_code == 200
    data = res.json()
    assert "session_id" in data


def test_get_session(client):
    # Buat session dulu
    create_res = client.post("/session")
    assert create_res.status_code == 200
    sid = create_res.json()["session_id"]

    res = client.get(f"/session/{sid}")
    assert res.status_code == 200
    assert res.json()["session_id"] == sid


def test_context_add_bad_session(client):
    res = client.post(
        "/context/add",
        json={"session_id": "nonexistent-xxx", "path": "main.py"},
    )
    assert res.status_code == 404


def test_context_list_bad_session(client):
    res = client.get("/context", params={"session_id": "nonexistent-xxx"})
    assert res.status_code == 404


def test_abort_bad_session(client):
    res = client.post("/session/nonexistent-xxx/abort")
    assert res.status_code == 404
