"""Verify task failure boundaries without spending cloud or speech allowance."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from video_use_mcp.pilot.runtime import Manager


def fixture():
    store = Mock()
    manager = Manager(
        store, SimpleNamespace(api_key="private-admin", speech_key="private-speech")
    )
    manager.session = AsyncMock(return_value=object())
    manager.checkpoint = AsyncMock()
    manager.stop = AsyncMock()
    task = {"owner": "user", "project": "project", "id": "task", "usage_id": "usage"}
    return manager, store, task


def status_queries(store):
    return [
        call.args[0] for call in store.sql.call_args_list if "status=" in call.args[0]
    ]


def test_success_only_after_source_checkpoint():
    manager, store, task = fixture()
    manager.perform = AsyncMock(return_value={"exit_code": 0})

    async def checkpoint(*args):
        assert not any("succeeded" in q for q in status_queries(store))

    manager.checkpoint.side_effect = checkpoint
    asyncio.run(manager.execute(task, 30))
    assert "succeeded" in status_queries(store)[-1]
    manager.checkpoint.assert_awaited_once()
    store.settle.assert_called_once()


def test_checkpoint_failure_never_reports_success_and_redacts_credentials():
    manager, store, task = fixture()
    manager.perform = AsyncMock(return_value={"exit_code": 0})
    manager.checkpoint.side_effect = ValueError(
        "private-admin private-speech unavailable"
    )
    asyncio.run(manager.execute(task, 30))
    assert "failed" in status_queries(store)[-1]
    assert "private-admin" not in str(store.sql.call_args_list)
    assert "private-speech" not in str(store.sql.call_args_list)
    store.settle.assert_called_once()


@pytest.mark.parametrize("cancel", [False, True])
def test_timeout_or_cancel_stops_workspace_without_checkpoint(cancel):
    manager, store, task = fixture()

    async def perform(*args):
        if cancel:
            raise asyncio.CancelledError()
        await asyncio.sleep(60)

    manager.perform = perform
    asyncio.run(manager.execute(task, 0.01))
    manager.stop.assert_awaited_once_with("project")
    manager.checkpoint.assert_not_awaited()
    assert ("cancelled" if cancel else "failed") in status_queries(store)[-1]
    store.settle.assert_called_once()


def test_runtime_image_does_not_shadow_frame_reader():
    import io
    from PIL import Image

    data = io.BytesIO()
    Image.new("RGB", (20, 10), "purple").save(data, "PNG")
    runtime_image = object()
    manager = Manager(Mock(), SimpleNamespace(), image=runtime_image)
    manager.session = AsyncMock(
        return_value=SimpleNamespace(read=AsyncMock(return_value=data.getvalue()))
    )
    result = asyncio.run(manager.image("u", "p", "edit/frame.png"))
    assert Image.open(io.BytesIO(result)).size == (20, 10)
    assert manager.runtime_image is runtime_image


def test_nonzero_exit_is_failed_with_logs_preserved():
    manager, store, task = fixture()
    store.get.return_value = None
    manager.perform = AsyncMock(
        return_value={"exit_code": 2, "stderr": "missing input"}
    )
    asyncio.run(manager.execute(task, 30))
    assert "failed" in status_queries(store)[-1]
    assert "missing input" in str(store.sql.call_args_list)
    manager.checkpoint.assert_awaited_once()


def test_idle_workspace_survives_coordinator_shutdown_and_adoption():
    async def scenario():
        store = Mock()
        store.sql.side_effect = (
            lambda query, *args: [
                {"id": "p", "owner": "u", "sandbox_id": "sb-test", "touched": 123}
            ]
            if "SELECT id,owner,sandbox_id" in query
            else []
        )
        instance = SimpleNamespace(
            poll=SimpleNamespace(aio=AsyncMock(return_value=None)),
            detach=SimpleNamespace(aio=AsyncMock()),
            terminate=SimpleNamespace(aio=AsyncMock()),
        )
        manager = Manager(store, SimpleNamespace())
        with patch("modal.Sandbox.from_id.aio", AsyncMock(return_value=instance)):
            await manager.start()
            assert manager.sessions["p"]["sandbox"].instance is instance
            assert manager.sessions["p"]["created"] == 123
            await manager.close()
        instance.terminate.aio.assert_not_awaited()
        instance.detach.aio.assert_awaited_once()
        assert not any("sandbox_id=NULL" in c.args[0] for c in store.sql.call_args_list)

    asyncio.run(scenario())


def test_request_ids_are_project_scoped_and_exact_retries_reuse_tasks():
    async def scenario():
        store = Mock()
        store.get.return_value = None
        tasks = [
            {
                "project": "old-project",
                "request_id": "export-1",
                "operation": "export",
                "payload": {},
            }
        ]

        def sql(query, *args):
            if query.startswith("SELECT * FROM public.vp_tasks"):
                return [t for t in tasks if t["request_id"] == args[1]]
            if query.startswith("INSERT INTO public.vp_tasks"):
                import json

                t = dict(
                    id=args[0],
                    owner=args[1],
                    project=args[2],
                    operation=args[3],
                    request_id=args[4],
                    payload=json.loads(args[5]),
                )
                tasks.append(t)
                return [t]
            return []

        store.sql.side_effect = sql
        manager = Manager(store, SimpleNamespace())
        manager.execute = AsyncMock()
        args = {"video_path": "edit/final.mp4"}
        first = manager.submit("u", "new-project", "export", args, "export-1")
        again = manager.submit("u", "new-project", "export", args, "export-1")
        assert first["id"] == again["id"]
        assert first["request_id"] == "new-project:export:export-1"
        store.reserve.assert_called_once()
        with pytest.raises(ValueError, match="new request_id"):
            manager.submit(
                "u",
                "new-project",
                "export",
                {"video_path": "different.mp4"},
                "export-1",
            )
        await asyncio.gather(*list(manager.running.values()))

    asyncio.run(scenario())


def test_deploy_refuses_workspace_between_tool_calls():
    from video_use_mcp.pilot.deploy import ensure_quiet

    store = Mock()
    store.sql.side_effect = [[], [{"id": "active-project"}]]
    with pytest.raises(RuntimeError, match="between calls"):
        ensure_quiet(store)
