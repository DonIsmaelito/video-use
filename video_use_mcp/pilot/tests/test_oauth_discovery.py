"""Exercise the scopes a real MCP client discovers instead of supplying them by hand."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from video_use_mcp.pilot.server import create_app
from video_use_mcp.store import Store
from video_use_mcp.tests.test_service import connect_oauth, exchange, mcp_call


@pytest.fixture
def pilot(tmp_path):
    store = Store(tmp_path)
    # OAuth persistence/transport are real. Project storage and browser identity
    # are local fixtures; this test needs neither cloud credentials nor email.
    store.identity = Mock(return_value={"id": "tester"})
    store.member = Mock(return_value={"id": "tester", "active": True})
    store.project = Mock(return_value={"title": "Created over discovered scopes"})
    store.sql = Mock(return_value=[])
    config = SimpleNamespace(
        public_url="http://localhost:8787",
        studio_url="http://localhost:5173",
        invite_code="test-invitation",
    )
    app = create_app(
        config, store, SimpleNamespace(start=AsyncMock(), close=AsyncMock())
    )
    with TestClient(app, base_url=config.public_url) as client:
        client.headers["Authorization"] = "Bearer browser-fixture"
        yield client, app


def test_discovered_scopes_allow_project_creation(pilot):
    client, app = pilot
    challenge = mcp_call(client, "invalid-token", "tools/list")
    assert challenge.status_code == 401
    assert 'scope="video:read video:write"' in challenge.headers["www-authenticate"]
    resource = client.get("/.well-known/oauth-protected-resource/mcp").json()
    scopes = " ".join(resource["scopes_supported"])
    cid, verifier, code = connect_oauth(client, app, scopes=scopes)
    response = exchange(client, cid, verifier, code)
    assert response.status_code == 200
    grant = response.json()
    assert set(grant["scope"].split()) == {"video:read", "video:write"}
    created = mcp_call(
        client,
        grant["access_token"],
        "tools/call",
        {
            "name": "create_video_project",
            "arguments": {"title": "Created over discovered scopes"},
        },
    )
    assert created.status_code == 200
    assert not created.json()["result"].get("isError"), created.text
    assert any(
        "INSERT INTO public.vp_projects" in call.args[0]
        for call in app.state.store.sql.call_args_list
    )


def test_old_read_only_grants_receive_scope_challenge(pilot):
    client, app = pilot
    grant = app.state.auth.issue("tester", "old-client", ["video:read"])
    response = mcp_call(client, grant.access_token, "tools/list")
    assert response.status_code == 403
    assert response.json()["error"] == "insufficient_scope"
    assert 'scope="video:read video:write"' in response.headers["www-authenticate"]
    assert "resource_metadata=" in response.headers["www-authenticate"]
