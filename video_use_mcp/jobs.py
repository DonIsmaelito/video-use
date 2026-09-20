"""Durable queue with isolated execution, cancellation, and retained editable revisions."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import shutil
import shlex
from pathlib import Path

from .agent import ProductionAgent
from .providers import ProviderError
from .sandbox import ModalSandbox

PACK_SOURCE = r"""
import pathlib, zipfile
root=pathlib.Path('/workspace/edit')
extensions={'.html','.css','.js','.mjs','.ts','.tsx','.py','.json','.md','.txt','.svg','.srt','.ass','.csv','.ttf','.otf','.woff','.woff2','.png','.jpg','.jpeg','.webp','.mp3','.wav'}
total=count=0
with zipfile.ZipFile('/workspace/project.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in root.rglob('*'):
  if p.is_symlink() or not p.is_file() or not p.resolve().is_relative_to(root): continue
  rel=p.relative_to(root)
  if any(x in {'node_modules','__pycache__','clips_graded','clips_preview','verify','media'} or x.endswith('.render') for x in rel.parts): continue
  size=p.stat().st_size
  if p.suffix.lower() not in extensions or size>32*1024*1024: continue
  count+=1; total+=size
  if count>3000 or total>200*1024*1024: raise ValueError('Editable project exceeds archive limit')
  z.write(p,'edit/'+str(rel))
"""

RESTORE_SOURCE = r"""
import pathlib,zipfile
root=pathlib.Path('/workspace')
with zipfile.ZipFile('/workspace/previous.zip') as z:
 if sum(x.file_size for x in z.infolist())>200*1024*1024: raise ValueError('Archive exceeds limit')
 for item in z.infolist():
  p=(root/item.filename).resolve()
  if not p.is_relative_to(root/'edit'): raise ValueError('Invalid source archive path')
 z.extractall(root)
"""


class JobManager:
    def __init__(
        self, store, settings, sandbox_factory=None, agent_factory=None, checkpoint=None
    ):
        self.store = store
        self.settings = settings
        self.sandbox_factory = sandbox_factory or (lambda: ModalSandbox(settings))
        self.agent_factory = agent_factory or ProductionAgent
        self.running = {}
        self.stopping = False
        self.loop_task = None
        self.checkpoint = checkpoint

    async def start(self):
        self.store.recover()
        self.loop_task = asyncio.create_task(self.dispatch())

    async def close(self):
        self.stopping = True
        if self.loop_task:
            self.loop_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.loop_task
        for task in list(self.running.values()):
            task.cancel()
        await asyncio.gather(*list(self.running.values()), return_exceptions=True)
        if self.checkpoint:
            await self.checkpoint()

    async def dispatch(self):
        ticks = 0
        while not self.stopping:
            for job in self.store.queued():
                if len(self.running) >= self.settings.max_parallel_jobs:
                    break
                if job["id"] in self.running:
                    continue
                task = asyncio.create_task(self.execute(job))
                self.running[job["id"]] = task
                task.add_done_callback(
                    lambda done, jid=job["id"]: self.finished(jid, done)
                )
            ticks += 1
            if self.checkpoint and ticks % 20 == 0:
                with contextlib.suppress(Exception):
                    await self.checkpoint()
            await asyncio.sleep(1)

    def finished(self, jid, task):
        self.running.pop(jid, None)
        # A task cancelled before its coroutine starts never reaches execute's
        # exception handler. Still persist a terminal state for that job.
        if task.cancelled():
            self.store.update_job(jid, "cancelled")

    def cancel(self, uid, jid):
        job = self.store.job(uid, jid)
        if job["status"] in {"succeeded", "failed", "cancelled"}:
            return job
        task = self.running.get(jid)
        if task:
            self.store.update_job(jid, "cancelling")
            task.cancel()
        else:
            self.store.update_job(jid, "cancelled")
        return self.store.job(uid, jid)

    async def execute(self, job):
        jid = job["id"]
        sandbox = None
        completed = False
        try:
            sandbox = self.sandbox_factory()
            self.store.update_job(jid, "running")
            await asyncio.wait_for(
                self.produce(job, sandbox), self.settings.job_timeout
            )
            completed = True
        except asyncio.CancelledError:
            self.store.update_job(
                jid,
                "cancelled",
                error="Stopped before completion. Previous revisions remain available.",
            )
        except asyncio.TimeoutError:
            self.store.update_job(
                jid,
                "failed",
                error="The job reached its 30 minute limit. Try a shorter or more focused brief.",
            )
        except ProviderError as exc:
            self.store.update_job(jid, "failed", error=str(exc))
        except Exception as exc:
            credentials = self.store.get("credentials", job["owner"]) or {}
            diagnostic = str(exc)
            for key in (credentials.get("key"), credentials.get("elevenlabs_key")):
                if key:
                    diagnostic = diagnostic.replace(key, "[redacted]")
            logging.getLogger(__name__).error(
                "Job %s failed: %s: %s", jid, type(exc).__name__, diagnostic[:1000]
            )
            # Never persist upstream exception bodies which may contain request headers.
            self.store.update_job(
                jid,
                "failed",
                error=f"The job could not finish ({type(exc).__name__}). Check worker configuration or try a narrower brief.",
            )
        finally:
            if not completed:
                shutil.rmtree(self.store.root / "jobs" / jid, ignore_errors=True)
            if sandbox:
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(sandbox.close(), 30)

    async def produce(self, job, sandbox):
        uid, pid, jid = job["owner"], job["project"], job["id"]
        credentials = self.store.get("credentials", uid)
        if not credentials or not credentials.get("key"):
            raise ProviderError(
                "Add your provider API key in Settings before creating a video."
            )
        event = lambda text: self.store.event(jid, text)
        event("Preparing your private render workspace")
        await sandbox.start()
        for asset in self.store.asset_rows(uid, pid):
            await sandbox.upload("sources/" + asset["name"], Path(asset["path"]))
        project = self.store.project(uid, pid)
        previous = self.store.latest_success(uid, pid)
        if previous:
            archive = self.store.root / "jobs" / previous["id"] / "project.zip"
            if archive.exists():
                await sandbox.upload("previous.zip", archive)
                restored = await sandbox.run(
                    "python -c " + shlex.quote(RESTORE_SOURCE), 60
                )
                if restored["exit_code"]:
                    raise RuntimeError("Could not restore previous source")
        listing = await sandbox.run(
            "find sources -maxdepth 1 -type f -printf '%f\n'", 30
        )
        prompt = f"Project: {project['title']}\nBrief: {job['prompt']}\nUploaded material:\n{listing['stdout']}"
        if previous:
            prompt += (
                "\nThis is a revision. Previous editable sources are in edit/. Previous outcome:\n"
                + (previous["result"] or {}).get("summary", "")
            )
        agent = self.agent_factory(sandbox, credentials, self.settings, event)
        result = await agent.run(prompt)
        event("Saving the video and editable project")
        output = self.store.root / "jobs" / jid
        output.mkdir(parents=True, exist_ok=True)
        result["size_bytes"] = await sandbox.download(
            result.pop("path"), output / "video.mp4"
        )
        packed = await sandbox.run("python -c " + shlex.quote(PACK_SOURCE), 60)
        if packed["exit_code"]:
            raise RuntimeError("Could not preserve editable source")
        result["source_bytes"] = await sandbox.download(
            "project.zip", output / "project.zip", 210 * 1024 * 1024
        )
        if (
            self.store.user_bytes(uid) + result["size_bytes"] + result["source_bytes"]
            > self.settings.max_user_bytes
        ):
            shutil.rmtree(output)
            raise ProviderError(
                "Workspace storage limit reached. Remove older projects before creating more videos."
            )
        self.store.update_job(jid, "succeeded", result=result)
        event("Ready · video decoded successfully and source saved")
