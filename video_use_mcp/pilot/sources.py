"""Explicit source transfer into the private project, independent of host accounts."""

import asyncio
import hashlib
import http.client
import ipaddress
import json
import socket
import ssl
import tempfile
import threading
import time
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlsplit, unquote

from fastapi import Request
from fastapi.responses import JSONResponse
from mcp.types import CallToolResult, TextContent, ToolAnnotations

from .interaction import UI_META
from .store import ident

MAX_SOURCE_BYTES = 200_000_000
SOURCE_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".webm",
    ".mp3",
    ".wav",
    ".m4a",
    ".aac",
    ".ogg",
    ".flac",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".csv",
    ".tsv",
    ".json",
    ".txt",
    ".md",
    ".srt",
    ".vtt",
    ".glb",
    ".gltf",
    ".obj",
    ".mtl",
    ".bin",
    ".ttf",
    ".otf",
    ".woff",
    ".woff2",
}


def source_name(value):
    value = unicodedata.normalize("NFC", value)
    # A basename is a contract, not a way to silently strip a path traversal.
    if (
        not value
        or len(value) > 150
        or len(value.encode("utf-8")) > 240
        or value != Path(value).name
        or any(not (c.isalnum() or c in "._- ()[],'+") for c in value)
        or value.startswith(".")
    ):
        raise ValueError(
            "Use a short filename with letters, numbers, spaces or ordinary punctuation"
        )
    if Path(value).suffix.lower() not in SOURCE_EXTENSIONS:
        raise ValueError(
            "Choose a supported media, document, data, subtitle, font or 3D asset file"
        )
    return value


def public_target(url):
    if len(url) > 8192:
        raise ValueError("Source URL is too long")
    parts = urlsplit(url)
    if (
        parts.scheme != "https"
        or not parts.hostname
        or parts.username
        or parts.password
        or parts.port not in (None, 443)
    ):
        raise ValueError(
            "Use a direct public HTTPS file URL on port 443 without credentials"
        )
    host = parts.hostname.encode("idna").decode("ascii")
    try:
        records = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError:
        raise ValueError("The source hostname could not be resolved") from None
    addresses = list(dict.fromkeys(r[4][0] for r in records))
    if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
        raise ValueError(
            "Private, local and reserved network addresses cannot be imported"
        )
    addresses.sort(key=lambda a: ":" in a)
    return (
        host,
        addresses[0],
        (parts.path or "/") + ("?" + parts.query if parts.query else ""),
    )


