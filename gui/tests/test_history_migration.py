from __future__ import annotations

from pathlib import Path

import pytest

from gui.migrate_history import migrate
from gui.r2_storage import R2Config, R2Storage, R2StorageError
from gui.run_store import RunStore
from gui.server import LaneBroker
from gui.tests.test_r2_storage import FakeS3Client


def _storage(client: FakeS3Client | None = None) -> R2Storage:
    return R2Storage(
        R2Config(
            account_id="account",
            access_key_id="access",
            secret_access_key="secret",
            bucket="videos",
            public_base_url="https://public.example.test",
        ),
        client=client or FakeS3Client(),
    )


def _legacy_run(tmp_path: Path) -> tuple[RunStore, Path]:
    store = RunStore(tmp_path / "data")
    run_dir = store.ensure_run("lane-1-legacy")
    (run_dir / "output.mp4").write_bytes(b"primary")
    (run_dir / "output-square.mp4").write_bytes(b"square")
    (run_dir / "poster.jpg").write_bytes(b"poster")
    store.save_record(
        "lane-1-legacy",
        run_dir,
        {
            "run_id": "lane-1-legacy",
            "lane_id": 1,
            "status": "ready",
            "prompt": "make two versions",
            "started_at": "2026-09-01T10:00:00+00:00",
            "finished_at": "2026-09-01T10:02:00+00:00",
            "artifacts": [
                {
                    "id": "wide",
                    "label": "wide",
                    "url": "/api/artifacts/wide",
                    "primary": True,
                },
                {
                    "id": "square",
                    "label": "square",
                    "url": "/api/artifacts/square",
                    "primary": False,
                },
            ],
            "events": [],
        },
    )
    return store, run_dir


def test_legacy_migration_defaults_to_a_non_mutating_dry_run(tmp_path: Path) -> None:
    store, run_dir = _legacy_run(tmp_path)

    plan = migrate(store, apply=False)

    assert plan == [
        {
            "run_id": "lane-1-legacy",
            "videos": ["output.mp4", "output-square.mp4"],
            "poster": "poster.jpg",
        }
    ]
    assert (run_dir / "output.mp4").is_file()
    assert store.list_history() == []
    old_entry = next(
        item for item in store.list_runs() if item["run_id"] == "lane-1-legacy"
    )
    assert old_entry["artifacts"][0]["video_url"].startswith("/api/")


def test_dry_run_does_not_create_an_absent_data_directory(tmp_path: Path) -> None:
    root = tmp_path / "does-not-exist"
    store = RunStore(root, create=False)

    assert migrate(store, apply=False) == []
    assert not root.exists()


def test_successful_migration_updates_index_after_verification_and_removes_media(
    tmp_path: Path,
) -> None:
    store, run_dir = _legacy_run(tmp_path)
    client = FakeS3Client()

    result = migrate(store, apply=True, storage=_storage(client))

    assert result[0]["poster_url"] == (
        "https://public.example.test/runs/lane-1-legacy/poster.jpg"
    )
    assert [item["id"] for item in result[0]["artifacts"]] == ["wide", "square"]
    assert not list(run_dir.glob("output*.mp4"))
    assert not (run_dir / "poster.jpg").exists()
    assert set(client.objects) == {
        "runs/lane-1-legacy/poster.jpg",
        "runs/lane-1-legacy/wide.mp4",
        "runs/lane-1-legacy/square.mp4",
    }
    restored = LaneBroker()
    restored.restore_completed_run(1, run_dir, store.history_item("lane-1-legacy"))
    assert restored.snapshot(1)["video_url"].startswith("https://public.example.test/")


def test_partial_migration_failure_keeps_local_files_and_old_index(
    tmp_path: Path,
) -> None:
    store, run_dir = _legacy_run(tmp_path)

    class BadVerificationClient(FakeS3Client):
        def head_object(self, *, Bucket: str, Key: str) -> dict:
            metadata = super().head_object(Bucket=Bucket, Key=Key)
            if Key.endswith("wide.mp4"):
                metadata["ContentLength"] += 1
            return metadata

    with pytest.raises(R2StorageError, match="object size does not match"):
        migrate(store, apply=True, storage=_storage(BadVerificationClient()))

    assert (run_dir / "output.mp4").is_file()
    assert (run_dir / "output-square.mp4").is_file()
    assert (run_dir / "poster.jpg").is_file()
    old_entry = next(
        item for item in store.list_runs() if item["run_id"] == "lane-1-legacy"
    )
    assert old_entry["artifacts"][0]["video_url"].startswith("/api/")


def test_migration_retry_overwrites_the_same_keys_idempotently(tmp_path: Path) -> None:
    store, run_dir = _legacy_run(tmp_path)
    client = FakeS3Client()
    storage = _storage(client)

    first = migrate(store, apply=True, storage=storage)
    (run_dir / "output.mp4").write_bytes(b"primary")
    (run_dir / "output-square.mp4").write_bytes(b"square")
    (run_dir / "poster.jpg").write_bytes(b"poster")
    second = migrate(store, apply=True, storage=storage)

    assert second == first
    assert len(client.objects) == 3
    assert not list(run_dir.glob("output*.mp4"))
