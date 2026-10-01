"""A targeted trace must retain unassigned evidence without guessing host state."""

from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from video_use_mcp.pilot.trace_report import collect, write_report


PID = "e84d7555-1a82-413d-a455-9269225440ac"
CREATED = "2026-10-01T06:57:42Z"


def call(
    tool, at, *, project=None, owner="owner", client="chat-a", outcome="ok", error=None
):
    result = {
        "tool": tool,
        "at": at,
        "project": project,
        "owner": owner,
        "client": client,
        "outcome": outcome,
        "task": None,
    }
    if error:
        result["error"] = error
    return result


def store_fixture(traces, tasks=None, owner="owner"):
    project = {
        "id": PID,
        "title": "Solar | explainer",
        "created": CREATED,
        "owner": owner,
    }
    tasks = (
        tasks
        if tasks is not None
        else [
            {
                "id": "narration-task",
                "operation": "narrate",
                "status": "succeeded",
                "created": "2026-10-01T06:58:37Z",
                "updated": "2026-10-01T06:58:49Z",
                "error": None,
                "result": {"duration": 31.76},
            }
        ]
    )

    def sql(query, *args):
        if "FROM public.vp_projects" in query:
            return [deepcopy(project)]
        if "FROM public.vp_kv" in query:
            return [{"value": json.dumps(trace)} for trace in traces]
        if "FROM public.vp_tasks" in query:
            return deepcopy(tasks)
        return []

    store = Mock()
    store.sql.side_effect = sql
    store.get.return_value = None
    store.vault.decrypt.side_effect = lambda value: value.decode()
    store.config = SimpleNamespace(
        api_key="private-admin-key", speech_key="", encryption_key="", invite_code=""
    )
    return store


def test_targeted_report_retains_only_owner_client_context_after_creation():
    guidance = call("video_use_guidance", "2026-09-30T23:58:54-07:00")
    missing_project_error = call(
        "render_video_scene",
        "2026-10-01T06:59:00Z",
        outcome="ToolError",
        error="project_id is required",
    )
    traces = [
        call("narrate_video", "2026-10-01T06:58:50Z", project=PID),
        guidance,
        missing_project_error,
        call("before", "2026-10-01T06:57:41Z"),
        call("another_owner", "2026-10-01T07:00:00Z", owner="other"),
        call("another_client", "2026-10-01T07:00:00Z", client="chat-b"),
        call("assigned_elsewhere", "2026-10-01T07:00:00Z", project="another-project"),
        call("invalid_time", "not-a-timestamp"),
    ]
    report = collect(store_fixture(traces), PID)
    assert report["unassigned_tool_calls"] == [guidance, missing_project_error]
    project = report["projects"][0]
    assert project["tool_counts"] == {"narrate_video": 1}
    assert (
        project["backend_activity"]["last_project_activity"]["tool"] == "narrate_video"
    )
    assert (
        project["backend_activity"]["last_unassigned_context_call"]
        == missing_project_error
    )
    assert "not assigned" in report["unassigned_tool_call_scope"]


def test_no_observed_client_falls_back_to_owner_time_but_missing_owner_fails_closed():
    traces = [
        call("guidance", "2026-10-01T06:58:00Z"),
        call("other", "2026-10-01T06:58:00Z", owner="other"),
    ]
    assert (
        len(collect(store_fixture(traces, tasks=[]), PID)["unassigned_tool_calls"]) == 1
    )
    assert (
        collect(store_fixture(traces, owner=None), PID)["unassigned_tool_calls"] == []
    )


@pytest.mark.parametrize(
    "status,state",
    [
        ("succeeded", "no_active_tasks"),
        ("failed", "no_active_tasks"),
        ("queued", "queued_tasks"),
        ("running", "running_tasks"),
    ],
)
def test_backend_state_does_not_infer_what_the_chat_is_doing(status, state):
    tasks = [
        {
            "id": "task",
            "operation": "narrate",
            "status": status,
            "created": CREATED,
            "updated": "2026-10-01T06:58:49Z",
            "error": "A task error" if status == "failed" else None,
            "result": {},
        }
    ]
    report = collect(store_fixture([], tasks=tasks), PID)
    activity = report["projects"][0]["backend_activity"]
    assert activity["state"] == state
    assert activity["running_tasks"] == int(status == "running")
    assert activity["queued_tasks"] == int(status == "queued")
    assert activity["last_project_activity"]["at"] == "2026-10-01T06:58:49Z"
    assert "does not establish whether the chat" in activity["limitation"]


def test_markdown_surfaces_taskless_tool_errors_and_unassigned_context(tmp_path):
    traces = [
        call(
            "render_video_scene",
            "2026-10-01T06:59:00Z",
            project=PID,
            outcome="ToolError",
            error="bad scene | time\nprivate-admin-key",
        ),
        call("video_use_guidance", "2026-10-01T06:59:02Z"),
        call(
            "assemble_video",
            "2026-10-01T06:59:04Z",
            outcome="ToolError",
            error="missing project_id",
        ),
    ]
    report = collect(store_fixture(traces), PID)
    write_report(report, tmp_path)
    markdown = (tmp_path / "latest.md").read_text()
    assert "No queued or running backend tasks" in markdown
    assert "### Tool call failures" in markdown
    assert "render_video_scene | No task | ToolError" in markdown
    assert "bad scene / time [redacted]" in markdown
    assert "## Unassigned tool call context" in markdown
    assert "video_use_guidance" in markdown and "missing project_id" in markdown
    assert "private-admin-key" not in (tmp_path / "latest.json").read_text()
    assert "not assigned to this project" in markdown


def test_global_report_keeps_all_unassigned_calls_as_before():
    traces = [
        call("guidance", "2026-10-01T06:58:00Z"),
        call("other", "2026-10-01T06:58:00Z", owner="other"),
    ]
    report = collect(store_fixture(traces))
    assert report["unassigned_tool_calls"] == traces
    assert "no project association is inferred" in report["unassigned_tool_call_scope"]
