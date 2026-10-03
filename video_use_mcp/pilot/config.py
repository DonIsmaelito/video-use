"""Server-only deployment settings; no model-agent credentials are required."""

import os
from dataclasses import dataclass


@dataclass
class Config:
    public_url: str
    studio_url: str
    insforge_url: str
    api_key: str
    encryption_key: str
    invite_code: str
    owner_email: str
    speech_key: str = ""
    voice: str = "21m00Tcm4TlvDq8ikWAM"
    bucket: str = "video-pilot"
    modal_app: str = "video-use-browser-pilot"
    job_timeout: int = 1800
    youtube_api_key: str = ""

    @classmethod
    def env(cls):
        return cls(
            **{
                k: os.environ["PILOT_" + k.upper()]
                for k in (
                    "public_url",
                    "studio_url",
                    "insforge_url",
                    "api_key",
                    "encryption_key",
                    "invite_code",
                    "owner_email",
                )
            },
            speech_key=os.getenv("ELEVENLABS_API_KEY", ""),
            youtube_api_key=os.getenv("PILOT_YOUTUBE_API_KEY", "") or os.getenv("YOUTUBE_API_KEY", ""),
        )
