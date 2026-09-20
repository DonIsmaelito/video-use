import base64
import hashlib
import json
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from video_use_mcp.config import Settings
from video_use_mcp.server import create_app
from video_use_mcp.store import Store


class IdleManager:
    async def start(self):
        pass

    async def close(self):
        pass


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.delenv("VIDEO_USE_OWNER_BOOTSTRAP", raising=False)
    settings = Settings(data_dir=tmp_path, public_url="http://localhost:8787")
    app = create_app(settings, manager=IdleManager())
    with TestClient(app, base_url=settings.public_url) as client:
        yield client, app


def account(client, name="alice"):
    response = client.post(
        "/api/register", json={"username": name, "password": "correct horse battery"}
    )
    assert response.status_code == 200, response.text
    me = client.get("/api/me").json()
    client.headers["X-CSRF-Token"] = me["csrf"]
    return me


def connect_oauth(client, app, scopes="video:read video:write"):
    registered = client.post(
        "/register",
        json={
            "client_name": "Test assistant",
            "redirect_uris": ["http://localhost:9456/callback"],
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "scope": scopes,
        },
    )
    assert registered.status_code == 201, registered.text
    cid = registered.json()["client_id"]
    verifier = "v" * 64
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    response = client.get(
        "/authorize",
        params={
            "client_id": cid,
            "response_type": "code",
            "redirect_uri": "http://localhost:9456/callback",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "scope": scopes,
            "state": "opaque-state",
            "resource": "http://localhost:8787/mcp",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302, response.text
    request_id = parse_qs(urlsplit(response.headers["location"]).query)["authorize"][0]
    info = client.get("/api/consent/" + request_id)
    assert info.json()["client_name"] == "Test assistant"
    response = client.post("/api/consent/" + request_id, json={"allow": True})
    query = parse_qs(urlsplit(response.json()["redirect_url"]).query)
    assert query["state"] == ["opaque-state"]
    return cid, verifier, query["code"][0]


def exchange(client, cid, verifier, code):
    return client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "client_id": cid,
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": "http://localhost:9456/callback",
            "resource": "http://localhost:8787/mcp",
        },
    )


def mcp_call(client, token, method, params=None):
    return client.post(
        "/mcp",
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/json, text/event-stream",
        },
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
    )


def test_browser_credentials_isolation_and_upload(service):
    client, app = service
    account(client)
    assert (
        client.put(
            "/api/settings",
            json={
                "provider": "openrouter",
                "model": "openai/gpt-6-astra",
                "key": "test-secret-value",
            },
        ).status_code
        == 200
    )
    settings = client.get("/api/settings").json()
    assert settings["key_configured"]
    assert "test-secret-value" not in json.dumps(settings)
    assert b"test-secret-value" not in (app.state.store.path).read_bytes()
    project = client.post("/api/projects", json={"title": "A real edit"}).json()
    pid = project["id"]
    response = client.post(
        f"/api/projects/{pid}/media",
        files={"file": ("../../test.mp4", b"media-bytes", "video/mp4")},
    )
    assert response.status_code == 200, response.text
    assert "/" not in response.json()["name"]
    assert (
        client.post(
            f"/api/projects/{pid}/media",
            files={"file": ("script.html", b"<script>", "text/html")},
        ).status_code
        == 400
    )
    job = client.post(
        f"/api/projects/{pid}/jobs",
        json={"prompt": "Edit my footage", "request_id": "one"},
    ).json()
    duplicate = client.post(
        f"/api/projects/{pid}/jobs",
        json={"prompt": "Edit my footage", "request_id": "one"},
    ).json()
    assert duplicate["id"] == job["id"]
    assert (
        client.post(
            f"/api/projects/{pid}/jobs",
            json={"prompt": "Different brief", "request_id": "one"},
        ).status_code
        == 400
    )
    account(client, "bob")
    assert client.get(f"/api/projects/{pid}").status_code == 404
    assert client.get("/api/jobs/" + job["id"]).status_code == 404
    assert not client.get("/api/settings").json()["key_configured"]


