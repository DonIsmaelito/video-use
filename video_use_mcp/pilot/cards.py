"""Portable MCP Apps preview card and efficient editing tools."""

import asyncio
import contextlib
import json
import re
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Annotated, Literal

from mcp.types import CallToolResult, TextContent
from mcp.server.fastmcp import Image
from pydantic import BaseModel, Field

from .interaction import (
    UI_URI,
    UI_META,
    creative_handoff,
    record_progress,
    wait_for_task,
)
from .feedback import feedback_context
from .widgets import creative_public
from .experience import experience_context
from .intake import intake_context
from .creative_state import creative_edit
from .store import ident

Stage = Literal[
    "planning", "style", "motion", "draft", "review", "complete", "needs_attention"
]


class Component(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    command: str = Field(min_length=1, max_length=10000)


class SourceFile(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    content: str = Field(max_length=2000000)


class ProductionScene(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    seconds: float = Field(gt=0, le=86400)


class ProductionTiming(BaseModel):
    scenes: list[ProductionScene] = Field(min_length=1, max_length=64)
    narration_offset: float | None = Field(default=None, ge=0)


def register_cards(
    mcp, store, manager, config, muser, link, workspace, public_task, read, execute
):
    def snapshot(uid, pid):
        project = store.project(uid, pid)
        state = store.get("progress", pid) or {"updates": []}
        # Build fresh expiring URLs only after verifying project ownership.
        updates = []
        for entry in state.get("updates", []):
            entry = dict(entry)
            preview = entry.get("preview")
            if preview:
                entry["preview"] = dict(preview, url=link(uid, preview["object_id"]))
            updates.append(entry)
        tasks = store.sql(
            "SELECT id,operation,status,created,updated,error FROM public.vp_tasks WHERE project=$1 ORDER BY created DESC LIMIT 6",
            pid,
        )
        revisions = store.sql(
            "SELECT id,video,summary,created FROM public.vp_revisions WHERE project=$1 ORDER BY created DESC LIMIT 3",
            pid,
        )
        return {
            "id": pid,
            "title": project["title"],
            "workspace_url": workspace(pid),
            "brief": state.get("brief", ""),
            "next_action": state.get("next_action", ""),
            "stage": state.get("stage", "planning"),
            "updates": updates,
            "tasks": tasks,
            "revisions": [
                dict(
                    r,
                    video_url=link(uid, r["video"]),
                    download_url=link(uid, r["video"]) + "&download=true",
                )
                for r in revisions
            ],
        }

    def card_result(uid, pid):
        data = snapshot(uid, pid)
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "project_id": pid,
                            "workspace_url": workspace(pid),
                            "stage": data["stage"],
                            "brief": data["brief"],
                            "next_action": data["next_action"],
                            "latest_update": (data["updates"] or [None])[-1],
                            "tasks": data["tasks"],
                        }
                    ),
                )
            ],
            structuredContent=data,
        )

    def current_media(uid, pid):
        """Only return authored media, never task state or internal QA sheets."""
        store.project(uid, pid)
        state = store.get("progress", pid) or {}
        revisions = store.sql(
            "SELECT id,video,created FROM public.vp_revisions WHERE project=$1 ORDER BY created DESC LIMIT 3",
            pid,
        )
        updates = state.get("updates", [])
        if state.get("latest_preview"):
            updates = [state["latest_preview"], *updates]
        items = [
            dict(u["preview"], at=u["at"], caption=u["note"], final=False)
            for u in updates
            if u.get("preview") and u["stage"] != "review"
        ]
        items += [
            dict(
                object_id=r["video"],
                media_type="video/mp4",
                at=r["created"],
                caption="Finished video",
                draft=False,
                final=state.get("stage") == "complete",
            )
            for r in revisions
        ]
        # Older view_video_frame calls published internal inspection sheets as
        # generic "Preview frame" updates. Keep an actual playable draft visible
        # instead of allowing those legacy QA images to replace it.
        if any(item["media_type"] == "video/mp4" for item in items):
            items = [
                item
                for item in items
                if not (
                    item["media_type"].startswith("image/")
                    and item.get("caption") == "Preview frame"
                )
            ]
        if not items:
            raise ValueError(
                "No visual exists yet. Finish a meaningful motion draft before showing it; style references are available separately with show_video_choices."
            )
        # InsForge timestamp strings may use Z or +00:00: normalize before sorting.
        from datetime import datetime

        media = max(
            items, key=lambda x: datetime.fromisoformat(x["at"].replace("Z", "+00:00"))
        )
        # Sign only the selected object. A refresh cannot expose unrelated
        # project objects, and has no reason to regenerate twenty old URLs.
        media["url"] = link(uid, media["object_id"])
        if media["media_type"] == "video/mp4":
            media["download_url"] = media["url"] + "&download=true"
        return media

    def media_result(uid, pid):
        media = current_media(uid, pid)
        creative = store.get("creative", pid)
        intake = intake_context(creative, pid)
        if intake and intake["mode"] == "delegate" and not media.get("final"):
            raise ValueError(
                "Hands off is selected. Finish and review the video, then show its final export; skip intermediate previews."
            )
        data = {
            "project_id": pid,
            "media": media,
            "creative": creative_public(creative),
            "intake": intake,
            "next_action": (
                "Present the finished video and download concisely, describing only "
                "the review evidence you actually inspected. The requested export is complete."
            )
            if media.get("final")
            else (
                "Add one brief chat sentence about what this actual draft shows "
                "and the next useful improvement, then continue working. Invite "
                "redirection only where it matters; do not require a reply. "
                "Use current creative choices before the next render. "
                "This player refreshes later drafts and the final export; reuse it "
                "rather than opening another player for each milestone. "
                "Do not describe workspace setup or terminal commands."
            ),
        }
        if (
            intake
            and intake["mode"] == "hands_on"
            and not media.get("final")
            and intake["excerpt_review"].get("status") != "approved"
        ):
            data["next_action"] = (
                "This is the short sample for the user's review. Explain the proposed direction in one sentence, call show_video_checkpoint, and wait for continue or refine before making the rest. Reuse this player for later media."
            )
            data["next_tool"] = {
                "name": "show_video_checkpoint",
                "arguments": {
                    "project_id": pid,
                    "creative_revision": creative["revision"],
                    "object_id": media["object_id"],
                },
            }
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=json.dumps(data),
                )
            ],
            structuredContent=data,
        )

    async def step_result(uid, task_id, include_logs=False):
        task = store.task(uid, task_id)
        out = public_task(task)
        result = out.get("result") or {}
        out["result"] = {
            k: v[-2000:] if k in ("stdout", "stderr") and not include_logs else v
            for k, v in result.items()
        }
        if result.get("components") and not include_logs:
            out["result"]["components"] = [
                {
                    k: (v[-2000:] if c.get("exit_code") else v[-400:])
                    if k in ("stdout", "stderr")
                    else v
                    for k, v in c.items()
                }
                for c in result["components"]
            ]
        for kind in ("video", "source"):
            if result.get(kind + "_id"):
                out[kind + "_url"] = link(uid, result[kind + "_id"])
        if out.get("video_url"):
            out["download_url"] = out["video_url"] + "&download=true"
        preview = result.get("preview") or {}
        if out["status"] == "succeeded" and not result.get("exit_code"):
            if result.get("video_id"):
                out["media"] = {
                    "object_id": result["video_id"],
                    "media_type": "video/mp4",
                    "url": out["video_url"],
                    "download_url": out["download_url"],
                    "caption": "Finished video",
                }
            elif preview.get("object_id"):
                out["media"] = preview | {
                    "url": link(uid, preview["object_id"]),
                }
                if preview.get("media_type") == "video/mp4":
                    out["media"]["download_url"] = (
                        out["media"]["url"] + "&download=true"
                    )
        image_object = result.get("review_object") or (
            preview.get("object_id")
            if preview.get("media_type") == "image/png"
            else None
        )
        content = []
        if out["status"] == "succeeded" and image_object:
            obj = store.sql(
                "SELECT key FROM public.vp_objects WHERE id=$1 AND owner=$2",
                image_object,
                uid,
            )[0]
            with tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp) / "frame.png"
                await asyncio.to_thread(store.download, obj["key"], target)
                content.append(
                    Image(data=target.read_bytes(), format="png").to_image_content()
                )
            if result.get("review_object"):
                store.put("reviewed", out["project"], result["sha256"], ttl=86400)
        out["creative"] = creative_public(store.get("creative", out["project"]))
        handoff_task = task
        if "creative_revision" not in (task.get("payload") or {}):
            submitted_context = store.get("task_context", task_id)
            if isinstance(submitted_context, dict):
                handoff_task = task | {
                    "submitted_creative_revision": submitted_context.get(
                        "submitted_creative_revision"
                    )
                }
        handoff = creative_handoff(handoff_task, out["creative"])
        if handoff:
            out["creative_handoff"] = handoff
        out["production_timing"] = store.get("production_timing", out["project"])
        out["review_findings"] = store.get("review_findings", out["project"]) or []
        out["feedback"] = feedback_context(store, out["project"])
        if isinstance(result.get("assembly"), dict):
            # Keep the output path and exact scene timing usable even when noisy
            # renderer stdout is truncated in the compact task response.
            out["assembly"] = result["assembly"]
        if task.get("payload", {}).get("scene_source"):
            out["scene_source"] = task["payload"]["scene_source"]
            with contextlib.suppress(ValueError, TypeError):
                rendered = json.loads(result.get("stdout", ""))
                if isinstance(rendered, dict):
                    out["scene_render"] = {
                        key: rendered[key]
                        for key in (
                            "duration",
                            "frame_count",
                            "width",
                            "height",
                            "fps",
                            "warnings",
                            "audio_start",
                        )
                        if key in rendered
                    }
        if out["status"] in ("queued", "running"):
            out["next_action"] = (
                "This task is still running. Call get_video_task with its default wait; "
                "do not resubmit it or display a placeholder."
            )
            out["next_tool"] = {
                "name": "get_video_task",
                "arguments": {"task_id": task_id},
            }
        elif out["status"] != "succeeded" or result.get("exit_code"):
            out["next_action"] = (
                "Inspect this task's error and correct only the failed work. "
                "Do not poll a finished task or repeat successful rendering."
            )
            if "narrate allowance reached" in (out.get("error") or ""):
                out["error"] = (
                    "The hosted video's daily narration allowance has been reached."
                )
                out["blocker"] = {
                    "kind": "service_allowance",
                    "resource": "narration",
                    "automatic_retry": False,
                    "resets": "00:00 UTC daily",
                }
                out["next_action"] = (
                    "Tell the user that the video service's daily narration allowance "
                    "is exhausted; this is not their Claude/ChatGPT subscription limit "
                    "or a rendering failure. Do not repeatedly retry or silently omit "
                    "requested voiceover. Continue useful story/visual work while the "
                    "host adjusts the allowance or it resets at 00:00 UTC. Once capacity "
                    "is available, retry narration with a new request_id and finish the "
                    "requested voiced video. Do not present a silent draft as complete."
                )
        elif out["operation"] == "narrate" and result.get("audio_path"):
            # The saved speech is an input to the next visual, not a reason to
            # wait or regenerate it. This handoff is response-only: reading an
            # old task must not overwrite the project's newer progress.
            out["narration_continuation"] = {
                key: result[key]
                for key in ("audio_path", "timing_path", "duration", "speech_end")
                if key in result
            }
            if handoff:
                out["narration_continuation"]["creative_revision"] = handoff[
                    "current_revision"
                ]
            out["next_action"] = (
                "Narration is saved. Reuse result.audio_path and any returned inline "
                "sentence_timings/word_timings. Reuse the measured duration when "
                "supplied instead of probing again. Use the current creative state. "
                "If no meaningful draft exists yet, author or adapt one short excerpt "
                "aligned to a relevant part of that audio before building the entire "
                "video. For compact 2D motion, use render_video_scene with a scene "
                "of at most 20 seconds; when another pipeline fits better, use "
                "run_video_step with preview_path. If a draft or finished video "
                "already exists, continue from it only as needed for the current "
                "request; rereading this narration is not a reason to restart work. "
                "After a new render succeeds, open show_video_preview only if no "
                "working player exists in this conversation; otherwise let the existing "
                "player refresh. Keep working without an approval pause. "
                "Do not display a placeholder, poll this completed task, or rerun "
                "completed speech merely to resume. Align the full "
                "video to the measured narration duration. If speech exceeds the "
                "requested duration, never silently trim it: extend an approximate "
                "target or explicitly revise the narration to honor an exact limit."
            )
        elif out.get("media"):
            out["next_action"] = (
                "Actual media is ready at media.url. If no player for this project is "
                "already open in THIS conversation, use preview_delivery.open_if_missing. An existing "
                "player refreshes new media for up to ten minutes when the host supports "
                "app tools; let it update instead of opening duplicate players. Reopen for "
                "a substantial new draft or final export if refresh is unavailable or expired. "
                "Accompany a new draft with one short chat sentence about what is "
                "visible and what comes next. Then continue without an approval "
                "pause. Do not poll this completed task."
            )
            out["preview_delivery"] = {
                "reuse_existing_player": True,
                "open_only_when": "No player exists in this conversation, or it has expired or cannot refresh.",
                "open_if_missing": {
                    "name": "show_video_preview",
                    "arguments": {"project_id": out["project"]},
                },
            }
            if result.get("review_object"):
                out["next_action"] += (
                    " Also inspect the returned encoded review image before exporting."
                )
        elif result.get("review_object"):
            out["next_action"] = (
                "Inspect the returned encoded review image. If it passes, export this "
                "exact video with an honest review summary. Reuse the player already "
                "open in this conversation; use show_video_preview only if absent, "
                "expired or unable to refresh. "
                "This inspection sheet is not a user-facing video preview. Do not poll again."
            )
        elif task.get("payload", {}).get("preview_pending"):
            out["preview_pending"] = True
            out["next_action"] = (
                "The work completed and its files are saved, but no preview_path was supplied. "
                "Publish the actual generated image or video with a small run_video_step call: "
                "set preview_path to that existing file, use a new request_id and the current "
                "creative_revision, and omit files, components and command. "
                "Do not resend the source files or rerender just to publish the preview."
            )
        else:
            out["next_action"] = (
                "This task is complete. Continue the next production step using its result; "
                "do not poll again. Publish meaningful media when it exists."
            )
        if out["status"] == "succeeded" and isinstance(result.get("assembly"), dict):
            if result["assembly"].get("quality") == "draft":
                out["next_action"] += (
                    " This assembly uses draft quality. After checking the draft, use "
                    "assemble_video quality=final for delivery unless the user explicitly "
                    "requested draft resolution. Do not silently export preview resolution "
                    "as the finished format."
                )
        if result.get("preferences_changed") or (
            handoff and handoff["preferences_changed"]
        ):
            out["next_action"] += (
                " Creative preferences changed during this work: read the "
                "current creative state and adapt before final rendering or export."
            )
        out["experience"] = experience_context(
            out.get("creative"),
            event="task",
            task=out,
            media=out.get("media"),
            handoff=handoff,
            blocker=out.get("blocker"),
        )
        intake = intake_context(out.get("creative"), out["project"])
        if intake:
            out["intake"] = intake
            final = (
                out["status"] == "succeeded"
                and out["operation"] == "export"
                and result.get("video_id")
            )
            if (
                intake["mode"] == "delegate"
                and not final
                and out["status"] == "succeeded"
            ):
                out.pop("preview_delivery", None)
                # Private QA still reaches the model. Only human-facing draft
                # displays and optional check-ins are suppressed by delegation.
                out["next_action"] = (
                    "Hands off: continue production and internal review using these results. Do not open a draft player or ask optional questions. Deliver the final playable export. Report real blockers honestly."
                )
            elif (
                intake["mode"] == "hands_on"
                and out.get("media")
                and not final
                and intake["excerpt_review"].get("status") != "approved"
            ):
                out["next_action"] = (
                    "The sample is ready. Show or refresh its actual player, then call show_video_checkpoint for continue/refine and wait before producing the complete film. Do not poll this completed task or silently complete the rest."
                )
                out["next_tool"] = {
                    "name": "show_video_checkpoint",
                    "arguments": {
                        "project_id": out["project"],
                        "creative_revision": out["creative"]["revision"],
                        "object_id": out["media"]["object_id"],
                    },
                }
        # A few hosts consume only text. Serialize after attaching the same media
        # and state-specific next action that structured clients receive.
        out.pop("next_check", None)
        content.insert(0, TextContent(type="text", text=json.dumps(out)))
        # Background tools must not create an empty workspace card. Only the
        # explicit media/choices/upload tools advertise a UI resource.
        return CallToolResult(content=content, structuredContent=out)

    @mcp.resource(
        UI_URI,
        mime_type="text/html;profile=mcp-app",
        meta={
            "ui": {
                "prefersBorder": False,
                "csp": {
                    "resourceDomains": [
                        config.public_url,
                        "https://f7e2vbn5.us-west.insforge.app",
                        "https://cdn.insforge.dev",
                    ],
                    "connectDomains": [config.public_url],
                },
            },
        },
    )
    def project_card() -> str:
        return (Path(__file__).parent / "ui" / "card.html").read_text()

    # Cached tool definitions in older conversations may still request these.
    for legacy_uri in (
        "ui://video-use/project-v2.html",
        "ui://video-use/project-v3.html",
        "ui://video-use/media-v4.html",
        "ui://video-use/media-v5.html",
        "ui://video-use/media-v6.html",
        "ui://video-use/media-v7.html",
        "ui://video-use/media-v8.html",
        "ui://video-use/media-v9.html",
    ):
        mcp.resource(
            legacy_uri,
            mime_type="text/html;profile=mcp-app",
            meta={
                "ui": {
                    "prefersBorder": False,
                    "csp": {
                        "resourceDomains": [
                            config.public_url,
                            "https://f7e2vbn5.us-west.insforge.app",
                            "https://cdn.insforge.dev",
                        ],
                        "connectDomains": [config.public_url],
                    },
                }
            },
        )(project_card)

    @mcp.resource(
        "ui://video-use/media-{version}.html",
        mime_type="text/html;profile=mcp-app",
        meta={
            "ui": {
                "prefersBorder": False,
                "csp": {
                    "resourceDomains": [
                        config.public_url,
                        "https://f7e2vbn5.us-west.insforge.app",
                        "https://cdn.insforge.dev",
                    ],
                    "connectDomains": [config.public_url],
                },
            },
        },
    )
    def previous_card_version(version: str) -> str:
        # Existing chats can retain tools from an earlier content-hash release.
        # A version is an identifier, never a filesystem path.
        if not re.fullmatch(r"[0-9a-f]{16}", version):
            raise ValueError("Unknown video card version")
        return project_card()

    @mcp.tool(annotations=read, meta=UI_META, title="Video preview")
    def show_video_preview(project_id: str) -> CallToolResult:
        """Show real media with playback/download. Hands off shows only the finished export. Hands on shows its short excerpt, then show_video_checkpoint waits for the user's direction before completing the rest. Key moments uses selective previews. Reuse the open player, which refreshes for up to ten minutes on supported hosts; reopen only when needed. No placeholders."""
        return media_result(muser(), project_id)

    @mcp.tool(annotations=execute, meta=UI_META, title="Review the sample")
    @creative_edit
    def show_video_checkpoint(
        project_id: str, creative_revision: int, object_id: str
    ) -> CallToolResult:
        """After showing a short hands-on excerpt, offer Continue with this or Refine the sample. Binds the decision to this exact rendered video. Never substitute an internal review or your own judgment for the user's answer. Use record_video_answers for an actual chat reply. Wait before rendering the rest."""
        uid = muser(True)
        store.project(uid, project_id)
        state = deepcopy(store.get("creative", project_id) or {})
        intake = intake_context(state, project_id)
        if (
            not intake
            or intake["mode"] != "hands_on"
            or intake["phase"] in ("mode", "basics", "personalization")
        ):
            raise ValueError(
                "Complete hands-on intake and the offered content/style choices before sample review"
            )
        if state.get("revision") != creative_revision:
            raise ValueError(
                "Creative preferences changed; read get_video_project before offering this review"
            )
        media = current_media(uid, project_id)
        if (
            media.get("object_id") != object_id
            or media.get("media_type") != "video/mp4"
            or media.get("final")
        ):
            raise ValueError(
                "Review the current sample video, not an old version, still image or finished export"
            )
        if media.get("duration") and media["duration"] > 20.1:
            raise ValueError(
                "Render a short sample of at most 20 seconds before offering hands-on review"
            )
        current = state.get("widgets", {}).get("brief") or {}
        if (
            current.get("purpose") == "excerpt_review"
            and current.get("media_object_id") == object_id
            and current.get("creative_revision") == creative_revision
        ):
            widget = current
        else:
            widget = dict(
                id=ident(),
                kind="brief",
                purpose="excerpt_review",
                title="How does this direction feel?",
                revision=1,
                creative_revision=creative_revision,
                state="open",
                media_object_id=object_id,
                required=["excerpt_review"],
                answers={},
                questions=[
                    dict(
                        id="excerpt_review",
                        prompt="Use this direction for the rest?",
                        options=[
                            dict(id="continue", label="Continue with this"),
                            dict(id="refine", label="Refine the sample"),
                        ],
                        recommended="",
                    )
                ],
            )
            state.setdefault("widgets", {})["brief"] = widget
            state["intake"]["excerpt_review"] = dict(
                status="pending",
                object_id=object_id,
                creative_revision=creative_revision,
            )
            store.put("creative", project_id, state)
        data = dict(
            project_id=project_id,
            widget={k: v for k, v in widget.items() if k != "receipts"},
            creative=creative_public(state),
            intake=intake_context(state, project_id),
            next_action=(
                "This sample direction is already accepted. Continue completing the film; do not ask for the same decision again."
                if state["intake"]["excerpt_review"].get("status") == "approved"
                else "Wait for the user's sample decision. Continue with this unlocks completing the film; Refine the sample means use their feedback or ask what should change, then present a revised excerpt. A recommendation or silence is not acceptance."
            ),
        )
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(data))],
            structuredContent=data,
        )

    @mcp.tool(annotations=read, meta={"ui": {"visibility": ["app"]}})
    def video_preview_updates(project_id: str) -> CallToolResult:
        """Refresh only the current media in an already-open player. App-only, read-only; never starts a task or sends a user message."""
        media = current_media(muser(), project_id)
        intake = intake_context(store.get("creative", project_id))
        data = {"project_id": project_id, "media": media}
        if intake and intake["mode"] == "delegate" and not media.get("final"):
            data.update(media=None, refresh="paused_by_involvement")
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(data))],
            structuredContent=data,
        )

    @mcp.tool(annotations=read, meta=UI_META)
    def show_video_project(project_id: str) -> CallToolResult:
        """Show the live in-chat project card with style frames, draft clips, progress, final videos and saved continuation context. Open once near the start; it updates itself."""
        return card_result(muser(), project_id)

    @mcp.tool(
        annotations=read, meta={"ui": {"resourceUri": UI_URI, "visibility": ["app"]}}
    )
    def video_project_updates(project_id: str) -> dict:
        """Refresh the project card without consuming a model-driven status check."""
        return snapshot(muser(), project_id)

    @mcp.tool(annotations=execute, title="Create video draft")
    async def run_video_step(
        project_id: str,
        request_id: Annotated[
            str,
            Field(
                description="A new identifier for this work; reuse only for an exact retry."
            ),
        ],
        note: str,
        stage: Annotated[
            Stage,
            Field(
                description="Use planning for source/probe work. For style, motion or draft, provide preview_path to the actual output file."
            ),
        ],
        files: list[SourceFile] = [],
        command: str = "",
        preview_path: Annotated[
            str,
            Field(
                description="Actual PNG/JPEG/MP4 output path to publish after the command succeeds. Required to deliver a visual milestone; may also publish an existing file with files and command omitted."
            ),
        ] = "",
        next_action: str = "",
        brief: str = "",
        timeout: int = 300,
        review_path: str = "",
        components: list[Component] = [],
        creative_revision: int = 0,
        production_timing: Annotated[
            ProductionTiming | None,
            Field(
                description="Actual ordered scene durations after narration alignment, separate from rough story beats. Supply with review_path or preview_path for that assembled video: {scenes:[{title,seconds}],narration_offset?}. Stored only after successful work; review checks total against the encoded duration."
            ),
        ] = None,
        production_stage: Annotated[
            Literal["excerpt", "full_video"],
            Field(
                description="excerpt means one short sample for creative review, not a complete film. full_video is default and waits for hands-on sample acceptance."
            ),
        ] = "full_video",
    ) -> CallToolResult:
        """Batch sources and render after intake. Declare excerpt for a short hands-on sample, full_video for completing the film; hands-on requires explicit sample acceptance first. Optional components (max6, concurrency2) render independently; command assembles after success. Pass current creative_revision, preview_path for the actual draft and review_path for final encoded inspection. Follow the saved mode for human-facing previews. Only poll unfinished tasks."""
        uid = muser(True)
        preview_pending = stage in ("style", "motion", "draft") and not preview_path
        if preview_pending and not (files or command or components):
            raise ValueError(
                "Supply preview_path for an existing visual, or files/command/components to create one."
            )
        if (
            len(components) > 6
            or len({c.name for c in components}) != len(components)
            or len(files) > 20
            or len(command) > 30000
            or len(note) > 1200
            or len(brief) > 4000
            or len(next_action) > 2000
        ):
            raise ValueError("Step exceeds file, command or context limits")
        task = manager.submit(
            uid,
            project_id,
            "step",
            {
                "files": [f.model_dump() for f in files],
                "command": command,
                "preview_path": preview_path,
                # Do not reject and discard a large authored payload merely
                # because publication was omitted. Preserve the work, but never
                # claim a visual milestone or guess an output filename.
                "stage": "planning" if preview_pending else stage,
                **({"preview_pending": True} if preview_pending else {}),
                "note": note,
                "next_action": next_action,
                "brief": brief,
                "timeout": timeout,
                "review_path": review_path,
                "components": [c.model_dump() for c in components],
                "creative_revision": creative_revision,
                **(
                    {"production_stage": production_stage}
                    if production_stage != "full_video"
                    or (store.get("creative", project_id) or {})
                    .get("intake", {})
                    .get("version")
                    == 1
                    else {}
                ),
                **(
                    {
                        "production_timing": production_timing.model_dump(
                            exclude_none=True
                        )
                    }
                    if production_timing is not None
                    else {}
                ),
            },
            request_id,
        )
        if task["status"] in ("queued", "running"):
            record_progress(
                store,
                project_id,
                "working",
                note,
                next_action,
                brief,
            )
        await wait_for_task(manager, task["id"], 25)
        return await step_result(uid, task["id"])

    @mcp.tool(annotations=execute)
    async def update_video_progress(
        project_id: str,
        stage: Stage,
        note: str,
        next_action: str = "",
        brief: str = "",
        preview_path: str = "",
        request_id: str = "",
    ) -> CallToolResult:
        """Save a concise progress update and next action for the live chat card and future turns. Optionally publish an existing PNG/JPEG frame or up-to-20-second draft clip (requires a unique request_id). Draft publication does not replace final review. Do not wait for approval unless the user requested it."""
        uid = muser(True)
        store.project(uid, project_id)
        if len(note) > 1200 or len(brief) > 4000 or len(next_action) > 2000:
            raise ValueError("Progress context exceeds limits")
        if preview_path:
            task = manager.submit(
                uid,
                project_id,
                "preview",
                {
                    "path": preview_path,
                    "stage": stage,
                    "note": note,
                    "next_action": next_action,
                    "brief": brief,
                    "timeout": 180,
                },
                request_id,
            )
            await wait_for_task(manager, task["id"], 25)
            return await step_result(uid, task["id"])
        if manager.lock(project_id).locked():
            raise ValueError(
                "A step is active; its saved progress will update when it finishes"
            )
        record_progress(store, project_id, stage, note, next_action, brief)
        return card_result(uid, project_id)

    return {
        "snapshot": snapshot,
        "card_result": card_result,
        "task_result": step_result,
        "media_result": media_result,
    }
