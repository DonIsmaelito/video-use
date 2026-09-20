from __future__ import annotations

import contextlib
import json
import os
import re
import secrets
import sqlite3
import shutil
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from cryptography.fernet import InvalidToken
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from mcp.server.fastmcp import FastMCP
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import (
    AuthSettings,
    ClientRegistrationOptions,
    RevocationOptions,
)
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from .auth import AuthProvider, SCOPES
from .config import Settings
from .jobs import JobManager
from .limits import RequestLimit
from .providers import PROVIDERS
from .store import Store, digest

STATIC = Path(__file__).parent / "static"
MEDIA_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".webm",
    ".m4v",
    ".avi",
    ".mp3",
    ".wav",
    ".m4a",
    ".aac",
    ".flac",
    ".ogg",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}


class Login(BaseModel):
    username: str = Field(min_length=3, max_length=80, pattern=r"^[a-zA-Z0-9_.@-]+$")
    password: str = Field(min_length=12, max_length=256)
    invite_code: str = Field(default="", max_length=256)


class KeySettings(BaseModel):
    provider: str
    model: str = Field(min_length=1, max_length=160, pattern=r"^[a-zA-Z0-9_./:~+-]+$")
    key: str = Field(default="", max_length=1024)
    elevenlabs_key: str = Field(default="", max_length=1024)
    elevenlabs_voice: str = Field(
        default="", max_length=80, pattern=r"^[a-zA-Z0-9_-]*$"
    )
    clear_elevenlabs: bool = False


