"""Internal QA must not overwrite the user's current playable draft."""

import io
import json
from unittest.mock import AsyncMock

from PIL import Image

from video_use_mcp.pilot.tests.test_cards import PID, rpc

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]


def test_frame_inspection_returns_image_without_publishing_or_changing_progress(pilot):
    _, app = pilot
    previous = {
        "stage": "draft",
        "updates": [
            {
                "stage": "draft",
                "note": "Solar motion draft",
                "at": "2026-10-01T03:56:47Z",
                "preview": {"object_id": "draft", "media_type": "video/mp4"},
            }
        ],
    }
    app.state.store.put("progress", PID, previous)
    image = io.BytesIO()
    Image.new("RGB", (2, 2)).save(image, format="PNG")
    app.state.manager.image = AsyncMock(return_value=image.getvalue())
    app.state.manager.publish_preview = AsyncMock()

    result = rpc(
        pilot,
        "tools/call",
        {
            "name": "view_video_frame",
            "arguments": {"project_id": PID, "path": "edit/verify/contact-sheet.png"},
        },
    )

    assert not result.get("isError"), result
    assert any(block["type"] == "image" for block in result["content"])
    assert result["structuredContent"] == json.loads(result["content"][0]["text"])
    assert result["structuredContent"]["purpose"] == "inspection"
    assert "media" not in result["structuredContent"]
    assert "project_card" not in result["structuredContent"]
    assert app.state.store.get("progress", PID) == previous
    app.state.manager.image.assert_awaited_once_with(
        "tester", PID, "edit/verify/contact-sheet.png"
    )
    app.state.manager.publish_preview.assert_not_awaited()
