"""The pilot has one coordinator; Postgres persists state, Modal isolates code."""

import os
import modal
from video_use_mcp.config import ROOT

app = modal.App("video-use-browser-pilot")
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "mcp>=1.30,<2",
        "fastapi>=0.115,<1",
        "uvicorn>=0.34,<1",
        "python-multipart>=0.0.20",
        "cryptography>=44",
        "argon2-cffi>=23",
        "httpx>=0.28,<1",
        "pillow",
        "python-dotenv>=1,<2",
    )
    .env(
        {
            "PYTHONPATH": "/opt/video-use",
            "VIDEO_USE_ROOT": "/opt/video-use",
            "PILOT_RUNTIME_IMAGE": os.environ["PILOT_RUNTIME_IMAGE"],
            "PILOT_HARNESS_VERSION": os.environ["PILOT_HARNESS_VERSION"],
        }
    )
    .add_local_dir(
        ROOT / "video_use_mcp",
        "/opt/video-use/video_use_mcp",
        ignore=["__pycache__", "*.pyc", "tests", "node_modules", "**/node_modules/**"],
    )
    .add_local_dir(
        ROOT / "helpers", "/opt/video-use/helpers", ignore=["__pycache__", "*.pyc"]
    )
    .add_local_dir(
        ROOT / "skills",
        "/opt/video-use/skills",
        ignore=["node_modules", "__pycache__", "*.pyc"],
    )
    .add_local_file(ROOT / "SKILL.md", "/opt/video-use/SKILL.md")
)


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("video-use-browser-pilot-config")],
    min_containers=1,
    max_containers=1,
    cpu=0.25,
    memory=1024,
    timeout=3600,
)
@modal.concurrent(max_inputs=64)
@modal.asgi_app()
def web():
    from .config import Config
    from .store import Store
    from .runtime import Manager
    from .server import create_app

    config = Config.env()
    store = Store(config)
    runtime = modal.Image.from_id(os.environ["PILOT_RUNTIME_IMAGE"])
    return create_app(config, store, Manager(store, config, runtime))
