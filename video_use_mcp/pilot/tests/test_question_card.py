"""ChatGPT choices save exactly once without changing Claude presentation."""

import json
from unittest.mock import Mock


from video_use_mcp.pilot.question_card import question_resource_uri
from video_use_mcp.tests.test_service import mcp_call

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]


def rpc(pilot, name, params, chatgpt=True):
    client, app = pilot
    cid = "chatgpt-choice-test" if chatgpt else "claude-choice-test"
    app.state.store.put(
        "client",
        cid,
        {
            "client_name": "ChatGPT" if chatgpt else "Claude",
            "redirect_uris": ["https://chatgpt.com/connector/oauth/test"]
            if chatgpt
            else ["https://claude.ai/callback"],
        },
    )
    grant = app.state.auth.issue("tester", cid, ["video:read", "video:write"])
    response = mcp_call(client, grant.access_token, name, params)
    assert response.status_code == 200
    return response.json()["result"]


def call(pilot, name, args, chatgpt=True):
    result = rpc(pilot, "tools/call", {"name": name, "arguments": args}, chatgpt)
    assert not result.get("isError"), result
    return result.get("structuredContent") or json.loads(result["content"][0]["text"])


def start(pilot):
    return call(
        pilot,
        "start_video",
        {
            "title": "Future",
            "brief": "Life in 2050",
            "category": "custom",
            "output_profile": {"duration_seconds": 30},
        },
    )


def submission(data, **updates):
    return {
        "project_id": data["project_id"],
        "widget_id": data["question"]["id"],
        "revision": data["question"]["revision"],
        "request_id": "click-1",
        "answers": {"involvement": "hands_on"},
    } | updates


def test_choice_metadata_is_client_scoped_without_mutating_claude(pilot):
    for chatgpt in (False, True, False):
        tools = {t["name"]: t for t in rpc(pilot, "tools/list", {}, chatgpt)["tools"]}
        for name in ("start_video", "show_video_brief", "show_video_checkpoint"):
            meta = tools[name].get("_meta", {})
            if chatgpt:
                assert meta["ui"]["resourceUri"] == question_resource_uri()
            else:
                assert "ui" not in meta
        assert tools["submit_video_choice"]["_meta"]["ui"]["visibility"] == ["app"]
    resource = rpc(pilot, "resources/read", {"uri": question_resource_uri()})[
        "contents"
    ][0]
    assert resource["mimeType"] == "text/html;profile=mcp-app"
    assert resource["_meta"]["ui"]["csp"] == {
        "resourceDomains": [],
        "connectDomains": [],
    }


def test_click_saves_once_and_sends_only_human_reply(pilot):
    first = start(pilot)
    assert first["question"]["presentation"] == "inline_choices"
    assert first["question"]["recorded_answers"] == {}
    args = submission(first)
    saved = call(pilot, "submit_video_choice", args)
    assert saved["saved"] and saved["message"] == "Hands on"
    assert saved["context"]["answer_already_saved"]
    assert saved["context"]["question"]["status"] == "answered"
    assert saved["context"]["intake"]["mode"] == "hands_on"
    assert saved["context"]["intake"]["source"] == "user_submit"
    assert saved["context"]["intake"]["missing_basics"] == ["viewing_destination"]
    repeated = call(pilot, "submit_video_choice", args)
    assert repeated["context"]["repeated"]
    assert (
        repeated["context"]["creative_revision"]
        == saved["context"]["creative_revision"]
    )
    for changed in (
        {"answers": {"involvement": "delegate"}},
        {"request_id": "new-click", "answers": {"involvement": "delegate"}},
    ):
        result = rpc(
            pilot,
            "tools/call",
            {"name": "submit_video_choice", "arguments": args | changed},
        )
        assert result["isError"]


def test_invalid_or_foreign_click_does_not_save(pilot):
    first = start(pilot)
    store = pilot[1].state.store
    before = store.get("creative", first["project_id"])
    for changes in (
        {"answers": {}},
        {"answers": {"involvement": "invented"}},
        {"widget_id": "other"},
    ):
        result = rpc(
            pilot,
            "tools/call",
            {"name": "submit_video_choice", "arguments": submission(first, **changes)},
        )
        assert result["isError"]
        assert store.get("creative", first["project_id"]) == before
    store.project = Mock(side_effect=PermissionError("Not your project"))
    result = rpc(
        pilot,
        "tools/call",
        {"name": "submit_video_choice", "arguments": submission(first)},
    )
    assert result["isError"]
    assert store.get("creative", first["project_id"]) == before
