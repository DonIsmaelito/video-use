"""Render a small editable motion composition through the existing task runner."""

import json
import math
import re
import shlex
from typing import Annotated

from mcp.types import CallToolResult
from pydantic import Field

from helpers.render_scene import validate_scene

from .interaction import record_progress, wait_for_task


def scene_payload(
    scene_id, scene, note, creative_revision, narration_path, narration_start
):
    """Keep generated paths and commands separate from untrusted drawing data."""
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,59}", scene_id):
        raise ValueError(
            "Use a scene_id of 1–60 letters, numbers, underscores or hyphens"
        )
    if not note.strip() or len(note) > 1200:
        raise ValueError("Describe the visual in 1–1200 characters")
    if not math.isfinite(narration_start) or not 0 <= narration_start <= 7200:
        raise ValueError(
            "narration_start must be 0–7200 seconds into the supplied audio"
        )
    if len(narration_path) > 500 or "\x00" in narration_path:
        raise ValueError("Invalid narration path")
    if narration_start and not narration_path:
        raise ValueError("Supply narration_path when selecting an audio offset")
    scene = validate_scene(scene)
    source = f"edit/scenes/{scene_id}.json"
    video = f"edit/scenes/{scene_id}.mp4"
    argv = [
        "python",
        "/opt/video-use/helpers/render_scene.py",
        source,
        "-o",
        video,
        "--overwrite",
    ]
    if narration_path:
        argv.extend(["--audio", narration_path, "--audio-start", str(narration_start)])
    return {
        "files": [{"path": source, "content": json.dumps(scene, ensure_ascii=False)}],
        "command": shlex.join(argv),
        "preview_path": video,
        "stage": "motion",
        "note": note,
        "next_action": "Show this motion excerpt, then develop the remaining piece. Reuse or revise its editable scene source.",
        "creative_revision": creative_revision,
        "timeout": 300,
        "scene_source": {"scene_id": scene_id, "path": source, "video_path": video},
    }


def register_scenes(mcp, store, manager, muser, cards, execute):
    @mcp.tool(annotations=execute, title="Animate a scene")
    async def render_video_scene(
        project_id: str,
        request_id: str,
        scene_id: str,
        scene: Annotated[
            dict,
            Field(
                description=(
                    "Editable 2D composition: {duration,width?,height?,fps?,background?,marks:["
                    "{id,kind,x,y,w?,h?,color?,fill?,text?,size?,font?,opacity?,"
                    "keyframes?:[{time,x?,y?,opacity?,rotation?,scale?,ease?}]}]}. "
                    "Kinds: text,rect,ellipse,line,polygon,arc,wave. Duration <=20 seconds; "
                    "default 960x540 at15fps. Hex colors. Keyframes hold omitted properties. "
                    "Use video_use_guidance topic=scenes for geometry and typography details."
                )
            ),
        ],
        note: str,
        creative_revision: int,
        narration_path: str = "",
        narration_start: float = 0,
    ) -> CallToolResult:
        """Create a real short motion excerpt from compact drawing data, without writing renderer or assembly code. Use for diagrams, typography and simple 2D motion; custom Manim, footage and 3D remain available through run_video_step. Author one useful visual idea, not the whole film. Saves editable JSON and MP4 together; same scene_id can be rendered again with changed data and a NEW request_id. Optional narration_path is existing project audio, with explicit start offset. Follow display_action to show it, then continue without an approval pause."""
        uid = muser(True)
        if not 1 <= len(request_id) <= 114:
            raise ValueError("Provide a request ID of 1–114 characters")
        payload = scene_payload(
            scene_id, scene, note, creative_revision, narration_path, narration_start
        )
        task = manager.submit(uid, project_id, "step", payload, "scene:" + request_id)
        if task["status"] in ("queued", "running"):
            record_progress(store, project_id, "working", note, payload["next_action"])
        await wait_for_task(manager, task["id"], 25)
        return await cards["task_result"](uid, task["id"])
