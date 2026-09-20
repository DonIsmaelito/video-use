from __future__ import annotations

from pathlib import Path

import pytest

from gui.r2_storage import (
    R2Config,
    R2Storage,
    R2StorageError,
    poster_object_key,
    video_object_key,
)


class FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.upload_args: list[dict] = []

    def upload_file(
        self, filename: str, bucket: str, key: str, ExtraArgs: dict
    ) -> None:
        self.objects[key] = Path(filename).read_bytes()
        self.upload_args.append(
            {"filename": filename, "bucket": bucket, "key": key, "extra": ExtraArgs}
        )

    def head_object(self, *, Bucket: str, Key: str) -> dict:
        return {"ContentLength": len(self.objects[Key])}

    def list_objects_v2(
        self, *, Bucket: str, Prefix: str, MaxKeys: int, **_kwargs
    ) -> dict:
        keys = sorted(key for key in self.objects if key.startswith(Prefix))[:MaxKeys]
        return {
            "Contents": [{"Key": key} for key in keys],
            "IsTruncated": False,
        }

    def delete_objects(self, *, Bucket: str, Delete: dict) -> dict:
        for item in Delete["Objects"]:
            self.objects.pop(item["Key"], None)
        return {}


def _config() -> R2Config:
    return R2Config(
        account_id="account",
        access_key_id="access",
        secret_access_key="secret",
        bucket="videos",
        public_base_url="https://public.example.test/base",
    )


def test_r2_upload_verifies_object_and_returns_only_public_url(tmp_path: Path) -> None:
    source = tmp_path / "output.mp4"
    source.write_bytes(b"video-bytes")
    client = FakeS3Client()
    storage = R2Storage(_config(), client=client)

    url = storage.upload_file(
        source,
        video_object_key("lane-1-example", "social_9x16"),
        content_type="video/mp4",
    )

    assert url == (
        "https://public.example.test/base/runs/lane-1-example/social_9x16.mp4"
    )
    assert client.upload_args[0]["bucket"] == "videos"
    assert client.upload_args[0]["extra"]["ContentType"] == "video/mp4"
    assert "account" not in url
    assert "access" not in url


def test_r2_delete_removes_and_verifies_the_complete_run_prefix() -> None:
    client = FakeS3Client()
    client.objects = {
        "runs/lane-2-example/preview.mp4": b"video",
        "runs/lane-2-example/poster.jpg": b"poster",
        "runs/lane-3-other/preview.mp4": b"other",
    }
    storage = R2Storage(_config(), client=client)

    assert storage.delete_run("lane-2-example") == 2
    assert set(client.objects) == {"runs/lane-3-other/preview.mp4"}


def test_r2_configuration_requires_every_secret_without_echoing_values() -> None:
    with pytest.raises(R2StorageError, match="R2_SECRET_ACCESS_KEY") as error:
        R2Config.from_env(
            {
                "R2_ACCOUNT_ID": "account",
                "R2_ACCESS_KEY_ID": "access",
                "R2_BUCKET": "bucket",
                "R2_PUBLIC_BASE_URL": "https://public.example.test",
            }
        )

    assert "access" not in str(error.value)
    assert poster_object_key("lane-1-example") == "runs/lane-1-example/poster.jpg"


def test_storage_ids_reject_path_traversal() -> None:
    with pytest.raises(ValueError, match="artifact id"):
        video_object_key("lane-1-example", "../secret")
