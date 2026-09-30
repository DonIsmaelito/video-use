"""Persistent project sessions and bounded commands, driven by the host assistant."""

import asyncio
import contextlib
import hashlib
import io
import json
import math
import shlex
import tempfile
import time
from pathlib import Path

from PIL import Image

from video_use_mcp.sandbox import ModalSandbox
from video_use_mcp.agent import ProductionAgent
from .store import ident
from .interaction import record_progress

PACK = r"""
import pathlib,zipfile
root=pathlib.Path('/workspace/edit');total=0;count=0
with zipfile.ZipFile('/workspace/checkpoint.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in root.rglob('*'):
  if p.is_symlink() or not p.is_file() or not p.resolve().is_relative_to(root): continue
  if any(x in {'node_modules','.git','__pycache__','clips_preview','clips_graded','verify'} for x in p.relative_to(root).parts): continue
  if p.suffix.lower() in {'.mp4','.mov','.mkv','.webm'}: continue
  total+=p.stat().st_size;count+=1
  if total>200000000 or count>10000: raise ValueError('Project source exceeds 200 MB or 10000 files')
  z.write(p,'edit/'+str(p.relative_to(root)))
"""
RESTORE = r"""
import pathlib,zipfile
root=pathlib.Path('/workspace')
with zipfile.ZipFile('/workspace/restore.zip') as z:
 if sum(i.file_size for i in z.infolist())>200000000: raise ValueError('Checkpoint too large')
 for i in z.infolist():
  if not (root/i.filename).resolve().is_relative_to(root/'edit') or (i.external_attr>>16)&0o170000==0o120000: raise ValueError('Invalid archive path')
 z.extractall(root)
"""
REVIEW = r"""
import subprocess,json,pathlib
from PIL import Image,ImageDraw
p=__import__('sys').argv[1]
d=float(json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-of','json',p]))['format']['duration'])
r=pathlib.Path('/workspace/edit/verify');r.mkdir(parents=True,exist_ok=True)
sheet=Image.new('RGB',(1280,780),'#171717');draw=ImageDraw.Draw(sheet)
for i,t in enumerate([min(.2,d/10),d*.33,d*.66,max(0,d-.2)]):
 f=r/f'frame-{i}.png'
 subprocess.run(['ffmpeg','-v','error','-y','-ss',str(t),'-i',p,'-frames:v','1','-vf','scale=640:360:force_original_aspect_ratio=decrease',str(f)],check=True)
 with Image.open(f) as im: sheet.paste(im,((i%2)*640+(640-im.width)//2,(i//2)*390))
 draw.text(((i%2)*640+12,(i//2)*390+365),f'{t:.2f}s',fill='white')
sheet.save(r/'output-review.png')
"""


class PilotSandbox(ModalSandbox):
    async def run(self, command, timeout=180):
        process = await self.instance.exec.aio(
            "bash",
            "-lc",
            command,
            timeout=min(int(timeout), 1800),
            workdir="/workspace",
        )

        async def drain(reader):
            tail = ""
            async for chunk in reader:
                tail = (tail + chunk)[-16000:]
            return tail

        stdout, stderr = await asyncio.gather(
            drain(process.stdout), drain(process.stderr)
        )
        return {
            "exit_code": await process.wait.aio(),
            "stdout": stdout,
            "stderr": stderr,
        }


