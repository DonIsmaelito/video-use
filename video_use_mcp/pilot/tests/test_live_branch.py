"""Opt-in integration checks against the isolated InsForge test branch."""

import asyncio
import base64
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient
from dotenv import load_dotenv
from video_use_mcp.pilot.config import Config
from video_use_mcp.pilot.store import Store, ident
from video_use_mcp.pilot.server import create_app
from video_use_mcp.pilot.runtime import Manager

pytestmark = pytest.mark.skipif(
    os.getenv("PILOT_LIVE_TEST") != "1", reason="Requires isolated InsForge test branch"
)


class PrivateFixture(dict):
    def __repr__(self):
        return "<private integration fixture>"


class Idle:
    running = {}
    sessions = {}

    async def start(self):
        pass

    async def close(self):
        pass


@pytest.fixture(scope="module")
def setup():
    load_dotenv(".env.pilot-test", interpolate=False)
    config = Config.env()
    assert config.insforge_url.startswith(
        "https://f7e2vbn5-"
    ) and config.insforge_url.endswith(
        ".us-west.insforge.app"
    ), "Never run destructive fixtures against the live pilot"
    store = Store(config)
    users = [
        PrivateFixture(x)
        for x in json.loads(Path(".pilot-test-users.json").read_text())
    ]
    for user in users:
        store.sql(
            "SELECT public.vp_admit($1::uuid,$2,false)",
            user["user"]["id"],
            user["user"]["email"],
        )
    # Test fixture accounts are unverified by design; production rejects them.
    for user in users:
        with pytest.raises(PermissionError):
            store.identity(user["accessToken"])

    def fixture_identity(bearer):
        r = store.http.get(
            "/api/auth/sessions/current", headers={"Authorization": "Bearer " + bearer}
        )
        if r.status_code != 200:
            raise PermissionError("Invalid test token")
        user = r.json()["user"]
        assert user["id"] in {u["user"]["id"] for u in users}
        return user

    store.identity = fixture_identity
    app = create_app(config, store, Idle())
    with TestClient(app, base_url=config.public_url) as client:
        yield config, store, users, client


def token(user):
    return PrivateFixture({"Authorization": "Bearer " + user["accessToken"]})


def test_identity_and_project_isolation(setup):
    _, s, u, c = setup
    assert c.get("/api/me", headers=token(u[0])).status_code == 200
    p = c.post(
        "/api/projects", headers=token(u[0]), json={"title": "Private project"}
    ).json()
    assert c.get("/api/projects/" + p["id"], headers=token(u[1])).status_code == 403
    assert c.get("/api/projects/" + p["id"], headers=token(u[0])).status_code == 200
    r = httpx.get(
        s.config.insforge_url + "/api/database/records/vp_projects",
        headers=token(u[1]),
        timeout=30,
    )
    assert r.status_code == 200
    assert p["id"] not in r.text
    assert c.get("/api/admin", headers=token(u[0])).status_code == 403


def test_oauth_and_mcp(setup):
    _, s, u, c = setup
    reg = c.post(
        "/register",
        json={
            "client_name": "Pilot integration test",
            "redirect_uris": ["http://localhost:9456/callback"],
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "scope": "video:read video:write",
        },
    )
    assert reg.status_code == 201, reg.text
    cid = reg.json()["client_id"]
    verifier = "v" * 64
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    response = c.get(
        "/authorize",
        params={
            "client_id": cid,
            "response_type": "code",
            "redirect_uri": "http://localhost:9456/callback",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "scope": "video:read video:write",
            "state": "test-state",
            "resource": s.config.public_url + "/mcp",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302, response.text
    redirect = response.headers["location"]
    assert redirect.startswith(s.config.studio_url)
    rid = parse_qs(urlsplit(redirect).query)["authorize"][0]
    assert c.get("/api/consent/" + rid, headers=token(u[0])).status_code == 200
    result = c.post("/api/consent/" + rid, headers=token(u[0]), json={"allow": True})
    assert result.status_code == 200, result.text
    query = parse_qs(urlsplit(result.json()["redirect_url"]).query)
    assert query["state"] == ["test-state"]
    body = {
        "grant_type": "authorization_code",
        "client_id": cid,
        "code_verifier": verifier,
        "code": query["code"][0],
        "redirect_uri": "http://localhost:9456/callback",
        "resource": s.config.public_url + "/mcp",
    }
    exchange = c.post("/token", data=body)
    assert exchange.status_code == 200, exchange.text
    assert c.post("/token", data=body).status_code == 400
    headers = {
        "Authorization": "Bearer " + exchange.json()["access_token"],
        "Accept": "application/json, text/event-stream",
    }
    result = c.post(
        "/mcp",
        headers=headers,
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    )
    assert result.status_code == 200, result.text
    names = {x["name"] for x in result.json()["result"]["tools"]}
    assert {
        "run_video_command",
        "view_video_frame",
        "export_video",
        "video_use_guidance",
    } <= names
    assert "start_video_job" not in names
    result = c.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "video_use_guidance", "arguments": {}},
        },
    )
    assert "Remote runtime" in result.text
    assert s.config.api_key not in result.text


def test_atomic_quota_reservation(setup):
    _, s, u, _ = setup
    uid = u[1]["user"]["id"]
    s.sql("DELETE FROM public.vp_usage WHERE owner=$1 AND kind='compute'", uid)

    def reserve(_):
        try:
            return s.reserve(uid, "compute", 2000, ident())
        except ValueError:
            return None

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(reserve, range(2)))
    assert sum(bool(x) for x in results) == 1
    for rid in results:
        if rid:
            s.settle(rid, 0)


def test_private_storage_and_downloads(setup, tmp_path):
    config, s, u, c = setup
    uid = u[0]["user"]["id"]
    p = c.post(
        "/api/projects", headers=token(u[0]), json={"title": "Storage check"}
    ).json()
    local = tmp_path / "source.txt"
    local.write_text("private artifact")
    manager = Manager(s, config)
    obj = asyncio.run(manager.save_object(uid, p["id"], "archive", "source.txt", local))
    downloaded = tmp_path / "download"
    s.download(obj["key"], downloaded)
    assert downloaded.read_text() == "private artifact"
    raw = config.insforge_url + s.object_path(obj["key"])
    assert httpx.get(raw, headers=token(u[1]), timeout=30).status_code in (
        401,
        403,
        404,
    )
    ticket = s.vault.encrypt(
        json.dumps({"owner": uid, "object": obj["id"]}).encode()
    ).decode()
    assert (
        c.get("/files/" + obj["id"], params={"ticket": ticket}).content
        == b"private artifact"
    )
    assert c.get("/files/" + ident(), params={"ticket": ticket}).status_code == 403
    s.remove_object(obj["key"])
    s.sql("DELETE FROM public.vp_objects WHERE id=$1", obj["id"])
    s.settle(
        obj["id"]
        if not obj
        else s.sql("SELECT id FROM public.vp_usage WHERE request_id=$1", obj["id"])[0][
            "id"
        ],
        0,
    )