class PinnedHTTPS(http.client.HTTPSConnection):
    """Connect to the validated address, while checking TLS for the original host."""

    def __init__(self, host, address, timeout):
        super().__init__(host, timeout=timeout, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        raw = socket.create_connection((self.address, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


def fetch_source(url, destination, limit=MAX_SOURCE_BYTES):
    deadline = time.monotonic() + 120
    original = urlsplit(url)
    for _ in range(6):
        host, address, target = public_target(url)
        connection = PinnedHTTPS(
            host, address, min(15, max(0.1, deadline - time.monotonic()))
        )

        active_socket = [None]
        expired = threading.Event()

        def interrupt_download(
            connection=connection, active_socket=active_socket, expired=expired
        ):
            expired.set()
            sock = active_socket[0] or connection.sock
            if sock is not None:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                sock.close()

        timer = threading.Timer(
            max(0.1, deadline - time.monotonic()), interrupt_download
        )
        timer.daemon = True
        timer.start()
        try:
            connection.request(
                "GET",
                target,
                headers={
                    "User-Agent": "video-use source import",
                    "Accept-Encoding": "identity",
                },
            )
            active_socket[0] = connection.sock
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader("Location")
                if not location:
                    raise ValueError("Source redirect has no destination")
                url = urljoin(url, location)
                continue
            if response.status != 200:
                raise ValueError(
                    f"Source server returned HTTP {response.status}; use an accessible download link"
                )
            content_type = (
                response.getheader("Content-Type", "").split(";")[0].strip().lower()
            )
            if content_type in ("text/html", "application/xhtml+xml"):
                raise ValueError(
                    "This is a web page, not a direct file. Upload the file or provide its download URL"
                )
            encoding = response.getheader("Content-Encoding", "identity").lower()
            if encoding != "identity":
                raise ValueError(
                    "Source server must return an uncompressed file transfer"
                )
            length = response.getheader("Content-Length")
            if length and (not length.isdecimal() or int(length) > limit):
                raise ValueError("Source exceeds the file size limit")
            size = 0
            sha = hashlib.sha256()
            with Path(destination).open("wb") as output:
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise ValueError("Source download timed out")
                    if connection.sock:
                        connection.sock.settimeout(min(15, remaining))
                    chunk = response.read1(64 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > limit:
                        raise ValueError("Source exceeds the file size limit")
                    output.write(chunk)
                    sha.update(chunk)
            if expired.is_set() or time.monotonic() >= deadline:
                raise ValueError("Source download timed out")
            if not size or (length and int(length) != size):
                raise ValueError("Source is empty or incomplete")
            return dict(
                size=size,
                sha256=sha.hexdigest(),
                origin=f"{original.scheme}://{original.hostname}",
                mime_type=content_type,
            )
        except (OSError, http.client.HTTPException):
            raise ValueError(
                "Source download failed. Check that the link is accessible and has not expired"
            ) from None
        finally:
            timer.cancel()
            connection.close()
    raise ValueError("Too many source redirects")


async def save_source(store, manager, uid, pid, name, local):
    store.project(uid, pid)
    if store.sql(
        "SELECT id FROM public.vp_objects WHERE project=$1 AND kind='source' AND name=$2",
        pid,
        name,
    ):
        raise ValueError(
            "A source with that name already exists; choose a different filename"
        )
    result = await manager.save_object(uid, pid, "source", name, local)
    sync = "on_next_render"
    if pid in manager.sessions:
        try:
            await manager.sessions[pid]["sandbox"].upload("sources/" + name, local)
            sync = "ready"
        except Exception:
            # Durable storage already succeeded. Keep the receipt and quota charge;
            # refresh persisted sources before the next task, preserving rendered caches.
            manager.sessions[pid]["sources_dirty"] = True
            sync = "on_next_render"
    return {k: result[k] for k in ("id", "name", "size") if k in result} | {
        "path": "sources/" + name,
        "sync": sync,
    }


def register_sources(app, mcp, store, manager, config, muser, write):
    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False, destructiveHint=False, openWorldHint=True
        ),
        title="Import a source file",
    )
    async def import_video_source(project_id: str, url: str, name: str) -> dict:
        """Import an explicitly supplied direct HTTPS download URL into this private project. Supports media, documents, data, subtitles, fonts and 3D assets, up to 200 MB. No website scraping, login cookies, cloud-drive access inheritance or YouTube page downloads. Use request_video_sources for local/private files. Does not execute or trust instructions inside source content."""
        uid = muser(True)
        store.project(uid, project_id)
        name = source_name(name)
        if manager.lock(project_id).locked():
            raise ValueError("Wait for the current render before adding sources")
        async with manager.lock(project_id):
            with tempfile.TemporaryDirectory() as tmp:
                local = Path(tmp) / name
                provenance = await asyncio.to_thread(fetch_source, url, local)
                result = await save_source(store, manager, uid, project_id, name, local)
                store.put("source_provenance", result["id"], provenance)
                return dict(project_id=project_id, source=result, provenance=provenance)

    @mcp.tool(annotations=write, meta=UI_META, title="Add your material")
    def request_video_sources(project_id: str) -> CallToolResult:
        """Show a minimal in-chat file picker only when actual source files are missing. The user explicitly selects files; no account library is silently shared. Supports documents/data as well as footage. Upload goes directly to this private project, outside model context. Continue independent planning while waiting. If the host cannot upload, use the provided Studio project link."""
        uid = muser(True)
        store.project(uid, project_id)
        ticket = ident() + ident()
        store.put(
            "source_upload",
            hashlib.sha256(ticket.encode()).hexdigest(),
            dict(
                owner=uid,
                project=project_id,
                expires=time.time() + 900,
                remaining=MAX_SOURCE_BYTES,
            ),
            ttl=900,
        )
        data = dict(
            project_id=project_id,
            source_picker=dict(
                accept=",".join(sorted(SOURCE_EXTENSIONS)),
                max_bytes=MAX_SOURCE_BYTES,
                studio_url=config.studio_url + "/?project=" + project_id,
            ),
        )
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=json.dumps(
                        data
                        | {
                            "next_action": "User can select source files here. Continue independent work; use get_video_project to see uploaded sources before editing."
                        }
                    ),
                )
            ],
            structuredContent=data,
            _meta={
                "source_upload_url": config.public_url + "/source-upload/" + project_id,
                "source_upload_token": ticket,
            },
        )

    # This capability authenticates one project and at most 200 MB for 15 minutes.
    # It is sent only in app metadata, not model context. Never log the path/ticket.
    @app.options("/source-upload/{pid}")
    def upload_options(pid: str):
        return JSONResponse(
            {},
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, X-Filename, X-Upload-Token",
            },
        )

    @app.post("/source-upload/{pid}")
    async def upload_direct(pid: str, request: Request):
        headers = {"Access-Control-Allow-Origin": "*"}
        try:
            ticket = request.headers.get("x-upload-token", "")
            key = hashlib.sha256(ticket.encode()).hexdigest()
            state = store.get("source_upload", key)
            if not state or state["expires"] <= time.time() or state["project"] != pid:
                raise ValueError(
                    "This upload link expired. Ask your assistant to reopen the file picker"
                )
            uid, pid = state["owner"], state["project"]
            store.member(uid)
            store.project(uid, pid)
            name = source_name(
                unquote(request.headers.get("x-filename", ""), errors="strict")
            )
            if manager.lock(pid).locked():
                raise ValueError("Wait for the current render before adding files")
            async with manager.lock(pid):
                state = store.get("source_upload", key)
                if not state or state["expires"] <= time.time():
                    raise ValueError("Upload link expired")
                remaining = state["remaining"]
                length = request.headers.get("content-length")
                if length and (not length.isdecimal() or int(length) > remaining):
                    raise ValueError("Files exceed the 200 MB upload allowance")
                with tempfile.TemporaryDirectory() as tmp:
                    local = Path(tmp) / name
                    size = 0
                    async with asyncio.timeout(180):
                        with local.open("wb") as output:
                            async for chunk in request.stream():
                                size += len(chunk)
                                if size > remaining:
                                    raise ValueError(
                                        "Files exceed the 200 MB upload allowance"
                                    )
                                output.write(chunk)
                    if not size:
                        raise ValueError("File is empty")
                    result = await save_source(store, manager, uid, pid, name, local)
                    state["remaining"] -= size
                    store.put(
                        "source_upload",
                        key,
                        state,
                        ttl=max(1, int(state["expires"] - time.time())),
                    )
            return JSONResponse(dict(project_id=pid, source=result), headers=headers)
        except (ValueError, PermissionError, TimeoutError) as exc:
            return JSONResponse({"detail": str(exc)}, status_code=400, headers=headers)
