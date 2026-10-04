"""New players select authored media; old polling cannot replace a shown sample."""

from unittest.mock import Mock, patch
import hashlib
import json
from pathlib import Path

from video_use_mcp.pilot.interaction import UI_URI
from video_use_mcp.pilot.tests.test_cards import PID, rpc

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]


def progress(app, *, stage="draft", include_qa=True):
    updates = [
        {
            "at": "2026-10-01T03:56:47Z",
            "stage": "draft",
            "note": "The first scene",
            "preview": {
                "object_id": "draft",
                "media_type": "video/mp4",
                "truncated": True,
                "duration": 120,
                "source_duration": 245,
            },
        }
    ]
    if include_qa:
        updates.append(
            {
                "at": "2026-10-01T03:58:47Z",
                "stage": "review",
                "note": "Checking frames",
                "preview": {"object_id": "qa", "media_type": "image/png"},
            }
        )
    app.state.store.put("progress", PID, {"stage": stage, "updates": updates})


def refresh(pilot):
    return rpc(
        pilot,
        "tools/call",
        {"name": "video_preview_updates", "arguments": {"project_id": PID}},
    )


def show(pilot):
    return rpc(
        pilot,
        "tools/call",
        {"name": "show_video_preview", "arguments": {"project_id": PID}},
    )


def test_refresh_is_app_only_read_only_without_its_own_visual_resource(pilot):
    tool = next(
        tool
        for tool in rpc(pilot, "tools/list", {})["tools"]
        if tool["name"] == "video_preview_updates"
    )
    assert tool["annotations"]["readOnlyHint"] is True
    assert tool["_meta"]["ui"] == {"visibility": ["app"]}
    document = Path(__file__).parents[1] / "ui" / "card.html"
    digest = hashlib.sha256(document.read_bytes()).hexdigest()[:16]
    assert UI_URI == f"ui://video-use/media-{digest}.html"
    old = rpc(pilot, "resources/read", {"uri": "ui://video-use/media-v6.html"})
    assert old["contents"][0]["mimeType"] == "text/html;profile=mcp-app"


def test_cached_versions_resolve_to_current_document_with_the_same_policy(pilot):
    current = rpc(pilot, "resources/read", {"uri": UI_URI})["contents"][0]
    for uri in (
        "ui://video-use/media-v9.html",
        "ui://video-use/media-0000000000000000.html",
    ):
        previous = rpc(pilot, "resources/read", {"uri": uri})["contents"][0]
        assert previous["text"] == current["text"]
        assert previous["mimeType"] == current["mimeType"]
        assert previous["_meta"] == current["_meta"]


def test_new_player_selects_actual_media_and_preserves_excerpt_metadata(pilot):
    _, app = pilot
    progress(app)
    result = show(pilot)
    assert not result.get("isError"), result
    data = result["structuredContent"]
    assert data["project_id"] == PID
    assert data["follow_project"] is False
    assert data["media"]["object_id"] == "draft"
    assert data["media"]["truncated"] is True
    assert data["media"]["duration"] == 120
    assert data["media"]["source_duration"] == 245
    assert data["media"]["final"] is False
    assert "/files/draft?ticket=" in data["media"]["url"]
    app.state.store.project.assert_called_with("tester", PID)
    assert not any(
        "vp_tasks" in call.args[0] for call in app.state.store.sql.call_args_list
    )


def test_refresh_cannot_read_another_owners_project(pilot):
    _, app = pilot
    progress(app)
    app.state.store.project.side_effect = PermissionError("Project not found")
    app.state.store.sql.reset_mock()
    result = refresh(pilot)
    assert result["isError"]
    app.state.store.sql.assert_not_called()


def test_new_player_never_manufactures_a_placeholder(pilot):
    result = show(pilot)
    assert result["isError"]
    assert "structuredContent" not in result


def test_final_marker_requires_exported_revision_and_completed_progress(pilot):
    _, app = pilot
    progress(app, stage="complete")
    app.state.store.sql = Mock(
        return_value=[
            {"id": "revision", "video": "export", "created": "2026-10-01T03:57:00Z"}
        ]
    )
    result = show(pilot)
    assert result["structuredContent"]["media"]["object_id"] == "export"
    assert result["structuredContent"]["media"]["final"] is True
    assert result["structuredContent"]["media"]["draft"] is False
    # Opening an older export during new work must not call it the finished edit.
    progress(app, stage="working")
    assert show(pilot)["structuredContent"]["media"]["final"] is False


def test_legacy_polling_freezes_without_selecting_or_signing_new_media(pilot):
    _, app = pilot
    store = app.state.store
    progress(app, stage="complete")
    store.sql.return_value = [
        {"id": "revision", "video": "export", "created": "2026-10-01T03:57:00Z"}
    ]
    store.sql.reset_mock()
    with patch.object(store, "get", wraps=store.get) as get:
        with patch.object(store.vault, "encrypt", wraps=store.vault.encrypt) as encrypt:
            for _ in range(3):
                result = refresh(pilot)
                assert not result.get("isError"), result
                assert result["structuredContent"] == {
                    "project_id": PID,
                    "media": None,
                    "refresh": "pinned_player",
                }
    store.project.assert_called_with("tester", PID)
    store.sql.assert_not_called()
    assert not any(call.args[0] in {"progress", "creative"} for call in get.call_args_list)
    assert not any("object" in json.loads(call.args[0]) for call in encrypt.call_args_list)


def test_legacy_polling_is_frozen_even_before_a_preview_exists(pilot):
    result = refresh(pilot)
    assert not result.get("isError"), result
    assert result["structuredContent"]["media"] is None
    assert result["structuredContent"]["refresh"] == "pinned_player"


def test_refresh_trace_is_card_activity_not_model_work(pilot):
    _, app = pilot
    progress(app)
    assert not refresh(pilot).get("isError")
    with app.state.store.db() as db:
        rows = db.execute("SELECT key FROM kv WHERE kind='trace'").fetchall()
    traces = [app.state.store.get("trace", row["key"]) for row in rows]
    trace = next(t for t in traces if t["tool"] == "video_preview_updates")
    assert trace["surface"] == "card" and trace["project"] == PID
    assert "result" not in trace and "arguments" not in trace
