"""An existing player must not lose its only draft during lengthy internal work."""

from video_use_mcp.pilot.interaction import record_progress
from video_use_mcp.pilot.tests.test_cards import PID, rpc

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]


def test_long_nonvisual_work_keeps_last_playable_media(pilot):
    store = pilot[1].state.store
    record_progress(
        store,
        PID,
        "draft",
        "Working motion excerpt",
        preview={"object_id": "real-draft", "media_type": "video/mp4", "draft": True},
    )
    for i in range(25):
        record_progress(store, PID, "working", f"Internal component {i}")
    record_progress(
        store,
        PID,
        "review",
        "Internal inspection",
        preview={"object_id": "qa-sheet", "media_type": "image/png"},
    )
    state = store.get("progress", PID)
    assert len(state["updates"]) == 20
    assert all(
        item.get("preview", {}).get("object_id") != "real-draft"
        for item in state["updates"]
    )
    result = rpc(
        pilot,
        "tools/call",
        {"name": "video_preview_updates", "arguments": {"project_id": PID}},
    )
    assert not result.get("isError"), result
    assert result["structuredContent"]["media"]["object_id"] == "real-draft"
    assert result["structuredContent"]["media"]["final"] is False
