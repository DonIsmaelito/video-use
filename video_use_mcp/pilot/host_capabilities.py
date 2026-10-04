"""Observe bounded, authenticated initialization metadata without changing MCP."""

import asyncio
import contextlib
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone

from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser

from .store import ident

MAX_INITIALIZE_BYTES = 16 * 1024
TRACE_TIMEOUT_SECONDS = 0.5


def initialize_capabilities(body):
    """Return only known advertisement flags, never arbitrary client metadata."""
    try:
        request = json.loads(body)
        if not isinstance(request, dict) or request.get("method") != "initialize":
            return None
        params = request.get("params")
        if not isinstance(params, dict):
            return None
        version = params.get("protocolVersion")
        if not isinstance(version, str) or not re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}", version
        ):
            return None
        capabilities = params.get("capabilities")
        if not isinstance(capabilities, dict):
            return None
        elicitation_value = capabilities.get("elicitation")
        elicitation = elicitation_value if isinstance(elicitation_value, dict) else {}
        extensions = capabilities.get("extensions")
        extensions = extensions if isinstance(extensions, dict) else {}
        openai = extensions.get("openai/elicitation")
        openai = openai if isinstance(openai, dict) else {}
        experimental = capabilities.get("experimental")
        experimental = experimental if isinstance(experimental, dict) else {}
        legacy_openai = experimental.get("openai/elicitation")
        legacy_openai = legacy_openai if isinstance(legacy_openai, dict) else {}
        return {
            "protocol_version": version,
            "advertised_capabilities": {
                # Older clients advertise elicitation={} without mode keys.
                # Preserve that distinction instead of reporting no support.
                "elicitation_present": isinstance(elicitation_value, dict),
                "elicitation_modes_unspecified": isinstance(elicitation_value, dict)
                and "form" not in elicitation
                and "url" not in elicitation,
                "elicitation_form": isinstance(elicitation.get("form"), dict),
                "elicitation_url": isinstance(elicitation.get("url"), dict),
                "openai_elicitation_form": isinstance(openai.get("form"), dict)
                or isinstance(legacy_openai.get("form"), dict),
            },
            "host_presentation": "unobserved",
        }
    except (ValueError, TypeError, RecursionError):
        return None


class InitializeCapabilityTelemetry:
    """Tee only bytes the existing authenticated MCP app already consumes.

    The SDK remains responsible for token, audience and scope checks. Its auth
    middleware populates scope.user; successful HTTP responses are observed only
    after that app finishes. Nothing is read ahead or inserted into the stream.
    """

    def __init__(self, app, store, path="/mcp"):
        self.app = app
        self.store = store
        self.path = path

    async def __call__(self, scope, receive, send):
        if (
            scope.get("type") != "http"
            or scope.get("method") != "POST"
            or scope.get("path") != self.path
        ):
            return await self.app(scope, receive, send)
        body = bytearray()
        complete = False
        oversized = False
        status = None
        started = time.monotonic()
        started_at = datetime.now(timezone.utc).isoformat()

        async def observed_receive():
            nonlocal complete, oversized
            message = await receive()
            if message["type"] == "http.request" and not oversized:
                chunk = message.get("body", b"")
                if len(body) + len(chunk) > MAX_INITIALIZE_BYTES:
                    body.clear()
                    oversized = True
                else:
                    body.extend(chunk)
                    complete = not message.get("more_body", False)
            return message

        async def observed_send(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        await self.app(scope, observed_receive, observed_send)
        # Diagnostics must neither substitute for auth nor change any response.
        with contextlib.suppress(Exception):
            user = scope.get("user")
            if (
                status != 200
                or oversized
                or not complete
                or not isinstance(user, AuthenticatedUser)
            ):
                return
            token = user.access_token
            if not token.subject:
                return
            observed = initialize_capabilities(body)
            if observed is None:
                return
            record = {
                "started_at": started_at,
                "at": datetime.now(timezone.utc).isoformat(),
                "tool": "initialize",
                "surface": "host",
                "owner": token.subject,
                "client": hashlib.sha256(token.client_id.encode()).hexdigest()[:12],
                "project": None,
                "task": None,
                "outcome": "ok",
                "elapsed_ms": round((time.monotonic() - started) * 1000),
                "harness_version": os.getenv("PILOT_HARNESS_VERSION", "development"),
                **observed,
            }
            await asyncio.wait_for(
                asyncio.to_thread(
                    self.store.put, "trace", ident(), record, ttl=2592000
                ),
                timeout=TRACE_TIMEOUT_SECONDS,
            )
