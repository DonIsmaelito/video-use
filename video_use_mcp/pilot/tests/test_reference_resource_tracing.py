"""Reference resource reads expose cache evidence without changing host resources."""

import asyncio
import hashlib
import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.server.lowlevel.helper_types import ReadResourceContents

from video_use_mcp.pilot import interaction
from video_use_mcp.pilot.reference_playback import CARD, REFERENCE_UI_URI
from video_use_mcp.pilot.tests.test_cards import rpc
from video_use_mcp.pilot.tests.test_trace_failures import traces

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]


def test_protocol_keeps_reference_html_and_csp_while_identifying_cached_uri(pilot, monkeypatch):
    _, app = pilot
    monkeypatch.setenv("PILOT_HARNESS_VERSION", "resource-test-build")
    resources = rpc(pilot, "resources/list", {})["resources"]
    discovered = next(item for item in resources if item["uri"] == REFERENCE_UI_URI)
    stale_uri = "ui://video-use/reference-0000000000000000.html"
    result = rpc(pilot, "resources/read", {"uri": stale_uri})
    content = result["contents"][0]
    assert content["uri"] == stale_uri
    assert content["text"] == CARD.read_text()
    assert content["_meta"] == discovered["_meta"]
    assert content["mimeType"] == discovered["mimeType"]
    record = traces(app)[-1]
    assert record["tool"] == "resources/read" and record["surface"] == "card"
    assert record["requested_uri"] == stale_uri
    assert record["current_resource_uri"] == REFERENCE_UI_URI
    assert record["current_resource_digest"] in REFERENCE_UI_URI
    assert len(record["current_resource_digest"]) == 16
    assert record["harness_version"] == "resource-test-build"
    assert record["project"] is None and record["task"] is None
    assert record["owner"] == "tester"
    assert record["client"] == hashlib.sha256(b"card-test").hexdigest()[:12]
    assert record["started_at"] <= record["at"] and record["elapsed_ms"] >= 0
    assert record["outcome"] == "ok"
    assert not {"result", "content", "body", "token", "error"}.intersection(record)


@pytest.fixture
def reader(monkeypatch):
    server = interaction.TracedMCP("resource-trace-test")
    server.trace_store = SimpleNamespace(put=Mock())
    token = SimpleNamespace(subject="owner", client_id="private-client-id", token="private-token")
    monkeypatch.setattr(interaction, "get_access_token", Mock(return_value=token))
    original = [ReadResourceContents(content="private HTML body and signed URL", mime_type="text/html",
                                     meta={"ui": {"csp": {"frameDomains": ["https://player.example"]}}})]
    underlying = AsyncMock(return_value=original)
    monkeypatch.setattr(FastMCP, "read_resource", underlying)
    return server, underlying, original


def test_resource_result_identity_and_metadata_are_untouched_and_body_never_logged(reader, caplog):
    server, underlying, original = reader
    with caplog.at_level(logging.INFO, logger=interaction.__name__):
        result = asyncio.run(server.read_resource(REFERENCE_UI_URI))
    assert result is original
    underlying.assert_awaited_once_with(REFERENCE_UI_URI)
    call = server.trace_store.put.call_args
    assert call.args[0] == "trace" and call.kwargs == {"ttl": 2592000}
    serialized = json.dumps(call.args[2]) + caplog.text
    for private in ("private HTML", "signed URL", "private-client-id", "private-token", "player.example"):
        assert private not in serialized
    assert "video_use_resource" in caplog.text


@pytest.mark.parametrize("uri", [
    "ui://video-use/reference-0000000000000000.html?token=private",
    "ui://video-use/reference-0000000000000000.html#private",
    "ui://video-use/reference-not-a-digest.html",
    "ui://video-use/media-0000000000000000.html",
    "https://private.example/resource?secret=private",
])
def test_non_reference_or_arbitrary_resource_uris_are_never_traced(reader, uri, caplog):
    server, underlying, original = reader
    with caplog.at_level(logging.INFO, logger=interaction.__name__):
        assert asyncio.run(server.read_resource(uri)) is original
    underlying.assert_awaited_once_with(uri)
    server.trace_store.put.assert_not_called()
    assert "video_use_resource" not in caplog.text


@pytest.mark.parametrize("access", [None, SimpleNamespace(subject="", client_id="client"), RuntimeError("no auth context")])
def test_missing_authentication_does_not_break_or_log_resource_reads(reader, monkeypatch, access):
    server, _, original = reader
    token = Mock(side_effect=access) if isinstance(access, Exception) else Mock(return_value=access)
    monkeypatch.setattr(interaction, "get_access_token", token)
    assert asyncio.run(server.read_resource(REFERENCE_UI_URI)) is original
    server.trace_store.put.assert_not_called()


def test_underlying_resource_error_is_preserved_without_error_content(reader, caplog):
    server, underlying, _ = reader
    failure = ValueError("private resource body https://private.example/?token=secret")
    underlying.side_effect = failure
    with caplog.at_level(logging.INFO, logger=interaction.__name__), pytest.raises(ValueError) as caught:
        asyncio.run(server.read_resource(REFERENCE_UI_URI))
    assert caught.value is failure
    record = server.trace_store.put.call_args.args[2]
    assert record["outcome"] == "ValueError"
    assert "private resource body" not in json.dumps(record) + caplog.text
    assert "token=secret" not in json.dumps(record) + caplog.text


def test_trace_persistence_failure_keeps_result_and_logs_only_failure_type(reader, caplog):
    server, _, original = reader
    server.trace_store.put.side_effect = RuntimeError("private database detail")
    with caplog.at_level(logging.INFO, logger=interaction.__name__):
        assert asyncio.run(server.read_resource(REFERENCE_UI_URI)) is original
    assert "video_use_resource" in caplog.text
    assert "video_use_trace_persist_failed RuntimeError" in caplog.text
    assert "private database detail" not in caplog.text


def test_failed_console_logging_cannot_change_resource_or_prevent_persistence(reader, monkeypatch):
    server, _, original = reader
    logger = logging.getLogger(interaction.__name__)
    monkeypatch.setattr(logger, "info", Mock(side_effect=RuntimeError("logging unavailable")))
    assert asyncio.run(server.read_resource(REFERENCE_UI_URI)) is original
    server.trace_store.put.assert_called_once()
    server.trace_store.put.side_effect = RuntimeError("private database detail")
    monkeypatch.setattr(logger, "warning", Mock(side_effect=RuntimeError("logging still unavailable")))
    assert asyncio.run(server.read_resource(REFERENCE_UI_URI)) is original
