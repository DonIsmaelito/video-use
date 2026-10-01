"""Adaptive creative context. Preferences steer work; they are not approval gates."""

import json
from pathlib import Path
from typing import Literal

from mcp.types import CallToolResult, TextContent
from pydantic import BaseModel, Field
from .interaction import UI_META, UI_URI

Category = Literal[
    "explainer",
    "social_clips",
    "precise_edit",
    "software_demo",
    "brand",
    "footage_story",
    "data_story",
    "generative",
]
RECIPES = {
    "explainer": dict(
        choices=["diagram", "editorial"],
        steps=[
            "Define the audience and one takeaway",
            "Outline hook, mechanism, example, takeaway; vary this structure to fit the subject",
            "Write timed script and EDL; establish shared visual language",
            "Render independent scenes, assemble, inspect, export",
        ],
        question="Visual explanation with diagrams, or an editorial story?",
        independent="Research supplied material and outline the explanation while style is undecided.",
        checks="Factual accuracy, visual causality, reading time, narration alignment.",
    ),
    "social_clips": dict(
        choices=["captions_quiet", "captions_bold"],
        steps=[
            "Obtain source and transcript",
            "Choose self-contained moments with hooks",
            "Reframe around the speaker and add chosen captions",
            "Render independent clips, inspect crops and captions, export",
        ],
        question="Subtle subtitles or punchier captions?",
        independent="Transcribe and identify clip boundaries before choosing typography.",
        checks="No truncated sentences, speaker-safe crops, caption timing, correct aspect ratio.",
    ),
    "precise_edit": dict(
        choices=[],
        steps=[
            "Locate the source and exact requested change",
            "Apply only that change",
            "Check affected boundaries and export",
        ],
        question="",
        independent="Execute directly when source and intent are clear. No style picker or storyboard.",
        checks="Preserve unrequested content, audio sync, exact cut boundaries.",
    ),
    "software_demo": dict(
        choices=["demo_focus", "editorial"],
        steps=[
            "Obtain actual recording or screenshots and intended user outcome",
            "Plan action, result, explanation",
            "Align callouts and zooms to real interface changes",
            "Assemble and verify each demonstrated action",
        ],
        question="Focus on the interface, or tell a more visual product story?",
        independent="Inspect source and outline actions while presentation style is undecided.",
        checks="Readable interface, truthful UI, stable zooms, cursor and narration timing.",
    ),
    "brand": dict(
        choices=["editorial", "demo_focus"],
        steps=[
            "Extract product truth, audience, assets and brand constraints",
            "Choose a subject-specific visual premise",
            "Prove the hardest asset or transformation",
            "Build choreography, inspect and export",
        ],
        question="Editorial motion, or a focused product demonstration?",
        independent="Inventory brand assets and develop the central message.",
        checks="Brand consistency, strong hero subject, readable type, purposeful motion.",
    ),
    "footage_story": dict(
        choices=[],
        steps=[
            "Inspect source footage and audio",
            "Find the story and emotional arc",
            "Create selects and EDL",
            "Edit picture and sound, inspect and export",
        ],
        question="What should the viewer feel at the end?",
        independent="Create source selects before committing to pacing or music.",
        checks="Continuity, meaningful sequence, sound transitions, source provenance.",
    ),
    "data_story": dict(
        choices=["diagram", "editorial"],
        steps=[
            "Validate supplied data and central comparison",
            "Storyboard the claim and its evidence",
            "Animate independent charts with consistent scales",
            "Check numbers, assemble and export",
        ],
        question="Precise chart-led explanation, or a broader editorial story?",
        independent="Validate data and outline claims while style is undecided.",
        checks="Accurate scales and labels, sourced numbers, no misleading transitions.",
    ),
    "generative": dict(
        choices=[],
        steps=[
            "Identify supplied assets and required generated shots",
            "Confirm an available generation provider before promising generation",
            "Plan continuity and shot coverage",
            "Generate only through a configured provider, then edit and review",
        ],
        question="Which reference best captures the world or mood?",
        independent="Write the shot list and identify which assets are already available.",
        checks="Character and scene continuity, available provider, explicit costs. This service currently has no generative-video provider.",
    ),
}
MANIFEST = Path(__file__).parent / "references" / "manifest.json"


def catalog():
    return json.loads(MANIFEST.read_text())["samples"]


