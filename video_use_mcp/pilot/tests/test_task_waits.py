"""Overlong host polls return usable state rather than wasting another call."""

from unittest.mock import AsyncMock, Mock

import pytest

from video_use_mcp.pilot.tests.test_cards import PID, rpc

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]
TID = "790d0a5a-eb6a-4115-99a2-1e63dbe03e9c"


@pytest.mark.parametrize("requested,effective", [(0, 0), (12, 12), (25, 25), (120, 25)])
def test_task_poll_caps_wait_without_rejecting_or_restarting(
    pilot, monkeypatch, requested, effective
):
    _, app = pilot
    task = dict(
        id=TID,
        project=PID,
        operation="step",
        status="running",
        result=None,
        error=None,
        created="",
        updated="",
    )
    app.state.store.task = Mock(return_value=task)
    waited = AsyncMock()
    monkeypatch.setattr("video_use_mcp.pilot.server.wait_for_task", waited)
    response = rpc(
        pilot,
        "tools/call",
        dict(
            name="get_video_task", arguments=dict(task_id=TID, wait_seconds=requested)
        ),
    )
    assert not response.get("isError"), response
    waited.assert_awaited_once_with(app.state.manager, TID, effective)
    assert response["structuredContent"]["status"] == "running"
    assert response["structuredContent"]["next_tool"] == {
        "name": "get_video_task",
        "arguments": {"task_id": TID},
    }


def test_task_poll_rejects_negative_wait_and_advertises_cap(pilot, monkeypatch):
    waited = AsyncMock()
    monkeypatch.setattr("video_use_mcp.pilot.server.wait_for_task", waited)
    response = rpc(
        pilot,
        "tools/call",
        dict(name="get_video_task", arguments=dict(task_id=TID, wait_seconds=-1)),
    )
    assert response["isError"]
    waited.assert_not_awaited()
    tool = next(
        t
        for t in rpc(pilot, "tools/list", {})["tools"]
        if t["name"] == "get_video_task"
    )
    wait = tool["inputSchema"]["properties"]["wait_seconds"]
    assert wait["minimum"] == 0 and wait["default"] == 25
    assert "capped at 25 seconds" in wait["description"]
