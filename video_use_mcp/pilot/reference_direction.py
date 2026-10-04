"""Durable reference choices reported from host research and conversation.

This module neither searches nor downloads media. Inspection and user quotes
are attributed to the calling assistant; a URL is not proof of video playback.
"""

import hashlib
import ipaddress
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from textwrap import shorten
from typing import Literal
from urllib.parse import parse_qsl, urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_serializer,
    model_validator,
)

from .creative_state import creative_edit
from .store import ident


def public_reference_url(value: str) -> str:
    """Accept public HTTP(S) reference locations without fetching or resolving."""
    if not value or len(value) > 2048 or any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError("Use a public HTTP(S) reference URL")
    if "\\" in value:
        raise ValueError("Use a public HTTP(S) reference URL")
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").rstrip(".").lower()
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Use a valid public reference URL") from exc
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 80, 443}
        or "%" in host
    ):
        raise ValueError("Use a public HTTP(S) URL without credentials or custom ports")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if (
            "." not in host
            or host.endswith(
                (
                    ".localhost",
                    ".local",
                    ".internal",
                    ".lan",
                    ".home",
                    ".test",
                    ".invalid",
                )
            )
            or all(part.isdigit() for part in host.split("."))
            or not all(
                part and all(c.isalnum() or c == "-" for c in part)
                for part in host.split(".")
            )
        ):
            raise ValueError("Local or non-public reference URLs are not allowed")
    else:
        if not address.is_global:
            raise ValueError("Local or non-public reference URLs are not allowed")
    return value


def reference_work_key(value):
    """Recognize known post aliases and strip tracking without merging real URLs."""
    from .social_references import social_post

    try:
        post = social_post(value)
        return (post["platform"], post["post_id"])
    except ValueError:
        pass
    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    path = parsed.path.rstrip("/") or "/"
    if host in {"vimeo.com", "player.vimeo.com"}:
        match = re.fullmatch(r"/(?:video/)?([0-9]{1,12})(?:/[a-fA-F0-9]+)?", path)
        if match:
            return ("vimeo", match.group(1))
    query = tuple(
        sorted(
            (key, val)
            for key, val in parse_qsl(parsed.query, keep_blank_values=True)
            if not key.lower().startswith("utm_")
            and key.lower() not in {"fbclid", "gclid"}
        )
    )
    return (host, path, query)


class ReferencePlayback(BaseModel):
    """A source URL observed in one actual Browser Harness page receipt."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    url: str = Field(min_length=1, max_length=2048)
    browser_request_id: str = Field(min_length=1, max_length=120)

    @field_validator("url")
    @classmethod
    def public_media(cls, value):
        public_reference_url(value)
        parsed = urlsplit(value)
        if parsed.scheme != "https" or parsed.port not in {None, 443}:
            raise ValueError("Reference playback needs a public HTTPS URL")
        return value


class Reference(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,59}$")
    title: str = Field(min_length=1, max_length=160)
    url: str = Field(min_length=1, max_length=2048)
    observed_traits: str = Field(min_length=1, max_length=1200)
    inspection: Literal["metadata", "page", "image", "video"]
    source: Literal["web_search", "user_supplied"] = "web_search"
    source_id: str = Field(default="", max_length=100)
    discovery_url: str = Field(default="", max_length=2048)
    evidence_ids: list[str] = Field(default_factory=list, max_length=6)
    playback: ReferencePlayback | None = None
    social_receipt_id: str = Field(default="", max_length=120)

    @model_serializer(mode="wrap")
    def serialized(self, handler):
        value = handler(self)
        if self.playback is None:
            value.pop("playback", None)  # Preserve earlier idempotent offer hashes.
        if not self.social_receipt_id:
            value.pop("social_receipt_id", None)
        return value

    @field_validator("url")
    @classmethod
    def valid_url(cls, value):
        return public_reference_url(value)

    @field_validator("discovery_url")
    @classmethod
    def valid_discovery(cls, value):
        return public_reference_url(value) if value else value


class CandidateEvaluation(BaseModel):
    """One candidate examined for this brief, not a reusable recommendation."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reference: Reference
    evidence_note: str = Field(min_length=1, max_length=800)
    fit: str = Field(min_length=1, max_length=800)
    limitations: str = Field(min_length=1, max_length=800)
    disposition: Literal["recommend", "reserve", "reject"]


