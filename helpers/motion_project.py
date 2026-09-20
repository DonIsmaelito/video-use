#!/usr/bin/env python3
"""Preserve an authored motion project and replay or package it from any directory.

This command does not interpret a prompt or choose a scene. An agent authors the
project; its exact input, creative decisions, source, and render contract remain
separate. Rendering reproducibility is different from identical AI authoring.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import shlex
import subprocess
import sys
import tempfile
import zipfile

MANIFEST = "motion-project.json"
INTEGRITY = "checksums.json"
INCOMPLETE = "VIDEO_USE_AUTHORING_REQUIRED"
EXCLUDED_DIRS = {"node_modules", ".git", ".venv", "venv", "__pycache__", ".cache", ".pytest_cache", "_video_use"}


class ProjectError(ValueError):
    """An incomplete, unsafe, or inconsistent project."""


def read_json(path: Path) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ProjectError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProjectError(f"Cannot read {path.name}: {error}") from error
    if not isinstance(value, dict):
        raise ProjectError(f"{path.name} must contain an object")
    return value


def local_path(root: Path, value: str, *, required: bool = False) -> Path:
    """Resolve a portable path without traversal, drive names, or symlinks."""
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ProjectError(f"Invalid relative project path: {value!r}")
    parts = value.split("/")
    if any(part in ("", ".", "..") or ":" in part for part in parts) or PurePosixPath(value).is_absolute():
        raise ProjectError(f"Path must stay inside the project: {value!r}")
    target = root
    for part in parts:
        target = target / part
        if target.is_symlink():
            raise ProjectError(f"Symlinks are not portable project inputs: {value}")
    if required and not target.is_file():
        raise ProjectError(f"Missing project file: {value}")
    return target


def project_path(value: Path) -> Path:
    value = value.expanduser().absolute()
    if value.is_dir():
        value = value / MANIFEST
    if value.is_symlink():
        raise ProjectError("The manifest must not be a symlink")
    return value


def number(value, name: str, minimum: float = 0, *, integer: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value <= minimum:
        raise ProjectError(f"{name} must be a finite number greater than {minimum}")
    if integer and not isinstance(value, int):
        raise ProjectError(f"{name} must be an integer")
    return value


def check_project(value: Path, *, allow_draft: bool = False, verify: bool = True) -> tuple[Path, dict]:
    path = project_path(value)
    root = path.parent.resolve()
    data = read_json(path)
    if type(data.get("schemaVersion")) is not int or data["schemaVersion"] != 1:
        raise ProjectError("schemaVersion must be 1")
    status = data.get("authoringStatus")
    if status not in ("draft", "ready"):
        raise ProjectError("authoringStatus must be draft or ready")
    if status != "ready" and not allow_draft:
        raise ProjectError("Project is a draft: author its source and set authoringStatus to ready")
    for field in ("prompt", "creativeContract", "entry"):
        file = local_path(root, data.get(field), required=True)
        try:
            content = file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise ProjectError(f"{field} must be readable UTF-8") from error
        if not content.strip():
            raise ProjectError(f"{field} must not be empty")
        if field == "entry" and INCOMPLETE in content and not allow_draft:
            raise ProjectError("Entry is still the empty authoring scaffold")
    if Path(data["entry"]).suffix.lower() not in (".html", ".htm"):
        raise ProjectError("entry must be an HTML composition")
    render = data.get("render")
    if not isinstance(render, dict):
        raise ProjectError("render must contain delivery settings")
    for field in ("width", "height"):
        value = number(render.get(field), field, integer=True)
        if value % 2:
            raise ProjectError(f"{field} must be even for H264")
    fps = number(render.get("fps"), "fps")
    duration = number(render.get("duration"), "duration")
    if duration * fps < 1 or abs(round(duration * fps) - duration * fps) > 1e-6:
        raise ProjectError("duration × fps must be a positive integer frame count")
    output = local_path(root, render.get("output"))
    if output.suffix.lower() != ".mp4":
        raise ProjectError("render.output must end in .mp4")
    if render.get("audio") is not None:
        local_path(root, render["audio"], required=True)
    stills = render.get("stills", [])
    if not isinstance(stills, list):
        raise ProjectError("render.stills must be a list")
    for time in [*stills, render.get("posterTime", duration * .6)]:
        if isinstance(time, bool) or not isinstance(time, (int, float)) or not math.isfinite(time) or not 0 <= time < duration:
            raise ProjectError("Still and poster times must be in [0, duration)")
    runtime = data.get("runtime")
    if not isinstance(runtime, dict):
        raise ProjectError("runtime must describe required tools")
    local_path(root, runtime.get("dependencyDirectory", "runtime"))
    provenance = data.get("provenance", [])
    if not isinstance(provenance, list) or any(not isinstance(item, dict) for item in provenance):
        raise ProjectError("provenance must be a list of asset records")
    for item in provenance:
        if "file" in item:
            local_path(root, item["file"], required=True)
    if verify and (root / INTEGRITY).exists():
        verify_integrity(root)
    return root, data


def init_project(prompt_file: Path, output: Path, duration: float = 12, width: int = 1920, height: int = 1080, fps: float = 30) -> Path:
    prompt = prompt_file.read_text(encoding="utf-8")
    if not prompt.strip():
        raise ProjectError("Prompt must not be empty")
    output = output.expanduser().absolute()
    if output.exists() or output.is_symlink():
        raise ProjectError(f"Output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        (temporary / "prompt.txt").write_text(prompt, encoding="utf-8")
        (temporary / "creative-contract.md").write_text("# Creative contract\n\nAuthor the visual idea, structure, typography, movement, sound, and assets here.\n", encoding="utf-8")
        (temporary / "index.html").write_text(f'<!doctype html>\n<html lang="en"><meta charset="utf-8"><title>Unauthored motion project</title>\n<body><script>\n// {INCOMPLETE}: author this composition from the brief.\nwindow.seek = () => {{ throw new Error("Author this project before rendering"); }};\n</script></body></html>\n', encoding="utf-8")
        manifest = {"schemaVersion": 1, "authoringStatus": "draft", "prompt": "prompt.txt", "creativeContract": "creative-contract.md", "entry": "index.html", "render": {"width": width, "height": height, "fps": fps, "duration": duration, "output": "renders/final.mp4", "audio": None, "posterTime": duration * .6, "stills": [0, duration * .3, duration * .6]}, "provenance": [], "runtime": {"node": ">=22.12", "chrome": "Chrome or Chromium", "ffmpeg": "ffmpeg and ffprobe on PATH", "dependencyDirectory": "runtime"}}
        (temporary / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        check_project(temporary, allow_draft=True)
        if output.exists():
            raise ProjectError(f"Output already exists: {output}")
        temporary.rename(output)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return output / MANIFEST


def helper_path(name: str) -> Path:
    path = Path(__file__).resolve().with_name(name)
    if not path.is_file():
        raise ProjectError(f"Required replay helper missing: {name}")
    return path


def render_project(value: Path, *, output: Path | None = None, deps: Path | None = None, chrome: Path | None = None, stills_only: bool = False, qa: bool = False, overwrite: bool = False) -> None:
    root, data = check_project(value)
    settings = data["render"]
    target = output.expanduser().absolute() if output else local_path(root, settings["output"])
    dependency_dir = deps.expanduser().absolute() if deps else local_path(root, data["runtime"].get("dependencyDirectory", "runtime"))
    if qa and stills_only:
        raise ProjectError("Video QA requires a video export; omit --stills-only")
    args = ["node", str(helper_path("motion_render.mjs")), str(local_path(root, data["entry"], required=True)), "-o", str(target), "--root", str(root), "--deps", str(dependency_dir)]
    for field in ("width", "height", "fps", "duration"):
        args += [f"--{field}", str(settings[field])]
    args += ["--poster-time", str(settings.get("posterTime", settings["duration"] * .6))]
    if settings.get("stills"):
        args += ["--stills", ",".join(str(value) for value in settings["stills"])]
    if settings.get("audio"):
        args += ["--audio", str(local_path(root, settings["audio"], required=True))]
    if chrome:
        args += ["--chrome", str(chrome.expanduser().absolute())]
    if stills_only:
        args.append("--stills-only")
    if overwrite:
        args.append("--overwrite")
    subprocess.run(args, cwd=root, check=True)
    if qa:
        args = [sys.executable, str(helper_path("motion_qa.py")), str(target)]
        for field in ("width", "height", "fps", "duration"):
            args += [f"--expect-{field}", str(settings[field])]
        if settings.get("audio"):
            args.append("--expect-audio")
        subprocess.run(args, cwd=root, check=True)


def source_files(root: Path, data: dict) -> list[Path]:
    """Collect editable inputs, excluding known generated artifacts and caches."""
    output = PurePosixPath(data["render"]["output"])
    generated = {str(output), str(output.with_suffix(".render")), str(output.with_suffix(".qa"))}
    files = []
    for directory, dirs, names in os.walk(root, followlinks=False):
        relative_dir = Path(directory).relative_to(root)
        kept = []
        for name in sorted(dirs):
            relative = (relative_dir / name).as_posix()
            if name in EXCLUDED_DIRS or name.endswith((".render", ".qa")) or relative in generated:
                continue
            local_path(root, relative)
            kept.append(name)
        dirs[:] = kept
        for name in sorted(names):
            relative = (relative_dir / name).as_posix()
            if relative in generated or relative in {INTEGRITY, "REPLAY.md"} or name == ".DS_Store" or name == ".env" or name.startswith(".env.") or name.endswith((".pyc", ".zip")):
                continue
            path = local_path(root, relative, required=True)
            if path.is_file():
                files.append(path)
    return files


def pinned_dependencies(directory: Path) -> tuple[Path, Path]:
    package, lock = directory / "package.json", directory / "package-lock.json"
    package_data, lock_data = read_json(package), read_json(lock)
    dependencies = package_data.get("dependencies", {})
    if "puppeteer-core" not in dependencies:
        raise ProjectError("Runtime dependencies must include puppeteer-core")
    for name, version in dependencies.items():
        if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?", version):
            raise ProjectError(f"Runtime dependency must have an exact registry version: {name}")
    packages = lock_data.get("packages", {})
    if packages.get("", {}).get("dependencies") != dependencies:
        raise ProjectError("Runtime package and lockfile dependencies disagree")
    for name, version in dependencies.items():
        if packages.get(f"node_modules/{name}", {}).get("version") != version:
            raise ProjectError(f"Lockfile does not pin {name} at {version}")
    return package, lock


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def verify_integrity(root: Path) -> None:
    checksums = read_json(root / INTEGRITY)
    if checksums.get("schemaVersion") != 1 or not isinstance(checksums.get("files"), dict):
        raise ProjectError("Invalid checksums manifest")
    for relative, record in checksums["files"].items():
        path = local_path(root, relative, required=True)
        if not isinstance(record, dict) or record.get("bytes") != path.stat().st_size or record.get("sha256") != digest(path):
            raise ProjectError(f"Integrity mismatch: {relative}")
    if MANIFEST not in checksums["files"]:
        raise ProjectError("Integrity manifest must include motion-project.json")
    actual = {path.relative_to(root).as_posix() for path in source_files(root, read_json(root / MANIFEST))}
    tool_root = root / "_video_use"
    if tool_root.exists():
        for path in tool_root.rglob("*"):
            relative = path.relative_to(root).as_posix()
            local_path(root, relative)
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                actual.add(relative)
    unexpected = actual - checksums["files"].keys()
    if unexpected:
        raise ProjectError(f"Unrecorded project inputs: {', '.join(sorted(unexpected))}")


def pack_project(value: Path, output: Path, *, deps_manifest: Path | None = None, max_file_mb: float = 32) -> Path:
    root, data = check_project(value)
    output = output.expanduser().absolute()
    if output.suffix.lower() != ".zip":
        raise ProjectError("Package output must be a .zip archive")
    if output.exists() or output.is_symlink():
        raise ProjectError(f"Output already exists: {output}")
    if output.is_relative_to(root):
        raise ProjectError("Write the package outside the source project")
    limit = number(max_file_mb, "max-file-mb") * 1024 * 1024
    runtime_dir = local_path(root, data["runtime"].get("dependencyDirectory", "runtime"))
    if deps_manifest is None:
        deps_manifest = runtime_dir
        if not (deps_manifest / "package-lock.json").is_file():
            deps_manifest = Path(__file__).resolve().parents[1] / "skills/motion-design/runtime"
    package, lock = pinned_dependencies(deps_manifest)
    selected = {path.relative_to(root).as_posix(): path for path in source_files(root, data)}
    dependency_relative = runtime_dir.relative_to(root).as_posix()
    for source in (package, lock):
        selected[f"{dependency_relative}/{source.name}"] = source
    for name in ("motion_project.py", "motion_render.mjs", "motion_qa.py"):
        selected[f"_video_use/{name}"] = helper_path(name)
    for relative, path in selected.items():
        if path.stat().st_size > limit:
            raise ProjectError(f"{relative} exceeds {max_file_mb:g} MB; inspect it and raise --max-file-mb if required")
    # Assert every declared input survives exclusions; never silently drop audio.
    required = [MANIFEST, data["prompt"], data["creativeContract"], data["entry"]]
    required += [data["render"]["audio"]] if data["render"].get("audio") else []
    required += [item["file"] for item in data.get("provenance", []) if "file" in item]
    for relative in required:
        if relative not in selected:
            raise ProjectError(f"Required input is excluded from packaging: {relative}")
    replay = ("# Replay this authored motion project\n\n"
              "The exact user prompt is stored separately from the authored creative contract and source. "
              "Reusing a prompt with an AI author does not guarantee the same design. This package preserves the particular authored design for rendering. "
              "Browser, operating system, fonts, and graphics drivers may still affect pixels; consult the render manifest for the original runtime.\n\n"
              "Install Node >=22.12, Chrome or Chromium, FFmpeg and ffprobe. From this extracted directory:\n\n"
              f"```sh\nnpm ci --prefix {shlex.quote(dependency_relative)}\npython3 _video_use/motion_project.py check .\npython3 _video_use/motion_project.py render .\n```\n\n"
              "Use `--chrome /path/to/chrome` or CHROME_PATH if browser discovery needs assistance. "
              "Optional `render . --qa` additionally needs NumPy and Pillow in that Python environment. "
              "`--output /path/to/final.mp4` changes delivery location without editing the source contract.\n\n"
              "Checksums cover the packaged input files. Before intentionally editing source, move checksums.json out of the project; "
              "otherwise check/render correctly rejects changed inputs. Repack the edited project to create new checksums.\n")
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{output.stem}.", suffix=".zip", dir=output.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        records = {}
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for relative, source in sorted(selected.items()):
                # Hash the bytes actually archived, even if a source is concurrently edited.
                contents = source.read_bytes()
                if len(contents) > limit:
                    raise ProjectError(f"Input grew beyond its packaging limit: {relative}")
                archive.writestr(relative, contents)
                records[relative] = {"bytes": len(contents), "sha256": hashlib.sha256(contents).hexdigest()}
            contents = replay.encode("utf-8")
            archive.writestr("REPLAY.md", contents)
            records["REPLAY.md"] = {"bytes": len(contents), "sha256": hashlib.sha256(contents).hexdigest()}
            archive.writestr(INTEGRITY, json.dumps({"schemaVersion": 1, "files": records}, indent=2) + "\n")
        # Atomic publication and no clobber, including a destination created mid-pack.
        os.link(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Create an empty authoring workspace with an exact prompt")
    init.add_argument("--prompt-file", type=Path, required=True)
    init.add_argument("--output", type=Path, required=True)
    init.add_argument("--duration", type=float, default=12)
    init.add_argument("--width", type=int, default=1920)
    init.add_argument("--height", type=int, default=1080)
    init.add_argument("--fps", type=float, default=30)
    check = commands.add_parser("check", help="Check project paths, delivery contract, and packaged integrity")
    check.add_argument("project", type=Path)
    check.add_argument("--allow-draft", action="store_true")
    render = commands.add_parser("render", help="Render the authored source using its recorded contract")
    render.add_argument("project", type=Path)
    render.add_argument("--output", type=Path)
    render.add_argument("--deps", type=Path)
    render.add_argument("--chrome", type=Path)
    render.add_argument("--stills-only", action="store_true")
    render.add_argument("--qa", action="store_true")
    render.add_argument("--overwrite", action="store_true")
    pack = commands.add_parser("pack", help="Package source, local assets, pinned dependencies and replay tools")
    pack.add_argument("project", type=Path)
    pack.add_argument("--output", type=Path, required=True)
    pack.add_argument("--deps-manifest", type=Path)
    pack.add_argument("--max-file-mb", type=float, default=32)
    args = vars(parser.parse_args(argv))
    command = args.pop("command")
    try:
        if command == "init":
            print(f"Draft created: {init_project(**args)}")
        elif command == "check":
            root, data = check_project(args["project"], allow_draft=args["allow_draft"])
            print(f"Project valid: {root} ({data['authoringStatus']}); visual review remains required")
        elif command == "render":
            value = args.pop("project")
            render_project(value, **args)
        elif command == "pack":
            value = args.pop("project")
            print(f"Portable project: {pack_project(value, **args)}")
        return 0
    except (ProjectError, OSError, subprocess.CalledProcessError) as error:
        print(f"Motion project failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
