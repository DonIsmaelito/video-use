"""Durable reference choices reported from host research and conversation.

This module neither searches nor downloads media. Inspection and user quotes
are attributed to the calling assistant; a URL is not proof of video playback.
"""

import hashlib
import ipaddress
import json
from copy import deepcopy
from datetime import datetime, timezone
from textwrap import shorten
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer, model_validator

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

    @model_serializer(mode="wrap")
    def serialized(self, handler):
        value = handler(self)
        if self.playback is None:
            value.pop("playback", None)  # Preserve earlier idempotent offer hashes.
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
            {item.url for item in references}
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
            "Call each reference's show_video_reference descriptor to show playable source media where available, keeping the source links visible, then ask this question once using native host questions when available. "
            "If native controls are unavailable or cannot fit every choice, use a short numbered chat question with all choices and the final free-input option. "
            "Do not build a custom form or gallery, paste tool arguments, or add an automatic delegation choice. "
            "If this presentation_key was already asked, wait for its answer. Use each choice's record_with arguments, "
            "adding a fresh request_id and the user's actual words as user_message. 'Give my input' opens a free-text reply; "
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
    if status in {"needed", "refining", "offered"}:
        from .reference_sources import reference_source_catalog

        context["source_catalog"] = reference_source_catalog(
            state.get("category"), compact=True
        )
    if status == "offered":
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
                **({"show_video_reference": {
                    "name": "show_video_reference",
                    "arguments": {"project_id": project_id, "reference_id": item["id"], "round_id": current["id"]},
                }} if project_id else {}),
            }
            for item in current.get("references", [])
        ]
        if current.get("id"):
            context["question"] = reference_question(state, current, project_id)
        context["next_action"] = (
            "Show these 1–5 real references once using each link_card's show_video_reference tool descriptor: play source media where available and retain a titled source link as fallback. "
            "These are source players, not generated project snippets. A short source clip must not be described as the complete film. "
            "Then present the supplied question using native host questions if available; no custom form or gallery. "
            "List each current reference and keep Give my input as the final free-text option. Record the actual choice with select or actual feedback with refine. "
            "A page or image inspection is not video playback. Wait for the user's choice before creating a snippet; do not begin production yet."
        )
    elif status == "refining":
        context["next_action"] = (
            "Use the saved rejection and any earlier likes to improve the search. If the feedback does not identify what to change, ask one focused "
            "contrast question in native questions or ordinary chat before searching again. Run a new query-specific search with available host tools, "
            "compare and inspect promising candidates, then record a new search and offer. Preserve liked traits while changing disliked ones. "
            "The registry lists places to search, not preselected examples. Do not recycle rejected examples unchanged or infer acceptance."
        )
    elif status in {"accepted", "delegated"}:
        context["next_action"] = (
            "Combine the original query with the chosen reference and requested traits to make one representative motion snippet. "
            "Show the snippet, then ask whether to continue or what to change using a native question if available or a short chat question. "
            "Revise when requested; only the user's explicit approval unlocks the full film. Preserve compatible work. "
            "References are inspiration, not a license to import their media."
        )
    else:
        context["next_action"] = (
            "Before creation, derive a visual search intent from this brief, then search suitable curated collections live using host tools. "
            "Search independent sources in parallel where supported, compare a small candidate pool, inspect promising material, and offer at most five distinct actual references. "
            "One good reference is sufficient; five is a maximum, not a quota. Record the search evidence and reasons for the choices. "
            "Collection order and prior research examples are not recommendations. "
            "Never invent candidates to meet a quota or claim video playback from page metadata. "
            "Use browse_video_references for live browser search and visual inspection where host tools fall short; save returned evidence_ids. Save playback.url and playback.browser_request_id from the cited page's actual videos, embedded_players, or YouTube/Vimeo links so the user can play the source before choosing. "
            "If both research paths or suitable approved sources are unavailable, ask for a user reference or explicit delegation. "
            "Record that actual reply with action delegate; silence is not delegation."
        )
    return context


