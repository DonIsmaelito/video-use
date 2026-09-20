from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

# Modal imports Python modules from its own mount; harness assets live at the
# explicit image path rather than alongside that import mount.
ROOT = Path(os.getenv("VIDEO_USE_ROOT", Path(__file__).resolve().parents[1]))


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    public_url: str = "http://localhost:8787"
    encryption_key: str = ""
    invite_code: str = ""
    max_upload_bytes: int = 500 * 1024 * 1024
    max_user_bytes: int = 5 * 1024 * 1024 * 1024
    max_jobs_per_day: int = 10
    max_parallel_jobs: int = 2
    job_timeout: int = 1800
    max_agent_turns: int = 60
    max_total_tokens: int = 800_000
    modal_app: str = "video-use-mcp"

    @classmethod
    def from_env(cls) -> "Settings":
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env", override=False, interpolate=False)
        load_dotenv(ROOT / ".env.local", override=False, interpolate=False)
        public_url = os.getenv("VIDEO_USE_PUBLIC_URL", "http://localhost:8787").rstrip(
            "/"
        )
        url = urlsplit(public_url)
        if url.scheme != "https" and not (
            url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1"}
        ):
            raise ValueError("VIDEO_USE_PUBLIC_URL must use HTTPS, except on localhost")
        if url.path or url.query or url.fragment or url.username:
            raise ValueError(
                "VIDEO_USE_PUBLIC_URL must be an origin without a path or credentials"
            )
        return cls(
            data_dir=Path(
                os.getenv("VIDEO_USE_DATA_DIR", str(ROOT / ".mcp-data"))
            ).expanduser(),
            public_url=public_url,
            encryption_key=os.getenv("VIDEO_USE_ENCRYPTION_KEY", ""),
            invite_code=os.getenv("VIDEO_USE_INVITE_CODE", ""),
            max_parallel_jobs=int(os.getenv("VIDEO_USE_MAX_JOBS", "2")),
            max_total_tokens=int(os.getenv("VIDEO_USE_MAX_TOTAL_TOKENS", "800000")),
            modal_app=os.getenv("VIDEO_USE_MODAL_APP", "video-use-mcp"),
        )
