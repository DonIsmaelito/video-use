"""Render a small editable motion composition through the existing task runner."""

import hashlib
import json
import math
import re
import shlex
from typing import Annotated, Literal

from mcp.types import CallToolResult, TextContent
from pydantic import Field

from helpers.render_scene import scene_validation_report, validate_scene
from helpers.assemble_scenes import validate_spec

from .interaction import record_progress, wait_for_task


def scene_payload(
    scene_id,
    scene,
    note,
    creative_revision,
    narration_path,
    narration_start,
    production_stage=None,
):
    """Keep generated paths and commands separate from untrusted drawing data."""
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,59}", scene_id):
        raise ValueError(
            "Use a scene_id of 1–60 letters, numbers, underscores or hyphens"
        )
    if not note.strip() or len(note) > 1200:
        raise ValueError("Describe the visual in 1–1200 characters")
    if production_stage is not None and production_stage not in {
        "excerpt",
        "full_video",
    }:
        raise ValueError("production_stage must be excerpt or full_video")
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
        **(
            {"production_stage": production_stage}
            if production_stage is not None
            else {}
        ),
        "note": note,
        "next_action": (
            "Show this motion excerpt, then develop the remaining piece. Reuse or revise its editable scene source."
            if production_stage is None
            else "Reuse or revise this editable motion excerpt. Follow the chosen involvement mode: hands-on requires explicit excerpt review before the complete film; key moments may show a useful update; hands-off continues without an intermediate preview."
        ),
        "creative_revision": creative_revision,
        "timeout": 300,
        "scene_source": {"scene_id": scene_id, "path": source, "video_path": video},
    }


def assembly_payload(
    request_id,
    scene_ids,
    scenes,
    note,
    creative_revision,
    production_stage=None,
    **options,
):
    """Construct a trusted assembly command; supplied compositions remain data."""
    if not 1 <= len(request_id) <= 111:
        raise ValueError("Provide a request ID of 1–111 characters")
    if not note.strip() or len(note) > 1200:
        raise ValueError("Describe the draft in 1–1200 characters")
    if production_stage is not None and production_stage not in {
        "excerpt",
        "full_video",
    }:
        raise ValueError("production_stage must be excerpt or full_video")
    spec = validate_spec({"scene_ids": scene_ids, **options})
    if not isinstance(scenes, dict) or set(scenes) - set(scene_ids):
        raise ValueError("scenes keys must appear in the ordered scene_ids")
    if len(json.dumps(scenes, ensure_ascii=False).encode()) > 1_000_000:
        raise ValueError("Provided scene data exceeds 1 MB")
    files, errors = [], []
    for scene_id, scene in scenes.items():
        report = scene_validation_report(scene)
        if not report["valid"]:
            errors.extend(f"{scene_id}: {error}" for error in report["errors"])
        else:
            files.append(
                {
                    "path": f"edit/scenes/{scene_id}.json",
                    "content": json.dumps(validate_scene(scene), ensure_ascii=False),
                }
            )
    if errors:
        raise ValueError("Assembly scene validation failed:\n" + "\n".join(errors))
    stem = "edit/assemblies/" + hashlib.sha256(request_id.encode()).hexdigest()[:20]
    source, video = stem + ".json", stem + ".mp4"
    files.append({"path": source, "content": json.dumps(spec, ensure_ascii=False)})
    if production_stage is None:
        # These strings are part of legacy request payload identity too.
        next_action = (
            "Show this complete playable draft now. Inspect the internal review images and correct issues. For delivery, call assemble_video with quality=final unless the user requested draft quality. Read current preferences before further work."
            if spec["quality"] == "draft"
            else "Show this complete playable video now. Inspect the internal review images, address any issues, then export. Read current preferences before further work."
        )
    elif production_stage == "excerpt":
        next_action = "This is a limited excerpt, not the complete film. Follow the chosen involvement mode; hands-on requires explicit excerpt review before full-video production."
    else:
        next_action = (
            "The complete playable draft is ready. Follow the chosen involvement mode when showing updates. Inspect the internal review images and correct issues. For delivery, call assemble_video with quality=final unless the user requested draft quality. Read current preferences before further work."
            if spec["quality"] == "draft"
            else "The complete playable video is ready. Inspect the internal review images, address any issues, then export and present the finished video. Read current preferences before further work."
        )
    return {
        "files": files,
        "command": shlex.join(
            ["python", "/opt/video-use/helpers/assemble_scenes.py", source, "-o", video]
        ),
        "preview_path": video,
        "review_path": video,
        "assembly_report": stem + ".assembly.json",
        "stage": "draft",
        **(
            {"production_stage": production_stage}
            if production_stage is not None
            else {}
        ),
        "note": note,
        "next_action": next_action,
        "creative_revision": creative_revision,
        "timeout": 600,
    }


