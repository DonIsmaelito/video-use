import asyncio
import json

import httpx
import pytest

from video_use_mcp.providers import AgentModel, ProviderError


@pytest.mark.parametrize("provider", ["openai", "anthropic", "openrouter"])
def test_tool_and_image_roundtrip_uses_each_provider_protocol(provider):
    payloads = []
    responses = {
        "openai": [
            {
                "output": [
                    {
                        "type": "function_call",
                        "call_id": "one",
                        "name": "view_image",
                        "arguments": '{"path":"proof.png"}',
                    }
                ],
                "usage": {"total_tokens": 50},
            },
            {
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {"type": "output_text", "text": "The title is readable."}
                        ],
                    }
                ]
            },
        ],
        "anthropic": [
            {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "one",
                        "name": "view_image",
                        "input": {"path": "proof.png"},
                    }
                ],
                "usage": {"input_tokens": 40, "output_tokens": 10},
            },
            {"content": [{"type": "text", "text": "The title is readable."}]},
        ],
        "openrouter": [
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "one",
                                    "type": "function",
                                    "function": {
                                        "name": "view_image",
                                        "arguments": '{"path":"proof.png"}',
                                    },
                                }
                            ],
                        }
                    }
                ],
                "usage": {"total_tokens": 50},
            },
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "The title is readable.",
                        }
                    }
                ]
            },
        ],
    }

    def upstream(request):
        payloads.append(json.loads(request.content))
        assert b"private-key" not in request.content
        return httpx.Response(200, json=responses[provider][len(payloads) - 1])

    async def exercise():
        agent = AgentModel(
            {"provider": provider, "key": "private-key", "model": "model"},
            "Make a video",
            [],
        )
        await agent.http.aclose()
        agent.http = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
        try:
            agent.user("Review my film")
            first = await agent.next()
            assert first.tokens == 50
            assert first.calls[0]["args"] == {"path": "proof.png"}
            agent.results(
                [
                    (
                        first.calls[0],
                        {"text": "Actual encoded frame", "image": "cHJvb2Y="},
                    )
                ]
            )
            second = await agent.next()
            assert second.text == "The title is readable."
            assert not second.calls
        finally:
            await agent.close()

    asyncio.run(exercise())
    sent = payloads[1].get("messages", payloads[1].get("input"))
    assert "cHJvb2Y=" in json.dumps(sent)
    if provider == "anthropic":
        block = sent[-1]["content"][0]
        assert block["type"] == "tool_result" and block["tool_use_id"] == "one"
        assert block["content"][1]["type"] == "image"
    else:
        assert sent[-1]["role"] == "user"
        assert sent[-2].get("tool_call_id", sent[-2].get("call_id")) == "one"


def test_transient_rate_limit_retries_but_credit_error_does_not():
    statuses = [429, 200, 402]
    requests = []

    def upstream(request):
        requests.append(request)
        code = statuses[len(requests) - 1]
        return httpx.Response(
            code,
            json={"message": "sensitive upstream details"},
            headers={"Retry-After": "0"},
        )

    async def exercise():
        model = AgentModel(
            {"provider": "openai", "key": "private-key", "model": "model"},
            "Make a video",
            [],
        )
        await model.http.aclose()
        model.http = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
        try:
            assert await model.post("/responses", {}, {}) == {
                "message": "sensitive upstream details"
            }
            with pytest.raises(ProviderError, match="insufficient credit") as caught:
                await model.post("/responses", {}, {})
            assert "sensitive upstream" not in str(caught.value)
        finally:
            await model.close()

    asyncio.run(exercise())
    assert len(requests) == 3
