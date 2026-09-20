"""Read the model picker catalog from the locally authenticated Codex install."""

from __future__ import annotations

import json
import select
import subprocess
import threading
import time
from typing import Any


FALLBACK_MODELS: list[dict[str, Any]] = [
    {
        "id": "gpt-5.6-sol",
        "display_name": "GPT-5.6-Sol",
        "description": "Latest frontier agentic coding model.",
        "default_reasoning_effort": "low",
        "reasoning_efforts": [
            {"id": effort, "description": ""}
            for effort in ("low", "medium", "high", "xhigh", "max", "ultra")
        ],
        "is_default": True,
    },
    {
        "id": "gpt-5.6-terra",
        "display_name": "GPT-5.6-Terra",
        "description": "Balanced agentic coding model for everyday work.",
        "default_reasoning_effort": "medium",
        "reasoning_efforts": [
            {"id": effort, "description": ""}
            for effort in ("low", "medium", "high", "xhigh", "max", "ultra")
        ],
        "is_default": False,
    },
    {
        "id": "gpt-5.6-luna",
        "display_name": "GPT-5.6-Luna",
        "description": "Fast and affordable agentic coding model.",
        "default_reasoning_effort": "medium",
        "reasoning_efforts": [
            {"id": effort, "description": ""}
            for effort in ("low", "medium", "high", "xhigh", "max")
        ],
        "is_default": False,
    },
]


class CodexCatalogError(RuntimeError):
    """Raised when the local Codex app-server cannot return its catalog."""


class CodexModelCatalog:
    """Small cached JSON-RPC client for ``codex app-server model/list``."""

    def __init__(self, timeout: float = 8.0) -> None:
        self.timeout = timeout
        self._lock = threading.Lock()
        self._cache: dict[str, Any] | None = None

    def get(self) -> dict[str, Any]:
        with self._lock:
            if self._cache is None:
                try:
                    models = self._query()
                    source = "codex"
                    warning = None
                except (CodexCatalogError, OSError, subprocess.SubprocessError) as exc:
                    models = FALLBACK_MODELS
                    source = "fallback"
                    warning = str(exc)
                default = next(
                    (model["id"] for model in models if model["is_default"]),
                    models[0]["id"],
                )
                self._cache = {
                    "models": models,
                    "default_model": default,
                    "source": source,
                    "warning": warning,
                }
            return dict(self._cache)

    def validate(self, model: str, reasoning_effort: str) -> None:
        catalog = self.get()
        selected = next(
            (item for item in catalog["models"] if item["id"] == model),
            None,
        )
        if selected is None:
            raise ValueError(f"model is not available: {model}")
        supported = {item["id"] for item in selected["reasoning_efforts"]}
        if reasoning_effort not in supported:
            raise ValueError(
                f"{model} does not support reasoning effort {reasoning_effort}"
            )

    def _query(self) -> list[dict[str, Any]]:
        process = subprocess.Popen(
            ["codex", "app-server", "--stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        try:
            self._send(
                process,
                {
                    "method": "initialize",
                    "id": 0,
                    "params": {
                        "clientInfo": {
                            "name": "video_use_gui",
                            "title": "video-use gui tool",
                            "version": "0.1.0",
                        }
                    },
                },
            )
            self._response(process, 0)
            self._send(process, {"method": "initialized", "params": {}})
            self._send(
                process,
                {
                    "method": "model/list",
                    "id": 1,
                    "params": {"limit": 50, "includeHidden": False},
                },
            )
            result = self._response(process, 1)
            return self._normalize_models(result.get("data") or [])
        finally:
            if process.stdin:
                process.stdin.close()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=2)

    @staticmethod
    def _send(process: subprocess.Popen[str], message: dict[str, Any]) -> None:
        if process.stdin is None:
            raise CodexCatalogError("Codex app-server stdin is unavailable")
        process.stdin.write(json.dumps(message) + "\n")
        process.stdin.flush()

    def _response(
        self,
        process: subprocess.Popen[str],
        request_id: int,
    ) -> dict[str, Any]:
        if process.stdout is None:
            raise CodexCatalogError("Codex app-server stdout is unavailable")
        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise CodexCatalogError("Codex model catalog timed out")
            ready, _, _ = select.select([process.stdout], [], [], remaining)
            if not ready:
                raise CodexCatalogError("Codex model catalog timed out")
            line = process.stdout.readline()
            if not line:
                detail = process.stderr.read().strip() if process.stderr else ""
                raise CodexCatalogError(detail or "Codex app-server exited early")
            message = json.loads(line)
            if message.get("id") != request_id:
                continue
            if message.get("error"):
                raise CodexCatalogError(str(message["error"].get("message") or "error"))
            return dict(message.get("result") or {})

    @staticmethod
    def _normalize_models(raw_models: list[dict[str, Any]]) -> list[dict[str, Any]]:
        models: list[dict[str, Any]] = []
        for raw in raw_models:
            model_id = str(raw.get("model") or raw.get("id") or "").strip()
            if not model_id or raw.get("hidden"):
                continue
            efforts = [
                {
                    "id": str(item.get("reasoningEffort") or ""),
                    "description": str(item.get("description") or ""),
                }
                for item in raw.get("supportedReasoningEfforts") or []
                if item.get("reasoningEffort")
            ]
            if not efforts:
                continue
            default_effort = str(raw.get("defaultReasoningEffort") or efforts[0]["id"])
            if default_effort not in {item["id"] for item in efforts}:
                default_effort = efforts[0]["id"]
            models.append(
                {
                    "id": model_id,
                    "display_name": str(raw.get("displayName") or model_id),
                    "description": str(raw.get("description") or ""),
                    "default_reasoning_effort": default_effort,
                    "reasoning_efforts": efforts,
                    "is_default": bool(raw.get("isDefault")),
                }
            )
        if not models:
            raise CodexCatalogError("Codex returned no selectable models")
        return models
