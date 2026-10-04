"""Initialization diagnostics preserve auth, stream semantics and privacy."""

import asyncio
import hashlib
import json
import threading
from unittest.mock import Mock

import pytest
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.auth.provider import AccessToken

from video_use_mcp.pilot.host_capabilities import (
    InitializeCapabilityTelemetry,
    MAX_INITIALIZE_BYTES,
    initialize_capabilities,
)
from video_use_mcp.tests.test_service import mcp_call
from video_use_mcp.store import digest

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]


def parameters(capabilities=None):
    return {
        "protocolVersion": "2025-11-25",
        "capabilities": capabilities if capabilities is not None else {},
        "clientInfo": {"name": "PRIVATE NAME", "version": "PRIVATE VERSION"},
    }


def traces(app):
    with app.state.store.db() as db:
        rows = db.execute("SELECT key FROM kv WHERE kind='trace'").fetchall()
    return [app.state.store.get("trace", row["key"]) for row in rows]


def test_authenticated_initialize_records_only_known_flags(pilot):
    client, app = pilot
    grant = app.state.auth.issue(
        "tester", "private-client", ["video:read", "video:write"]
    )
    params = parameters(
        {
            "elicitation": {"form": {}, "url": {}},
            "extensions": {
                "openai/elicitation": {"form": {}, "private": "PRIVATE EXTENSION"},
                "private/extension": {"secret": "PRIVATE SECRET"},
            },
        }
    )
    response = mcp_call(client, grant.access_token, "initialize", params)
    assert response.status_code == 200
    assert "serverInfo" in response.json()["result"]
    records = traces(app)
    assert len(records) == 1
    record = records[0]
    assert record["tool"] == "initialize" and record["owner"] == "tester"
    assert record["client"] == hashlib.sha256(b"private-client").hexdigest()[:12]
    assert record["project"] is None and record["task"] is None
    assert record["protocol_version"] == "2025-11-25"
    assert record["advertised_capabilities"] == {
        "elicitation_present": True,
        "elicitation_modes_unspecified": False,
        "elicitation_form": True,
        "elicitation_url": True,
        "openai_elicitation_form": True,
    }
    assert record["host_presentation"] == "unobserved"
    serialized = json.dumps(record)
    for excluded in (
        "PRIVATE",
        "private-client",
        grant.access_token,
        "clientInfo",
        "arguments",
        "result",
    ):
        assert excluded not in serialized


@pytest.mark.parametrize("scopes,status", [(None, 401), (["video:read"], 403)])
def test_unauthorized_initialize_has_no_telemetry(pilot, scopes, status):
    client, app = pilot
    token = (
        app.state.auth.issue("tester", "client", scopes).access_token
        if scopes
        else "invalid"
    )
    response = mcp_call(client, token, "initialize", parameters())
    assert response.status_code == status
    assert not traces(app)


def test_oversized_initialize_still_reaches_mcp_but_is_not_recorded(pilot):
    client, app = pilot
    token = app.state.auth.issue(
        "tester", "client", ["video:read", "video:write"]
    ).access_token
    params = parameters()
    params["clientInfo"]["name"] = "x" * (MAX_INITIALIZE_BYTES + 1)
    response = mcp_call(client, token, "initialize", params)
    assert response.status_code == 200
    assert "serverInfo" in response.json()["result"]
    assert not traces(app)


def test_wrong_resource_token_keeps_sdk_auth_failure_and_no_trace(pilot):
    client, app = pilot
    token = app.state.auth.issue(
        "tester", "client", ["video:read", "video:write"]
    ).access_token
    access = app.state.store.get("access", digest(token))
    access["resource"] = "https://wrong.example/mcp"
    app.state.store.put("access", digest(token), access)
    response = mcp_call(client, token, "initialize", parameters())
    assert response.status_code == 401
    assert not traces(app)


def test_other_mcp_method_does_not_create_initialize_trace(pilot):
    client, app = pilot
    token = app.state.auth.issue(
        "tester", "client", ["video:read", "video:write"]
    ).access_token
    response = mcp_call(client, token, "tools/list", {})
    assert response.status_code == 200
    assert not traces(app)


