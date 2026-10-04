"""Selected media must arrive intact before an adapted snippet can be rendered."""

import asyncio
import hashlib
import json
import shutil
import subprocess
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from video_use_mcp.pilot import reference_clone as clone
from video_use_mcp.pilot.reference_download_worker import inspect_media
from video_use_mcp.pilot.runtime import require_production_intake
from video_use_mcp.pilot.tests.test_cards import rpc
from video_use_mcp.pilot.tests.test_reference_direction import (
    invoke,
    mark_downloaded,
    refs,
    saved,
)
from video_use_mcp.pilot.tests.test_reference_direction import (
    project as project,
)
from video_use_mcp.pilot.tests.test_reference_direction import (
    registry as registry,
)

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]


def selected(pilot, project, both=False):
    invoke(pilot, project, references=refs())
    result = invoke(
        pilot,
        project,
        "select",
        selected_ids=["diagram", "editorial"] if both else ["diagram"],
        user_message="Use that motion for the Moon",
        direction="Same timing, lunar subject",
    )
    return result


def test_selection_requires_acquisition_but_preserves_full_video_checkpoint(
    pilot, project
):
    result = selected(pilot, project)
    state = saved(pilot, project)
    context = result["reference_direction"]["clone"]
    assert context["status"] == "download_required"
    assert context["prepare"][0]["arguments"] == {
        "project_id": project,
        "reference_id": "diagram",
    }
    with pytest.raises(ValueError, match="Download the selected"):
        require_production_intake(state, "step", {"production_stage": "excerpt"})
    require_production_intake(state, "reference_download", {})
    state = mark_downloaded(state)
    require_production_intake(state, "step", {"production_stage": "excerpt"})
    with pytest.raises(ValueError, match="explicit excerpt acceptance"):
        require_production_intake(state, "step", {"production_stage": "full_video"})
    state["intake"]["excerpt_review"]["status"] = "approved"
    require_production_intake(state, "step", {"production_stage": "full_video"})


def test_all_selected_references_required_and_legacy_projects_unchanged(pilot, project):
    selected(pilot, project, both=True)
    state = saved(pilot, project)
    direction = state["intake"]["reference_direction"]
    direction["clone"]["media"]["diagram"] = {"source": "verified"}
    assert clone.clone_context(direction)["pending_reference_ids"] == ["editorial"]
    with pytest.raises(ValueError):
        require_production_intake(state, "step", {"production_stage": "excerpt"})
    direction.pop("clone")
    require_production_intake(state, "step", {"production_stage": "excerpt"})


def test_unselected_and_stale_selection_cannot_download(pilot, project):
    with pytest.raises(ValueError, match="Choose a reference"):
        clone.selected_reference(saved(pilot, project), "diagram")
    selected(pilot, project)
    state = saved(pilot, project)
    with pytest.raises(ValueError, match="selected in this project"):
        clone.selected_reference(state, "editorial")
    with pytest.raises(ValueError, match="selection changed"):
        clone.selected_reference(state, "diagram", "old-key")


def test_prepare_tool_is_discovered_and_checks_selection_before_spending(
    pilot, project
):
    tools = {t["name"]: t for t in rpc(pilot, "tools/list", {})["tools"]}
    assert tools["prepare_video_reference"]["annotations"]["openWorldHint"]
    result = rpc(
        pilot,
        "tools/call",
        dict(
            name="prepare_video_reference",
            arguments=dict(
                project_id=project, reference_id="diagram", request_id="download"
            ),
        ),
    )
    assert result.get("isError")
    selected(pilot, project)
    manager = pilot[1].state.manager
    manager.submit = Mock(side_effect=ValueError("submission reached"))
    result = rpc(
        pilot,
        "tools/call",
        dict(
            name="prepare_video_reference",
            arguments=dict(
                project_id=project, reference_id="diagram", request_id="download"
            ),
        ),
    )
    assert "submission reached" in str(result)
    assert manager.submit.call_args.args[2] == "reference_download"
    assert manager.submit.call_args.args[3]["selection_key"] == clone.selection_key(
        saved(pilot, project)["intake"]["reference_direction"]
    )
    guide = rpc(
        pilot,
        "tools/call",
        dict(name="video_use_guidance", arguments={"topic": "reference-cloning"}),
    )
    assert not guide.get("isError")
    assert "Measure before planning" in str(guide)


def manager_for(pilot, project):
    store = pilot[1].state.store

    async def save_object(uid, pid, kind, name, local):
        return dict(
            id=hashlib.sha256(name.encode()).hexdigest(),
            name=name,
            size=local.stat().st_size,
        )

    return SimpleNamespace(
        store=store, sessions={}, save_object=AsyncMock(side_effect=save_object)
    )


def task_for(pilot, project):
    return dict(
        owner="tester",
        project=project,
        payload=dict(
            reference_id="diagram",
            selection_key=clone.selection_key(
                saved(pilot, project)["intake"]["reference_direction"]
            ),
        ),
    )


async def fake_download(manager, uid, pid, reference, directory, source_object_id):
    video, sheet = directory / "video.mp4", directory / "sheet.jpg"
    video.write_bytes(b"downloaded reference")
    sheet.write_bytes(b"sheet")
    return (
        video,
        sheet,
        dict(
            sha256=hashlib.sha256(video.read_bytes()).hexdigest(),
            size=video.stat().st_size,
            duration_seconds=8,
            sample_times=[0, 4, 7.9],
        ),
    )


