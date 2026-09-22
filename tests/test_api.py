from __future__ import annotations

import importlib

from fastapi.testclient import TestClient


def make_client(monkeypatch, tmp_path):
    monkeypatch.setenv("QR_DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("QR_API_SECRET", "test-secret")
    import app.main

    module = importlib.reload(app.main)
    return TestClient(module.app)


def register(client: TestClient, email="user@example.com"):
    response = client.post("/auth/register", json={"email": email, "password": "safe-password-123"})
    assert response.status_code == 201
    login = client.post("/auth/token", data={"username": email, "password": "safe-password-123"})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_authenticated_qr_lifecycle(monkeypatch, tmp_path):
    with make_client(monkeypatch, tmp_path) as client:
        headers = register(client)
        created = client.post("/qrcodes", headers=headers, json={"url": "https://example.com/path", "foreground": "#123456", "error_correction": "H"})
        assert created.status_code == 201
        item = created.json()
        assert item["foreground"] == "#123456"
        listing = client.get("/qrcodes", headers=headers)
        assert listing.json()["total"] == 1
        image = client.get(f"/qrcodes/{item['id']}/download", headers=headers)
        assert image.status_code == 200
        assert image.headers["content-type"] == "image/png"
        assert image.content.startswith(b"\x89PNG")
        assert client.delete(f"/qrcodes/{item['id']}", headers=headers).status_code == 204


def test_users_cannot_access_each_others_qrs(monkeypatch, tmp_path):
    with make_client(monkeypatch, tmp_path) as client:
        alice = register(client, "alice@example.com")
        qr_id = client.post("/qrcodes", headers=alice, json={"url": "https://example.com"}).json()["id"]
        bob = register(client, "bob@example.com")
        assert client.get(f"/qrcodes/{qr_id}/download", headers=bob).status_code == 404
