"""Fresh Modal sandboxes contain the harness and one project's files, never API keys."""

from __future__ import annotations

import asyncio
import json
import shlex
from pathlib import Path, PurePosixPath

from .config import ROOT


def worker_image():
    import modal

    return (
        modal.Image.from_registry("node:22-bookworm-slim", add_python="3.12")
        .apt_install(
            "ffmpeg",
            "poppler-utils",
            "chromium",
            "fonts-dejavu-core",
            "fonts-liberation",
            "fonts-noto-core",
            "fonts-noto-cjk",
            "libcairo2-dev",
            "libpango1.0-dev",
            "pkg-config",
        )
        .apt_install("build-essential")
        # Modal's injected standalone Python retains /install in extension-build
        # metadata even though the distribution is copied to /usr/local.
        .run_commands(
            "test -f /usr/local/include/python3.12/Python.h && ln -s /usr/local /install"
        )
        .env({"CC": "gcc", "CXX": "g++"})
        .pip_install(
            "requests",
            "python-dotenv>=1,<2",
            "librosa",
            "matplotlib",
            "pillow",
            "numpy",
            "pypdf>=5,<7",
            "manim>=0.19,<0.20",
            "opencv-python-headless>=4.8,<5",
        )
        # Manim's default MathTex template needs standalone, AMS fonts and SVG
        # conversion. Keep this separate from the Python build cache.
        .apt_install(
            "texlive-latex-base",
            "texlive-latex-extra",
            "texlive-fonts-recommended",
            "dvisvgm",
        )
        .add_local_dir(
            ROOT / "helpers",
            "/opt/video-use/helpers",
            copy=True,
            ignore=["__pycache__", "*.pyc"],
        )
        .add_local_dir(
            ROOT / "skills",
            "/opt/video-use/skills",
            copy=True,
            ignore=["node_modules", "__pycache__", "*.pyc"],
        )
        .add_local_dir(
            ROOT / "assets" / "models" / "yunet",
            "/opt/video-use/assets/models/yunet",
            copy=True,
        )
        .add_local_file(ROOT / "SKILL.md", "/opt/video-use/SKILL.md", copy=True)
        .run_commands(
            "npm ci --prefix /opt/video-use/skills/motion-design/runtime",
            "mkdir -p /workspace/sources /workspace/edit",
        )
        .env(
            {
                "CHROME_PATH": "/usr/bin/chromium",
                "PYTHONPATH": "/opt/video-use",
                "PYTHONUNBUFFERED": "1",
                "VIDEO_USE_ISOLATED_WORKER": "1",
            }
        )
    )


def workspace_path(path: str) -> str:
    value = PurePosixPath(path)
    if not value.is_absolute():
        value = PurePosixPath("/workspace") / value
    if ".." in value.parts or not value.is_relative_to("/workspace"):
        raise ValueError("File paths must stay inside /workspace")
    return str(value)


class ModalSandbox:
    def __init__(self, settings, image=None):
        self.settings = settings
        self.image = image
        self.instance = None

    async def start(self):
        import modal

        app = await modal.App.lookup.aio(
            self.settings.modal_app, create_if_missing=True
        )
        self.instance = await modal.Sandbox.create.aio(
            app=app,
            image=self.image or worker_image(),
            timeout=self.settings.job_timeout,
            cpu=(2.0, 4.0),
            memory=(4096, 8192),
            workdir="/workspace",
            block_network=True,
            include_oidc_identity_token=False,
        )

    async def close(self):
        if self.instance:
            await self.instance.terminate.aio()

    async def run(self, command: str, timeout=180):
        process = await self.instance.exec.aio(
            "bash", "-lc", command, timeout=min(int(timeout), 600), workdir="/workspace"
        )

        # Drain both pipes concurrently, with bounded retained output.
        async def drain(reader):
            tail = ""
            async for chunk in reader:
                tail = (tail + chunk)[-16000:]
            return tail

        stdout, stderr = await asyncio.gather(
            drain(process.stdout), drain(process.stderr)
        )
        code = await process.wait.aio()
        return {"exit_code": code, "stdout": stdout, "stderr": stderr}

    async def safe_path(self, path, *, write=False):
        path = workspace_path(path)
        script = "import pathlib,sys; p=pathlib.Path(sys.argv[1]).resolve(); assert p.is_relative_to('/workspace'), 'Path escapes workspace'; print(p)"
        result = await self.run(
            "python -c " + shlex.quote(script) + " " + shlex.quote(path), 30
        )
        if result["exit_code"]:
            raise ValueError("Path escapes the project workspace")
        path = result["stdout"].strip()
        if write:
            await self.instance.filesystem.make_directory.aio(
                str(PurePosixPath(path).parent), create_parents=True
            )
        return path

    async def write(self, path, data: bytes):
        path = await self.safe_path(path, write=True)
        await self.instance.filesystem.write_bytes.aio(data, path)

    async def upload(self, path, local: Path):
        path = await self.safe_path(path, write=True)
        await self.instance.filesystem.copy_from_local.aio(local, path)

    async def read(self, path, max_bytes=8 * 1024 * 1024):
        path = await self.safe_path(path)
        info = await self.instance.filesystem.stat.aio(path)
        if info.size > max_bytes:
            raise ValueError("File exceeds the permitted size")
        data = await self.instance.filesystem.read_bytes.aio(path)
        if len(data) > max_bytes:
            raise ValueError("File exceeds the permitted size")
        return data

    async def download(self, path, local: Path, max_bytes=500 * 1024 * 1024):
        path = await self.safe_path(path)
        local.parent.mkdir(parents=True, exist_ok=True)
        try:
            info = await self.instance.filesystem.stat.aio(path)
            if info.size > max_bytes:
                raise ValueError("Output exceeds the permitted size")
            await self.instance.filesystem.copy_to_local.aio(path, local)
            total = local.stat().st_size
            if total > max_bytes:
                raise ValueError("Output exceeds the permitted size")
        except BaseException:
            local.unlink(missing_ok=True)
            raise
        return total

    async def inspect_video(self, path):
        path = await self.safe_path(path)
        result = await self.run(
            "ffprobe -v error -show_format -show_streams -of json " + shlex.quote(path),
            30,
        )
        if result["exit_code"]:
            raise ValueError("The output is not a readable video")
        value = json.loads(result["stdout"])
        video = next((s for s in value["streams"] if s["codec_type"] == "video"), None)
        if not video or float(value["format"].get("duration", 0)) <= 0:
            raise ValueError("The output must contain a nonempty video stream")
        result = await self.run(
            "ffmpeg -v error -xerror -i " + shlex.quote(path) + " -f null -", 300
        )
        if result["exit_code"]:
            raise ValueError("The output failed full decode verification")
        return {
            "duration": float(value["format"]["duration"]),
            "width": video["width"],
            "height": video["height"],
            "has_audio": any(s["codec_type"] == "audio" for s in value["streams"]),
        }