def test_trace_store_failure_does_not_change_initialize_response(pilot, monkeypatch):
    client, app = pilot
    token = app.state.auth.issue(
        "tester", "client", ["video:read", "video:write"]
    ).access_token
    original = app.state.store.put

    def failing_put(kind, *args, **kwargs):
        if kind == "trace":
            raise RuntimeError("private store failure")
        return original(kind, *args, **kwargs)

    monkeypatch.setattr(app.state.store, "put", failing_put)
    response = mcp_call(client, token, "initialize", parameters())
    assert response.status_code == 200
    assert "serverInfo" in response.json()["result"]
    assert "private store failure" not in response.text


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b"[]",
        b"null",
        b'{"method":"tools/call"}',
        b'{"method":"initialize","params":null}',
    ],
)
def test_other_or_invalid_messages_are_not_diagnostics(body):
    assert initialize_capabilities(body) is None


def test_absent_or_malformed_flags_do_not_claim_capability():
    params = parameters(
        {
            "elicitation": {"form": True, "url": "PRIVATE"},
            "experimental": {"openai/elicitation": {"form": False}},
            "extensions": {"openai/elicitation": {"form": None}},
        }
    )
    record = initialize_capabilities(
        json.dumps({"method": "initialize", "params": params})
    )
    flags = record["advertised_capabilities"]
    assert flags["elicitation_present"] is True
    assert not any(
        value for key, value in flags.items() if key != "elicitation_present"
    )
    params["protocolVersion"] = "PRIVATE VALUE"
    assert (
        initialize_capabilities(json.dumps({"method": "initialize", "params": params}))
        is None
    )


def test_legacy_mode_unspecified_and_openai_experimental_are_preserved():
    params = parameters(
        {
            "elicitation": {},
            "experimental": {"openai/elicitation": {"form": {}}},
        }
    )
    params["protocolVersion"] = "2025-06-18"
    record = initialize_capabilities(
        json.dumps({"method": "initialize", "params": params})
    )
    flags = record["advertised_capabilities"]
    assert flags["elicitation_present"] is True
    assert flags["elicitation_modes_unspecified"] is True
    assert flags["elicitation_form"] is False  # No explicit form-mode key.
    assert flags["openai_elicitation_form"] is True
    assert record["host_presentation"] == "unobserved"


def test_chunked_body_and_response_are_passed_through_unchanged():
    async def scenario():
        body = json.dumps({"method": "initialize", "params": parameters()}).encode()
        incoming = [
            {"type": "http.request", "body": body[:29], "more_body": True},
            {"type": "http.request", "body": body[29:], "more_body": False},
        ]
        expected_response = [
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"x-test", b"same")],
            },
            {"type": "http.response.body", "body": b"unchanged", "more_body": False},
        ]
        consumed, outgoing = [], []

        async def receive():
            value = incoming[len(consumed)]
            consumed.append(value)
            return value

        async def send(message):
            outgoing.append(message)

        async def app(scope, receive, send):
            scope["user"] = AuthenticatedUser(
                AccessToken(token="secret", client_id="cid", subject="uid", scopes=[])
            )
            for expected in incoming:
                assert await receive() is expected
            for message in expected_response:
                await send(message)

        store = Mock()
        await InitializeCapabilityTelemetry(app, store)(
            {"type": "http", "method": "POST", "path": "/mcp"}, receive, send
        )
        assert outgoing == expected_response
        store.put.assert_called_once()

    asyncio.run(scenario())


def test_slow_trace_store_does_not_hold_the_completed_response(monkeypatch):
    monkeypatch.setattr(
        "video_use_mcp.pilot.host_capabilities.TRACE_TIMEOUT_SECONDS", 0.01
    )
    released = threading.Event()

    async def scenario():
        sent = []

        async def receive():
            return {
                "type": "http.request",
                "body": json.dumps(
                    {"method": "initialize", "params": parameters()}
                ).encode(),
            }

        async def send(message):
            sent.append(message)

        async def app(scope, receive, send):
            scope["user"] = AuthenticatedUser(
                AccessToken(token="secret", client_id="cid", subject="uid", scopes=[])
            )
            await receive()
            await send({"type": "http.response.start", "status": 200})
            await send({"type": "http.response.body", "body": b"done"})

        store = Mock()
        store.put.side_effect = lambda *args, **kwargs: released.wait(1)
        try:
            await asyncio.wait_for(
                InitializeCapabilityTelemetry(app, store)(
                    {"type": "http", "method": "POST", "path": "/mcp"}, receive, send
                ),
                timeout=0.2,
            )
            assert sent[-1]["body"] == b"done"
        finally:
            released.set()

    asyncio.run(scenario())