def register_references(mcp, store, muser, read, write):
    @mcp.tool(annotations=write, title="Record visual references")
    @creative_edit
    def record_video_references(
        project_id: str,
        creative_revision: int,
        request_id: str,
        action: Literal["offer", "select", "refine", "delegate"],
        references: list[Reference] | None = None,
        selected_ids: list[str] | None = None,
        direction: str = "",
        user_message: str = "",
        search: ReferenceSearch | None = None,
    ) -> dict:
        """Save live, brief-specific reference research or the user's response without displaying an app. This tool does NOT search or inspect: use host tools or browse_video_references first. Each offer requires search: search_intent, actual search_queries (empty for direct browsing), candidates with reference/evidence_note/fit/limitations/disposition, selection_reason, coverage_limitations. Compare relevance, design differences and production feasibility; no fixed candidate quota or fabricated rejections. Offer 1–5 inspected references, never more than five; their records must match the recommended candidates exactly. Save optional playback:{url,browser_request_id} from a cited page's actual Browser Harness videos, embedded_players or YouTube/Vimeo links. Invoke returned show_video_reference descriptors to let the user play available sources, then ask the native reference-choice question with a final free-input option. No custom choice widget; source playback is separate from project creation. Record page/image/video evidence honestly: only actual motion inspection supports pacing claims. web_search entries need curated source_id and discovery_url. The registry supplies search locations, never preapproved example videos. Select current IDs, refine with actual user feedback and new research, or delegate only on explicit user request to skip. Selection unlocks a snippet, not the full video. Decisions quote user_message. All inspection and user quotes are assistant-reported, not independently verified."""
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
        if action not in {"offer", "select", "refine", "delegate"}:
            raise ValueError("Choose offer, select, refine, or delegate")
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
        # Omit absent search to preserve exact retry hashes from earlier clients.
        if search is not None:
            payload["search"] = search.model_dump()
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        state = deepcopy(store.get("creative", project_id) or {})
        reference = state.get("intake", {}).get("reference_direction", {})

        def result(repeated=False):
            context = reference_context(state, project_id)
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
            return result(repeated=True)
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
        if action == "offer":
            if status not in {"needed", "refining"}:
                raise ValueError(
                    "Record the user's response to the current direction before replacing its references"
                )
            if selected_ids:
                raise ValueError("An offer cannot select references for the user")
            if not references:
                raise ValueError(
                    "Offer 1–5 actual references; five is a maximum, not a quota"
                )
            if len({item.id for item in references}) != len(references) or len(
                {item.url for item in references}
            ) != len(references):
                raise ValueError(
                    "Offer references with distinct stable IDs and source URLs"
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
            for candidate in search.candidates:
                validate_reference_source(candidate.reference.model_dump())
                if candidate.reference.playback:
                    from .reference_playback import observed_playback

                    observed_playback(store, uid, project_id, candidate.reference.model_dump())
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
            reference["rounds"] = (
                rounds
                + [
                    dict(
                        id=ident(),
                        references=payload["references"],
                        search=comparison,
                        status="offered",
                    )
                ]
            )[-6:]
            reference.update(
                status="offered",
                selected_ids=[],
                direction=payload["direction"],
                decision_source=None,
                user_message="",
            )
        else:
            if search is not None:
                raise ValueError("Save search evidence with action offer only")
            if references:
                raise ValueError(
                    "Save new references with action offer; do not replace them while recording a response"
                )
            if not payload["user_message"]:
                raise ValueError(
                    "Quote the user's explicit reply in user_message; silence is not a decision"
                )
            if action == "select":
                if status != "offered" or not rounds:
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
                if action == "refine":
                    if status not in {"offered", "accepted", "delegated", "refining"}:
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
                                    )
                                ]
                            )[-6:],
                        )
                    reference.update(status="refining", selected_ids=[])
                else:
                    reference.update(status="delegated", selected_ids=[])
            reference.update(
                direction=payload["direction"],
                user_message=payload["user_message"],
                decision_source="assistant_reported_user",
            )
            if action != "select":
                reference.pop("selected_references", None)
        state["intake"]["excerpt_review"] = {"status": "not_requested"}
        state["revision"] = int(state.get("revision", 0)) + 1
        reference["receipts"] = (
            reference.get("receipts", []) + [dict(request_id=request_id, digest=digest)]
        )[-40:]
        store.put("creative", project_id, state)
        return result()
