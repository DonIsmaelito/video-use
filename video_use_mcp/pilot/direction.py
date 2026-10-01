"""Fast, code-free visual proposals and durable conversational design approval."""

import asyncio
import io
import json
import math
import tempfile
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, Field
from mcp.types import CallToolResult, TextContent
from mcp.server.fastmcp import Image as MCPImage

from .interaction import UI_META, record_progress


class Mark(BaseModel):
    kind: Literal["text", "rect", "ellipse", "line", "polygon", "arc", "wave"]
    x: float = Field(default=0, ge=-1280, le=2560)
    y: float = Field(default=0, ge=-720, le=1440)
    w: float = Field(default=100, ge=0, le=2560)
    h: float = Field(default=100, ge=0, le=1440)
    color: str = Field(default="#ffffff", max_length=30)
    fill: str | None = Field(default=None, max_length=30)
    stroke_width: int = Field(default=3, ge=1, le=30)
    radius: int = Field(default=0, ge=0, le=200)
    text: str = Field(default="", max_length=300)
    size: int = Field(default=32, ge=10, le=140)
    font: Literal["sans", "bold", "serif"] = "sans"
    align: Literal["left", "center", "right"] = "left"
    points: list[tuple[float, float]] = Field(default_factory=list, max_length=200)
    start: float = Field(default=0, ge=-360, le=360)
    end: float = Field(default=180, ge=-360, le=720)
    cycles: float = Field(default=3, ge=0.1, le=20)
    phase: float = Field(default=0, ge=-360, le=360)


class Frame(BaseModel):
    background: str = Field(default="#11141e", max_length=30)
    width: int = Field(default=960, ge=320, le=1280)
    height: int = Field(default=540, ge=180, le=720)
    marks: list[Mark] = Field(min_length=1, max_length=80)


def draw_frame(frame):
    """Only bounded drawing data runs here. No shell, network, SVG, or user code."""
    image = Image.new("RGB", (frame.width, frame.height), frame.background)
    draw = ImageDraw.Draw(image)
    font_names = {
        "sans": "DejaVuSans.ttf",
        "bold": "DejaVuSans-Bold.ttf",
        "serif": "DejaVuSerif.ttf",
    }
    for m in frame.marks:
        box = (m.x, m.y, m.x + m.w, m.y + m.h)
        if m.kind == "text":
            try:
                font = ImageFont.truetype(font_names[m.font], m.size)
            except OSError:
                font = ImageFont.load_default(size=m.size)
            draw.text(
                (m.x, m.y),
                m.text,
                fill=m.color,
                font=font,
                anchor={"left": "lt", "center": "mt", "right": "rt"}[m.align],
                spacing=8,
                align=m.align,
            )
        elif m.kind == "rect":
            draw.rounded_rectangle(
                box, radius=m.radius, fill=m.fill, outline=m.color, width=m.stroke_width
            )
        elif m.kind == "ellipse":
            draw.ellipse(box, fill=m.fill, outline=m.color, width=m.stroke_width)
        elif m.kind == "arc":
            draw.arc(box, m.start, m.end, fill=m.color, width=m.stroke_width)
        elif m.kind == "wave":
            pts = [
                (
                    m.x + m.w * i / 400,
                    m.y
                    + m.h
                    / 2
                    * math.sin(
                        2 * math.pi * m.cycles * i / 400 + math.radians(m.phase)
                    ),
                )
                for i in range(401)
            ]
            draw.line(pts, fill=m.color, width=m.stroke_width)
        elif m.kind in ("line", "polygon"):
            if len(m.points) < (3 if m.kind == "polygon" else 2):
                raise ValueError("Lines need two points and polygons need three")
            if not all(
                math.isfinite(v) and abs(v) <= 10000 for p in m.points for v in p
            ):
                raise ValueError("Drawing coordinates are out of bounds")
            if m.kind == "polygon":
                draw.polygon(
                    m.points, fill=m.fill, outline=m.color, width=m.stroke_width
                )
            else:
                draw.line(m.points, fill=m.color, width=m.stroke_width)
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


def register_direction(mcp, store, manager, muser, new_project, cards, write):
    @mcp.tool(annotations=write, meta=UI_META, title="First frame")
    async def propose_video(
        title: str, brief: str, frame: Frame, question: str, project_id: str = ""
    ) -> CallToolResult:
        """Legacy optional still proposal. Prefer start_video and cached motion references for new projects. This does not block rendering or require a reply."""
        uid = muser(True)
        if (
            not 1 <= len(title.strip()) <= 120
            or not 1 <= len(brief.strip()) <= 4000
            or not 1 <= len(question.strip()) <= 300
        ):
            raise ValueError("Provide a title, brief, and short design question")
        raw = await asyncio.to_thread(draw_frame, frame)
        pid = project_id
        if pid:
            store.project(uid, pid)
            if manager.lock(pid).locked():
                raise ValueError("Finish the current render before changing direction")
        else:
            pid = new_project(uid, title)["id"]
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "direction.png"
            local.write_bytes(raw)
            obj = await manager.save_object(uid, pid, "review", "direction.png", local)
        state = {
            "status": "proposed",
            "frame": frame.model_dump(),
            "preview_object": obj["id"],
            "question": question,
            "brief": brief,
        }
        store.put("direction", pid, state)
        preview = {
            "object_id": obj["id"],
            "media_type": "image/png",
            "name": "direction.png",
            "draft": True,
        }
        record_progress(
            store,
            pid,
            "style",
            "Proposed visual direction",
            "Use this optional still as a reference; continue independent work without mandatory approval.",
            brief,
            preview,
        )
        result = cards["media_result"](uid, pid)
        result.content = [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "project_id": pid,
                        "status": "proposed",
                        "question": question,
                        "next_action": "Describe the optional visual direction briefly and continue. Ask for input only if it materially affects the piece.",
                    }
                ),
            ),
            MCPImage(data=raw, format="png").to_image_content(),
        ]
        return result

    @mcp.tool(annotations=write, title="Use this visual direction")
    def accept_video_direction(project_id: str, user_feedback: str) -> dict:
        """Legacy: record actual feedback about a proposed still. New projects use start_video and plan_video; this is not a required gate."""
        uid = muser(True)
        store.project(uid, project_id)
        state = store.get("direction", project_id)
        if not state or not user_feedback.strip() or len(user_feedback) > 2000:
            raise ValueError("Show a proposed frame and obtain user feedback first")
        state.update(status="approved", user_feedback=user_feedback)
        store.put("direction", project_id, state)
        record_progress(
            store,
            project_id,
            "planning",
            "Developing the story from your direction.",
            "Write the story and EDL, then create a short motion draft. Show it when useful and continue unless genuinely blocked.",
            state["brief"],
        )
        return {
            "project_id": project_id,
            "status": "approved",
            "next_action": "Read relevant video_use_guidance now. Use run_video_step to save edit/project.md, edit/direction.json, edit/story.md and edit/edl.json along with the first animation source. Generate narration only after writing the script. Use the approved frame design as the visual reference. Show meaningful new motion and continue through final export.",
        }
