"""Durable reference choices reported from host research and conversation.

This module neither searches nor downloads media. Inspection and user quotes
are attributed to the calling assistant; a URL is not proof of video playback.
"""

import hashlib
import ipaddress
import json
from copy import deepcopy
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

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


class Reference(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,59}$")
    title: str = Field(min_length=1, max_length=160)
    url: str = Field(min_length=1, max_length=2048)
    observed_traits: str = Field(min_length=1, max_length=1200)
    inspection: Literal["page", "image", "video"]
    source: Literal["web_search", "user_supplied"] = "web_search"
    source_id: str = Field(default="", max_length=100)
    discovery_url: str = Field(default="", max_length=2048)

    @field_validator("url")
    @classmethod
    def valid_url(cls, value):
        return public_reference_url(value)

    @field_validator("discovery_url")
    @classmethod
    def valid_discovery(cls, value):
        return public_reference_url(value) if value else value


def reference_context(state):
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

        context["source_catalog"] = reference_source_catalog()
    if status == "offered":
        context["next_action"] = (
            "Show these real source links once in ordinary chat with brief observed traits and any available native previews. "
            "Use a native question only if available; no custom form or gallery. Ask which traits to use or combine, then record the explicit reply "
            "with action select or refine. A page or image inspection is not video playback. Do not begin production yet."
        )
    elif status == "refining":
        context["next_action"] = (
            "Use the saved rejection and any earlier likes to improve the search. If the feedback does not identify what to change, ask one focused "
            "contrast question in native questions or ordinary chat before searching again. Search the curated sources using available host tools, "
            "inspect the actual results, then offer a new round. Do not recycle rejected examples unchanged or infer acceptance."
        )
    elif status in {"accepted", "delegated"}:
        context["next_action"] = (
            "Use this explicit direction for the story and one representative motion excerpt. Preserve compatible work and follow the remaining "
            "hands-on review steps before the full film. References are inspiration, not a license to import their media."
        )
    else:
        context["next_action"] = (
            "Before creation, search the maintained source catalog with available host web tools for 2–3 relevant visual or video references, "
            "inspect the actual material, and record an offer. One user-supplied reference is sufficient. Do not invent links, observations, or video playback. "
            "If search or approved sources are unavailable, explain that and ask for a user reference or explicit delegation to skip reference search. "
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
    ) -> dict:
        """Save a Hands on reference-search round or the user's explicit response, without displaying an app. Search using available host tools and the curated source catalog first; this tool does not browse. Offer 2–3 inspected references (one if user supplied), with stable IDs, actual observed_traits and inspection page/image/video. Use video only if playback was inspected. web_search entries need a curated source_id and discovery_url. Select only IDs from the current offer, or refine rejected examples and search again. Delegate only when the user's actual words authorize skipping search. Decisions must quote user_message, never inferred consent. These reports are assistant-reported, not verified native clicks."""
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
        selected_ids = selected_ids or []
        if len(references) > 3 or len(selected_ids) > 3:
            raise ValueError("Use at most three reference choices")
        payload = dict(
            creative_revision=creative_revision,
            action=action,
            references=[item.model_dump() for item in references],
            selected_ids=selected_ids,
            direction=direction.strip(),
            user_message=user_message.strip(),
        )
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        state = deepcopy(store.get("creative", project_id) or {})
        reference = state.get("intake", {}).get("reference_direction", {})

        def result(repeated=False):
            context = reference_context(state)
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
        if intake["phase"] in {"mode", "basics", "personalization"}:
            raise ValueError(
                "Answer the pending involvement, basics, content, or style question before recording references"
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
            if len(references) not in {2, 3} and not (
                len(references) == 1 and references[0].source == "user_supplied"
            ):
                raise ValueError(
                    "Offer 2–3 references, or one reference supplied by the user"
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
            reference["rounds"] = (
                rounds
                + [dict(id=ident(), references=payload["references"], status="offered")]
            )[-6:]
            reference.update(
                status="offered",
                selected_ids=[],
                direction=payload["direction"],
                decision_source=None,
                user_message="",
            )
        else:
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