class Beat(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    visual: str = Field(min_length=1, max_length=400)
    seconds: float = Field(gt=0, le=600)


def register_workflow(mcp, store, muser, new_project, read, write):
    def context(uid, pid):
        store.project(uid, pid)
        state = store.get("creative", pid)
        if not state:
            raise ValueError("Start a creative brief with start_video first")
        return state

    @mcp.tool(annotations=write, title="Develop the video")
    def start_video(
        title: str,
        brief: str,
        category: Category,
        preferences: str = "",
        project_id: str = "",
    ) -> dict:
        """Start here for a new request. Infer category from intent, not a questionnaire. Save what the user ALREADY specified in preferences; do not invent answers. No workspace card, render or first-frame approval. Returns a tailored workflow. Use show_video_choices only if an unresolved creative choice would materially change the result. Precise edits execute directly. Missing source is a genuine blocker; style is usually a reversible default. Reuse project_id to revise the brief."""
        uid = muser(True)
        if (
            not title.strip()
            or len(title) > 120
            or not brief.strip()
            or len(brief) > 4000
            or len(preferences) > 2000
        ):
            raise ValueError("Keep title, brief and preferences concise")
        if project_id:
            store.project(uid, project_id)
        pid = project_id or new_project(uid, title)["id"]
        old = store.get("creative", pid) or {}
        if old and old["category"] != category:
            old = {
                "revision": old["revision"],
                "choice_revision": old.get("choice_revision", 0),
            }
        state = old | dict(
            category=category,
            brief=brief,
            preferences=preferences,
            revision=old.get("revision", 0) + 1,
            choice_revision=old.get("choice_revision", 0) + 1,
        )
        store.put("creative", pid, state)
        recipe = RECIPES[category]
        return dict(
            project_id=pid,
            creative=state,
            workflow=recipe,
            next_action="Read the relevant harness guidance, then make progress. Offer at most one compact set of meaningful choices when helpful; keep working on independent parts. State reversible defaults instead of waiting for approval. Ask for a reply only when genuinely blocked or the user requests a checkpoint.",
            capabilities={
                "render": "Python, Manim, FFmpeg, browser motion",
                "generative_video": False,
                "user_cloud_accounts": "Not automatically shared by the chat host; use explicitly supplied accessible assets.",
            },
        )

    @mcp.tool(annotations=write, meta=UI_META, title="Choose a visual approach")
    def show_video_choices(
        project_id: str, question: str = "", recommended: str = ""
    ) -> CallToolResult:
        """Optional: show TWO cached motion references for an unresolved high-impact choice. Skip if the user specified a style, delegated choices, or requested a precise edit. Samples are references, NOT user drafts. Explain your default briefly and continue independent work. A click saves preference; do not require a click to proceed. Free-form chat can override these examples."""
        uid = muser(True)
        state = context(uid, project_id)
        recipe = RECIPES[state["category"]]
        if not recipe["choices"]:
            raise ValueError(
                "This workflow does not need a style picker; ask a brief question only if necessary"
            )
        if len(question) > 300 or (
            recommended and recommended not in recipe["choices"]
        ):
            raise ValueError("Choose a recommended reference from this workflow")
        samples = catalog()
        options = [samples[k] | {"id": k} for k in recipe["choices"]]
        state["offered"] = recipe["choices"]
        state["default"] = recommended or recipe["choices"][0]
        store.put("creative", project_id, state)
        data = dict(
            project_id=project_id,
            choices=dict(
                question=question or recipe["question"],
                options=options,
                recommended=state["default"],
                selected=state.get("selected"),
                revision=state["choice_revision"],
            ),
        )
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=json.dumps(
                        data
                        | {
                            "next_action": recipe["independent"]
                            + " Continue with the stated default if no answer arrives. Never claim it was approved."
                        }
                    ),
                )
            ],
            structuredContent=data,
        )

    @mcp.tool(
        annotations=write,
        meta={"ui": {"resourceUri": UI_URI, "visibility": ["app"]}},
        title="Choose this style",
    )
    def choose_video_style(project_id: str, choice: str, revision: int) -> dict:
        """Save an explicit click in the reference picker. Reject outdated pickers and choices that were not offered."""
        state = context(muser(True), project_id)
        if revision != state["choice_revision"]:
            raise ValueError("This choice is outdated. Ask to see the latest options.")
        if choice not in state.get("offered", []):
            raise ValueError("Choose one of the offered references")
        state.update(
            selected=choice,
            selection_source="user_click",
            revision=state["revision"] + 1,
            choice_revision=revision + 1,
        )
        store.put("creative", project_id, state)
        return dict(project_id=project_id, creative=state)

    @mcp.tool(annotations=write, title="Shape the story")
    def plan_video(
        project_id: str, revision: int, beats: list[Beat], direction: str = ""
    ) -> dict:
        """Save a concise beat plan and actual conversational feedback (direction) for this run. This is context, not an approval gate. Summarize the story naturally in chat only when useful; continue working. Keep individual scenes independently renderable with shared visual rules. If preferences changed, reread get_video_project and adapt. Use 1-12 beats, not always four. For precise edits this tool is unnecessary."""
        state = context(muser(True), project_id)
        if revision != state["revision"]:
            raise ValueError(
                "Creative preferences changed. Read get_video_project and adapt the plan."
            )
        if not 1 <= len(beats) <= 12 or len(direction) > 2000:
            raise ValueError("Use 1-12 concise beats and a short direction")
        state.update(
            beats=[b.model_dump() for b in beats],
            direction=direction,
            revision=revision + 1,
        )
        store.put("creative", project_id, state)
        return dict(
            project_id=project_id,
            creative=state,
            next_action="Write the script and EDL; batch sources and independent renders in run_video_step. Show a meaningful motion draft, not an arbitrary first frame. Continue through review and export unless real input is missing.",
        )
