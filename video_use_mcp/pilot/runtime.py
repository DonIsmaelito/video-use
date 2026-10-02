"""Persistent project sessions and bounded commands, driven by the host assistant."""

import asyncio
import contextlib
import hashlib
import io
import json
import math
import re
from fractions import Fraction
import shlex
import tempfile
import time
from pathlib import Path

from PIL import Image

from video_use_mcp.sandbox import ModalSandbox
from video_use_mcp.agent import ProductionAgent
from video_use_mcp.review import REVIEW_CODE as REVIEW, REVIEW_INSTRUCTION
from .store import ident
from .interaction import record_progress
from .review_findings import merge_review_findings, require_resolved_review_findings
from .intake import intake_context

PACK = r"""
import pathlib,zipfile
root=pathlib.Path('/workspace');total=0;count=0
skip={'node_modules','.git','__pycache__','.cache','.npm','.venv','.assembly-cache','clips_preview','clips_graded','verify'}
with zipfile.ZipFile('/workspace/checkpoint.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in root.rglob('*'):
  if p.is_symlink() or not p.is_file() or not p.resolve().is_relative_to(root): continue
  rel=p.relative_to(root)
  if rel.parts[0] in {'sources','checkpoint.zip','restore.zip'} or any(x in skip for x in rel.parts): continue
  if p.suffix.lower() in {'.mp4','.mov','.mkv','.webm'}: continue
  total+=p.stat().st_size;count+=1
  if total>200000000 or count>10000: raise ValueError('Project source exceeds 200 MB or 10000 files')
  z.write(p,str(rel))
"""
RESTORE = r"""
import pathlib,zipfile
root=pathlib.Path('/workspace')
with zipfile.ZipFile('/workspace/restore.zip') as z:
 if len(z.infolist())>10000 or sum(i.file_size for i in z.infolist())>200000000: raise ValueError('Checkpoint too large')
 seen=set()
 for i in z.infolist():
  p=pathlib.PurePosixPath(i.filename)
  if (not p.parts or p.is_absolute() or '..' in p.parts or chr(92) in i.filename
      or p.parts[0] in {'sources','checkpoint.zip','restore.zip'}
      or not (root/i.filename).resolve().is_relative_to(root)
      or (i.external_attr>>16)&0o170000==0o120000
      or str(p) in seen): raise ValueError('Invalid archive path')
  seen.add(str(p))
 z.extractall(root)
"""


def require_production_intake(creative, operation, payload):
    """Honor explicit v1 intake before paid work; older projects keep their flow.

    Custom commands declare excerpt/full-video intent. We cannot infer their
    meaning from shell text. Ordinary reads/imports never enter this runner.
    """
    context = intake_context(creative)
    if context is None:
        return
    if context["phase"] in {"mode", "basics", "approach", "personalization", "references"}:
        raise ValueError(
            "Production is waiting for the user's intake choices. "
            + context["next_action"]
        )
    if context["mode"] != "hands_on":
        return
    intake = creative["intake"]
    if intake.get("excerpt_review", {}).get("status") == "approved":
        return
    if operation == "step":
        stage = payload.get("production_stage", "full_video")
        if stage not in {"excerpt", "full_video"}:
            raise ValueError("production_stage must be excerpt or full_video")
        needs_review = stage == "full_video"
    else:
        # Legacy arbitrary execution has no declared excerpt scope. Inspection,
        # speech and source edits can support the initial reviewed excerpt.
        needs_review = operation in {"run", "export"}
    if needs_review:
        raise ValueError(
            "The user chose hands-on involvement. Create and show a short excerpt, "
            "then obtain their explicit excerpt acceptance before producing or "
            "exporting the full video. Use production_stage='excerpt' only for "
            "that limited sample; do not label the complete film as an excerpt."
        )