def register_scenes(mcp, store, manager, muser, cards, execute):
    def production_scope(project_id, stage):
        if stage != "full_video":
            return stage
        creative = store.get("creative", project_id)
        intake = creative.get("intake") if isinstance(creative, dict) else None
        # Do not add a default field to exact retries from older conversations.
        return (
            stage if isinstance(intake, dict) and intake.get("version") == 1 else None
        )

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
                    "keyframes?:[{time,x?,y?,opacity?,rotation?,scale?,phase?,cycles?,size?,stroke_width?,ease?}],"
                    "motion_path?:{points:[[x,y],...],seconds,start?,loop?,closed?,count?,stagger?,orient?}}]}. "
                    "Kinds: text,rect,ellipse,line,polygon,arc,wave. Duration <=20 seconds; "
                    "default 960x540 at15fps. Hex colors. Keyframes can animate every numeric mark field; wave phase is in degrees. Omitted properties hold. "
                    "Use video_use_guidance topic=scenes for geometry and typography details."
                )
            ),
        ],
        note: str,
        creative_revision: int,
        narration_path: str = "",
        narration_start: float = 0,
        validate_only: bool = False,
        production_stage: Annotated[
            Literal["excerpt", "full_video"],
            Field(
                description="Declare excerpt only for the limited sample being reviewed or revised. The default full_video also covers individual scenes for the remaining film; hands-on mode requires acceptance of the excerpt before these renders."
            ),
        ] = "full_video",
    ) -> CallToolResult:
        """Create a real short motion excerpt from compact drawing data, without writing renderer or assembly code. Use for diagrams, typography and simple 2D motion; custom Manim, footage and 3D remain available through run_video_step. Author one useful visual idea, not the whole film. Saves editable JSON and MP4 together; same scene_id can be rendered again with changed data and a NEW request_id. Optional narration_path is existing project audio, with explicit start offset. validate_only returns all keyframe errors without writing files or rendering. Follow the chosen involvement mode: hands-on requires explicit excerpt review before full production, hands-off skips intermediate displays, and key moments shows selective updates. Reuse an existing player. Use assemble_video for the complete draft and final-quality rendering."""
        uid = muser(True)
        if validate_only:
            store.project(uid, project_id)
            report = scene_validation_report(scene)
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps(report))],
                structuredContent=report,
            )
        if not 1 <= len(request_id) <= 114:
            raise ValueError("Provide a request ID of 1–114 characters")
        payload = scene_payload(
            scene_id,
            scene,
            note,
            creative_revision,
            narration_path,
            narration_start,
            production_stage=production_scope(project_id, production_stage),
        )
        task = manager.submit(uid, project_id, "step", payload, "scene:" + request_id)
        if task["status"] in ("queued", "running"):
            record_progress(store, project_id, "working", note, payload["next_action"])
        await wait_for_task(manager, task["id"], 25)
        return await cards["task_result"](uid, task["id"])

    @mcp.tool(annotations=execute, title="Assemble the video")
    async def assemble_video(
        project_id: str,
        request_id: str,
        scene_ids: list[str],
        creative_revision: int,
        scenes: dict[str, dict] | None = None,
        narration_path: str = "",
        narration_offset: float = 0,
        quality: Literal["draft", "final"] = "draft",
        width: int = 0,
        height: int = 0,
        fps: int = 0,
        audio_normalization: Literal["web", "none"] = "web",
        note: str = "The complete video draft is ready to watch.",
        production_stage: Annotated[
            Literal["excerpt", "full_video"],
            Field(
                description="Declare excerpt only when assembling a limited sample for review. Full-video work in hands-on mode requires explicit acceptance of the earlier excerpt."
            ),
        ] = "full_video",
    ) -> CallToolResult:
        """Join 1–12 ordered editable scene IDs into one playable video without writing Python or FFmpeg. IDs refer to edit/scenes/<id>.json. Supply any new or revised compositions in scenes={id: scene data}; all sources validate before any rendering. Default production_stage=full_video requires excerpt acceptance in hands-on mode; declare excerpt only for a limited sample. Unchanged compositions reuse their renders. draft defaults to 540p/15fps; final rerenders vector/text at 1080p/30fps, preserving the authored aspect ratio. Optional width/height/fps override output quality. narration_path uses existing audio; narration_offset delays it on the full timeline, and overlong narration is rejected, never silently cut. web normalizes narration toward -16 LUFS with -1.5 dBTP limit; none preserves its level. Returns a playable draft, private review images and measured scene timings. Follow the chosen involvement mode for intermediate displays; inspect the review, correct problems, then export the completed output. Maximum 180 seconds."""
        uid = muser(True)
        payload = assembly_payload(
            request_id,
            scene_ids,
            scenes or {},
            note,
            creative_revision,
            production_stage=production_scope(project_id, production_stage),
            narration_path=narration_path,
            narration_offset=narration_offset,
            quality=quality,
            width=width,
            height=height,
            fps=fps,
            audio_normalization=audio_normalization,
        )
        task = manager.submit(
            uid, project_id, "step", payload, "assemble:" + request_id
        )
        if task["status"] in ("queued", "running"):
            record_progress(
                store,
                project_id,
                "working",
                "Putting the scenes together.",
                payload["next_action"],
            )
        await wait_for_task(manager, task["id"], 25)
        return await cards["task_result"](uid, task["id"])
