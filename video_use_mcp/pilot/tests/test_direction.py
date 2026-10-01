import asyncio
import base64
import io
import json
from unittest.mock import AsyncMock

from PIL import Image
from video_use_mcp.pilot.tests.test_cards import rpc

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]


def proposal(pilot, **extra):
    return rpc(
        pilot,
        "tools/call",
        {
            "name": "propose_video",
            "arguments": {
                "title": "Headphones",
                "brief": "A short headphones explainer",
                "question": "Would you like this dark technical look or a warmer illustration?",
                "frame": {
                    "background": "#111827",
                    "marks": [
                        {
                            "kind": "wave",
                            "x": 100,
                            "y": 270,
                            "w": 400,
                            "h": 60,
                            "color": "#f59478",
                        },
                        {
                            "kind": "text",
                            "x": 80,
                            "y": 50,
                            "text": "A quieter world",
                            "size": 45,
                        },
                    ],
                },
                **extra,
            },
        },
    )


def test_legacy_proposal_is_optional_artwork_not_a_gate(
    pilot,
):
    _, app = pilot
    app.state.manager.save_object = AsyncMock(return_value={"id": "frame-id"})
    result = proposal(pilot)
    assert not result.get("isError"), result
    image = next(c for c in result["content"] if c["type"] == "image")
    assert Image.open(io.BytesIO(base64.b64decode(image["data"]))).size == (960, 540)
    data = json.loads(result["content"][0]["text"])
    pid = data["project_id"]
    assert data["status"] == "proposed" and "END YOUR TURN" not in data["next_action"]
    displayed = result["structuredContent"]
    assert displayed["project_id"] == pid
    assert displayed["media"]["object_id"] == "frame-id"
    assert displayed["media"]["media_type"] == "image/png"
    assert "creative" in displayed
    assert "chat sentence" in displayed["next_action"]
    assert "do not require a reply" in displayed["next_action"]
    assert not {"workspace_url", "project_card", "tasks", "updates"} & displayed.keys()
    store = app.state.store
    approved = rpc(
        pilot,
        "tools/call",
        {
            "name": "accept_video_direction",
            "arguments": {"project_id": pid, "user_feedback": "Yes use this look"},
        },
    )
    assert not approved.get("isError")
    assert store.get("direction", pid)["status"] == "approved"
    app.state.manager.lock = lambda pid: asyncio.Lock()
    revised = proposal(pilot, project_id=pid)
    assert not revised.get("isError")
    assert store.get("direction", pid)["status"] == "proposed"


def test_preview_requires_actual_media_instead_of_empty_card(pilot):
    result = rpc(
        pilot,
        "tools/call",
        {
            "name": "show_video_preview",
            "arguments": {"project_id": "1691c5fc-be06-4465-9ade-b8d29d9517ba"},
        },
    )
    assert result["isError"]
    assert "No visual exists yet" in result["content"][0]["text"]


def test_readonly_account_cannot_approve_or_generate_proposals(pilot):
    tools = rpc(pilot, "tools/list", {})["tools"]
    for name in ("start_video", "plan_video", "run_video_step"):
        tool = next(t for t in tools if t["name"] == name)
        assert not tool["annotations"]["readOnlyHint"]
        assert not tool["annotations"]["openWorldHint"]