class ProjectInput(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class JobInput(BaseModel):
    prompt: str = Field(min_length=3, max_length=16000)
    request_id: str | None = Field(default=None, max_length=120)


def create_app(settings=None, *, store=None, manager=None):
    settings = settings or Settings.from_env()
    store = store or Store(settings.data_dir, settings.encryption_key)
    auth = AuthProvider(store, settings.public_url)
    manager = manager or JobManager(store, settings)
    host = urlsplit(settings.public_url).netloc
    mcp = FastMCP(
        "video-use",
        instructions="Create and edit videos using the video-use harness. Start by listing projects or creating one. Provide the project's workspace_url for media uploads. Users add provider API keys privately in Settings; never ask for API keys in chat. start_video_job launches an autonomous billed production job with the user's configured model. Jobs take minutes: return the workspace link immediately, then check status on follow-up. Do not repeatedly poll within a single response. Reuse project IDs for revisions, and request IDs when retrying the same submission.",
        auth_server_provider=auth,
        auth=AuthSettings(
            issuer_url=settings.public_url,
            resource_server_url=auth.resource,
            validate_token_resource=True,
            client_registration_options=ClientRegistrationOptions(
                enabled=True, valid_scopes=SCOPES, default_scopes=SCOPES
            ),
            revocation_options=RevocationOptions(enabled=True),
            required_scopes=["video:read"],
        ),
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[host],
            allowed_origins=[settings.public_url],
        ),
    )

    def mcp_user(write=False):
        token = get_access_token()
        if token is None or not token.subject or not store.user(token.subject):
            raise ValueError("Connect your video-use account first")
        if write and "video:write" not in token.scopes:
            raise ValueError("Reconnect and grant permission to create videos")
        return token.subject

    def workspace(pid=None):
        return settings.public_url + ("/?project=" + pid if pid else "/")

    def public_job(job):
        job = dict(job)
        job.pop("owner", None)
        job.pop("idempotency_key", None)
        job["workspace_url"] = workspace(job["project"])
        if job["status"] == "succeeded":
            result = dict(job["result"])
            for kind, filename in [("video", "video.mp4"), ("source", "project.zip")]:
                token = store.vault.encrypt(
                    json.dumps({"job": job["id"], "kind": kind}).encode()
                ).decode()
                result[kind + "_url"] = (
                    f"{settings.public_url}/files/{job['id']}/{filename}?ticket={token}"
                )
            result["links_expire_in_seconds"] = 3600
            job["result"] = result
        return job

    def public_project(project):
        project = dict(project)
        project.pop("owner", None)
        project["workspace_url"] = workspace(project["id"])
        project["jobs"] = [public_job(x) for x in project.get("jobs", [])]
        return project

    def submit(uid, pid, prompt, request_id=None):
        if not 3 <= len(prompt) <= 16000:
            raise ValueError("Provide a brief between 3 and 16000 characters")
        if request_id and len(request_id) > 120:
            raise ValueError("Request ID is too long")
        credentials = store.get("credentials", uid)
        if not credentials or not credentials.get("key"):
            raise ValueError("Add a provider API key in Settings at " + workspace())
        if store.user_bytes(uid) >= settings.max_user_bytes:
            raise ValueError("Workspace storage limit reached")
        return public_job(
            store.queue_job(uid, pid, prompt, request_id, settings.max_jobs_per_day)
        )

    read = ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, openWorldHint=False
    )
    write = ToolAnnotations(
        readOnlyHint=False, destructiveHint=False, openWorldHint=False
    )
    production = ToolAnnotations(
        readOnlyHint=False, destructiveHint=False, openWorldHint=True
    )

    @mcp.tool(annotations=read)
    def video_use_setup() -> dict[str, Any]:
        """Get the browser workspace and provider setup status. Keys are entered privately in the browser, never in chat."""
        uid = mcp_user()
        creds = store.get("credentials", uid) or {}
        return {
            "workspace_url": workspace(),
            "provider_configured": bool(creds.get("key")),
            "provider": creds.get("provider"),
            "model": creds.get("model"),
            "speech_configured": bool(creds.get("elevenlabs_key"))
            or creds.get("provider") == "openai",
        }

    @mcp.tool(annotations=read)
    def list_video_projects() -> dict[str, Any]:
        """List the current user's video projects. Reuse a project for follow-up edits so media and editable source are retained."""
        return {"projects": [public_project(x) for x in store.projects(mcp_user())]}

    @mcp.tool(annotations=write)
    def create_video_project(title: str) -> dict[str, Any]:
        """Create a project for an original video or uploaded footage. Return its workspace_url to the user for drag-and-drop uploads before starting an edit."""
        if not 1 <= len(title) <= 120:
            raise ValueError("Title must contain 1–120 characters")
        return public_project(store.create_project(mcp_user(True), title))

    @mcp.tool(annotations=read)
    def get_video_project(project_id: str) -> dict[str, Any]:
        """Inspect uploaded media and earlier jobs for one project. Confirm uploads are present before submitting a footage edit."""
        return public_project(store.project(mcp_user(), project_id))

    @mcp.tool(annotations=production)
    def start_video_job(project_id: str, brief: str, request_id: str) -> dict[str, Any]:
        """Create or revise a video from a creative brief and the project's media. This starts a paid model and render job with the user's saved keys. Use a unique request_id; reuse it only when retrying this exact submission. Returns immediately with job ID and workspace link. Execution continues independently of the chat."""
        return submit(mcp_user(True), project_id, brief, request_id)

    @mcp.tool(annotations=read)
    def get_video_job(job_id: str) -> dict[str, Any]:
        """Check progress or retrieve a finished MP4 and editable source ZIP. Download links expire after one hour; calling again refreshes them. Do not busy-poll: direct the user to the live workspace while production runs."""
        return public_job(store.job(mcp_user(), job_id))

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False, destructiveHint=True, openWorldHint=False
        )
    )
    def cancel_video_job(job_id: str) -> dict[str, Any]:
        """Stop an active production job. Previous successful revisions and uploaded media are retained. Provider work already completed may still be billed."""
        return public_job(manager.cancel(mcp_user(True), job_id))

    mcp_app = mcp.streamable_http_app()

    @contextlib.asynccontextmanager
    async def lifespan(app):
        await manager.start()
        async with mcp.session_manager.run():
            try:
                yield
            finally:
                await manager.close()

    app = FastAPI(
        title="video-use",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.store = store
    app.state.manager = manager
    app.state.mcp = mcp
    app.state.auth = auth
    attempts = defaultdict(deque)

    def rate_limit(key, limit=15, period=600):
        now = time.monotonic()
        if len(attempts) > 10000:
            for old in list(attempts):
                if not attempts[old] or attempts[old][-1] < now - period:
                    del attempts[old]
        values = attempts[key]
        while values and values[0] < now - period:
            values.popleft()
        if len(values) >= limit:
            raise HTTPException(429, "Too many attempts. Please try again later.")
        values.append(now)

    def session(request, csrf=False):
        value = store.get(
            "session", digest(request.cookies.get("video_use_session", ""))
        )
        if not value or not store.user(value["uid"]):
            raise HTTPException(401, "Sign in to your video-use workspace")
        if csrf and not secrets.compare_digest(
            request.headers.get("x-csrf-token", ""), value["csrf"]
        ):
            raise HTTPException(403, "Refresh the page and try again")
        return value

    def signed_in(uid):
        token = secrets.token_urlsafe(32)
        store.put(
            "session",
            digest(token),
            {"uid": uid, "csrf": secrets.token_urlsafe(24)},
            ttl=604800,
        )
        response = JSONResponse({"ok": True})
        response.set_cookie(
            "video_use_session",
            token,
            httponly=True,
            secure=settings.public_url.startswith("https:"),
            samesite="lax",
            max_age=604800,
            path="/",
        )
        return response

    @app.middleware("http")
    async def security(request, call_next):
        if request.method not in {
            "GET",
            "HEAD",
            "OPTIONS",
        } and request.url.path.startswith("/api/"):
            origin = request.headers.get("origin")
            if origin and origin != settings.public_url:
                return JSONResponse(
                    {"detail": "Request origin is not allowed"}, status_code=403
                )
        if request.url.path in {"/register", "/authorize", "/token"}:
            try:
                rate_limit(
                    (
                        request.client.host if request.client else "unknown",
                        request.url.path,
                    ),
                    100,
                )
            except HTTPException as exc:
                return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        return response

    @app.exception_handler(KeyError)
    async def not_found(request, exc):
        return JSONResponse({"detail": "Project or job not found"}, status_code=404)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/health")
    def health():
        return {"ok": True, "service": "video-use-mcp"}

    @app.get("/api/config")
    def config():
        return {
            "providers": {k: {"model": v["model"]} for k, v in PROVIDERS.items()},
            "mcp_url": auth.resource,
            "invite_required": bool(settings.invite_code),
            "max_upload_mb": settings.max_upload_bytes // 1024 // 1024,
        }

    @app.post("/api/register")
    def register(body: Login, request: Request):
        rate_limit((request.client.host if request.client else "unknown", "signup"))
        if settings.invite_code and not secrets.compare_digest(
            body.invite_code, settings.invite_code
        ):
            raise HTTPException(403, "An invitation code is required")
        try:
            uid = store.create_user(body.username, body.password)
        except sqlite3.IntegrityError:
            raise HTTPException(409, "That username is already in use") from None
        return signed_in(uid)

    @app.post("/api/login")
    def login(body: Login, request: Request):
        rate_limit((request.client.host if request.client else "unknown", "login"))
        uid = store.login(body.username, body.password)
        if not uid:
            raise HTTPException(401, "Username or password is incorrect")
        return signed_in(uid)

    @app.post("/api/logout")
    def logout(request: Request):
        session(request, True)
        store.delete("session", digest(request.cookies.get("video_use_session", "")))
        response = JSONResponse({"ok": True})
        response.delete_cookie("video_use_session", path="/")
        return response

    @app.get("/api/me")
    def me(request: Request):
        current = session(request)
        return {**store.user(current["uid"]), "csrf": current["csrf"]}

    @app.get("/api/settings")
    def get_settings(request: Request):
        creds = store.get("credentials", session(request)["uid"]) or {}
        return {
            "provider": creds.get("provider", "openai"),
            "model": creds.get("model", PROVIDERS["openai"]["model"]),
            "key_configured": bool(creds.get("key")),
            "elevenlabs_configured": bool(creds.get("elevenlabs_key")),
            "elevenlabs_voice": creds.get("elevenlabs_voice", ""),
        }

    @app.put("/api/settings")
    def save_settings(body: KeySettings, request: Request):
        uid = session(request, True)["uid"]
        if body.provider not in PROVIDERS:
            raise ValueError("Choose a supported provider")
        old = store.get("credentials", uid) or {}
        key = body.key.strip() or (
            old.get("key") if old.get("provider") == body.provider else ""
        )
        if not key:
            raise ValueError("Add an API key for the selected provider")
        if any(c.isspace() for c in key):
            raise ValueError("API keys cannot contain whitespace")
        value = {
            "provider": body.provider,
            "model": body.model,
            "key": key,
            "elevenlabs_key": ""
            if body.clear_elevenlabs
            else (body.elevenlabs_key.strip() or old.get("elevenlabs_key", "")),
            "elevenlabs_voice": body.elevenlabs_voice,
        }
        store.put("credentials", uid, value)
        return {"ok": True}

    @app.delete("/api/settings/keys")
    def remove_keys(request: Request):
        store.delete("credentials", session(request, True)["uid"])
        return {"ok": True}

    @app.put("/api/password")
    async def set_password(request: Request):
        uid = session(request, True)["uid"]
        data = await request.json()
        password = data.get("password", "")
        if not isinstance(password, str) or not 12 <= len(password) <= 256:
            raise ValueError("Use a password with 12–256 characters")
        with store.db() as db:
            db.execute(
                "UPDATE users SET password=? WHERE id=?",
                (store.passwords.hash(password), uid),
            )
        return {"ok": True}

    @app.get("/api/projects")
    def list_projects(request: Request):
        return [public_project(x) for x in store.projects(session(request)["uid"])]

    @app.post("/api/projects")
    def add_project(body: ProjectInput, request: Request):
        return public_project(
            store.create_project(session(request, True)["uid"], body.title)
        )

    @app.get("/api/projects/{pid}")
    def get_project(pid: str, request: Request):
        return public_project(store.project(session(request)["uid"], pid))

    @app.delete("/api/projects/{pid}")
    def delete_project(pid: str, request: Request):
        jobs = store.remove_project(session(request, True)["uid"], pid)
        for jid in jobs:
            shutil.rmtree(store.root / "jobs" / jid, ignore_errors=True)
        shutil.rmtree(store.root / "uploads" / pid, ignore_errors=True)
        return {"ok": True}

    @app.delete("/api/projects/{pid}/media/{aid}")
    def delete_media(pid: str, aid: str, request: Request):
        store.remove_asset(session(request, True)["uid"], pid, aid).unlink(
            missing_ok=True
        )
        return {"ok": True}

    @app.post("/api/projects/{pid}/media")
    async def upload(pid: str, request: Request, file: UploadFile = File(...)):
        uid = session(request, True)["uid"]
        store.project(uid, pid)
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in MEDIA_EXTENSIONS:
            raise ValueError("Upload a video, audio file, PNG, JPEG or WebP image")
        name = (
            re.sub(r"[^a-zA-Z0-9_.-]", "_", Path(file.filename or "media").stem)[:70]
            + "_"
            + secrets.token_hex(4)
            + suffix
        )
        directory = store.root / "uploads" / pid
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / name
        used = store.user_bytes(uid)
        total = 0
        try:
            with path.open("xb") as out:
                while chunk := await file.read(1024 * 1024):
                    total += len(chunk)
                    if (
                        total > settings.max_upload_bytes
                        or total + used > settings.max_user_bytes
                    ):
                        raise HTTPException(
                            413, "Upload or workspace storage limit exceeded"
                        )
                    out.write(chunk)
            if not total:
                raise ValueError("The uploaded file is empty")
            if store.user_bytes(uid) + total > settings.max_user_bytes:
                raise HTTPException(413, "Workspace storage limit exceeded")
            return store.add_asset(uid, pid, name, path, total)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        finally:
            await file.close()

    @app.post("/api/projects/{pid}/jobs")
    def create_job(pid: str, body: JobInput, request: Request):
        return submit(session(request, True)["uid"], pid, body.prompt, body.request_id)

    @app.get("/api/jobs/{jid}")
    def get_job(jid: str, request: Request):
        return public_job(store.job(session(request)["uid"], jid))

    @app.post("/api/jobs/{jid}/cancel")
    def cancel_job(jid: str, request: Request):
        return public_job(manager.cancel(session(request, True)["uid"], jid))

    @app.get("/api/consent/{request_id}")
    def consent_info(request_id: str, request: Request):
        session(request)
        value = store.get("authorization_request", digest(request_id))
        if not value:
            raise ValueError(
                "Connection request expired. Start again from your assistant."
            )
        return {
            "client_name": value["client_name"],
            "scopes": value["params"]["scopes"] or SCOPES,
        }

    @app.post("/api/consent/{request_id}")
    async def accept_consent(request_id: str, request: Request):
        uid = session(request, True)["uid"]
        data = await request.json()
        return {
            "redirect_url": auth.consent(uid, request_id, data.get("allow") is True)
        }

    @app.get("/files/{jid}/{filename}")
    def download(jid: str, filename: str, ticket: str):
        if filename not in {"video.mp4", "project.zip"}:
            raise HTTPException(404)
        try:
            value = json.loads(store.vault.decrypt(ticket.encode(), ttl=3600))
        except (InvalidToken, ValueError):
            raise HTTPException(
                403, "Download link expired. Refresh the job to get a new link."
            ) from None
        expected = "video" if filename == "video.mp4" else "source"
        if value != {"job": jid, "kind": expected}:
            raise HTTPException(403)
        path = store.root / "jobs" / jid / filename
        if not re.fullmatch(r"job_[a-f0-9]{24}", jid) or not path.is_file():
            raise HTTPException(404)
        return FileResponse(
            path,
            media_type="video/mp4" if expected == "video" else "application/zip",
            filename=filename,
            content_disposition_type="inline" if expected == "video" else "attachment",
        )

    # Owner credentials are opt-in, scoped to a pre-created account, and never shared with signups.
    bootstrap = os.getenv("VIDEO_USE_OWNER_BOOTSTRAP", "")
    if bootstrap:
        with store.db() as db:
            owner = db.execute("SELECT id FROM users WHERE username='owner'").fetchone()
        owner_id = (
            owner["id"]
            if owner
            else store.create_user("owner", secrets.token_urlsafe(48))
        )
        # Seed only at account creation. Removing saved keys must stay effective
        # across restarts even while the operator's bootstrap secret still exists.
        if not owner:
            for provider, key_name in [
                ("openrouter", "OPENROUTER_API_KEY"),
                ("openai", "OPENAI_API_KEY"),
                ("anthropic", "ANTHROPIC_API_KEY"),
            ]:
                if os.getenv(key_name):
                    store.put(
                        "credentials",
                        owner_id,
                        {
                            "provider": provider,
                            "model": PROVIDERS[provider]["model"],
                            "key": os.environ[key_name],
                            "elevenlabs_key": os.getenv("ELEVENLABS_API_KEY", ""),
                            "elevenlabs_voice": os.getenv("ELEVENLABS_VOICE_ID", ""),
                        },
                    )
                    break

        @app.post("/api/bootstrap")
        async def owner_setup(request: Request):
            rate_limit(
                (request.client.host if request.client else "unknown", "bootstrap")
            )
            body = await request.json()
            token = body.get("token", "")
            if not isinstance(token, str) or not secrets.compare_digest(
                token, bootstrap
            ):
                raise HTTPException(403, "Invalid setup link")
            with store.db() as db:
                try:
                    db.execute(
                        "INSERT INTO kv VALUES ('bootstrap_used',?, ?,NULL)",
                        (digest(bootstrap), store.vault.encrypt(b"true")),
                    )
                except sqlite3.IntegrityError:
                    raise HTTPException(
                        403,
                        "This setup link has already been used. Sign in with your password.",
                    ) from None
            return signed_in(owner_id)

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    app.mount("/", mcp_app)
    app.add_middleware(RequestLimit, upload_limit=settings.max_upload_bytes)
    return app
