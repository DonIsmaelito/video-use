"""Transfers have hard deadlines and keep durable receipts after worker failure."""

import asyncio
import hashlib
import http.client
import socket
import threading
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from video_use_mcp.pilot import sources
from video_use_mcp.pilot.tests.test_cards import PID, rpc

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]


@pytest.mark.parametrize(
    "stage", ["headers", "body", "closing_body", "closing_without_length"]
)
def test_hard_deadline_interrupts_headers_and_body(tmp_path, monkeypatch, stage):
    """A close response detaches Connection.sock while the response is still read."""
    reader, writer = socket.socketpair()
    reader.settimeout(0.5)  # Avoid hanging the test if the hard deadline regresses.
    connection = http.client.HTTPConnection("public.example", timeout=0.5)
    connection.sock = reader
    if stage != "headers":
        extra = b"Connection: close\r\n" if stage.startswith("closing_") else b""
        length = (
            b"" if stage == "closing_without_length" else b"Content-Length: 100000\r\n"
        )
        writer.sendall(
            b"HTTP/1.1 200 OK\r\nContent-Type: video/mp4\r\n"
            + length
            + extra
            + b"\r\npart"
        )
    monkeypatch.setattr(
        sources, "public_target", lambda url: ("public.example", "1.1.1.1", "/file")
    )
    monkeypatch.setattr(sources, "PinnedHTTPS", lambda *args: connection)
    real_timer = threading.Timer
    timers = []

    def accelerated_deadline(interval, callback):
        assert 0 < interval <= 120
        timer = real_timer(0.035, callback)
        timers.append(timer)
        return timer

    monkeypatch.setattr(sources.threading, "Timer", accelerated_deadline)
    started = time.monotonic()
    try:
        with pytest.raises(ValueError):
            sources.fetch_source("https://public.example/file", tmp_path / "asset")
        assert time.monotonic() - started < 0.3
        assert len(timers) == 1
    finally:
        writer.close()
        reader.close()
        connection.close()
        for timer in timers:
            timer.cancel()
            timer.join(timeout=1)


def test_worker_sync_failure_keeps_durable_source_receipt(tmp_path):
    local = tmp_path / "image.png"
    local.write_bytes(b"source")
    store = Mock()
    store.sql.return_value = []
    sandbox = SimpleNamespace(
        upload=AsyncMock(side_effect=RuntimeError("worker unavailable"))
    )
    session = {"sandbox": sandbox}
    manager = SimpleNamespace(
        sessions={"project": session},
        save_object=AsyncMock(
            return_value={"id": "saved", "name": local.name, "size": 6}
        ),
    )
    result = asyncio.run(
        sources.save_source(store, manager, "user", "project", local.name, local)
    )
    assert result == dict(
        id="saved",
        name="image.png",
        size=6,
        path="sources/image.png",
        sync="on_next_render",
    )
    assert session["sources_dirty"] is True
    manager.save_object.assert_awaited_once_with(
        "user", "project", "source", "image.png", local
    )
    assert "worker unavailable" not in str(result)


def test_picker_quota_is_charged_even_when_workspace_sync_fails(pilot):
    client, app = pilot
    lock = asyncio.Lock()
    session = {
        "sandbox": SimpleNamespace(
            upload=AsyncMock(side_effect=RuntimeError("worker unavailable"))
        )
    }
    app.state.manager.lock = lambda pid: lock
    app.state.manager.sessions = {PID: session}
    app.state.manager.save_object = AsyncMock(
        return_value={"id": "saved", "name": "brief.txt", "size": 5}
    )
    response = rpc(
        pilot,
        "tools/call",
        dict(name="request_video_sources", arguments=dict(project_id=PID)),
    )
    token = response["_meta"]["source_upload_token"]
    result = client.post(
        response["_meta"]["source_upload_url"],
        headers={"X-Upload-Token": token, "X-Filename": "brief.txt"},
        content=b"hello",
    )
    assert result.status_code == 200, result.text
    assert result.json()["source"]["id"] == "saved"
    assert result.json()["source"]["sync"] == "on_next_render"
    state = app.state.store.get(
        "source_upload", hashlib.sha256(token.encode()).hexdigest()
    )
    assert state["remaining"] == sources.MAX_SOURCE_BYTES - 5
    assert session["sources_dirty"] is True


@pytest.mark.parametrize("transient_failure", [False, True])
def test_refreshing_sources_preserves_healthy_worker_and_render_cache(
    tmp_path, transient_failure
):
    from video_use_mcp.pilot.runtime import Manager

    workspace = tmp_path / "worker"
    (workspace / "edit").mkdir(parents=True)
    cached_render = workspace / "edit" / "expensive-scene.mp4"
    cached_render.write_bytes(b"existing rendered video")
    objects = [
        dict(id="first", key="private/first", name="first.txt"),
        dict(id="second", key="private/second", name="second.txt"),
    ]
    expected = {"private/first": b"source one", "private/second": b"source two"}
    store = Mock()
    store.project.return_value = {"checkpoint": "last-checkpoint"}
    store.sql.return_value = objects
    store.download.side_effect = lambda key, local: local.write_bytes(expected[key])
    pending_failure = transient_failure

    async def upload(destination, local):
        nonlocal pending_failure
        if pending_failure and destination.endswith("second.txt"):
            pending_failure = False
            raise RuntimeError("transient source copy failure")
        path = workspace / destination
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(local.read_bytes())

    sandbox = SimpleNamespace(
        instance=SimpleNamespace(
            poll=SimpleNamespace(aio=AsyncMock(return_value=None))
        ),
        upload=AsyncMock(side_effect=upload),
        close=AsyncMock(),
    )
    session = dict(sandbox=sandbox, owner="owner", sources_dirty=True, touched=0)
    manager = Manager(store, SimpleNamespace())
    manager.sessions["project"] = session
    manager.stop = AsyncMock(
        side_effect=AssertionError("Healthy cached worker must stay alive")
    )

    async def scenario():
        if transient_failure:
            with pytest.raises(RuntimeError, match="transient source copy"):
                await manager.session("owner", "project")
            assert session["sources_dirty"] is True
            assert cached_render.read_bytes() == b"existing rendered video"
        refreshed = await manager.session("owner", "project")
        assert refreshed is sandbox
        assert manager.sessions["project"] is session
        assert session["sources_dirty"] is False
        assert session["touched"] > 0
        assert cached_render.read_bytes() == b"existing rendered video"
        assert (workspace / "sources" / "first.txt").read_bytes() == expected[
            "private/first"
        ]
        assert (workspace / "sources" / "second.txt").read_bytes() == expected[
            "private/second"
        ]
        downloads = store.download.call_count
        assert await manager.session("owner", "project") is sandbox
        assert store.download.call_count == downloads
        manager.stop.assert_not_awaited()
        sandbox.close.assert_not_awaited()

    asyncio.run(scenario())