def test_acquisition_persists_source_paths_and_retries_reuse_media(
    pilot, project, monkeypatch
):
    selected(pilot, project)
    manager = manager_for(pilot, project)
    download = AsyncMock(side_effect=fake_download)
    monkeypatch.setattr(clone, "download_selected", download)
    sandbox = SimpleNamespace(upload=AsyncMock(), write=AsyncMock())
    result = asyncio.run(
        clone.prepare_reference(manager, task_for(pilot, project), sandbox)
    )
    assert result["reference"]["source"]["path"].startswith("sources/reference-")
    assert result["clone"]["status"] == "ready_for_analysis"
    assert manager.save_object.await_count == 2
    assert sandbox.upload.await_count == 2
    brief = json.loads(sandbox.write.call_args.args[1])
    assert brief["brief"] == "Explain the Moon"
    assert brief["direction"] == "Same timing, lunar subject"
    assert (
        saved(pilot, project)["intake"]["excerpt_review"]["status"] == "not_requested"
    )
    again = asyncio.run(
        clone.prepare_reference(manager, task_for(pilot, project), sandbox)
    )
    assert again["cached"]
    assert download.await_count == 1


def test_download_failure_never_unlocks_snippet(pilot, project, monkeypatch):
    selected(pilot, project)
    manager = manager_for(pilot, project)
    monkeypatch.setattr(
        clone, "download_selected", AsyncMock(side_effect=ValueError("Unavailable"))
    )
    with pytest.raises(ValueError, match="Unavailable"):
        asyncio.run(
            clone.prepare_reference(
                manager, task_for(pilot, project), SimpleNamespace()
            )
        )
    assert not manager.save_object.called
    with pytest.raises(ValueError, match="Download the selected"):
        require_production_intake(
            saved(pilot, project), "step", {"production_stage": "excerpt"}
        )


def test_choice_changed_during_download_does_not_publish_or_unlock(
    pilot, project, monkeypatch
):
    selected(pilot, project)
    manager = manager_for(pilot, project)

    async def changed(*args):
        result = await fake_download(*args)
        state = saved(pilot, project)
        state["intake"]["reference_direction"]["direction"] = "Different treatment"
        manager.store.put("creative", project, state)
        return result

    monkeypatch.setattr(clone, "download_selected", changed)
    with pytest.raises(ValueError, match="selection changed"):
        asyncio.run(
            clone.prepare_reference(
                manager, task_for(pilot, project), SimpleNamespace()
            )
        )
    manager.save_object.assert_not_called()


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg needed"
)
def test_real_media_probe_sheet_and_invalid_source(tmp_path):
    source = tmp_path / "reference.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=160x90:rate=12",
            "-t",
            "1",
            "-c:v",
            "libx264",
            str(source),
        ],
        check=True,
    )
    result = inspect_media(source, tmp_path)
    assert result["width"] == 160 and result["height"] == 90
    assert result["duration_seconds"] == 1
    assert not result["has_audio"]
    assert result["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert len(result["sample_times"]) == 12
    from PIL import Image

    with Image.open(tmp_path / "contact-sheet.jpg") as image:
        assert image.size == (960, 840)
    source.write_text("<html>not a video</html>")
    with pytest.raises(subprocess.CalledProcessError):
        inspect_media(source, tmp_path)


def test_public_project_context_preserves_download_progress(pilot, project):
    from video_use_mcp.pilot.intake import intake_context
    from video_use_mcp.pilot.widgets import creative_public

    selected(pilot, project)
    state = mark_downloaded(saved(pilot, project))
    context = intake_context(creative_public(state), project)
    assert context["reference_direction"]["clone"]["status"] == "ready_for_analysis"
    assert not context["reference_direction"]["clone"]["pending_reference_ids"]
    state["intake"]["reference_direction"]["direction"] = "Changed selected traits"
    with pytest.raises(ValueError, match="Download the selected"):
        require_production_intake(state, "step", {"production_stage": "excerpt"})


def test_uploaded_fallback_cannot_read_another_projects_source(monkeypatch, tmp_path):
    monkeypatch.setenv("PILOT_REFERENCE_BROWSER_IMAGE", "test-image")
    store = SimpleNamespace(sql=Mock(return_value=[]), download=Mock(), reserve=Mock())
    manager = SimpleNamespace(store=store)
    with pytest.raises(ValueError, match="belonging to this project"):
        asyncio.run(
            clone.download_selected(
                manager,
                "user",
                "project",
                {"url": "https://example.com/video.mp4"},
                tmp_path,
                "foreign-object",
            )
        )
    assert store.sql.call_args.args[1:] == ("foreign-object", "user", "project")
    store.download.assert_not_called()
    store.reserve.assert_not_called()


def test_cancellation_does_not_unlock_acquisition(pilot, project, monkeypatch):
    selected(pilot, project)
    manager = manager_for(pilot, project)
    monkeypatch.setattr(
        clone, "download_selected", AsyncMock(side_effect=asyncio.CancelledError)
    )
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            clone.prepare_reference(
                manager, task_for(pilot, project), SimpleNamespace()
            )
        )
    assert not manager.save_object.called
    assert (
        clone.clone_context(saved(pilot, project)["intake"]["reference_direction"])[
            "status"
        ]
        == "download_required"
    )
