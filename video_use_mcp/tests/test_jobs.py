import asyncio

from video_use_mcp.config import Settings
from video_use_mcp.jobs import JobManager
from video_use_mcp.store import Store


class FakeSandbox:
    def __init__(self):
        self.started = False
        self.closed = False
        self.uploads = []
        self.commands = []

    async def start(self):
        self.started = True

    async def close(self):
        self.closed = True

    async def upload(self, name, path):
        self.uploads.append(name)

    async def run(self, command, timeout):
        self.commands.append(command)
        return {"exit_code": 0, "stdout": "source.mp4", "stderr": ""}

    async def download(self, name, path, max_bytes=None):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(
            b"finished-video" if name.endswith(".mp4") else b"project-archive"
        )
        return path.stat().st_size


class FakeAgent:
    def __init__(self, sandbox, credentials, settings, event):
        self.event = event

    async def run(self, prompt):
        self.event("Reviewed actual encoded frames")
        return {
            "path": "/workspace/edit/final.mp4",
            "summary": "Original film",
            "duration": 8,
            "width": 1920,
            "height": 1080,
            "total_tokens": 2000,
        }


def prepared(tmp_path):
    store = Store(tmp_path)
    uid = store.create_user("alice", "correct horse battery")
    store.put(
        "credentials",
        uid,
        {"provider": "openrouter", "model": "test", "key": "not-real"},
    )
    pid = store.create_project(uid, "Original film")["id"]
    source = tmp_path / "upload.mp4"
    source.write_bytes(b"source")
    store.add_asset(uid, pid, "source.mp4", source, 6)
    return store, uid, pid


def test_completed_job_preserves_source_and_restores_for_revision(tmp_path):
    store, uid, pid = prepared(tmp_path)
    workers = []

    def factory():
        worker = FakeSandbox()
        workers.append(worker)
        return worker

    manager = JobManager(
        store, Settings(tmp_path), sandbox_factory=factory, agent_factory=FakeAgent
    )
    first = store.queue_job(uid, pid, "Make a film", "original", 10)
    asyncio.run(manager.execute(first))
    saved = store.job(uid, first["id"])
    assert saved["status"] == "succeeded"
    assert (
        tmp_path / "jobs" / first["id"] / "video.mp4"
    ).read_bytes() == b"finished-video"
    assert (tmp_path / "jobs" / first["id"] / "project.zip").exists()
    assert workers[0].closed
    second = store.queue_job(uid, pid, "Make the typography larger", "revision", 10)
    asyncio.run(manager.execute(second))
    assert store.job(uid, second["id"])["status"] == "succeeded"
    assert workers[1].uploads == ["sources/source.mp4", "previous.zip"]
    assert any("extractall" in command for command in workers[1].commands)


def test_cancellation_terminates_worker_and_preserves_uploads(tmp_path):
    store, uid, pid = prepared(tmp_path)
    started = asyncio.Event()

    class SlowAgent(FakeAgent):
        async def run(self, prompt):
            started.set()
            await asyncio.sleep(3600)

    sandbox = FakeSandbox()
    manager = JobManager(
        store,
        Settings(tmp_path),
        sandbox_factory=lambda: sandbox,
        agent_factory=SlowAgent,
    )
    job = store.queue_job(uid, pid, "Make a film", None, 10)

    async def exercise():
        task = asyncio.create_task(manager.execute(job))
        manager.running[job["id"]] = task
        await started.wait()
        manager.cancel(uid, job["id"])
        await task

    asyncio.run(exercise())
    assert store.job(uid, job["id"])["status"] == "cancelled"
    assert sandbox.closed
    assert store.asset_rows(uid, pid)


def test_cancel_before_worker_starts_is_terminal(tmp_path):
    store, uid, pid = prepared(tmp_path)
    worker = FakeSandbox()
    manager = JobManager(store, Settings(tmp_path), sandbox_factory=lambda: worker)
    job = store.queue_job(uid, pid, "Make a film", None, 10)

    async def exercise():
        task = asyncio.create_task(manager.execute(job))
        manager.running[job["id"]] = task
        task.add_done_callback(lambda done: manager.finished(job["id"], done))
        manager.cancel(uid, job["id"])
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(exercise())
    assert store.job(uid, job["id"])["status"] == "cancelled"
    assert not worker.started
    assert not manager.running


def test_failure_removes_partial_output_and_closes_worker(tmp_path):
    store, uid, pid = prepared(tmp_path)

    class BrokenDownload(FakeSandbox):
        async def download(self, name, path, max_bytes=None):
            await super().download(name, path, max_bytes)
            if name.endswith(".zip"):
                raise OSError("Download interrupted")
            return path.stat().st_size

    worker = BrokenDownload()
    manager = JobManager(
        store,
        Settings(tmp_path),
        sandbox_factory=lambda: worker,
        agent_factory=FakeAgent,
    )
    job = store.queue_job(uid, pid, "Make a film", None, 10)
    asyncio.run(manager.execute(job))
    assert store.job(uid, job["id"])["status"] == "failed"
    assert worker.closed
    assert not (tmp_path / "jobs" / job["id"]).exists()
    assert store.asset_rows(uid, pid)


def test_project_delete_requires_owner_and_no_active_job(tmp_path):
    import pytest

    store, uid, pid = prepared(tmp_path)
    job = store.queue_job(uid, pid, "Make a film", None, 10)
    with pytest.raises(ValueError):
        store.remove_project(uid, pid)
    store.update_job(job["id"], "failed", error="test")
    with pytest.raises(KeyError):
        store.remove_project("different-user", pid)
    assert store.remove_project(uid, pid) == [job["id"]]
    with pytest.raises(KeyError):
        store.project(uid, pid)


def test_deleting_projects_does_not_reset_daily_usage(tmp_path):
    import pytest

    store, uid, pid = prepared(tmp_path)
    job = store.queue_job(uid, pid, "Make a film", None, 1)
    store.update_job(job["id"], "cancelled")
    store.remove_project(uid, pid)
    replacement = store.create_project(uid, "Another film")["id"]
    with pytest.raises(ValueError, match="Daily job limit"):
        store.queue_job(uid, replacement, "Another film", None, 1)
