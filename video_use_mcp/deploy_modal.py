"""Deploy the browser workspace, OAuth server, and MCP endpoint on Modal.

The service uses one persistent coordinator. Each production job gets a separate
network-isolated sandbox with no credentials or other users' media.
"""

import os

import modal

from video_use_mcp.config import ROOT

app = modal.App("video-use-mcp")
volume = modal.Volume.from_name("video-use-mcp-data", create_if_missing=True)
runtime_id = os.environ.get("VIDEO_USE_RUNTIME_IMAGE")
if not runtime_id:
    raise RuntimeError("Deploy with: python -m video_use_mcp.deploy")
api_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "mcp>=1.30,<2",
        "fastapi>=0.115,<1",
        "uvicorn>=0.34,<1",
        "python-multipart>=0.0.20",
        "python-dotenv>=1,<2",
        "cryptography>=44",
        "argon2-cffi>=23",
        "httpx>=0.28,<1",
        "pillow",
    )
    .env(
        {
            "PYTHONPATH": "/opt/video-use",
            "VIDEO_USE_ROOT": "/opt/video-use",
            "VIDEO_USE_DATA_DIR": "/data",
            "VIDEO_USE_MODAL_APP": "video-use-mcp",
            "VIDEO_USE_RUNTIME_IMAGE": runtime_id,
        }
    )
    .add_local_dir(
        ROOT / "video_use_mcp",
        "/opt/video-use/video_use_mcp",
        ignore=["__pycache__", "*.pyc", "tests"],
    )
    .add_local_file(ROOT / "SKILL.md", "/opt/video-use/SKILL.md")
)


@app.function(
    image=api_image,
    volumes={"/data": volume},
    secrets=[modal.Secret.from_name("video-use-mcp-config")],
    min_containers=1,
    max_containers=1,
    cpu=0.25,
    memory=1024,
    timeout=3600,
)
@modal.concurrent(max_inputs=64)
@modal.asgi_app()
def web():
    from video_use_mcp.config import Settings
    from video_use_mcp.jobs import JobManager
    from video_use_mcp.sandbox import ModalSandbox
    from video_use_mcp.server import create_app
    from video_use_mcp.store import Store

    settings = Settings.from_env()
    store = Store(settings.data_dir, settings.encryption_key)
    runtime_image = modal.Image.from_id(os.environ["VIDEO_USE_RUNTIME_IMAGE"])
    manager = JobManager(
        store,
        settings,
        sandbox_factory=lambda: ModalSandbox(settings, runtime_image),
        checkpoint=volume.commit.aio,
    )
    return create_app(settings, store=store, manager=manager)
