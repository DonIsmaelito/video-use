"""Verify task failure boundaries without spending cloud or speech allowance."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

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
