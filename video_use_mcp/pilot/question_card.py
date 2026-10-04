"""Small MCP App choice controls for ChatGPT; Claude keeps host questions.

OAuth client metadata is only a presentation hint. It never grants access,
changes scopes, or establishes that the host actually rendered a component.
"""

import hashlib
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from mcp.server.auth.middleware.auth_context import get_access_token

HTML_PATH = Path(__file__).parent / "ui" / "question-card.html"
QUESTION_TOOLS = {"start_video", "show_video_brief", "show_video_checkpoint"}


@lru_cache(maxsize=1)
def question_resource_uri():
    digest = hashlib.sha256(HTML_PATH.read_bytes()).hexdigest()[:16]
    return f"ui://video-use/question-{digest}.html"


def chatgpt_choice_cards(store):
    token = get_access_token()
    if token is None:
        return False
    client = store.get("client", token.client_id) or {}
    return (client.get("client_name") or "").casefold() == "chatgpt" and any(
        urlsplit(str(uri)).hostname == "chatgpt.com"
        for uri in client.get("redirect_uris", [])
    )


def choice_tool_metadata(tools, store):
    if not chatgpt_choice_cards(store):
        return tools
    descriptions = {
        "start_video": (
            "Start a new video with the user's faithful brief and known output basics. "
            "Displays clickable Hands off, Key moments and Hands on choices in chat. "
            "Wait for the user's selection; do not repeat the displayed question in text "
            "or call show_video_brief to display it again. A click saves the answer directly. "
            "Then follow saved intake: missing basics, approach and references for Hands on, "
            "a snippet for explicit review, then the full video in a separate new player. "
            "Reuse project_id for revisions; do not mix separate requests or infer preferences."
        ),
        "show_video_brief": (
            "Show compact clickable choices for the current missing video information. "
            "Use returned intake questions; involvement and output basics are canonical. "
            "Ask only missing information; never repeat a question already displayed by start_video. "
            "Clicks save the selected answers directly; typed answers use record_video_answers. "
            "Read saved state before continuing; recommendations and silence are not answers."
        ),
        "show_video_checkpoint": (
            "After displaying the current snippet, show Continue with this or Refine the sample "
            "as compact clickable choices. Only explicit acceptance unlocks the full video. "
            "Clicks save directly; typed feedback uses record_video_answers. "
            "Do not repeat an already answered checkpoint or treat refinement as approval."
        ),
    }
    return [
        tool.model_copy(
            update={
                "meta": dict(
                    tool.meta or {}, ui={"resourceUri": question_resource_uri()}
                ),
                "description": descriptions[tool.name],
            },
            deep=True,
        )
        if tool.name in QUESTION_TOOLS
        else tool
        for tool in tools
    ]


def choice_presentation(data, store):
    if not isinstance(data.get("question"), dict) or not chatgpt_choice_cards(store):
        return data
    data = deepcopy(data)
    question = data["question"]
    question["presentation"] = "inline_choices"
    question["presenter"] = "mcp_app"
    question["instructions"] = (
        "The compact choice card displays this question. Wait for the user's selection "
        "or typed reply; do not ask it again or open another card. A click saves the "
        "answer directly; use its saved context and do not record it again. For a typed "
        "reply use record_video_answers. If the user cannot see the card, ask one short "
        "chat question. A suggested option or silence is never an answer."
        if question["status"] == "awaiting_user"
        else "This answer is already saved. Continue from the supplied intake without asking or recording it again."
    )
    data["next_action"] = (
        question["instructions"]
        if question["status"] == "awaiting_user"
        else data.get("next_action")
    )
    intake = data.get("intake")
    if (
        isinstance(intake, dict)
        and (intake.get("question") or {}).get("id") == question["id"]
    ):
        intake["question"] = deepcopy(question)
        intake["next_action"] = data["next_action"]
    return data


def register_question_resource(mcp):
    @mcp.resource(
        question_resource_uri(),
        mime_type="text/html;profile=mcp-app",
        meta={
            "ui": {
                "prefersBorder": False,
                "csp": {"resourceDomains": [], "connectDomains": []},
            }
        },
    )
    def question_card() -> str:
        return HTML_PATH.read_text()
