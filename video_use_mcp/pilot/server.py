"""OAuth MCP and browser API for direct, owner-funded editing sessions."""

import asyncio
import contextlib
import json
import secrets
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from starlette.background import BackgroundTask
from mcp.server.fastmcp import FastMCP, Image
from mcp.server.auth.settings import (
    AuthSettings,
    ClientRegistrationOptions,
    RevocationOptions,
)
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from video_use_mcp.auth import AuthProvider, SCOPES
from video_use_mcp.config import ROOT
from video_use_mcp.store import digest
from .config import Config
from .store import Store, ident
from .runtime import Manager


class PilotAuth(AuthProvider):
    def __init__(self, store, config):
        super().__init__(store, config.public_url)
        self.studio = config.studio_url

    async def authorize(self, client, params):
        url = await super().authorize(client, params)
        return self.studio + url[len(self.origin) :]


class Join(BaseModel):
    code: str = Field(min_length=1, max_length=200)


class ProjectInput(BaseModel):
    title: str = Field(min_length=1, max_length=120)


def create_app(config=None, store=None, manager=None):
    config = config or Config.env()
    store = store or Store(config)
    manager = manager or Manager(store, config)
    auth = PilotAuth(store, config)
    mcp = FastMCP(
        "video-use",
        instructions=(
            "You are the editing agent. Use video-use tools directly: open a project, read harness guidance, "
            "inspect media, write editing code, execute it, inspect actual images, then review_video and export_video. "
            "Do not ask for API keys. Uploads use the workspace link. Long calls return task IDs: get_video_task "
            "retrieves results and review images. Do not busy-poll. Preserve project IDs for revisions. "
            "Use a new request_id for each mutation and reuse it only for an exact retry. "
            "Tasks execute independently, but further creative work requires your next tool call. "
            "The environment is network-isolated. Speech is supplied by transcribe_video and narrate_video. "
            "No subagent tool is available here; complete work with these tools."
        ),
        auth_server_provider=auth,
        auth=AuthSettings(
            issuer_url=config.public_url,
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
            allowed_hosts=[urlsplit(config.public_url).netloc],
            allowed_origins=[config.public_url, config.studio_url],
        ),
    )
    read = ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, openWorldHint=False
    )
    write = ToolAnnotations(
        readOnlyHint=False, destructiveHint=False, openWorldHint=False
    )
    execute = ToolAnnotations(
        readOnlyHint=False, destructiveHint=False, openWorldHint=True
    )

    def muser(mutate=False):
        token = get_access_token()
        if not token or not token.subject:
            raise PermissionError("Connect your video-use account")
        if mutate and "video:write" not in token.scopes:
            raise PermissionError("Reconnect with editing permission")
        store.member(token.subject)
        return token.subject

    def workspace(pid=None):
        return config.studio_url + ("/?project=" + pid if pid else "/")

    def link(uid, oid):
        ticket = store.vault.encrypt(
            json.dumps({"owner": uid, "object": oid}).encode()
        ).decode()
        return config.public_url + "/files/" + oid + "?ticket=" + ticket

    def public_task(t):
        return {
            k: t[k]
            for k in (
                "id",
                "project",
                "operation",
                "status",
                "result",
                "error",
                "created",
                "updated",
            )
        } | {"workspace_url": workspace(t["project"])}

    def project_detail(uid, pid):
        p = store.project(uid, pid)
        return {
            "id": pid,
            "title": p["title"],
            "workspace_url": workspace(pid),
            "harness_version": __import__("os").getenv(
                "PILOT_HARNESS_VERSION", "development"
            ),
            "media": store.sql(
                "SELECT id,name,size,kind FROM public.vp_objects WHERE project=$1 AND kind='source' ORDER BY created",
                pid,
            ),
            "tasks": [
                public_task(t)
                for t in store.sql(
                    "SELECT * FROM public.vp_tasks WHERE project=$1 ORDER BY created DESC LIMIT 30",
                    pid,
                )
            ],
            "revisions": [
                r
                | {
                    "video_url": link(uid, r["video"]),
                    "source_url": link(uid, r["archive"]),
                }
                for r in store.sql(
                    "SELECT * FROM public.vp_revisions WHERE project=$1 ORDER BY created DESC LIMIT 30",
                    pid,
                )
            ],
        }

    def new_project(uid, title):
        store.member(uid)
        if not 1 <= len(title.strip()) <= 120:
            raise ValueError("Title must contain 1–120 characters")
        pid = ident()
        store.sql(
            "INSERT INTO public.vp_projects(id,owner,title) VALUES($1,$2,$3)",
            pid,
            uid,
            title.strip(),
        )
        return project_detail(uid, pid)

    @mcp.tool(annotations=read)
    def video_use_setup() -> dict:
        """Get your private workspace link, speech availability, and editing capabilities."""
        uid = muser()
        return {
            "workspace_url": workspace(),
            "speech_available": bool(config.speech_key),
            "member": store.member(uid),
            "guidance": "Call video_use_guidance, list or create a project, then edit with the remote tools.",
        }

    @mcp.tool(annotations=read)
    def video_use_guidance(topic: str = "overview") -> str:
        """Read current harness instructions. Topics: overview, motion, manim, or a helpers/<file> or skills/<file> documentation path."""
        muser()
        target = {
            "overview": "SKILL.md",
            "motion": "skills/motion-design/SKILL.md",
            "manim": "skills/manim-video/SKILL.md",
        }.get(topic, topic)
        path = (ROOT / target).resolve()
        if (
            not path.is_relative_to(ROOT)
            or not path.is_file()
            or path.suffix not in (".md", ".py", ".mjs", ".js")
        ):
            raise ValueError("Choose a harness documentation or helper source file")
        if target != "SKILL.md" and not (
            target.startswith("helpers/") or target.startswith("skills/")
        ):
            raise ValueError("Choose a harness path under helpers/ or skills/")
        return (
            "Remote runtime: /opt/video-use contains the harness; /workspace contains sources/ and edit/. "
            "Use the connector speech tools instead of API keys. No external network, package installation, "
            "local machine paths or subagents. Read relevant guidance and preserve edit/project.md.\n\n"
            + path.read_text()[:60000]
        )

    @mcp.tool(annotations=read)
    def list_video_projects() -> dict:
        """List your projects; reuse a project for follow-up edits."""
        return {
            "projects": store.sql(
                "SELECT id,title,created FROM public.vp_projects WHERE owner=$1 ORDER BY created DESC LIMIT 100",
                muser(),
            )
        }

    @mcp.tool(annotations=write)
    def create_video_project(title: str) -> dict:
        """Create a private project and return its browser upload link."""
        return new_project(muser(True), title)

    @mcp.tool(annotations=read)
    def get_video_project(project_id: str) -> dict:
        """Inspect uploaded media, current task results, and previous exports."""
        return project_detail(muser(), project_id)

    @mcp.tool(annotations=execute)
    async def read_video_file(project_id: str, path: str = "edit/project.md") -> str:
        """Read a UTF-8 workspace file; preserves project context across chats. May start your remote workspace."""
        uid = muser()
        store.project(uid, project_id)
        async with manager.lock(project_id):
            sb = await manager.session(uid, project_id)
            return (await sb.read(path, 200000)).decode()

    @mcp.tool(annotations=execute)
    async def list_video_files(project_id: str) -> dict:
        """List workspace files without exposing other projects."""
        uid = muser()
        async with manager.lock(project_id):
            sb = await manager.session(uid, project_id)
            return await sb.run(
                "find sources edit -type f -not -path '*/node_modules/*' | head -300",
                30,
            )

    @mcp.tool(annotations=execute)
    async def write_video_file(
        project_id: str, path: str, content: str, request_id: str
    ) -> dict:
        """Save UTF-8 project source and a durable checkpoint. Returns a task ID."""
        return public_task(
            manager.submit(
                muser(True),
                project_id,
                "write",
                {"path": path, "content": content, "timeout": 120},
                request_id,
            )
        )

    @mcp.tool(annotations=execute)
    async def patch_video_file(
        project_id: str, path: str, old: str, new: str, request_id: str
    ) -> dict:
        """Replace one exact occurrence in a project file, then checkpoint."""
        return public_task(
            manager.submit(
                muser(True),
                project_id,
                "patch",
                {"path": path, "old": old, "new": new, "timeout": 120},
                request_id,
            )
        )

    @mcp.tool(annotations=execute)
    async def run_video_command(
        project_id: str, command: str, request_id: str, timeout: int = 300
    ) -> dict:
        """Execute FFmpeg, Python, Manim, Node or shell in the isolated workspace. Return a task ID promptly; retrieve logs using get_video_task. Maximum 1800 seconds. No network or secrets."""
        if len(command) > 30000:
            raise ValueError("Command exceeds 30000 characters")
        return public_task(
            manager.submit(
                muser(True),
                project_id,
                "run",
                {"command": command, "timeout": timeout},
                request_id,
            )
        )

    @mcp.tool(annotations=execute)
    async def view_video_frame(project_id: str, path: str) -> Image:
        """See an actual PNG/JPEG frame or contact sheet, not just its path."""
        return Image(data=await manager.image(muser(), project_id, path), format="png")

    @mcp.tool(annotations=execute)
    async def transcribe_video(project_id: str, path: str, request_id: str) -> dict:
        """Transcribe uploaded speech with word timing using the owner's speech allowance."""
        return public_task(
            manager.submit(
                muser(True),
                project_id,
                "transcribe",
                {"path": path, "timeout": 300},
                request_id,
            )
        )

    @mcp.tool(annotations=execute)
    async def narrate_video(
        project_id: str, text: str, output: str, request_id: str
    ) -> dict:
        """Generate narration and word timing using the owner's speech allowance."""
        if not 1 <= len(text) <= 2000:
            raise ValueError("Narration must be 1–2000 characters")
        return public_task(
            manager.submit(
                muser(True),
                project_id,
                "narrate",
                {"text": text, "output": output, "timeout": 300},
                request_id,
            )
        )

    @mcp.tool(annotations=execute)
    async def review_video(project_id: str, video_path: str, request_id: str) -> dict:
        """Extract four encoded frames from the final MP4. Call get_video_task to see and inspect the review image before export."""
        return public_task(
            manager.submit(
                muser(True),
                project_id,
                "review",
                {"video_path": video_path, "timeout": 180},
                request_id,
            )
        )

    @mcp.tool(annotations=execute)
    async def export_video(
        project_id: str, video_path: str, summary: str, request_id: str
    ) -> dict:
        """Verify and publish a reviewed MP4 and editable source ZIP. Requires review of this exact encoded video. Summarize your visual assessment honestly."""
        return public_task(
            manager.submit(
                muser(True),
                project_id,
                "export",
                {"video_path": video_path, "summary": summary, "timeout": 300},
                request_id,
            )
        )

    @mcp.tool(annotations=read)
    async def get_video_task(task_id: str) -> list:
        """Get task status/results/logs, final links, or actual encoded review images. Avoid repeated polling; return the live workspace while rendering."""
        uid = muser()
        t = store.task(uid, task_id)
        out = public_task(t)
        out["events"] = store.sql(
            "SELECT id,message FROM public.vp_events WHERE task=$1 ORDER BY id DESC LIMIT 10",
            task_id,
        )
        result = t.get("result") or {}
        items = []
        for kind in ("video", "source"):
            if result.get(kind + "_id"):
                out[kind + "_url"] = link(uid, result[kind + "_id"])
        items.append(json.dumps(out))
        if t["status"] == "succeeded" and result.get("review_object"):
            obj = store.sql(
                "SELECT key FROM public.vp_objects WHERE id=$1 AND owner=$2",
                result["review_object"],
                uid,
            )[0]
            with tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp) / "review.png"
                await asyncio.to_thread(store.download, obj["key"], p)
                items.append(Image(data=p.read_bytes(), format="png"))
            store.put("reviewed", t["project"], result["sha256"], ttl=86400)
        return items

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False, destructiveHint=True, openWorldHint=False
        )
    )
    async def cancel_video_task(task_id: str) -> dict:
        uid = muser(True)
        t = store.task(uid, task_id)
        if task_id in manager.running:
            manager.running[task_id].cancel()
        return {
            "id": task_id,
            "status": "cancelling"
            if t["status"] in ("queued", "running")
            else t["status"],
        }

    @mcp.tool(annotations=write)
    async def close_video_workspace(project_id: str) -> dict:
        uid = muser(True)
        store.project(uid, project_id)
        if manager.lock(project_id).locked():
            raise ValueError("Cancel or finish the running task first")
        async with manager.lock(project_id):
            await manager.stop(project_id)
        return {"closed": project_id, "message": "Saved project remains available"}

    mcp_app = mcp.streamable_http_app()

    @contextlib.asynccontextmanager
    async def lifespan(app):
        if not store.get("control", "invite"):
            store.put("control", "invite", digest(config.invite_code))
        await manager.start()
        async with mcp.session_manager.run():
            yield
        await manager.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store = store
    app.state.manager = manager
    app.state.auth = auth
    app.state.mcp = mcp
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[config.studio_url],
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["Content-Length", "Content-Range"],
    )
    attempts = {}

    def limit(request, category, maximum=30):
        key = (request.client.host if request.client else "unknown", category)
        now = time.time()
        rows = [t for t in attempts.get(key, []) if now - t < 600]
        if len(rows) >= maximum:
            raise HTTPException(429, "Too many requests; try again shortly")
        attempts[key] = rows + [now]

    def identity(request):
        token = request.headers.get("authorization", "")
        if not token.startswith("Bearer "):
            raise PermissionError("Sign in first")
        return store.identity(token[7:])

    def member(request):
        user = identity(request)
        store.member(user["id"])
        return user["id"]

    def owner(request):
        uid = member(request)
        if not store.member(uid)["is_owner"]:
            raise PermissionError("Owner access required")
        return uid

    @app.middleware("http")
    async def security(request, call_next):
        length = request.headers.get("content-length")
        if length and (not length.isdigit() or int(length) > 201000000):
            return JSONResponse({"detail": "Upload is too large"}, 413)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.exception_handler(PermissionError)
    async def forbidden(request, exc):
        return JSONResponse({"detail": str(exc)}, 403)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"detail": str(exc)}, 400)

    @app.get("/health")
    def health():
        return {"ok": True, "service": "video-use-browser-pilot"}

    @app.get("/")
    def home():
        return RedirectResponse(config.studio_url)

    @app.get("/api/config")
    def public_config():
        return {
            "mcp_url": auth.resource,
            "speech_available": bool(config.speech_key),
            "upload_limit": 200000000,
        }

    @app.get("/api/me")
    def me(request: Request):
        user = identity(request)
        return {
            "id": user["id"],
            "email": user["email"],
            "member": store.user(user["id"]),
        }

    @app.post("/api/join")
    def join(body: Join, request: Request):
        limit(request, "join", 10)
        user = identity(request)
        owner_access = user["email"].lower() == config.owner_email.lower()
        if not owner_access and not secrets.compare_digest(
            digest(body.code), store.get("control", "invite") or ""
        ):
            raise PermissionError("Invitation code is incorrect")
        store.sql(
            "SELECT public.vp_admit($1::uuid,$2,$3::boolean)",
            user["id"],
            user["email"],
            owner_access,
        )
        return {"member": store.member(user["id"])}

    @app.get("/api/projects")
    def projects(request: Request):
        return store.sql(
            "SELECT id,title,created FROM public.vp_projects WHERE owner=$1 ORDER BY created DESC LIMIT 100",
            member(request),
        )

    @app.post("/api/projects")
    def add_project(body: ProjectInput, request: Request):
        return new_project(member(request), body.title)

    @app.get("/api/projects/{pid}")
    def get_project(pid: str, request: Request):
        return project_detail(member(request), pid)

    @app.post("/api/projects/{pid}/upload")
    async def upload(pid: str, request: Request, file: UploadFile = File(...)):
        uid = member(request)
        store.project(uid, pid)
        if manager.lock(pid).locked():
            raise ValueError("Wait for the current task before uploading")
        name = Path(file.filename or "media").name
        if (
            not name
            or len(name) > 150
            or any(
                c
                not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._- "
                for c in name
            )
        ):
            raise ValueError(
                "Use a simple filename with letters, numbers, spaces, dots or dashes"
            )
        if Path(name).suffix.lower() not in {
            ".mp4",
            ".mov",
            ".mkv",
            ".webm",
            ".mp3",
            ".wav",
            ".m4a",
            ".aac",
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
        }:
            raise ValueError("Upload video, audio, or an image")
        async with manager.lock(pid):
            if store.sql(
                "SELECT id FROM public.vp_objects WHERE project=$1 AND kind='source' AND name=$2",
                pid,
                name,
            ):
                raise ValueError(
                    "A source with that name already exists; rename the new file"
                )
            # save_object reserves storage quota before uploading the received file.
            with tempfile.TemporaryDirectory() as tmp:
                local = Path(tmp) / name
                size = 0
                with local.open("wb") as stream:
                    while chunk := await file.read(1024 * 1024):
                        size += len(chunk)
                        if size > 200000000:
                            raise ValueError("Files must be at most 200 MB")
                        stream.write(chunk)
                if not size:
                    raise ValueError("File is empty")
                result = await manager.save_object(uid, pid, "source", name, local)
                if pid in manager.sessions:
                    await manager.sessions[pid]["sandbox"].upload(
                        "sources/" + name, local
                    )
            return result

    @app.get("/api/tasks/{tid}")
    def get_task(tid: str, request: Request):
        uid = member(request)
        t = store.task(uid, tid)
        return public_task(t) | {
            "events": store.sql(
                "SELECT id,message FROM public.vp_events WHERE task=$1 ORDER BY id DESC LIMIT 20",
                tid,
            )
        }

    @app.post("/api/tasks/{tid}/cancel")
    async def cancel(tid: str, request: Request):
        store.task(member(request), tid)
        if tid in manager.running:
            manager.running[tid].cancel()
        return {"ok": True}

    @app.get("/api/consent/{rid}")
    def consent_info(rid: str, request: Request):
        member(request)
        value = store.get("authorization_request", digest(rid))
        if not value:
            raise ValueError(
                "Connection request expired; start again in your assistant"
            )
        return {
            "client_name": value["client_name"],
            "scopes": value["params"]["scopes"],
        }

    @app.post("/api/consent/{rid}")
    async def consent(rid: str, request: Request):
        uid = member(request)
        data = await request.json()
        return {"redirect_url": auth.consent(uid, rid, data.get("allow") is True)}

    @app.get("/api/usage")
    def usage(request: Request):
        uid = member(request)
        return store.sql(
            "SELECT kind,sum(amount) AS amount FROM public.vp_usage WHERE owner=$1 AND (kind='storage' OR created>=date_trunc('day',now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC') GROUP BY kind",
            uid,
        )

    @app.get("/api/admin")
    def admin(request: Request):
        owner(request)
        return {
            "members": store.sql("SELECT * FROM public.vp_members ORDER BY created"),
            "usage": store.sql(
                "SELECT owner,kind,sum(amount) AS amount FROM public.vp_usage WHERE kind='storage' OR created>=date_trunc('day',now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC' GROUP BY owner,kind"
            ),
            "paused": bool(store.get("control", "paused")),
        }

    @app.post("/api/admin/rotate-invite")
    def rotate(request: Request):
        owner(request)
        code = secrets.token_urlsafe(18)
        store.put("control", "invite", digest(code))
        return {"code": code}

    @app.post("/api/admin/pause")
    async def pause(request: Request):
        owner(request)
        value = await request.json()
        store.put("control", "paused", bool(value.get("paused")))
        return {"ok": True}

    @app.post("/api/admin/members/{uid}/revoke")
    async def revoke(uid: str, request: Request):
        owner(request)
        if store.member(uid)["is_owner"]:
            raise ValueError("Cannot revoke the owner")
        store.sql("UPDATE public.vp_members SET active=false WHERE id=$1", uid)
        for tid, t in list(manager.running.items()):
            if store.sql(
                "SELECT id FROM public.vp_tasks WHERE id=$1 AND owner=$2", tid, uid
            ):
                t.cancel()
        for pid, s in list(manager.sessions.items()):
            if s["owner"] == uid and not manager.lock(pid).locked():
                await manager.stop(pid)
        return {"ok": True}

    @app.get("/files/{oid}")
    async def download(oid: str, ticket: str):
        try:
            data = json.loads(store.vault.decrypt(ticket.encode(), ttl=3600))
        except Exception:
            raise PermissionError("Download expired; refresh the workspace")
        if data.get("object") != oid:
            raise PermissionError("Invalid download")
        store.member(data["owner"])
        rows = store.sql(
            "SELECT * FROM public.vp_objects WHERE id=$1 AND owner=$2",
            oid,
            data["owner"],
        )
        if not rows:
            raise PermissionError("File not found")
        obj = rows[0]
        tmp = tempfile.TemporaryDirectory()
        local = Path(tmp.name) / obj["name"]
        try:
            await asyncio.to_thread(store.download, obj["key"], local)
        except BaseException:
            tmp.cleanup()
            raise
        return FileResponse(
            local,
            media_type="video/mp4"
            if obj["kind"] == "video"
            else "application/octet-stream",
            filename=obj["name"],
            content_disposition_type="inline"
            if obj["kind"] == "video"
            else "attachment",
            background=BackgroundTask(tmp.cleanup),
        )

    app.mount("/", mcp_app)
    return app