class ReferenceSearch(BaseModel):
    """Assistant-reported, query-specific inspection and comparison record."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    search_intent: str = Field(min_length=1, max_length=1200)
    search_queries: list[str] = Field(default_factory=list, max_length=8)
    candidates: list[CandidateEvaluation] = Field(min_length=1, max_length=12)
    selection_reason: str = Field(min_length=1, max_length=1200)
    coverage_limitations: str = Field(min_length=1, max_length=800)
    elapsed_seconds: float | None = Field(
        default=None, ge=0, le=86400, allow_inf_nan=False
    )

    @field_validator("search_queries")
    @classmethod
    def valid_queries(cls, values):
        if any(not value.strip() or len(value) > 500 for value in values):
            raise ValueError("Keep actual search queries within 1–500 characters")
        return [value.strip() for value in values]

    @model_validator(mode="after")
    def distinct_candidates(self):
        references = [candidate.reference for candidate in self.candidates]
        if len({item.id for item in references}) != len(references) or len(
            {reference_work_key(item.url) for item in references}
        ) != len(references):
            raise ValueError("Candidate evaluations need distinct IDs and URLs")
        return self


def search_summary(search):
    """Keep routine context small; the full comparison stays in project history."""
    if not search:
        return None
    return {
        key: deepcopy(search[key])
        for key in (
            "search_intent",
            "search_queries",
            "selection_reason",
            "coverage_limitations",
            "recorded_at",
            "elapsed_seconds",
        )
        if key in search
    } | {
        "candidate_count": len(search["candidates"]),
        "recommended_evidence": [
            {
                "id": candidate["reference"]["id"],
                **{
                    key: candidate[key]
                    for key in ("evidence_note", "fit", "limitations")
                },
            }
            for candidate in search["candidates"]
            if candidate["disposition"] == "recommend"
        ],
        "other_candidates": [
            {
                "id": candidate["reference"]["id"],
                "title": candidate["reference"]["title"],
                "url": candidate["reference"]["url"],
                "disposition": candidate["disposition"],
                "fit": candidate["fit"][:300],
                "limitations": candidate["limitations"][:300],
            }
            for candidate in search["candidates"]
            if candidate["disposition"] != "recommend"
        ],
    }


def reference_question(state, current, project_id=None):
    """Describe a host-native choice, without allocating or rendering an app."""

    def recorder(action, **values):
        if not project_id:
            return {}
        return {
            "record_with": {
                "name": "record_video_references",
                "arguments": {
                    "project_id": project_id,
                    "creative_revision": state["revision"],
                    "action": action,
                    "round_id": current["id"],
                    **values,
                },
            }
        }

    options = [
        {
            "id": item["id"],
            "label": shorten(item["title"], width=80, placeholder="…"),
            "reference_id": item["id"],
            **recorder("select", selected_ids=[item["id"]]),
        }
        for item in current.get("references", [])
    ]
    options.append(
        {
            "id": "__another_batch__",
            "label": "Find another batch",
            "description": "Show different references while keeping my saved preferences.",
            **recorder("another_batch"),
        }
    )
    options.append(
        {
            "id": "__input__",
            "label": "Give my input",
            "description": "Describe a different direction, combine ideas, or share your own reference link.",
            "input": "text",
            **recorder("refine"),
        }
    )
    return {
        "id": current["id"],
        "presentation_key": f"references:{current['id']}",
        "presenter": "host",
        "presentation": "native_question_tool_if_available_else_short_chat",
        "status": "awaiting_user",
        "questions": [
            {
                "id": "reference_direction",
                "prompt": "Which reference should guide your video?",
                "options": options,
            }
        ],
        "required": ["reference_direction"],
        "instructions": (
            "Show only references not already displayed, using their stable presentation keys and show_video_reference descriptors for source thumbnails when available and original links. After each reference card, add one short conversational sentence about fit, with creator and observed engagement/date from saved social metadata when available. Then ask this question once using native host questions when available. "
            "If native controls are unavailable or cannot fit every choice, use a short numbered chat question with each reference, Find another batch and the final Give my input option. "
            "Do not build a custom form or gallery, paste tool arguments, or add an automatic delegation choice. "
            "If this presentation_key was already asked, wait for its answer. Use each choice's record_with arguments, "
            "adding a fresh request_id and the user's actual words as user_message. Find another batch records another_batch and immediately resumes research; do not demand a critique. 'Give my input' opens a free-text reply; "
            "the button label alone is not feedback. Record actual preferences or rejection as refine and inspect any new reference link before offering it. "
            "If the user explicitly chooses a combination of current references, record select with those IDs and their requested traits in direction. "
            "No answer is not acceptance. Only an explicit selection or user-requested delegation unlocks the snippet; full production still requires snippet approval."
        ),
    }


def reference_context(state, project_id=None):
    """Return current reference direction, without private receipts or full history."""
    if not isinstance(state, dict) or not isinstance(state.get("intake"), dict):
        return None
    reference = state["intake"].get("reference_direction")
    if not isinstance(reference, dict) or reference.get("version") != 1:
        return None
    status = reference.get("status", "needed")
    rounds = reference.get("rounds", [])
    current = rounds[-1] if rounds else {}
    context = {
        "version": 1,
        "status": status,
        "presenter": "host",
        "presentation": "native_question_tool_if_available_else_short_chat",
        "inspection_provenance": "assistant_reported_not_server_verified",
        "round_id": current.get("id"),
        "references": deepcopy(current.get("references", [])),
        "search_summary": search_summary(current.get("search")),
        "search_batches": [
            search_summary(batch) for batch in current.get("search_batches", [])
        ],
        "creation_approach": deepcopy(state["intake"].get("creation_approach", {})),
        "excluded_reference_urls": list(reference.get("excluded_reference_urls", [])),
        "selected_ids": deepcopy(reference.get("selected_ids", [])),
        "direction": reference.get("direction", ""),
        "decision_source": reference.get("decision_source"),
        "user_message": reference.get("user_message", ""),
        "recent_feedback": [
            {
                "round_id": item.get("id"),
                "events": deepcopy(item["feedback_events"]),
                "references": [
                    {
                        key: value
                        for key, value in ref.items()
                        if key in {"id", "title", "url"}
                    }
                    for ref in item.get("references", [])
                ],
                "previous_selection": deepcopy(item.get("selection")),
            }
            for item in rounds[-3:]
            if item.get("feedback_events")
        ],
        "selected_references": deepcopy(reference.get("selected_references", [])),
        "record_with": "record_video_references",
    }
    if status in {"needed", "refining", "collecting", "offered"}:
        from .reference_sources import reference_source_catalog

        context["source_catalog"] = reference_source_catalog(
            state.get("category"), compact=True
        )
    if status in {"collecting", "offered"}:
        context["link_presentation"] = (
            "native_link_preview_if_available_else_markdown_link"
        )
        context["link_cards"] = [
            {
                "id": item["id"],
                "title": item["title"],
                "url": item["url"],
                "description": shorten(
                    item["observed_traits"], width=240, placeholder="…"
                ),
                "inspection": item["inspection"],
                "presentation_key": f"reference:{current['id']}:{item['id']}",
                **({"social": deepcopy(item["social"])} if item.get("social") else {}),
                **(
                    {
                        "show_video_reference": {
                            "name": "show_video_reference",
                            "arguments": {
                                "project_id": project_id,
                                "reference_id": item["id"],
                                "round_id": current["id"],
                            },
                        }
                    }
                    if project_id
                    else {}
                ),
            }
            for item in current.get("references", [])
        ]
        if status == "offered" and current.get("id"):
            context["question"] = reference_question(state, current, project_id)
        context["next_action"] = (
            "Show only references not previously displayed, deduplicating by presentation_key; use each new link_card's show_video_reference descriptor immediately for a source thumbnail when available and a titled original source link. "
            "After each reference card, add one short fit explanation plus creator and sourced views/likes/date where saved social metadata is available; missing metrics are unavailable, not zero. Reference cards retain the original source link and do not generate project snippets. A short source clip must not be described as the complete film. "
            "Then present the supplied question using native host questions if available; no custom form or gallery. "
            "List each current reference, Find another batch, then Give my input as the final free-text option. Record the actual choice with select or actual feedback with refine. "
            "A page or image inspection is not video playback. Wait for the user's choice before creating a snippet; do not begin production yet."
        )
        if status == "collecting":
            context["more_expected"] = True
            context["next_action"] = (
                "Show the newly found reference immediately with its show_video_reference descriptor for a thumbnail when available and original source link, deduplicating by presentation_key, then one short fit explanation and sourced social attribution/engagement where available. "
                "Search YouTube, TikTok and X sequentially for the next candidate; inspect it, call inspect_social_reference for its identity and available metrics, and append it with social_receipt_id and its search evidence to this same round. "
                "Never hold the first reference card until a batch is complete or redisplay already shown references. "
                "Finish at at most five, without filler: set more_expected=false on the last append, or use finish if no more suitable references are found. "
                "After collection, ask one native question with each reference, Find another batch and Give my input. Do not ask the final choice question while still collecting. An explicit unsolicited choice may be saved with select to stop collection and proceed to the snippet."
            )
            if project_id:
                context["finish_with"] = dict(
                    name="record_video_references",
                    arguments=dict(
                        project_id=project_id,
                        creative_revision=state["revision"],
                        action="finish",
                        round_id=current["id"],
                    ),
                )
    elif status == "refining":
        context["next_action"] = (
            "Use saved preferences, earlier likes and feedback to improve the search; exclude every excluded_reference_urls work. If the feedback does not identify what to change, ask one focused "
            "contrast question in native questions or ordinary chat before searching again. Run a new query-specific search sequentially on YouTube, TikTok and X with available host tools. "
            "Inspect one promising candidate, use inspect_social_reference for available attribution and metrics, save social_receipt_id, and offer/show it immediately before searching for another. Add a short fit explanation between player cards. Finish with one native choice including Find another batch and Give my input. Preserve liked traits while changing disliked ones. "
            "The registry lists places to search, not preselected examples. Do not recycle rejected examples unchanged or infer acceptance."
        )
        if reference.get("search_request") == "another_batch":
            context["next_action"] = (
                "The user explicitly requested another batch. Resume research immediately with the existing brief, creation approach and saved preferences; "
                "do not ask them to invent a critique. Exclude excluded_reference_urls and find different works. "
                "Search YouTube, TikTok and X sequentially. Inspect the first useful reference, call inspect_social_reference and save social_receipt_id, then offer it with more_expected=true and show its player immediately with one short fit sentence and available sourced engagement. Append others one at a time as found; finish with a native question including Find another batch and Give my input. "
                "Keep the user's earlier likes and dislikes; another batch is not permission to change their video direction or begin production."
            )
    elif status in {"accepted", "delegated"}:
        context["next_action"] = (
            "Combine the original query with the chosen reference and requested traits to make one representative motion snippet. "
            "Show the snippet, then ask whether to continue or what to change using a native question if available or a short chat question. "
            "Revise when requested; only the user's explicit approval unlocks the full film. Preserve compatible work. "
            "For a selected video, download and measure it before recreating the treatment with the user's content; do not substitute the reference itself for the output."
        )
    else:
        context["next_action"] = (
            "Before creation, derive a visual search intent from this brief and selected approach. Use YouTube, TikTok and X as primary sources; specialist collections are supplemental when requested or after explaining why primary sources did not fit. "
            "Search sequentially with host tools: inspect one useful candidate, call inspect_social_reference for available attribution/engagement and save social_receipt_id, offer it immediately with more_expected=true, then show its source thumbnail when available and original link with a short conversational fit explanation before searching for the next. Append later candidates as found. Usually three useful references, at most five, then finish and ask one native question listing references, Find another batch and Give my input. "
            "One good reference is sufficient; five is a maximum, not a quota. Record search evidence and reasons for the choices. Use only sourced creator/engagement and observation dates after each reference card; unknown counts are unavailable, never zero or evidence of popularity. oEmbed verifies identity, not visual inspection or popularity. "
            "Collection order and prior research examples are not recommendations. "
            "Never invent candidates to meet a quota or claim video playback from page metadata. "
            "Use browse_video_references for live browser search and visual inspection where host tools fall short; save returned evidence_ids. Save playback.url and playback.browser_request_id from the cited page's actual videos, embedded_players, or YouTube/Vimeo links so the reference card can link to the observed source before choosing. "
            "If both research paths or suitable approved sources are unavailable, ask for a user reference or explicit delegation. "
            "Record that actual reply with action delegate; silence is not delegation."
        )
    if status == "accepted":
        from .reference_clone import clone_context

        clone = clone_context(reference, project_id)
        if clone:
            context["clone"] = clone
            context["next_action"] = clone["next_action"]
    return context


def register_references(mcp, store, muser, read, write):
    @mcp.tool(annotations=write, title="Record visual references")
    @creative_edit
    def record_video_references(
        project_id: str,
        creative_revision: int,
        request_id: str,
        action: Literal[
            "offer", "append", "finish", "select", "refine", "another_batch", "delegate"
        ],
        references: list[Reference] | None = None,
        selected_ids: list[str] | None = None,
        direction: str = "",
        user_message: str = "",
        search: ReferenceSearch | None = None,
        more_expected: bool = False,
        round_id: str = "",
    ) -> dict:
        """Save live, brief-specific reference research or the user's response without displaying an app. This tool does NOT search or inspect. Search YouTube, TikTok and X sequentially with host tools or browse_video_references. Inspect one candidate; for supported YouTube, TikTok or X posts call inspect_social_reference and save its social_receipt_id for observed identity and available engagement. Do not send unsupported studio links to the social-post tool. Specialist collections are supplemental when requested or primary sources do not fit. Offer the first inspected candidate with more_expected=true and display its source thumbnail when available and original link immediately followed by one short fit explanation, creator and sourced views/likes/date where available; append each new candidate to the same round_id as found with its own search record. Use more_expected=false on the final append or finish with no new candidates. At five references collection finishes automatically. Legacy offer defaults to a completed batch. Each offer or append requires search: search_intent, actual search_queries (empty for direct browsing), candidates with reference/evidence_note/fit/limitations/disposition, selection_reason, coverage_limitations. Compare relevance, design differences and production feasibility; no fixed candidate quota or fabricated rejections. Offer 1–5 inspected references, never more than five; their records must match the recommended candidates exactly. Save optional playback:{url,browser_request_id} from a cited page's actual Browser Harness videos, embedded_players or YouTube/Vimeo links. Invoke returned show_video_reference descriptors to show source thumbnails when available and original links, then ask the native reference-choice question including Find another batch and final Give my input. Never invent metrics or interpret missing counts as zero; oEmbed does not prove popularity or visual inspection. No custom choice widget; reference presentation is separate from project creation. Record page/image/video evidence honestly: only actual motion inspection supports pacing claims. web_search entries need curated source_id and discovery_url. The registry supplies search locations, never preapproved example videos. Select current IDs (including an explicit early choice while collecting), refine with actual user feedback, another_batch on the explicit Find another batch request without demanding a critique, or delegate only on explicit user request to skip. Keep saved preferences and exclude previously rejected works in new batches. Selection unlocks a snippet, not the full video. Decisions quote user_message. Visual inspection and user quotes remain assistant-reported; social metadata is hydrated only from the saved server receipt."""
        uid = muser(True)
        store.project(uid, project_id)
        if (
            not isinstance(request_id, str)
            or not request_id.strip()
            or len(request_id) > 120
        ):
            raise ValueError("Provide a request ID of 1–120 characters")
        if len(direction) > 2400 or len(user_message) > 4000:
            raise ValueError(
                "Keep direction within 2400 characters and the user reply within 4000"
            )
        if action not in {
            "offer",
            "append",
            "finish",
            "select",
            "refine",
            "another_batch",
            "delegate",
        }:
            raise ValueError(
                "Choose offer, append, finish, select, refine, another_batch, or delegate"
            )
        if len(round_id) > 120:
            raise ValueError("Keep the round ID within 120 characters")
        if more_expected and action not in {"offer", "append"}:
            raise ValueError("more_expected is only for offer or append")
        references = [
            item if isinstance(item, Reference) else Reference.model_validate(item)
            for item in references or []
        ]
        if search is not None and not isinstance(search, ReferenceSearch):
            search = ReferenceSearch.model_validate(search)
        selected_ids = selected_ids or []
        if len(references) > 5 or len(selected_ids) > 5:
            raise ValueError("Use at most five reference choices")
        payload = dict(
            creative_revision=creative_revision,
            action=action,
            references=[item.model_dump() for item in references],
            selected_ids=selected_ids,
            direction=direction.strip(),
            user_message=user_message.strip(),
        )
        if more_expected:
            payload["more_expected"] = True
        if round_id:
            payload["round_id"] = round_id
        # Omit absent search to preserve exact retry hashes from earlier clients.
        if search is not None:
            payload["search"] = search.model_dump()
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        state = deepcopy(store.get("creative", project_id) or {})
        reference = state.get("intake", {}).get("reference_direction", {})

        def result(repeated=False, new_reference_ids=None, presentation_round_id=None):
            context = reference_context(state, project_id)
            if presentation_round_id and presentation_round_id != context.get(
                "round_id"
            ):
                new_reference_ids = []
            if new_reference_ids is not None:
                context["new_reference_ids"] = list(new_reference_ids)
                context["new_link_cards"] = [
                    card
                    for card in context.get("link_cards", [])
                    if card["id"] in new_reference_ids
                ]
            return dict(
                project_id=project_id,
                creative_revision=state["revision"],
                saved=True,
                repeated=repeated,
                reference_direction=context,
                next_action=context["next_action"],
            )

        receipt = next(
            (
                item
                for item in reference.get("receipts", [])
                if item["request_id"] == request_id
            ),
            None,
        )
        if receipt:
            if receipt["digest"] != digest:
                raise ValueError(
                    "This request ID already records a different reference action; use a new request_id"
                )
            return result(
                repeated=True,
                new_reference_ids=receipt.get("new_reference_ids"),
                presentation_round_id=receipt.get("presentation_round_id"),
            )
        if not state or state.get("revision") != creative_revision:
            raise ValueError(
                "Creative direction changed; read the current project revision before recording references"
            )
        # Local import avoids a cycle: intake_context also exposes reference_context.
        from .intake import intake_context

        intake = intake_context(state, project_id)
        if not intake or intake["mode"] != "hands_on":
            raise ValueError(
                "Reference direction is for a project with explicit Hands on involvement"
            )
        if intake["phase"] in {"mode", "basics", "approach", "personalization"}:
            raise ValueError(
                "Answer the pending involvement, basics, video type, content, or style question before recording references"
            )
        if reference.get("version") not in {None, 1}:
            raise ValueError("This reference workflow version is not supported")
        if not reference:
            reference = dict(version=1, status="needed", rounds=[])
            state["intake"]["reference_direction"] = reference
        status = reference.get("status", "needed")
        rounds = reference.setdefault("rounds", [])
        if round_id and (not rounds or rounds[-1].get("id") != round_id):
            raise ValueError(
                "This reference round is outdated; read the current reference choices"
            )
        if action in {"append", "finish"} and not round_id:
            raise ValueError(
                "Supply the current round_id when appending or finishing references"
            )
        new_reference_ids = None
        if action in {"offer", "append"}:
            if action == "offer" and status not in {"needed", "refining"}:
                raise ValueError(
                    "Record the user's response to the current direction before replacing its references"
                )
            if action == "append" and (status != "collecting" or not rounds):
                raise ValueError(
                    "Append references only to the current collecting round"
                )
            if selected_ids:
                raise ValueError("An offer cannot select references for the user")
            if not references:
                raise ValueError(
                    "Offer 1–5 actual references; five is a maximum, not a quota"
                )
            if len({item.id for item in references}) != len(references) or len(
                {reference_work_key(item.url) for item in references}
            ) != len(references):
                raise ValueError(
                    "Offer references with distinct stable IDs and source URLs"
                )
            previous_references = rounds[-1]["references"] if action == "append" else []
            combined = previous_references + payload["references"]
            if len(combined) > 5:
                raise ValueError("Use at most five reference choices in this round")
            if len({item["id"] for item in combined}) != len(combined) or len(
                {reference_work_key(item["url"]) for item in combined}
            ) != len(combined):
                raise ValueError(
                    "Appended references must have new distinct IDs and source URLs"
                )
            excluded = {
                reference_work_key(url)
                for url in reference.get("excluded_reference_urls", [])
            }
            if any(reference_work_key(item.url) in excluded for item in references):
                raise ValueError(
                    "These works were rejected in an earlier batch; find different references"
                )
            from .reference_sources import validate_reference_source

            for item in references:
                validate_reference_source(item.model_dump())
            if search is None:
                raise ValueError(
                    "Record this brief's live search, candidate evidence and comparison in search before offering references"
                )
            recommended = {
                candidate.reference.id: candidate.reference.model_dump()
                for candidate in search.candidates
                if candidate.disposition == "recommend"
            }
            if recommended != {item.id: item.model_dump() for item in references}:
                raise ValueError(
                    "Offered references must match the recommended candidate records exactly"
                )
            social_evidence = {}
            for candidate in search.candidates:
                validate_reference_source(candidate.reference.model_dump())
                if candidate.reference.social_receipt_id:
                    from .social_references import validate_social_receipt

                    social_evidence[candidate.reference.id] = validate_social_receipt(
                        store,
                        uid,
                        project_id,
                        candidate.reference.social_receipt_id,
                        candidate.reference.url,
                    )
                if candidate.reference.playback:
                    from .reference_playback import observed_playback

                    observed_playback(
                        store, uid, project_id, candidate.reference.model_dump()
                    )
                for evidence_id in candidate.reference.evidence_ids:
                    evidence = store.get("reference_browser_evidence", evidence_id)
                    if (
                        not evidence
                        or evidence.get("owner") != uid
                        or evidence.get("project") != project_id
                    ):
                        raise ValueError(
                            "Reference evidence must belong to this project"
                        )
                    cited_urls = {
                        candidate.reference.url,
                        candidate.reference.discovery_url,
                    } - {""}
                    if not cited_urls.intersection(
                        {evidence.get("page_url"), evidence.get("source_page_url")}
                    ):
                        raise ValueError(
                            "Reference evidence must show the cited reference or discovery page"
                        )
            comparison = deepcopy(payload["search"])
            comparison["recorded_at"] = datetime.now(timezone.utc).isoformat()
            new_references = deepcopy(payload["references"])
            for item in new_references:
                if item["id"] in social_evidence:
                    item["social"] = deepcopy(social_evidence[item["id"]])
            for candidate in comparison["candidates"]:
                if candidate["reference"]["id"] in social_evidence:
                    candidate["reference"]["social"] = deepcopy(
                        social_evidence[candidate["reference"]["id"]]
                    )
            new_reference_ids = [item["id"] for item in new_references]
            next_status = (
                "collecting" if more_expected and len(combined) < 5 else "offered"
            )
            if action == "append":
                rounds[-1]["references"].extend(new_references)
                rounds[-1]["search_batches"] = rounds[-1].get(
                    "search_batches", [deepcopy(rounds[-1]["search"])]
                ) + [comparison]
                rounds[-1]["status"] = next_status
                reference["status"] = next_status
            else:
                reference["rounds"] = (
                    rounds
                    + [
                        dict(
                            id=ident(),
                            references=new_references,
                            search=comparison,
                            search_batches=[comparison],
                            status=next_status,
                        )
                    ]
                )[-6:]
                reference.update(
                    status=next_status,
                    selected_ids=[],
                    direction=payload["direction"] or reference.get("direction", ""),
                    decision_source=None,
                    user_message="",
                )
                reference.pop("search_request", None)
        elif action == "finish":
            if status != "collecting" or not rounds:
                raise ValueError("Finish only the current collecting reference round")
            if (
                references
                or search is not None
                or selected_ids
                or direction
                or user_message
            ):
                raise ValueError(
                    "Finish closes the current batch without new references, research, or user choices"
                )
            reference["status"] = rounds[-1]["status"] = "offered"
            new_reference_ids = []
        else:
            if search is not None:
                raise ValueError(
                    "Save search evidence with action offer or append only"
                )
            if references:
                raise ValueError(
                    "Save new references with action offer or append; do not replace them while recording a response"
                )
            if not payload["user_message"]:
                raise ValueError(
                    "Quote the user's explicit reply in user_message; silence is not a decision"
                )
            if action == "select":
                if status not in {"offered", "collecting"} or not rounds:
                    raise ValueError(
                        "Select references from the current unanswered offer"
                    )
                offered = {item["id"]: item for item in rounds[-1]["references"]}
                if (
                    not selected_ids
                    or len(set(selected_ids)) != len(selected_ids)
                    or any(item not in offered for item in selected_ids)
                ):
                    raise ValueError(
                        "Select distinct reference IDs from the current offer"
                    )
                selected = [deepcopy(offered[item]) for item in selected_ids]
                reference.update(
                    status="accepted",
                    selected_ids=selected_ids,
                    selected_references=selected,
                )
                rounds[-1].update(
                    status="accepted",
                    selected_ids=selected_ids,
                    selection=dict(
                        selected_ids=selected_ids,
                        direction=payload["direction"],
                        user_message=payload["user_message"],
                        references=selected,
                    ),
                )
            else:
                if selected_ids:
                    raise ValueError(
                        "Reference IDs are only selected with action select"
                    )
                if action in {"refine", "another_batch"}:
                    if status not in {
                        "collecting",
                        "offered",
                        "accepted",
                        "delegated",
                        "refining",
                    }:
                        raise ValueError(
                            "Offer references before recording a rejection"
                        )
                    if status == "delegated" or not rounds:
                        # A user may reject a delegated direction before any
                        # search round exists. Keep that feedback and its basis
                        # when the next offer replaces the current direction.
                        rounds = (
                            rounds
                            + [
                                dict(
                                    id=ident(),
                                    references=[],
                                    status="delegated",
                                    selection=dict(
                                        direction=reference.get("direction", ""),
                                        user_message=reference.get("user_message", ""),
                                        references=[],
                                        selected_ids=[],
                                    ),
                                )
                            ]
                        )[-6:]
                        reference["rounds"] = rounds
                    if rounds:
                        rounds[-1].update(
                            status="rejected",
                            feedback_events=(
                                rounds[-1].get("feedback_events", [])
                                + [
                                    dict(
                                        user_message=payload["user_message"],
                                        direction=payload["direction"],
                                        **(
                                            {"kind": "another_batch"}
                                            if action == "another_batch"
                                            else {}
                                        ),
                                    )
                                ]
                            )[-6:],
                        )
                    rejected = (
                        [item["url"] for item in rounds[-1].get("references", [])]
                        if rounds
                        else []
                    )
                    reference["excluded_reference_urls"] = list(
                        dict.fromkeys(
                            reference.get("excluded_reference_urls", []) + rejected
                        )
                    )
                    reference.update(
                        status="refining",
                        selected_ids=[],
                        search_request="another_batch"
                        if action == "another_batch"
                        else "refine",
                    )
                else:
                    reference.update(status="delegated", selected_ids=[])
            reference.update(
                direction=(payload["direction"] or reference.get("direction", ""))
                if action == "another_batch"
                else payload["direction"],
                user_message=payload["user_message"],
                decision_source="assistant_reported_user",
            )
            if action != "select":
                reference.pop("selected_references", None)
        if action == "select":
            from .reference_clone import selection_key

            reference["clone"] = dict(
                version=1, selection_key=selection_key(reference), media={}
            )
        else:
            reference.pop("clone", None)
        state["intake"]["excerpt_review"] = {"status": "not_requested"}
        state["revision"] = int(state.get("revision", 0)) + 1
        reference["receipts"] = (
            reference.get("receipts", [])
            + [
                dict(
                    request_id=request_id,
                    digest=digest,
                    presentation_round_id=reference["rounds"][-1]["id"]
                    if reference.get("rounds")
                    else None,
                    **(
                        {"new_reference_ids": new_reference_ids}
                        if new_reference_ids is not None
                        else {}
                    ),
                )
            ]
        )[-40:]
        store.put("creative", project_id, state)
        return result(new_reference_ids=new_reference_ids)