def validate_production_timing(value):
    """Validate supplied render timings without changing creative preferences."""
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) - {"scenes", "narration_offset"}:
        raise ValueError(
            "production_timing accepts scenes and optional narration_offset"
        )
    scenes = value.get("scenes")
    if not isinstance(scenes, list) or not 1 <= len(scenes) <= 64:
        raise ValueError("production_timing needs 1–64 ordered scenes")
    normalized = []
    for scene in scenes:
        if not isinstance(scene, dict) or set(scene) != {"title", "seconds"}:
            raise ValueError("Each production scene needs title and seconds")
        title, seconds = scene["title"], scene["seconds"]
        if not isinstance(title, str) or not title.strip() or len(title) > 120:
            raise ValueError("Production scene titles must contain 1–120 characters")
        if (
            isinstance(seconds, bool)
            or not isinstance(seconds, (int, float))
            or not math.isfinite(seconds)
            or seconds <= 0
        ):
            raise ValueError("Production scene seconds must be finite and positive")
        normalized.append({"title": title.strip(), "seconds": float(seconds)})
    if sum(scene["seconds"] for scene in normalized) > 86400:
        raise ValueError("Production timeline exceeds 24 hours")
    out = {"scenes": normalized}
    offset = value.get("narration_offset")
    if offset is not None:
        if (
            isinstance(offset, bool)
            or not isinstance(offset, (int, float))
            or not math.isfinite(offset)
            or offset < 0
        ):
            raise ValueError("narration_offset must be finite and nonnegative")
        out["narration_offset"] = float(offset)
    return out


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
                    if v.get("sources_dirty"):
                        # Preserve expensive rendered caches in a healthy worker.
                        # Only session loss below recreates from checkpoint.
                        with tempfile.TemporaryDirectory() as tmp:
                            for obj in self.store.sql(
                                "SELECT * FROM public.vp_objects WHERE project=$1 AND kind='source'",
                                pid,
                            ):
                                local = Path(tmp) / obj["id"]
                                await asyncio.to_thread(
                                    self.store.download, obj["key"], local
                                )
                                await v["sandbox"].upload(
                                    "sources/" + obj["name"], local
                                )
                        v["sources_dirty"] = False
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
        if len(json.dumps(args).encode()) > 2100000:
            raise ValueError("Tool input exceeds 2 MB")
        if not 1 <= len(request_id) <= 120:
            raise ValueError("Provide a request ID of 1–120 characters")
        if self.store.get("control", "paused"):
            raise ValueError("Execution is paused")
        # An operation gets its own retry namespace: "first" may legitimately
        # identify both narration and a render. Retain exact retry protection
        # for earlier unscoped and project-scoped task records.
        scoped_id = pid + ":" + operation + ":" + request_id
        previous = self.store.sql(
            "SELECT * FROM public.vp_tasks WHERE owner=$1 AND request_id IN ($2,$3,$4) "
            "ORDER BY CASE WHEN request_id=$2 THEN 0 WHEN request_id=$3 THEN 1 ELSE 2 END",
            uid,
            scoped_id,
            pid + ":" + request_id,
            request_id,
        )
        old = [
            task
            for task in previous
            if task["project"] == pid and task["operation"] == operation
        ]
        if old:
            if old[0]["payload"] != args:
                raise ValueError(
                    "Request ID already used for different work in this project and operation. "
                    "Use a new request_id; only exact retries may reuse it."
                )
            return old[0]
        if operation == "step" and args.get("production_timing") is not None:
            validate_production_timing(args["production_timing"])
            timing_path = args.get("review_path") or args.get("preview_path") or ""
            if Path(timing_path).suffix.lower() not in {
                ".mp4",
                ".mov",
                ".mkv",
                ".webm",
            }:
                raise ValueError(
                    "production_timing needs an encoded video in review_path or preview_path"
                )
        creative = self.store.get("creative", pid)
        require_production_intake(creative, operation, args)
        if (
            isinstance(creative, dict)
            and operation == "step"
            and args.get("creative_revision") != creative["revision"]
        ):
            raise ValueError(
                "Creative preferences changed. Read get_video_project before rendering."
            )
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
        # Record a comparison baseline for speech/inspection too, without
        # changing the user-supplied payload used to identify exact retries.
        # Missing metadata must not strand an admitted task; the response then
        # reports an unknown baseline instead of claiming nothing changed.
        if isinstance(creative, dict) and type(creative.get("revision")) is int:
            with contextlib.suppress(Exception):
                self.store.put(
                    "task_context",
                    tid,
                    {"submitted_creative_revision": creative["revision"]},
                    ttl=2592000,
                )
        self.running[tid] = asyncio.create_task(self.execute(task, seconds))
        self.running[tid].add_done_callback(lambda _: self.running.pop(tid, None))
        return task

    async def execute(self, task, seconds):
        uid, pid, tid = task["owner"], task["project"], task["id"]
        started = time.monotonic()
        sb = None
        work_started = False
        try:
            async with self.lock(pid):
                require_production_intake(
                    self.store.get("creative", pid),
                    task.get("operation", "run"),
                    task.get("payload") or {},
                )
                work_started = True
                sb = await self.session(uid, pid)
                self.store.sql(
                    "UPDATE public.vp_tasks SET status='running',updated=now() WHERE id=$1",
                    tid,
                )
                self.event(task, "Workspace ready")
                result = await asyncio.wait_for(self.perform(task, sb), seconds)
                if task.get("operation") not in ("review", "export", "preview"):
                    await self.checkpoint(uid, pid, sb)
                pending_timing = result.pop("_production_timing", None)
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
                    if pending_timing:
                        latest = self.store.get("creative", pid) or {}
                        if (
                            latest.get("revision", 0)
                            == pending_timing["creative_revision"]
                        ):
                            self.store.put("production_timing", pid, pending_timing)
                            result["production_timing"] = pending_timing
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
                task["usage_id"],
                min(seconds, math.ceil(time.monotonic() - started))
                if work_started
                else 0,
            )
            if pid in self.sessions:
                self.sessions[pid]["touched"] = time.time()

    async def perform(self, task, sb):
        uid, pid, tid = task["owner"], task["project"], task["id"]
        a = task["payload"]
        op = task["operation"]
        creative = self.store.get("creative", pid)
        require_production_intake(creative, op, a)
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
        if creative and op == "step":
            if a.get("creative_revision") != creative["revision"]:
                raise ValueError(
                    "Creative preferences changed. Read get_video_project and adapt before rendering."
                )
            await sb.write("edit/creative.json", json.dumps(creative).encode())
        if creative and op == "export":
            if self.store.get("render_revision", pid) != creative["revision"]:
                raise ValueError(
                    "Creative preferences changed since rendering. Adapt and review before exporting."
                )
        if op == "step":
            for item in a.get("files", []):
                await sb.write(item["path"], item["content"].encode())
            result = {"saved": [x["path"] for x in a.get("files", [])]}
            if a.get("components"):
                sem = asyncio.Semaphore(2)

                async def render_component(component):
                    async with sem:
                        output = await sb.run(
                            component["command"], a.get("timeout", 300)
                        )
                        self.event(
                            task,
                            component["name"]
                            + "\n"
                            + output["stdout"]
                            + "\n"
                            + output["stderr"],
                        )
                        return {"name": component["name"], **output}

                results = await asyncio.gather(
                    *(render_component(c) for c in a["components"])
                )
                result["components"] = results
                if any(c["exit_code"] for c in results):
                    return result | {
                        "exit_code": 1,
                        "stderr": "A component failed; assembly was skipped. Inspect component results.",
                    }
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
            pending_timing = None
            timing_args = a
            if a.get("assembly_report"):
                report_bytes = await sb.read(a["assembly_report"])
                if len(report_bytes) > 100_000:
                    raise ValueError("Assembly timing report exceeds 100 KB")
                report = json.loads(report_bytes)
                timing = validate_production_timing(report.get("production_timing"))
                if timing is None:
                    raise ValueError("Assembly did not provide measured scene timings")
                timing_args = a | {"production_timing": timing}
                result["assembly"] = {
                    key: report.get(key)
                    for key in (
                        "quality",
                        "width",
                        "height",
                        "fps",
                        "duration",
                        "frame_count",
                        "scenes",
                        "audio_normalization",
                    )
                } | {"output": a["preview_path"]}
            if timing_args.get("production_timing") is not None:
                pending_timing = await self.production_timing_metadata(
                    task | {"payload": timing_args}, sb, creative
                )
                result["_production_timing"] = pending_timing
            # A movie supplied for review is already a useful playable draft.
            # Publish that movie, never the internal inspection contact sheet.
            preview_path = a.get("preview_path")
            if not preview_path and Path(a.get("review_path", "")).suffix.lower() in {
                ".mp4",
                ".mov",
                ".mkv",
                ".webm",
            }:
                preview_path = a["review_path"]
            preview = (
                await self.publish_preview(uid, pid, sb, preview_path)
                if preview_path
                else None
            )
            record_progress(
                self.store,
                pid,
                "draft" if preview and a["stage"] == "review" else a["stage"],
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
                            "payload": {
                                "video_path": a["review_path"],
                                "_production_timing": pending_timing,
                            },
                        },
                        sb,
                    )
                )
            if creative:
                result["creative_revision"] = creative["revision"]
                if a.get("command") or a.get("components"):
                    self.store.put("render_revision", pid, creative["revision"])
                latest = self.store.get("creative", pid)
                result["preferences_changed"] = (
                    latest["revision"] != creative["revision"]
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
            voice = a.get("voice_id") or self.config.voice
            speech.credentials = {
                "provider": "elevenlabs",
                "elevenlabs_key": self.config.speech_key,
                "elevenlabs_voice": voice,
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
            cachekey = uid + ":" + hashlib.sha256((voice + text).encode()).hexdigest()
            cached = self.store.get("narration", cachekey)
            if cached:
                with tempfile.TemporaryDirectory() as tmp:
                    local = Path(tmp) / "voice.mp3"
                    await asyncio.to_thread(self.store.download, cached["key"], local)
                    await sb.upload(a["output"], local)
                await sb.write(a["output"] + ".json", cached["timings"].encode())
                return {
                    "saved": a["output"],
                    "cached": True,
                    "voice_id": voice,
                    **await self.narration_metadata(sb, a["output"], cached["timings"]),
                }
            rid = self.store.reserve(uid, "narrate", len(text), tid)
            result = await speech.narrate(text, a["output"])
            with tempfile.TemporaryDirectory() as tmp:
                local = Path(tmp) / "voice.mp3"
                await sb.download(a["output"], local)
                obj = await self.save_object(uid, pid, "speech", "voice.mp3", local)
            timings = (await sb.read(a["output"] + ".json")).decode()
            self.store.put(
                "narration",
                cachekey,
                {"key": obj["key"], "timings": timings},
            )
            self.store.settle(rid, len(text))
            return (
                result
                | {"voice_id": voice}
                | await self.narration_metadata(sb, a["output"], timings)
            )
        if op in ("review", "export"):
            path = await sb.safe_path(a["video_path"])
            hashed = await sb.run("sha256sum " + shlex.quote(path), 30)
            if hashed["exit_code"]:
                raise ValueError("Video not found")
            digest = hashed["stdout"].split()[0]
            if op == "review":
                timing = a.get("_production_timing") or self.store.get(
                    "production_timing", pid
                )
                verified_timing = (
                    isinstance(timing, dict)
                    and timing.get("sha256") == digest
                    and timing.get("creative_revision", 0)
                    == (creative or {}).get("revision", 0)
                    and isinstance(timing.get("scenes"), list)
                )
                beats = (
                    timing["scenes"]
                    if verified_timing
                    else (creative or {}).get("beats", [])
                )
                r = await sb.run(
                    "python -c "
                    + shlex.quote(REVIEW)
                    + " "
                    + shlex.quote(path)
                    + " --beats-json "
                    + shlex.quote(json.dumps(beats)),
                    120,
                )
                if r["exit_code"]:
                    raise ValueError("Could not extract encoded frames")
                sampling = {}
                with contextlib.suppress(ValueError, TypeError):
                    report = json.loads(r["stdout"])
                    if isinstance(report, dict) and isinstance(
                        report.get("audio_evidence"), dict
                    ):
                        sampling["audio_evidence"] = report["audio_evidence"]
                    times = (
                        report.get("sample_times") if isinstance(report, dict) else None
                    )
                    if (
                        isinstance(times, list)
                        and times
                        and all(
                            isinstance(t, (int, float)) and math.isfinite(t) and t >= 0
                            for t in times
                        )
                    ):
                        sampling["sample_times"] = [round(t, 3) for t in times[:12]]
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
                    "timing_source": "production_timing"
                    if verified_timing
                    else "creative_plan",
                    **sampling,
                    "instruction": REVIEW_INSTRUCTION
                    + " If it passes, export this exact video with an honest review summary. No extra status call is needed when the image is present.",
                }
            if self.store.get("reviewed", pid) != digest:
                raise ValueError(
                    "Call review_video to inspect the current encoded output before export. Poll get_video_task only if review is still running."
                )
            findings = merge_review_findings(
                self.store.get("review_findings", pid) or [], a.get("findings")
            )
            # Persist even when publication is denied: a new encode or an
            # omitted list must not silently erase an acknowledged defect.
            self.store.put("review_findings", pid, findings)
            require_resolved_review_findings(findings)
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
            if (
                creative
                and self.store.get("creative", pid)["revision"] != creative["revision"]
            ):
                raise ValueError(
                    "Creative preferences changed during export. Adapt and review before publishing."
                )
            self.store.sql(
                "INSERT INTO public.vp_revisions(id,project,owner,video,archive,summary,metadata) VALUES($1,$2,$3,$4,$5,$6,$7::jsonb)",
                revision,
                pid,
                uid,
                video["id"],
                archive["id"],
                a["summary"][:4000],
                json.dumps(meta | {"sha256": digest, "review_findings": findings}),
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

    async def production_timing_metadata(self, task, sb, creative):
        """Bind reported scene boundaries to a measured, exact encoded video."""
        args = task["payload"]
        timing = validate_production_timing(args["production_timing"])
        video_path = args.get("review_path") or args.get("preview_path")
        if not video_path or Path(video_path).suffix.lower() not in {
            ".mp4",
            ".mov",
            ".mkv",
            ".webm",
        }:
            raise ValueError(
                "production_timing needs an encoded video in review_path or preview_path"
            )
        path = await sb.safe_path(video_path)
        probe = await sb.run(
            "ffprobe -v error -show_entries format=duration:stream=codec_type,duration,avg_frame_rate -of json "
            + shlex.quote(path),
            30,
        )
        if probe["exit_code"]:
            raise ValueError("Could not verify production timing against the video")
        media = json.loads(probe["stdout"])
        video = next(
            (
                stream
                for stream in media.get("streams", [])
                if stream.get("codec_type") == "video"
            ),
            None,
        )
        if video is None:
            raise ValueError("Production timing requires a video stream")
        duration = float(video.get("duration") or media["format"]["duration"])
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("Production video duration must be finite and positive")
        try:
            fps = float(Fraction(video.get("avg_frame_rate", "0/1")))
        except (ValueError, ZeroDivisionError):
            fps = 0
        tolerance = max(0.12, 2 / fps) if fps > 0 else 0.12
        total = sum(scene["seconds"] for scene in timing["scenes"])
        if abs(total - duration) > tolerance:
            raise ValueError(
                f"Production scenes total {total:.3f}s but the encoded video is {duration:.3f}s. "
                "Use the actual ordered scene durations, including opening/closing holds."
            )
        if timing.get("narration_offset", 0) > duration:
            raise ValueError("narration_offset is beyond the encoded video")
        hashed = await sb.run("sha256sum " + shlex.quote(path), 30)
        if hashed["exit_code"]:
            raise ValueError("Could not identify the production video")
        digest = hashed["stdout"].split()[0]
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("Could not identify the production video")
        return timing | {
            "duration": duration,
            "scene_duration_total": total,
            "sha256": digest,
            "video_path": video_path,
            "creative_revision": (creative or {}).get("revision", 0),
            "task_id": task["id"],
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": "reported_render_timeline",
        }

    async def narration_metadata(self, sb, output, timings):
        """Return usable timing evidence with the audio, avoiding another tool turn."""
        path = await sb.safe_path(output)
        probe = await sb.run(
            "ffprobe -v error -show_entries format=duration -of json "
            + shlex.quote(path),
            30,
        )
        if probe["exit_code"]:
            raise ValueError("Could not measure the saved narration")
        duration = float(json.loads(probe["stdout"])["format"]["duration"])
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("Narration has an invalid duration")
        words = json.loads(timings).get("words", [])
        sentences, current, clean_words = [], [], []
        for word in words:
            start, end = float(word["start"]), float(word["end"])
            if not all(math.isfinite(t) for t in (start, end)) or not 0 <= start <= end:
                raise ValueError("Narration contains invalid word timings")
            cleaned = {"text": str(word["text"]), "start": start, "end": end}
            current.append(cleaned)
            clean_words.append(cleaned)
            if re.search(r"[.!?。！？][\"'’”)]*$", str(word["text"])):
                sentences.append(
                    {
                        "text": " ".join(w["text"] for w in current),
                        "start": current[0]["start"],
                        "end": current[-1]["end"],
                    }
                )
                current = []
        if current:
            sentences.append(
                {
                    "text": " ".join(w["text"] for w in current),
                    "start": current[0]["start"],
                    "end": current[-1]["end"],
                }
            )
        return {
            "audio_path": output,
            "timing_path": output + ".json",
            "duration": duration,
            "speech_end": max((float(w["end"]) for w in words), default=None),
            "word_count": len(words),
            "sentence_timings": sentences,
            "word_timings": clean_words[:500],
            "word_timings_truncated": len(clean_words) > 500,
            "text": "Narration is ready. Use inline word_timings for label/reveal cues and sentence_timings for scene boundaries; full timings remain in timing_path. No timing probe is needed. Timing data alone is not a playback or listening check.",
        }

    async def publish_preview(self, uid, pid, sb, source):
        """Publish a complete short draft, or an explicitly labeled long excerpt."""
        metadata = {}
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
                probe = await sb.run(
                    "ffprobe -v error -show_entries format=duration:stream=codec_type,avg_frame_rate "
                    "-of json " + shlex.quote(path),
                    30,
                )
                if probe["exit_code"]:
                    raise ValueError("Could not inspect preview clip")
                info = json.loads(probe["stdout"])
                duration = float(info["format"]["duration"])
                video = next(
                    (s for s in info["streams"] if s["codec_type"] == "video"), None
                )
                if not video or not math.isfinite(duration) or duration <= 0:
                    raise ValueError("Preview must contain a nonempty video stream")
                try:
                    fps = Fraction(video.get("avg_frame_rate", "0/1"))
                except (ValueError, ZeroDivisionError):
                    fps = Fraction(0)
                # Keep lower frame rates; never duplicate 15 fps draft frames at 24 fps.
                fps_filter = ",fps=24" if fps > 24 else ""
                clip = min(duration, 120.0)
                r = await sb.run(
                    "ffmpeg -v error -y -i "
                    + shlex.quote(path)
                    + (" -t 120" if duration > 120 else "")
                    + " -vf "
                    + shlex.quote(
                        "scale=w='min(960,iw)':h='min(540,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2"
                        + fps_filter
                    )
                    + " -c:v libx264 -preset veryfast -crf 25 -pix_fmt yuv420p -c:a aac -movflags +faststart "
                    + shlex.quote(dest),
                    120,
                )
                metadata = {
                    "source_duration": duration,
                    "duration": clip,
                    "truncated": duration > 120,
                }
                if duration > 120:
                    metadata["preview_range"] = {"start": 0, "end": clip}
                    metadata["notice"] = (
                        "Preview excerpt: first 120 seconds. The source video is longer."
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
            **metadata,
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
