"""Public MCP recovery contract; no worker, provider or allowance use."""

from unittest.mock import Mock

import pytest

from video_use_mcp.pilot.tests.test_cards import PID, rpc

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]


def test_transcription_schema_exposes_explicit_recovery(pilot):
    tool = next(t for t in rpc(pilot,"tools/list",{})["tools"] if t["name"]=="transcribe_video")
    option = tool["inputSchema"]["properties"]["cache_mode"]
    assert option["enum"]==["reuse","new_clock"] and option["default"]=="reuse"
    assert "original cache stays unchanged" in tool["description"]


@pytest.mark.parametrize("mode",[None,"reuse","new_clock","overwrite"])
def test_recovery_mode_plumbing_and_default_idempotency_payload(pilot,mode):
    _,app=pilot
    task={"id":"t","project":PID,"operation":"transcribe","status":"succeeded",
          "result":{"path":"edit/transcripts/fixture.json","cached":True},
          "error":None,"created":"","updated":""}
    app.state.manager.running={}
    app.state.manager.submit=Mock(return_value=task)
    app.state.store.task=Mock(return_value=task)
    arguments={"project_id":PID,"path":"sources/clip.mp4","request_id":"speech-1"}
    if mode is not None:
        arguments["cache_mode"]=mode
    result=rpc(pilot,"tools/call",{"name":"transcribe_video","arguments":arguments})
    if mode=="overwrite":
        assert result.get("isError")
        app.state.manager.submit.assert_not_called()
    else:
        assert not result.get("isError"),result
        expected={"path":"sources/clip.mp4","timeout":300}
        if mode=="new_clock":
            expected["cache_mode"]=mode
        app.state.manager.submit.assert_called_once_with("tester",PID,"transcribe",expected,"speech-1")
