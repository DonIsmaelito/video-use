"""Adaptive creative context. Preferences steer work; they are not approval gates."""

import json
from copy import deepcopy
from pathlib import Path
from typing import Annotated, Literal

from mcp.types import CallToolResult, TextContent
from pydantic import BaseModel, Field
from .interaction import UI_META, UI_URI
from .creative_state import creative_edit
from .widgets import creative_public

Category = Literal[
    "explainer",
    "social_clips",
    "precise_edit",
    "software_demo",
    "brand",
    "footage_story",
    "data_story",
    "generative",
    "document_video",
    "audio_first",
    "personalized",
    "procedural_3d",
    "custom",
]
RECIPES = {
    "explainer": dict(
        choices=["diagram", "editorial"],
        steps=[
            "Define the audience and one takeaway",
            "Choose a structure that makes the mechanism, evidence or worked example understandable",
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
# These are composition hints, not a dispatch system. Existing category names
# remain stable because project state and cached client schemas contain them.
RECIPES.update(
    {
        "document_video": dict(
            choices=[],
            steps=[
                "Extract and inspect the source, retaining page or slide references",
                "Choose what to preserve, explain or omit for the intended audience",
                "Compose narration and visuals around supported claims",
                "Check source fidelity, pacing and document-specific caveats",
            ],
            question="Preserve the document's visual structure, or make a fresh visual explanation?",
            independent="Extract the source and identify its central claims while visual direction is undecided.",
            checks="Page and slide provenance, complete qualifiers, accurate numbers and readable visuals; extracted text is not a faithful slide rendering.",
        ),
        "audio_first": dict(
            choices=["captions_quiet", "captions_bold"],
            steps=[
                "Inspect the audio and identify the relevant timing or spoken passage",
                "Choose whether visuals support speech, lyrics, rhythm or mood",
                "Build synchronized captions, imagery or audio-reactive motion",
                "Review timing, audio quality and the complete viewing experience",
            ],
            question="Keep the voice in focus with subtle captions, or use a more expressive caption treatment?",
            independent="Measure duration and waveform or transcribe speech before committing to the visual treatment.",
            checks="No clipped audio or misleading speech edits; supplied lyrics and music timing need verification rather than assumed speech-ASR accuracy.",
        ),
        "personalized": dict(
            choices=[],
            steps=[
                "Validate the recipient data and separate shared content from variable facts",
                "Build one editable composition with explicit placeholders",
                "Check a representative small sample before bounded parallel variants",
                "Verify each output against its input record and requested language",
            ],
            question="Which details should feel personal, and which should stay identical across versions?",
            independent="Validate records and establish shared structure without inventing recipient facts.",
            checks="Correct recipient mapping, no cross-recipient data, locale-sensitive text and number formats, pronunciation and translation review.",
        ),
        "procedural_3d": dict(
            choices=[],
            steps=[
                "Inspect the supplied model or define the geometry needed to communicate the idea",
                "Prove geometry, lighting and the essential camera move cheaply",
                "Animate from absolute time with local assets and reproducible controls",
                "Inspect occlusion, surface quality, motion and render cost",
            ],
            question="Is fidelity to a real object essential, or can the visual be stylized?",
            independent="Inspect available models and prototype geometry before committing to polish.",
            checks="Real object fidelity when promised, local model dependencies, predictable camera and lighting; CPU/software WebGL is bounded and is not a photoreal render farm.",
        ),
        "custom": dict(
            choices=[],
            steps=[
                "Identify the actual inputs, desired outcome and missing capabilities",
                "Combine the relevant editing, motion, audio, data and scene primitives",
                "Prove the uncertain part first, then build and inspect the piece",
            ],
            question="What should this help the viewer see, feel or do?",
            independent="Inspect available material and test the uncertain operation without forcing the request into a template.",
            checks="Honor the requested medium and source truth; expose missing providers instead of substituting a different task silently.",
        ),
    }
)

WORKFLOW_DETAILS = {
    "explainer": dict(
        label="Educational and explanatory",
        inputs=[
            "Topic, audience and desired takeaway",
            "Source material for specialized or current claims",
        ],
        techniques=[
            "Manim geometry and diagrams",
            "Browser motion, typography and local images",
            "Narration with word timing",
        ],
        decision_points=[
            "Audience knowledge changes the level of explanation",
            "An established visual direction already answers the style question",
        ],
        limitations=[
            "No automatic factual research or source licensing; the host must supply verified facts and assets",
            "No fixed hook-mechanism-example structure is required",
        ],
        guidance=["workflows", "manim-video", "motion-design"],
    ),
    "social_clips": dict(
        label="Clips and social repurposing",
        inputs=[
            "Accessible source audio or video",
            "Platform, audience or requested moments when specified",
        ],
        techniques=[
            "Timed transcription and EDL selects",
            "Reframing and speaker tracking",
            "Caption and layout variants",
        ],
        decision_points=[
            "Source selection matters more than a style picker",
            "A caption example helps only when caption presentation is unresolved",
        ],
        limitations=[
            "A watch-page URL is not a downloadable media file",
            "Network-blocked rendering cannot scrape YouTube or read private cloud accounts",
        ],
        guidance=["workflows", "overview"],
    ),
    "precise_edit": dict(
        label="Specific edits and repairs",
        inputs=[
            "Accessible source",
            "The requested change and enough timing context to locate it",
        ],
        techniques=[
            "EDL cuts",
            "Audio and color treatment",
            "Captions, crop, overlays and re-encoding",
        ],
        decision_points=[
            "Ask only when a requested edit is ambiguous or would alter intended content"
        ],
        limitations=[
            "Removing a segment, cropping or masking is supported; generative object removal or reconstruction is not configured"
        ],
        guidance=["workflows", "overview"],
    ),
    "software_demo": dict(
        label="Software demonstrations and tutorials",
        inputs=[
            "Real recordings or screenshots and relevant product version",
            "The action or user outcome being demonstrated",
        ],
        techniques=[
            "Screen crops and callouts",
            "Tracked overlays",
            "Timed narration, captions and interface-focused motion",
        ],
        decision_points=[
            "Demonstrating a real workflow requires real UI evidence",
            "A fictional or conceptual mockup must be identified as such",
        ],
        limitations=[
            "No logged-in browser capture or remote product session is provided",
            "The host may supply capture from another tool; video-use cannot inherit it implicitly",
        ],
        guidance=["workflows", "overview", "motion-design"],
    ),
    "brand": dict(
        label="Marketing and commercial",
        inputs=[
            "Product facts, brand assets and audience",
            "A real offer or call to action if requested",
        ],
        techniques=[
            "Product and photo sequences",
            "Motion graphics, typography and local 3D",
            "Editable variant compositions",
        ],
        decision_points=[
            "A brand constraint, product truth or offer matters more than selecting a default template",
            "Show a visual reference only when materially different directions remain plausible",
        ],
        limitations=[
            "No automatic product photography, stock library, ad placement or conversion-testing service",
            "Do not invent testimonials, ratings, features, prices or offers",
        ],
        guidance=["workflows", "motion-design"],
    ),
    "footage_story": dict(
        label="Personal footage and montages",
        inputs=[
            "User-selected footage, photos and optional music",
            "Any important people, moments, order or exclusions",
        ],
        techniques=[
            "Photo and video sequencing",
            "Transcript-led or visual selects",
            "Sound transitions, titles and reframing",
        ],
        decision_points=[
            "Meaningful relationships, chronology and sensitive omissions may need a short question",
            "Default pacing is reversible; a mandatory template choice is unnecessary",
        ],
        limitations=[
            "No implicit access to Photos, Drive or local user folders",
            "Source provenance and real chronology must be preserved",
        ],
        guidance=["workflows", "overview"],
    ),
    "data_story": dict(
        label="Data and quantitative stories",
        inputs=[
            "A readable dataset with units, dates and definitions",
            "The comparison or question the viewer should understand",
        ],
        techniques=[
            "CSV/TSV/JSON/XLSX inspection",
            "Manim or browser charts and maps from local geometry",
            "Parameterized chart scenes",
        ],
        decision_points=[
            "Ask about conflicting units or incomparable measures",
            "Choose the chart to explain the data rather than enforce a visual preset",
        ],
        limitations=[
            "No live stock, weather, election or sports feed is configured",
            "Parsing data does not verify provenance or make missing values zero",
        ],
        guidance=["workflows", "manim-video", "motion-design"],
    ),
    "generative": dict(
        label="Generative and hybrid footage",
        inputs=[
            "Supplied generated media or an explicitly available external provider",
            "Continuity references and an intended shot list",
        ],
        techniques=[
            "Editing supplied generated clips",
            "Compositing, sound and caption finishing",
            "Procedural alternatives only when they fit the user's request",
        ],
        decision_points=[
            "Provider availability, asset continuity and generation budget change feasibility"
        ],
        limitations=[
            "No generative-video or image provider is configured in this MCP",
            "Do not relabel procedural animation as model-generated footage",
        ],
        guidance=["workflows", "overview", "motion-design"],
    ),
    "document_video": dict(
        label="Documents and presentations to video",
        inputs=[
            "Readable PDF, DOCX, PPTX, plain text or Markdown",
            "Desired audience and relationship to the original document",
        ],
        techniques=[
            "Document extraction with page or slide references",
            "Re-authored narration and visual explanation",
            "PDF page rasterization and supplied slide images with timing",
        ],
        decision_points=[
            "Faithful presentation versus editorial adaptation can change the whole result",
            "Dense claims may need shorter coverage rather than faster reading",
        ],
        limitations=[
            "Text extraction does not preserve slide layout, animation, scanned text or all document graphics; PDF page rasterization preserves appearance separately",
            "For exact presentation appearance, request slide images or a rendered PDF; no Office renderer or OCR is bundled",
        ],
        guidance=["workflows", "manim-video", "motion-design"],
    ),
    "audio_first": dict(
        label="Podcasts, lyrics and audio-led visuals",
        inputs=[
            "Supplied speech or music",
            "Cover art, timed lyrics or the desired visual intent where relevant",
        ],
        techniques=[
            "Audio-first picture sequences",
            "Waveform and spectral analysis",
            "Audio-reactive browser motion",
            "Word-timed speech captions",
        ],
        decision_points=[
            "Music, speech and lyrics require different timing evidence",
            "An established cover or visualizer request rarely needs a caption style picker",
        ],
        limitations=[
            "No music generation, stem separation or reliable singing alignment service is configured",
            "Long episodes may exceed per-task or daily compute limits",
        ],
        guidance=["workflows", "overview", "motion-design"],
    ),
    "personalized": dict(
        label="Personalized versions and localization",
        inputs=[
            "Explicit recipient or locale records",
            "Shared content and clearly defined variable fields",
        ],
        techniques=[
            "Data-bound text and scenes",
            "A small set of independent render components",
            "Host-authored translations and supplied or configured narration",
        ],
        decision_points=[
            "Validate representative long names, scripts and missing fields before scaling",
            "Consent to a sample video does not imply external distribution",
        ],
        limitations=[
            "Bounded small batches, not a campaign scheduler or mailer",
            "The speech tool uses one configured voice; voice cloning, lip sync and guaranteed multilingual dubbing are not implemented",
        ],
        guidance=["workflows", "motion-design", "overview"],
    ),
    "procedural_3d": dict(
        label="3D and procedural animation",
        inputs=[
            "An achievable geometric concept or an explicitly supplied local model",
            "Reference views if exact physical appearance matters",
        ],
        techniques=[
            "Three.js procedural meshes and local GLB/glTF",
            "Manim mathematical 3D",
            "Deterministic browser capture and compositing",
        ],
        decision_points=[
            "Exact product geometry requires appropriate assets",
            "Prove a complex model loads and renders before designing a long shot",
        ],
        limitations=[
            "Software WebGL with CPU and memory bounds; no dedicated GPU render service",
            "No Blender, CAD/BIM conversion, architectural model reconstruction or guaranteed photorealism",
        ],
        guidance=["workflows", "motion-design", "manim-video"],
    ),
    "custom": dict(
        label="Other or mixed requests",
        inputs=["Whatever material and constraints the intended result needs"],
        techniques=["Compose existing media, scene, data and audio primitives"],
        decision_points=[
            "Ask about the uncertain dependency rather than forcing a category questionnaire"
        ],
        limitations=[
            "Check the live capability report before promising an unfamiliar provider or renderer"
        ],
        guidance=["workflows"],
    ),
}


def workflow_summary(category: str) -> dict:
    """Return independent suggestions; callers may compose or ignore them."""
    if category not in RECIPES:
        raise ValueError(
            "Unknown video category; use custom for a mixed or unfamiliar request"
        )
    recipe = deepcopy(RECIPES[category])
    recipe["building_blocks"] = recipe.pop("steps")
    details = deepcopy(WORKFLOW_DETAILS[category])
    # Keep the extended category reference discoverable without making it a
    # compulsory first read before the agent can make anything.
    details["optional_technique_guidance"] = [
        topic for topic in details["guidance"] if topic not in ("workflows", "overview")
    ]
    if category in ("explainer", "brand", "data_story", "document_video"):
        details["optional_technique_guidance"].insert(0, "scenes")
    details["guidance"] = ["overview"]
    return dict(
        category=category,
        **details,
        **recipe,
        structure="Suggestions, not a required sequence or a fixed visual template. Combine workflows as needed.",
    )


def workflow_catalog() -> list[dict]:
    """Compact discovery; detailed hints are retrieved only for relevant work."""
    return [
        dict(
            category=key,
            label=value["label"],
            inputs=deepcopy(value["inputs"]),
            techniques=deepcopy(value["techniques"]),
        )
        for key, value in WORKFLOW_DETAILS.items()
    ]


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
    @creative_edit
    def start_video(
        title: str,
        brief: Annotated[
            str,
            Field(
                description="Faithful summary of what the user requested. Do not add inferred audience, content scope, style or format as if specified; save those in assumptions or the proposed plan."
            ),
        ],
        category: Category,
        preferences: str | None = None,
        project_id: str = "",
        supporting_categories: list[Category] | None = None,
        assumptions: Annotated[
            str | None,
            Field(
                description="Your proposed audience, scope, style and delivery format where the user left them open. These are reversible assumptions, not user instructions or approval. Omit to preserve earlier assumptions."
            ),
        ] = None,
    ) -> dict:
        """Start here for a new request. Infer category from intent, not a questionnaire. Keep brief faithful to the request and preferences limited to what the user ALREADY specified; put your proposed scope, audience, look and format in assumptions. State consequential assumptions and the script or outline briefly in chat before paid narration or substantial rendering, then continue without waiting for approval. Omit preferences/assumptions to preserve them; an empty string clears them. No workspace card or first-frame approval. Combine up to three supporting_categories for mixed media; use custom rather than forcing an unfamiliar request into a preset. Offer show_video_choices once if a relevant unresolved choice would materially change the piece, with a recommended default. Precise edits execute directly. Reuse project_id for revisions."""
        uid = muser(True)
        if (
            not title.strip()
            or len(title) > 120
            or not brief.strip()
            or len(brief) > 4000
            or (preferences is not None and len(preferences) > 2000)
            or (assumptions is not None and len(assumptions) > 2000)
        ):
            raise ValueError("Keep title, brief, preferences and assumptions concise")
        if supporting_categories is not None and len(supporting_categories) > 3:
            raise ValueError(
                "Use at most three supporting categories; the categories are hints, not a checklist"
            )
        if project_id:
            store.project(uid, project_id)
        pid = project_id or new_project(uid, title)["id"]
        old = store.get("creative", pid) or {}
        if old and old["category"] != category:
            # Reclassifying a request must not erase explicit choices or edits.
            # Retire category-specific picker state while keeping its user choice
            # as prior context, never as a selection in the new category.
            old = dict(old)
            if old.get("selected") and old.get("selection_source") == "user_click":
                old["visual_choice_history"] = old.get("visual_choice_history", []) + [
                    dict(
                        category=old["category"],
                        selected=old["selected"],
                        source="user_click",
                        creative_revision=old["revision"],
                    )
                ]
            for key in (
                "offered",
                "default",
                "selected",
                "selection_source",
                "supporting_categories",
            ):
                old.pop(key, None)
        supporting = list(
            dict.fromkeys(
                supporting_categories
                if supporting_categories is not None
                else old.get("supporting_categories", [])
            )
        )
        supporting = [c for c in supporting if c != category]
        state = old | dict(
            category=category,
            supporting_categories=supporting,
            brief=brief,
            brief_provenance="assistant_summary",
            preferences=preferences
            if preferences is not None
            else old.get("preferences", ""),
            assumptions=assumptions
            if assumptions is not None
            else old.get("assumptions", ""),
            revision=old.get("revision", 0) + 1,
            choice_revision=old.get("choice_revision", 0) + 1,
        )
        store.put("creative", pid, state)
        recipe = workflow_summary(category)
        return dict(
            project_id=pid,
            creative=creative_public(state),
            workflow=recipe,
            complementary_workflows=[workflow_summary(c) for c in supporting],
            next_action="Before narration or substantial original rendering, briefly state the proposed audience, look and format as assumptions. For a substantial new narrated story, use show_video_story to display an editable scene/script proposal before narration; it also saves the plan, so skip a separate plan_video call. If an unanswered audience or tone question materially changes the piece, use show_video_brief; use show_video_choices when motion references explain the decision better. Pick useful interactions, not every card. Keep working after showing them without an approval pause. Precise edits and delegated scripts need no questionnaire. Read only relevant guidance. Show one meaningful excerpt before all remaining scene code, with a short chat sentence about what is visible and what comes next. Apply the latest creative choices from task results before subsequent renders. Ask for a reply only when genuinely blocked or the user requests a checkpoint.",
            capabilities={
                "render": "Python, Manim, FFmpeg, browser motion and bounded procedural Three.js",
                "generative_video": False,
                "automatic_research_or_screen_capture": False,
                "campaign_delivery": False,
                "user_cloud_accounts": "Not automatically shared by the chat host; use explicitly supplied accessible assets.",
            },
        )

    @mcp.tool(annotations=write, meta=UI_META, title="Choose a visual approach")
    @creative_edit
    def show_video_choices(
        project_id: str,
        question: str = "",
        recommended: str = "",
        reference_ids: list[str] = [],
    ) -> CallToolResult:
        """Optional: show 2–3 cached motion references for an unresolved high-impact choice. These examples illustrate a technique, not coverage of every category; skip them when they do not fit (for example a music visualizer, faithful slide conversion or supplied style reference). Skip if the user specified a style, delegated choices, or requested a precise edit. Samples are references, NOT user drafts. Explain your default briefly and continue independent work. A click saves preference; do not require a click to proceed. Free-form chat can override these examples."""
        uid = muser(True)
        state = context(uid, project_id)
        recipe = RECIPES[state["category"]]
        offered = reference_ids or recipe["choices"]
        if not offered:
            raise ValueError(
                "This workflow does not need a style picker; ask a brief question only if necessary"
            )
        samples = catalog()
        if (
            not 2 <= len(offered) <= 3
            or len(set(offered)) != len(offered)
            or any(k not in samples for k in offered)
        ):
            raise ValueError(
                "Choose two or three distinct references from video_use_capabilities"
            )
        if len(question) > 300 or (recommended and recommended not in offered):
            raise ValueError("Choose a recommended reference from this workflow")
        options = [samples[k] | {"id": k} for k in offered]
        state["offered"] = offered
        state["default"] = recommended or offered[0]
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
            next_action=recipe["independent"]
            + " Briefly name the recommended default and continue if no answer arrives; a click is optional. Never claim the default was approved. Read the current creative state from subsequent task results before committing to more renders.",
        )
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=json.dumps(data),
                )
            ],
            structuredContent=data,
        )

    @mcp.tool(
        annotations=write,
        meta={"ui": {"resourceUri": UI_URI, "visibility": ["app"]}},
        title="Choose this style",
    )
    @creative_edit
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
        return dict(project_id=project_id, creative=creative_public(state))

    @mcp.tool(annotations=write, title="Shape the story")
    @creative_edit
    def plan_video(
        project_id: str, revision: int, beats: list[Beat], direction: str = ""
    ) -> dict:
        """Save your proposed beat plan and visual direction, preserving explicit user choices. The plan is authored by you; it is not evidence the user requested each detail or approved it. Share consequential direction briefly in chat and continue without an approval pause. Keep scenes independently editable. Use current creative state returned by task results; refresh get_video_project only if it may be stale. Use 1-12 beats, not always four. Precise edits need no new plan."""
        state = context(muser(True), project_id)
        if revision != state["revision"]:
            raise ValueError(
                "Creative preferences changed. Read get_video_project and adapt the plan."
            )
        if not 1 <= len(beats) <= 12 or len(direction) > 2000:
            raise ValueError("Use 1-12 concise beats and a short direction")
        # This outline has no narration fields. Keep the older editable story
        # in its widget, but do not present its script as aligned to this plan.
        state.pop("script", None)
        state.update(
            beats=[b.model_dump() for b in beats],
            direction=direction,
            plan_provenance="assistant_plan",
            revision=revision + 1,
        )
        store.put("creative", project_id, state)
        return dict(
            project_id=project_id,
            creative=creative_public(state),
            next_action="Make one meaningful excerpt with render_video_scene for compact 2D motion, or run_video_step for custom source. Defer unrelated scene code until it is visible; use show_video_preview when ready and keep working. Batch later independent renders. After narration alignment, pass actual ordered scene durations in production_timing with the assembled video so reviews and resumed edits use its real timeline. Continue through export unless real input is missing.",
        )