def test_csrf_origin_and_secret_deletion(service):
    client, app = service
    account(client)
    assert (
        client.post(
            "/api/projects",
            json={"title": "Blocked"},
            headers={"X-CSRF-Token": "wrong"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/projects",
            json={"title": "Blocked"},
            headers={"Origin": "https://attacker.example"},
        ).status_code
        == 403
    )
    client.put(
        "/api/settings",
        json={"provider": "openai", "model": "gpt-6-astra", "key": "saved-secret"},
    )
    assert (
        client.put(
            "/api/settings", json={"provider": "anthropic", "model": "claude-opus-5"}
        ).status_code
        == 400
    )
    assert client.delete("/api/settings/keys").status_code == 200
    assert not client.get("/api/settings").json()["key_configured"]


def test_real_oauth_pkce_refresh_and_mcp_transport(service):
    client, app = service
    account(client)
    metadata = client.get("/.well-known/oauth-authorization-server").json()
    assert metadata["code_challenge_methods_supported"] == ["S256"]
    response = mcp_call(client, "bad-token", "tools/list")
    assert response.status_code == 401
    assert "resource_metadata=" in response.headers["www-authenticate"]
    cid, verifier, code = connect_oauth(client, app)
    assert exchange(client, cid, "wrong", code).status_code == 400
    response = exchange(client, cid, verifier, code)
    assert response.status_code == 200, response.text
    grant = response.json()
    assert exchange(client, cid, verifier, code).status_code == 400
    token = grant["access_token"]
    tools = mcp_call(client, token, "tools/list")
    assert tools.status_code == 200, tools.text
    names = {t["name"] for t in tools.json()["result"]["tools"]}
    assert {"create_video_project", "start_video_job", "get_video_job"} <= names
    created = mcp_call(
        client,
        token,
        "tools/call",
        {"name": "create_video_project", "arguments": {"title": "Created over MCP"}},
    )
    assert not created.json()["result"].get("isError"), created.text
    assert client.get("/api/projects").json()[0]["title"] == "Created over MCP"
    refresh = client.post(
        "/token",
        data={
            "grant_type": "refresh_token",
            "client_id": cid,
            "refresh_token": grant["refresh_token"],
            "resource": "http://localhost:8787/mcp",
        },
    )
    assert refresh.status_code == 200, refresh.text
    assert refresh.json()["access_token"] != token
    assert mcp_call(client, token, "tools/list").status_code == 401
    reused = client.post(
        "/token",
        data={
            "grant_type": "refresh_token",
            "client_id": cid,
            "refresh_token": grant["refresh_token"],
        },
    )
    assert reused.status_code == 400


def test_readonly_scope_cannot_create(service):
    client, app = service
    account(client)
    cid, verifier, code = connect_oauth(client, app, "video:read")
    token = exchange(client, cid, verifier, code).json()["access_token"]
    result = mcp_call(
        client,
        token,
        "tools/call",
        {"name": "create_video_project", "arguments": {"title": "No permission"}},
    ).json()["result"]
    assert result["isError"]
    assert client.get("/api/projects").json() == []


def test_download_links_expire_and_bind_to_artifact(service):
    client, app = service
    user = account(client)
    store = app.state.store
    p = store.create_project(user["id"], "Finished")
    job = store.queue_job(user["id"], p["id"], "A film", None, 10)
    directory = store.root / "jobs" / job["id"]
    directory.mkdir(parents=True)
    (directory / "video.mp4").write_bytes(b"video")
    (directory / "project.zip").write_bytes(b"source")
    store.update_job(job["id"], "succeeded", result={"summary": "Done"})
    result = client.get("/api/jobs/" + job["id"]).json()["result"]
    assert client.get(result["video_url"]).content == b"video"
    assert (
        client.get(result["video_url"].replace("video.mp4", "project.zip")).status_code
        == 403
    )
    old = store.vault.encrypt_at_time(
        json.dumps({"job": job["id"], "kind": "video"}).encode(), 1
    ).decode()
    assert client.get(f"/files/{job['id']}/video.mp4?ticket={old}").status_code == 403


def test_restart_preserves_credentials_and_marks_interrupted_jobs(tmp_path):
    first = Store(tmp_path)
    uid = first.create_user("alice", "correct horse battery")
    first.put("credentials", uid, {"key": "secret"})
    pid = first.create_project(uid, "Persistent")["id"]
    job = first.queue_job(uid, pid, "Create a film", None, 10)
    first.update_job(job["id"], "running")
    second = Store(tmp_path)
    second.recover()
    assert second.get("credentials", uid) == {"key": "secret"}
    assert second.job(uid, job["id"])["status"] == "failed"
    assert "restarted" in second.job(uid, job["id"])["error"]


def test_registration_rejects_unsafe_redirects(service):
    client, _ = service
    for uri in [
        "https://example.com/cb#fragment",
        "http://example.com/cb",
        "https://name:password@example.com/cb",
    ]:
        response = client.post(
            "/register",
            json={"redirect_uris": [uri], "token_endpoint_auth_method": "none"},
        )
        assert response.status_code == 400, response.text


def test_request_limit_rejects_declared_and_streamed_oversize(service):
    client, _ = service
    declared = client.post(
        "/api/login", headers={"Content-Length": str(5 * 1024 * 1024)}, content=b"{}"
    )
    assert declared.status_code == 413
    # Chunked bodies have no Content-Length, so limiting only that header is
    # insufficient. Stop the body before JSON or multipart parsing retains it.
    streamed = client.post(
        "/api/login",
        headers={"Content-Type": "application/json"},
        content=iter([b" " * (1024 * 1024)] * 5),
    )
    assert streamed.status_code == 413


def test_removed_owner_keys_are_not_restored_on_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_USE_OWNER_BOOTSTRAP", "test-owner-bootstrap")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-operator-key")
    settings = Settings(tmp_path)
    app = create_app(settings, manager=IdleManager())
    with TestClient(app, base_url=settings.public_url) as client:
        assert (
            client.post(
                "/api/bootstrap", json={"token": "test-owner-bootstrap"}
            ).status_code
            == 200
        )
        me = client.get("/api/me").json()
        client.headers["X-CSRF-Token"] = me["csrf"]
        assert client.get("/api/settings").json()["key_configured"]
        assert client.delete("/api/settings/keys").status_code == 200
    restarted = create_app(settings, manager=IdleManager())
    assert restarted.state.store.get("credentials", me["id"]) is None
