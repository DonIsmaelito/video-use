"""Cloudflare R2 storage boundary for durable GUI video outputs."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote


R2_ENV_NAMES = (
    "R2_ACCOUNT_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET",
    "R2_PUBLIC_BASE_URL",
)
SAFE_ID_PATTERN = re.compile(r"[a-zA-Z0-9_-]+")


class R2StorageError(RuntimeError):
    """Raised when R2 configuration or an object operation is invalid."""


@dataclass(frozen=True)
class R2Config:
    account_id: str
    access_key_id: str = field(repr=False)
    secret_access_key: str = field(repr=False)
    bucket: str
    public_base_url: str

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "R2Config":
        values = environ or os.environ
        missing = [
            name for name in R2_ENV_NAMES if not str(values.get(name) or "").strip()
        ]
        if missing:
            raise R2StorageError("missing R2 configuration: " + ", ".join(missing))
        public_base_url = str(values["R2_PUBLIC_BASE_URL"]).strip().rstrip("/")
        if not public_base_url.startswith("https://"):
            raise R2StorageError("R2_PUBLIC_BASE_URL must use https://")
        return cls(
            account_id=str(values["R2_ACCOUNT_ID"]).strip(),
            access_key_id=str(values["R2_ACCESS_KEY_ID"]).strip(),
            secret_access_key=str(values["R2_SECRET_ACCESS_KEY"]).strip(),
            bucket=str(values["R2_BUCKET"]).strip(),
            public_base_url=public_base_url,
        )

    @property
    def endpoint_url(self) -> str:
        return f"https://{self.account_id}.r2.cloudflarestorage.com"


def safe_storage_id(value: str, *, label: str) -> str:
    cleaned = str(value)
    if SAFE_ID_PATTERN.fullmatch(cleaned) is None:
        raise ValueError(f"invalid {label}")
    return cleaned


def video_object_key(run_id: str, artifact_id: str) -> str:
    return (
        f"runs/{safe_storage_id(run_id, label='run id')}/"
        f"{safe_storage_id(artifact_id, label='artifact id')}.mp4"
    )


def poster_object_key(run_id: str) -> str:
    return f"runs/{safe_storage_id(run_id, label='run id')}/poster.jpg"


class R2Storage:
    """Small S3-compatible adapter that never exposes private endpoints."""

    def __init__(self, config: R2Config, client: Any | None = None) -> None:
        self.config = config
        if client is None:
            try:
                import boto3
                from botocore.config import Config
            except ImportError as exc:
                raise R2StorageError(
                    "boto3 is required for R2 storage; install gui/requirements.txt"
                ) from exc
            client = boto3.client(
                "s3",
                endpoint_url=config.endpoint_url,
                aws_access_key_id=config.access_key_id,
                aws_secret_access_key=config.secret_access_key,
                region_name="auto",
                config=Config(signature_version="s3v4"),
            )
        self.client = client

    @classmethod
    def from_env(cls) -> "R2Storage":
        return cls(R2Config.from_env())

    def public_url(self, key: str) -> str:
        return f"{self.config.public_base_url}/{quote(key, safe='/')}"

    def upload_file(self, path: Path, key: str, *, content_type: str) -> str:
        source = path.resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
        size = source.stat().st_size
        self.client.upload_file(
            str(source),
            self.config.bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )
        self.verify_object(key, expected_size=size)
        return self.public_url(key)

    def verify_object(
        self, key: str, *, expected_size: int | None = None
    ) -> dict[str, Any]:
        metadata = dict(self.client.head_object(Bucket=self.config.bucket, Key=key))
        if (
            expected_size is not None
            and int(metadata.get("ContentLength", -1)) != expected_size
        ):
            raise R2StorageError(
                f"R2 verification failed for {key}: object size does not match"
            )
        return metadata

    def delete_run(self, run_id: str) -> int:
        prefix = f"runs/{safe_storage_id(run_id, label='run id')}/"
        deleted = 0
        continuation_token: str | None = None
        while True:
            request: dict[str, Any] = {
                "Bucket": self.config.bucket,
                "Prefix": prefix,
                "MaxKeys": 1_000,
            }
            if continuation_token:
                request["ContinuationToken"] = continuation_token
            page = self.client.list_objects_v2(**request)
            objects = [{"Key": str(item["Key"])} for item in page.get("Contents") or []]
            if objects:
                result = self.client.delete_objects(
                    Bucket=self.config.bucket,
                    Delete={"Objects": objects, "Quiet": True},
                )
                errors = result.get("Errors") or []
                if errors:
                    raise R2StorageError(
                        f"R2 deletion failed for {errors[0].get('Key', prefix)}"
                    )
                deleted += len(objects)
            if not page.get("IsTruncated"):
                break
            continuation_token = str(page.get("NextContinuationToken") or "")
            if not continuation_token:
                raise R2StorageError(
                    "R2 returned a truncated listing without a continuation token"
                )
        remaining = self.client.list_objects_v2(
            Bucket=self.config.bucket,
            Prefix=prefix,
            MaxKeys=1,
        )
        if remaining.get("Contents"):
            raise R2StorageError(f"R2 deletion verification failed for {prefix}")
        return deleted
