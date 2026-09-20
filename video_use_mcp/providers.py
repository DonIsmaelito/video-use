"""Provider keys never enter an agent's prompt, sandbox, trace, or browser response."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

import httpx

PROVIDERS = {
    "openai": {"url": "https://api.openai.com/v1", "model": "gpt-6-astra"},
    "anthropic": {"url": "https://api.anthropic.com/v1", "model": "claude-opus-5"},
    "openrouter": {
        "url": "https://openrouter.ai/api/v1",
        "model": "openai/gpt-6-astra",
    },
}


class ProviderError(RuntimeError):
    pass


@dataclass
class Reply:
    text: str
    calls: list[dict]
    tokens: int


async def checked(response: httpx.Response):
    if response.status_code >= 400:
        if response.status_code in (401, 403):
            raise ProviderError(
                "The provider rejected your API key or model access. Check Settings."
            )
        if response.status_code == 402:
            raise ProviderError(
                "Your provider has insufficient credit for this model request. Add credit in your provider account, or choose a less expensive model in Settings, then retry."
            )
        if response.status_code == 429:
            raise ProviderError(
                "Your provider is temporarily rate limiting requests. Wait a little before retrying, or choose another model in Settings."
            )
        # Do not reflect raw upstream bodies, which may echo secrets or request content.
        raise ProviderError(
            f"The provider returned HTTP {response.status_code}. Check your model ID and retry."
        )
    return response.json()


class AgentModel:
    def __init__(self, credentials, instructions, tools):
        self.kind = credentials["provider"]
        self.key = credentials["key"]
        self.model = credentials["model"]
        # A custom endpoint is operator-provisioned only, never accepted from public input.
        self.url = credentials.get("base_url") or PROVIDERS[self.kind]["url"]
        self.instructions = instructions
        self.tools = tools
        self.history = []
        self.http = httpx.AsyncClient(timeout=httpx.Timeout(180, connect=30))

    async def close(self):
        await self.http.aclose()

    def user(self, text):
        self.history.append({"role": "user", "content": text})

    async def next(self):
        if self.kind == "anthropic":
            return await self._anthropic()
        if self.kind == "openrouter":
            return await self._chat()
        return await self._responses()

    async def post(self, endpoint, headers, payload):
        for attempt in range(3):
            response = await self.http.post(
                self.url + endpoint, headers=headers, json=payload
            )
            if response.status_code not in {429, 500, 502, 503, 504} or attempt == 2:
                return await checked(response)
            try:
                delay = float(response.headers.get("retry-after", 2 ** (attempt + 1)))
            except ValueError:
                delay = 2 ** (attempt + 1)
            if delay > 30:
                return await checked(response)
            await asyncio.sleep(max(0, delay))

    async def _responses(self):
        tools = [
            {
                "type": "function",
                "name": x["name"],
                "description": x["description"],
                "parameters": x["input_schema"],
                "strict": True,
            }
            for x in self.tools
        ]
        payload = {
            "model": self.model,
            "instructions": self.instructions,
            "input": self.history,
            "tools": tools,
            "store": False,
            "max_output_tokens": 20000,
        }
        if self.model.startswith(("gpt-5", "gpt-6", "o3")):
            payload["reasoning"] = {"effort": "high"}
        data = await self.post(
            "/responses", {"Authorization": "Bearer " + self.key}, payload
        )
        self.history.extend(data.get("output", []))
        calls = [
            {"id": x["call_id"], "name": x["name"], "args": json.loads(x["arguments"])}
            for x in data.get("output", [])
            if x["type"] == "function_call"
        ]
        text = "\n".join(
            c["text"]
            for x in data.get("output", [])
            if x["type"] == "message"
            for c in x.get("content", [])
            if c["type"] == "output_text"
        )
        return Reply(text, calls, data.get("usage", {}).get("total_tokens", 0))

    async def _anthropic(self):
        data = await self.post(
            "/messages",
            {"x-api-key": self.key, "anthropic-version": "2023-06-01"},
            {
                "model": self.model,
                "system": self.instructions,
                "messages": self.history,
                "tools": self.tools,
                "max_tokens": 16000,
            },
        )
        self.history.append({"role": "assistant", "content": data["content"]})
        calls = [
            {"id": x["id"], "name": x["name"], "args": x["input"]}
            for x in data["content"]
            if x["type"] == "tool_use"
        ]
        text = "\n".join(x["text"] for x in data["content"] if x["type"] == "text")
        usage = data.get("usage", {})
        return Reply(
            text,
            calls,
            sum(
                usage.get(k, 0)
                for k in (
                    "input_tokens",
                    "output_tokens",
                    "cache_creation_input_tokens",
                    "cache_read_input_tokens",
                )
            ),
        )

    async def _chat(self):
        tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in self.tools
        ]
        data = await self.post(
            "/chat/completions",
            {"Authorization": "Bearer " + self.key},
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self.instructions},
                    *self.history,
                ],
                "tools": tools,
                "max_tokens": 20000,
            },
        )
        msg = data["choices"][0]["message"]
        self.history.append(msg)
        calls = [
            {
                "id": x["id"],
                "name": x["function"]["name"],
                "args": json.loads(x["function"]["arguments"]),
            }
            for x in msg.get("tool_calls", [])
        ]
        return Reply(
            msg.get("content") or "",
            calls,
            data.get("usage", {}).get("total_tokens", 0),
        )

    def results(self, results):
        if self.kind == "anthropic":
            content = []
            for call, result in results:
                parts = [{"type": "text", "text": result["text"]}]
                if result.get("image"):
                    parts.append(
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": result["image"],
                            },
                        }
                    )
                content.append(
                    {"type": "tool_result", "tool_use_id": call["id"], "content": parts}
                )
            self.history.append({"role": "user", "content": content})
        else:
            images = []
            for call, result in results:
                if self.kind == "openrouter":
                    self.history.append(
                        {
                            "role": "tool",
                            "tool_call_id": call["id"],
                            "content": result["text"],
                        }
                    )
                else:
                    self.history.append(
                        {
                            "type": "function_call_output",
                            "call_id": call["id"],
                            "output": result["text"],
                        }
                    )
                if result.get("image"):
                    url = "data:image/png;base64," + result["image"]
                    images.append(
                        {"type": "image_url", "image_url": {"url": url}}
                        if self.kind == "openrouter"
                        else {"type": "input_image", "image_url": url}
                    )
            if images:
                self.history.append({"role": "user", "content": images})
