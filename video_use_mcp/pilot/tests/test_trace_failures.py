"""Pre-job failures remain diagnosable without retaining source or credentials."""

import json
import logging
from unittest.mock import Mock

import pytest
from mcp.types import CallToolResult, TextContent

from video_use_mcp.pilot.tests.test_cards import rpc
from video_use_mcp.pilot.tests.test_preview_delivery import TID
from video_use_mcp.pilot.interaction import question_delivery

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]


def traces(app):
    with app.state.store.db() as db:
        rows = db.execute("SELECT key FROM kv WHERE kind='trace'").fetchall()
    return [app.state.store.get("trace", row["key"]) for row in rows]


def test_question_trace_does_not_claim_native_ui_or_capture_answers(pilot):
    _, app = pilot
    result = rpc(
        pilot,
        "tools/call",
        {
            "name": "start_video",
            "arguments": {
                "title": "Private project title",
                "brief": "Private creative brief",
                "category": "custom",
            },
        },
    )
    assert not result.get("isError")
    delivery = traces(app)[-1]["question_delivery"]
    assert delivery == {
        "question_id": result["structuredContent"]["question"]["id"],
        "status": "awaiting_user",
        "mechanism": "host_instruction",
        "server_form_requested": False,
        "host_presentation": "unobserved",
    }
    assert "Private" not in json.dumps(traces(app)[-1])


def test_question_trace_ignores_unrecognized_delivery_and_private_content():
    question = {
        "id": TID,
        "presentation": "native_question_tool_if_available_else_short_chat",
        "status": "answered",
        "recorded_answers": {"sensitive": "private answer"},
        "questions": [{"prompt": "private question"}],
    }
    delivery = question_delivery({"intake": {"question": question}})
    assert delivery["status"] == "answered"
    assert "private" not in json.dumps(delivery)
    assert (
        question_delivery({"question": question | {"presentation": "new_protocol"}})
        is None
    )
    assert question_delivery({"question": None, "intake": []}) is None


def test_omitted_arguments_and_known_guide_topic_are_traced(pilot, monkeypatch):
    _, app = pilot
    monkeypatch.setenv("PILOT_HARNESS_VERSION", "test-version")
    result = rpc(pilot, "tools/call", {"name": "video_use_guidance"})
    assert not result.get("isError")
    trace = traces(app)[-1]
    assert trace["topic"] == "overview"
    assert trace["started_at"] <= trace["at"]
    assert trace["harness_version"] == "test-version"
    assert trace["project"] is None
    assert "arguments" not in trace and "result" not in trace


def test_missing_task_error_is_not_lost_during_project_lookup(pilot):
    _, app = pilot
    app.state.store.task = Mock(side_effect=PermissionError("Task not found"))
    result = rpc(
        pilot,
        "tools/call",
        {
            "name": "get_video_task",
            "arguments": {"task_id": TID},
        },
    )
    assert result["isError"]
    trace = traces(app)[-1]
    assert trace["task"] == TID and trace["project"] is None
    assert "Task not found" in trace["error"]
    assert trace["outcome"] != "ok"


def test_returned_error_result_retains_redacted_detail(pilot):
    _, app = pilot
    app.state.mcp.trace_config.api_key = "private-service-key"

    @app.state.mcp.tool()
    def returned_error() -> CallToolResult:
        return CallToolResult(
            isError=True,
            content=[
                TextContent(
                    type="text",
                    text="invalid scene private-service-key https://private.test/?ticket=secret",
                )
            ],
        )

    result = rpc(pilot, "tools/call", {"name": "returned_error", "arguments": {}})
    assert result["isError"]
    trace = traces(app)[-1]
    assert trace["outcome"] == "error"
    assert "invalid scene" in trace["error"]
    assert "private-service-key" not in trace["error"]
    assert "ticket=" not in trace["error"]


def test_trace_storage_failure_does_not_change_tool_response(pilot, caplog):
    _, app = pilot
    put = app.state.store.put

    def failing_trace(kind, *args, **kwargs):
        if kind == "trace":
            raise RuntimeError("private provider detail must not enter logs")
        return put(kind, *args, **kwargs)

    app.state.store.put = failing_trace
    with caplog.at_level(logging.INFO, logger="video_use_mcp.pilot.interaction"):
        result = rpc(
            pilot,
            "tools/call",
            {"name": "video_use_guidance", "arguments": {"topic": "scenes"}},
        )
    assert not result.get("isError")
    entries = [r.message for r in caplog.records if r.message.startswith("video_use_")]
    event = next(e for e in entries if e.startswith("video_use_tool "))
    assert json.loads(event.split(" ", 1)[1])["topic"] == "scenes"
    assert "video_use_trace_persist_failed RuntimeError" in entries
    assert "private provider detail" not in " ".join(entries)


def test_missing_required_scene_arguments_record_validation_error(pilot):
    _, app = pilot
    result = rpc(pilot, "tools/call", {"name": "render_video_scene", "arguments": {}})
    assert result["isError"]
    trace = traces(app)[-1]
    assert trace["tool"] == "render_video_scene" and trace["project"] is None
    assert trace["outcome"] != "ok" and trace["error"]


@pytest.mark.parametrize("topic", [[], {}])
def test_malformed_guidance_arguments_do_not_break_error_tracing(pilot, topic):
    _, app = pilot
    result = rpc(
        pilot,
        "tools/call",
        {
            "name": "video_use_guidance",
            "arguments": {"topic": topic},
        },
    )
    assert result["isError"]
    trace = traces(app)[-1]
    assert trace["tool"] == "video_use_guidance"
    assert trace["outcome"] != "ok" and trace["error"]
    assert "topic" not in trace