class Manager:
    def __init__(self, store, config, image=None):
        self.store, self.config, self.runtime_image = store, config, image
        self.sessions = {}
        self.locks = {}
        self.running = {}
        self.admission = asyncio.Lock()

    def lock(self, pid):
        return self.locks.setdefault(pid, asyncio.Lock())

    def event(self, task, message):
        self.store.sql(
            "INSERT INTO public.vp_events(task,owner,message) VALUES ($1,$2,$3)",
            task["id"],
            task["owner"],
            str(message)[-16000:],
        )

    async def start(self):
        import modal

        # Keep idle workspaces (and their rendered media) across coordinator changes.
        # Interrupted commands cannot safely be replayed or adopted mid-execution.
        interrupted = {
            p["project"]
            for p in self.store.sql(
                "SELECT DISTINCT project FROM public.vp_tasks WHERE status IN ('queued','running')"
            )
        }
        for p in self.store.sql(
            "SELECT id,owner,sandbox_id,touched FROM public.vp_projects WHERE sandbox_id IS NOT NULL"
        ):
            try:
                sb = await modal.Sandbox.from_id.aio(p["sandbox_id"])
                if p["id"] not in interrupted and await sb.poll.aio() is None:
                    wrapper = PilotSandbox(self.config, self.runtime_image)
                    wrapper.instance = sb
                    self.sessions[p["id"]] = {
                        "sandbox": wrapper,
                        "owner": p["owner"],
                        "created": p["touched"],
                        "touched": time.time(),
                    }
                    continue
                await sb.terminate.aio()
            except modal.exception.NotFoundError:
                pass
            self.store.sql(
                "UPDATE public.vp_projects SET sandbox_id=NULL WHERE id=$1", p["id"]
            )
        self.store.sql(
            "UPDATE public.vp_tasks SET status='failed',error='Service restarted; last saved source is retained. Start a new task.',updated=now() WHERE status IN ('queued','running')"
        )
        self.reaper = asyncio.create_task(self.reap())

    async def close(self):
        self.reaper.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self.reaper
        for task in list(self.running.values()):
            task.cancel()
        await asyncio.gather(*list(self.running.values()), return_exceptions=True)
        # Sandboxes have their own idle/absolute limits; the next coordinator adopts them.
        for session in self.sessions.values():
            with contextlib.suppress(Exception):
                await session["sandbox"].instance.detach.aio()
        self.sessions.clear()

    async def stop(self, pid):
        value = self.sessions.pop(pid, None)
        if value:
            await value["sandbox"].close()
            self.store.sql(
                "UPDATE public.vp_projects SET sandbox_id=NULL WHERE id=$1", pid
            )
            self.store.put(
                "lifetime",
                ident(),
                {"project": pid, "seconds": round(time.time() - value["created"])},
                ttl=2592000,
            )

    async def reap(self):
        while True:
            await asyncio.sleep(30)
            for pid, session in list(self.sessions.items()):
                if (
                    time.time() - session["touched"] > 300
                    and not self.lock(pid).locked()
                ):
                    async with self.lock(pid):
                        await self.stop(pid)

    async def session(self, uid, pid):
        p = self.store.project(uid, pid)
        async with self.admission:
            if pid in self.sessions:
                v = self.sessions[pid]
                if await v["sandbox"].instance.poll.aio() is None:
                    v["touched"] = time.time()
                    return v["sandbox"]
                await self.stop(pid)
            others = [s for s in self.sessions.values() if s["owner"] == uid]
            if others:
                raise ValueError(
                    "Close your other active workspace first, or wait five minutes"
                )
            if len(self.sessions) >= 2:
                raise ValueError(
                    "Both pilot render workspaces are busy. Try again shortly"
                )
            if self.store.get("control", "paused"):
                raise ValueError("The owner has paused new execution")
            sb = PilotSandbox(self.config, self.runtime_image)
            # Keep the existing isolation; one hour absolute lifetime bounds forgotten sessions.
            import modal

            app = await modal.App.lookup.aio(
                self.config.modal_app, create_if_missing=True
            )
            sb.instance = await modal.Sandbox.create.aio(
                app=app,
                image=self.runtime_image,
                timeout=3600,
                idle_timeout=600,
                cpu=(2.0, 4.0),
                memory=(4096, 8192),
                workdir="/workspace",
                block_network=True,
                include_oidc_identity_token=False,
            )
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    for obj in self.store.sql(
                        "SELECT * FROM public.vp_objects WHERE project=$1 AND kind='source'",
                        pid,
                    ):
                        local = Path(tmp) / obj["id"]
                        await asyncio.to_thread(self.store.download, obj["key"], local)
                        await sb.upload("sources/" + obj["name"], local)
                    if p["checkpoint"]:
                        local = Path(tmp) / "restore.zip"
                        await asyncio.to_thread(
                            self.store.download, p["checkpoint"], local
                        )
                        await sb.upload("restore.zip", local)
                        r = await sb.run("python -c " + shlex.quote(RESTORE), 60)
                        if r["exit_code"]:
                            raise ValueError("Could not restore saved project")
                self.sessions[pid] = {
                    "sandbox": sb,
                    "owner": uid,
                    "touched": time.time(),
                    "created": time.time(),
                }
                self.store.sql(
                    "UPDATE public.vp_projects SET sandbox_id=$2,touched=$3 WHERE id=$1",
                    pid,
                    sb.instance.object_id,
                    time.time(),
                )
                return sb
            except BaseException:
                await sb.close()
                raise

    async def save_object(self, uid, pid, kind, name, local):
        size = Path(local).stat().st_size
        oid = ident()
        key = f"{uid}/{pid}/{oid}/{name}"
        reservation = self.store.reserve(uid, "storage", size, oid)
        try:
            result = await asyncio.to_thread(
                self.store.upload,
                key,
                local,
                "video/mp4" if kind == "video" else "application/octet-stream",
            )
            self.store.sql(
                "INSERT INTO public.vp_objects(id,owner,project,kind,name,key,url,size,usage_id) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)",
                oid,
                uid,
                pid,
                kind,
                name,
                key,
                result["url"],
                size,
                reservation,
            )
            self.store.settle(reservation, size)
            return {"id": oid, "key": key, "size": size, "name": name}
        except BaseException:
            # Retain reservation if upload may have succeeded; reconciliation can reclaim it.
            raise

    async def checkpoint(self, uid, pid, sb):
        r = await sb.run("python -c " + shlex.quote(PACK), 120)
        if r["exit_code"]:
            raise ValueError("Could not save editable project: " + r["stderr"][-300:])
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "project.zip"
            await sb.download("checkpoint.zip", local, 210000000)
            obj = await self.save_object(uid, pid, "checkpoint", "project.zip", local)
        old = self.store.project(uid, pid)["checkpoint"]
        self.store.sql(
            "UPDATE public.vp_projects SET checkpoint=$2 WHERE id=$1", pid, obj["key"]
        )
        if old:
            rows = self.store.sql(
                "SELECT * FROM public.vp_objects WHERE key=$1 AND kind='checkpoint'",
                old,
            )
            if rows:
                await asyncio.to_thread(self.store.remove_object, old)
                self.store.sql(
                    "DELETE FROM public.vp_objects WHERE id=$1", rows[0]["id"]
                )
                self.store.settle(rows[0]["usage_id"], 0)
        return obj

    def submit(self, uid, pid, operation, args, request_id):
        self.store.project(uid, pid)
        direction = self.store.get("direction", pid)
        if (
            isinstance(direction, dict)
            and direction.get("status") == "awaiting_feedback"
        ):
            raise ValueError(
                "The proposed frame is waiting for user feedback. Ask the design question and end your turn. Do not generate narration or render until the user agrees and accept_video_direction records their reply."
            )
        if len(json.dumps(args).encode()) > 2100000:
            raise ValueError("Tool input exceeds 2 MB")
        if not 1 <= len(request_id) <= 120:
            raise ValueError("Provide a request ID of 1–120 characters")
        if self.store.get("control", "paused"):
            raise ValueError("Execution is paused")
        # Keep exact retries idempotent while allowing different projects to use export-1.
        legacy = self.store.sql(
            "SELECT * FROM public.vp_tasks WHERE owner=$1 AND request_id=$2",
            uid,
            request_id,
        )
        scoped_id = pid + ":" + request_id
        old = [t for t in legacy if t["project"] == pid] or self.store.sql(
            "SELECT * FROM public.vp_tasks WHERE owner=$1 AND request_id=$2",
            uid,
            scoped_id,
        )
        if old:
            if (
                old[0]["operation"] != operation
                or old[0]["payload"] != args
                or old[0]["project"] != pid
            ):
                raise ValueError(
                    "Request ID already used for different work in this project. Use a new request_id; only exact retries may reuse it."
                )
            return old[0]
        tid = ident()
        seconds = int(args.get("timeout", 300))
        if not 1 <= seconds <= 1800:
            raise ValueError("Command timeout must be 1–1800 seconds")
        usage = self.store.reserve(uid, "compute", seconds, scoped_id)
        try:
            task = self.store.sql(
                "INSERT INTO public.vp_tasks(id,owner,project,operation,request_id,payload,usage_id) VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7) RETURNING *",
                tid,
                uid,
                pid,
                operation,
                scoped_id,
                json.dumps(args),
                usage,
            )[0]
        except Exception:
            self.store.settle(usage, 0)
            raise
        self.running[tid] = asyncio.create_task(self.execute(task, seconds))
        self.running[tid].add_done_callback(lambda _: self.running.pop(tid, None))
        return task

    async def execute(self, task, seconds):
        uid, pid, tid = task["owner"], task["project"], task["id"]
        started = time.monotonic()
        sb = None
        try:
            async with self.lock(pid):
                sb = await self.session(uid, pid)
                self.store.sql(
                    "UPDATE public.vp_tasks SET status='running',updated=now() WHERE id=$1",
                    tid,
                )
                self.event(task, "Workspace ready")
                result = await asyncio.wait_for(self.perform(task, sb), seconds)
                if task.get("operation") not in ("review", "export", "preview"):
                    await self.checkpoint(uid, pid, sb)
                if result.get("exit_code", 0):
                    self.store.sql(
                        "UPDATE public.vp_tasks SET status='failed',result=$2::jsonb,error=$3,updated=now() WHERE id=$1",
                        tid,
                        json.dumps(result),
                        f"Command exited with code {result['exit_code']}; inspect stderr and correct the command.",
                    )
                    record_progress(
                        self.store,
                        pid,
                        "needs_attention",
                        "Fixing a rendering issue.",
                        "Inspect the failed command and retry with a new request_id.",
                    )
                else:
                    self.store.sql(
                        "UPDATE public.vp_tasks SET status='succeeded',result=$2::jsonb,updated=now() WHERE id=$1",
                        tid,
                        json.dumps(result),
                    )
                self.event(task, "Saved project source")
        except asyncio.CancelledError:
            if sb:
                with contextlib.suppress(Exception):
                    await self.stop(pid)
            self.store.sql(
                "UPDATE public.vp_tasks SET status='cancelled',error='Cancelled; previous checkpoint retained',updated=now() WHERE id=$1",
                tid,
            )
        except Exception as exc:
            message = (
                "Task timed out; previous checkpoint retained"
                if isinstance(exc, asyncio.TimeoutError)
                else str(exc)[:500]
            )
            for secret in (self.config.api_key, self.config.speech_key):
                if secret:
                    message = message.replace(secret, "[redacted]")
            if isinstance(exc, asyncio.TimeoutError) and sb:
                with contextlib.suppress(Exception):
                    await self.stop(pid)
            self.store.sql(
                "UPDATE public.vp_tasks SET status='failed',error=$2,updated=now() WHERE id=$1",
                tid,
                message,
            )
        finally:
            self.store.settle(
                task["usage_id"], min(seconds, math.ceil(time.monotonic() - started))
            )
            if pid in self.sessions:
                self.sessions[pid]["touched"] = time.time()

    async def perform(self, task, sb):
        uid, pid, tid = task["owner"], task["project"], task["id"]
        a = task["payload"]
        op = task["operation"]
        direction = self.store.get("direction", pid)
        if isinstance(direction, dict) and direction.get("status") == "approved":
            # Preserve the selected design for future turns and restored workspaces.
            if (
                self.sessions.get(pid, {}).get("direction_object")
                != direction["preview_object"]
            ):
                await sb.write("edit/direction.json", json.dumps(direction).encode())
                rows = self.store.sql(
                    "SELECT key FROM public.vp_objects WHERE id=$1 AND owner=$2",
                    direction["preview_object"],
                    uid,
                )
                if not rows:
                    raise ValueError(
                        "The approved frame is no longer available; propose a new direction"
                    )
                with tempfile.TemporaryDirectory() as tmp:
                    local = Path(tmp) / "direction.png"
                    await asyncio.to_thread(self.store.download, rows[0]["key"], local)
                    await sb.upload("edit/direction.png", local)
                if pid in self.sessions:
                    self.sessions[pid]["direction_object"] = direction["preview_object"]
        if op == "step":
            for item in a.get("files", []):
                await sb.write(item["path"], item["content"].encode())
            result = {"saved": [x["path"] for x in a.get("files", [])]}
            if a.get("command"):
                command = await sb.run(a["command"], a.get("timeout", 300))
                self.event(task, command["stdout"] + "\n" + command["stderr"])
                result.update(command)
                if command["exit_code"]:
                    record_progress(
                        self.store,
                        pid,
                        "needs_attention",
                        "The command needs a correction.",
                        a.get("next_action", "Inspect the command error and retry."),
                    )
                    return result
            preview = (
                await self.publish_preview(uid, pid, sb, a["preview_path"])
                if a.get("preview_path")
                else None
            )
            record_progress(
                self.store,
                pid,
                a["stage"],
                a["note"],
                a.get("next_action", ""),
                a.get("brief", ""),
                preview,
            )
            if preview:
                result["preview"] = preview
            if a.get("review_path"):
                result.update(
                    await self.perform(
                        task
                        | {
                            "operation": "review",
                            "payload": {"video_path": a["review_path"]},
                        },
                        sb,
                    )
                )
            return result
        if op == "preview":
            preview = await self.publish_preview(uid, pid, sb, a["path"])
            record_progress(
                self.store,
                pid,
                a["stage"],
                a["note"],
                a.get("next_action", ""),
                a.get("brief", ""),
                preview,
            )
            return {"preview": preview}
        if op == "run":
            r = await sb.run(a["command"], a.get("timeout", 300))
            self.event(task, r["stdout"] + "\n" + r["stderr"])
            return r
        if op == "write":
            if len(a["content"].encode()) > 2000000:
                raise ValueError("Source file exceeds 2 MB")
            await sb.write(a["path"], a["content"].encode())
            return {"saved": a["path"]}
        if op == "patch":
            old = (await sb.read(a["path"], 2000000)).decode()
            if not a["old"] or old.count(a["old"]) != 1:
                raise ValueError("Patch must match exactly once")
            await sb.write(a["path"], old.replace(a["old"], a["new"], 1).encode())
            return {"saved": a["path"]}
        if op in ("transcribe", "narrate"):
            if not self.config.speech_key:
                raise ValueError("Owner speech service is not configured")
            # Reuse the speech adapters without initializing or running a model agent.
            speech = object.__new__(ProductionAgent)
            speech.sandbox = sb
            speech.credentials = {
                "provider": "elevenlabs",
                "elevenlabs_key": self.config.speech_key,
                "elevenlabs_voice": self.config.voice,
            }
            if op == "transcribe":
                path = await sb.safe_path(a["path"])
                r = await sb.run("sha256sum " + shlex.quote(path), 30)
                if r["exit_code"]:
                    raise ValueError("Media not found")
                digest = r["stdout"].split()[0]
                cache = self.store.get("transcript", uid + ":" + digest)
                if cache:
                    await sb.write(
                        "edit/transcripts/" + digest + ".json",
                        json.dumps(cache).encode(),
                    )
                    return {
                        "path": "edit/transcripts/" + digest + ".json",
                        "cached": True,
                    }
                r = await sb.run(
                    "ffprobe -v error -show_format -of json " + shlex.quote(path), 30
                )
                duration = float(json.loads(r["stdout"])["format"]["duration"])
                if not math.isfinite(duration) or duration <= 0:
                    raise ValueError("Invalid media duration")
                self.store.reserve(uid, "transcribe", math.ceil(duration), tid)
                # Hash-based path prevents the legacy basename cache from returning stale words.
                await sb.run(
                    "cp "
                    + shlex.quote(path)
                    + " /workspace/sources/"
                    + digest
                    + Path(path).suffix,
                    60,
                )
                result = await speech.transcribe(
                    "sources/" + digest + Path(path).suffix
                )
                payload = json.loads(
                    await sb.read("edit/transcripts/" + digest + ".json", 2000000)
                )
                self.store.put("transcript", uid + ":" + digest, payload)
                return result
            text = a["text"]
            cachekey = (
                uid
                + ":"
                + hashlib.sha256((self.config.voice + text).encode()).hexdigest()
            )
            cached = self.store.get("narration", cachekey)
            if cached:
                with tempfile.TemporaryDirectory() as tmp:
                    local = Path(tmp) / "voice.mp3"
                    await asyncio.to_thread(self.store.download, cached["key"], local)
                    await sb.upload(a["output"], local)
                await sb.write(a["output"] + ".json", cached["timings"].encode())
                return {"saved": a["output"], "cached": True}
            rid = self.store.reserve(uid, "narrate", len(text), tid)
            result = await speech.narrate(text, a["output"])
            with tempfile.TemporaryDirectory() as tmp:
                local = Path(tmp) / "voice.mp3"
                await sb.download(a["output"], local)
                obj = await self.save_object(uid, pid, "speech", "voice.mp3", local)
            self.store.put(
                "narration",
                cachekey,
                {
                    "key": obj["key"],
                    "timings": (await sb.read(a["output"] + ".json")).decode(),
                },
            )
            self.store.settle(rid, len(text))
            return result
        if op in ("review", "export"):
            path = await sb.safe_path(a["video_path"])
            hashed = await sb.run("sha256sum " + shlex.quote(path), 30)
            if hashed["exit_code"]:
                raise ValueError("Video not found")
            digest = hashed["stdout"].split()[0]
            if op == "review":
                r = await sb.run(
                    "python -c " + shlex.quote(REVIEW) + " " + shlex.quote(path), 120
                )
                if r["exit_code"]:
                    raise ValueError("Could not extract encoded frames")
                with tempfile.TemporaryDirectory() as tmp:
                    local = Path(tmp) / "review.png"
                    await sb.download("edit/verify/output-review.png", local, 8000000)
                    obj = await self.save_object(
                        uid, pid, "review", "review.png", local
                    )
                record_progress(
                    self.store,
                    pid,
                    "review",
                    "Checking the rendered frames.",
                    "Inspect the returned image, then export this exact video if it passes.",
                    preview={
                        "object_id": obj["id"],
                        "media_type": "image/png",
                        "name": "review.png",
                        "draft": True,
                    },
                )
                return {
                    "review_object": obj["id"],
                    "sha256": digest,
                    "video_path": a["video_path"],
                    "instruction": "Inspect the image returned with this result. If it passes, export this exact video with an honest review summary. No extra status call is needed when the image is present.",
                }
            if self.store.get("reviewed", pid) != digest:
                raise ValueError(
                    "Call review_video to inspect the current encoded output before export. Poll get_video_task only if review is still running."
                )
            meta = await sb.inspect_video(path)
            with tempfile.TemporaryDirectory() as tmp:
                local = Path(tmp) / "video.mp4"
                await sb.download(path, local, 200000000)
                video = await self.save_object(uid, pid, "video", "video.mp4", local)
            archive = await self.checkpoint(uid, pid, sb)
            self.store.sql(
                "UPDATE public.vp_objects SET kind='archive' WHERE id=$1", archive["id"]
            )
            revision = ident()
            self.store.sql(
                "INSERT INTO public.vp_revisions(id,project,owner,video,archive,summary,metadata) VALUES($1,$2,$3,$4,$5,$6,$7::jsonb)",
                revision,
                pid,
                uid,
                video["id"],
                archive["id"],
                a["summary"][:4000],
                json.dumps(meta | {"sha256": digest}),
            )
            record_progress(
                self.store,
                pid,
                "complete",
                a["summary"][:1200],
                "Export complete. Continue in this project for revisions.",
            )
            return {
                "revision_id": revision,
                "video_id": video["id"],
                "source_id": archive["id"],
                **meta,
            }
        raise ValueError("Unknown operation")

    async def publish_preview(self, uid, pid, sb, source):
        """Publish bounded PNG or H.264 draft; it never marks final review complete."""
        path = await sb.safe_path(source)
        suffix = Path(path).suffix.lower()
        with tempfile.TemporaryDirectory() as tmp:
            if suffix in (".png", ".jpg", ".jpeg"):
                raw = await sb.read(source, 8000000)
                local = Path(tmp) / "preview.png"
                with Image.open(io.BytesIO(raw)) as im:
                    if im.width * im.height > 20000000:
                        raise ValueError("Preview image exceeds 20 megapixels")
                    im.thumbnail((1280, 1280))
                    im.convert("RGB").save(local, "PNG")
                kind, media_type = "review", "image/png"
            elif suffix in (".mp4", ".mov", ".webm", ".mkv"):
                draft = "edit/verify/preview-" + ident() + ".mp4"
                dest = await sb.safe_path(draft, write=True)
                r = await sb.run(
                    "ffmpeg -v error -y -i "
                    + shlex.quote(path)
                    + " -t 20 -vf "
                    + shlex.quote(
                        "scale=960:540:force_original_aspect_ratio=decrease:force_divisible_by=2,fps=24"
                    )
                    + " -c:v libx264 -preset veryfast -crf 25 -pix_fmt yuv420p -c:a aac -movflags +faststart "
                    + shlex.quote(dest),
                    120,
                )
                if r["exit_code"]:
                    raise ValueError("Could not encode preview clip")
                local = Path(tmp) / "preview.mp4"
                await sb.download(draft, local, 25000000)
                kind, media_type = "video", "video/mp4"
            else:
                raise ValueError("Preview must be a PNG, JPEG or video file")
            obj = await self.save_object(uid, pid, kind, local.name, local)
        return {
            "object_id": obj["id"],
            "media_type": media_type,
            "name": obj["name"],
            "draft": True,
        }

    async def image(self, uid, pid, path):
        async with self.lock(pid):
            sb = await self.session(uid, pid)
            raw = await sb.read(path, 8000000)
            with Image.open(io.BytesIO(raw)) as im:
                if im.width * im.height > 20000000:
                    raise ValueError("Image is larger than 20 megapixels")
                im.thumbnail((1600, 1600))
                out = io.BytesIO()
                im.convert("RGB").save(out, format="PNG")
                return out.getvalue()
