"""Render named Manim scenes once per source/settings version; reuse for audio edits.

python /opt/video-use/helpers/render_manim_cached.py edit/animations/script.py \
    SceneOne SceneTwo --quality preview
Outputs JSON with ordered video paths. Mix audio and mux those files separately.
Pass --dependency for non-Python inputs that affect the animation.
"""

import argparse
import ast
import fcntl
import hashlib
import json
import shutil
import subprocess
import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def _inputs_digest(inputs, settings):
    digest = hashlib.sha256(json.dumps(settings, sort_keys=True).encode())
    for path in inputs:
        digest.update(str(path).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:20]


def _scene_source(source, scene):
    """Ignore unrelated, static scene classes; fall back for dynamic Python.

    Shared helpers, constants, imports, base classes and referenced scene classes
    remain in every affected fingerprint. This never evaluates the source.
    """
    text = source.read_text()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text
    if any(isinstance(node, (ast.Global, ast.Nonlocal)) for node in ast.walk(tree)):
        return text
    dynamic = {
        "globals",
        "locals",
        "eval",
        "exec",
        "__import__",
        "__file__",
        "inspect",
        "vars",
        "getattr",
        "setattr",
        "delattr",
        "sys",
    }
    if any(
        isinstance(node, ast.Name) and node.id in dynamic for node in ast.walk(tree)
    ):
        return text
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue
        if not isinstance(
            node,
            (
                ast.Import,
                ast.ImportFrom,
                ast.Assign,
                ast.AnnAssign,
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
            ),
        ):
            return text
    classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
    standard_bases = {
        "Scene",
        "MovingCameraScene",
        "ThreeDScene",
        "ZoomedScene",
        "VectorScene",
        "LinearTransformationScene",
    }
    known_bases = set()
    module_values = set()
    numpy_aliases = {
        alias.asname or alias.name
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name == "numpy"
    }
    # Imported project factories can mutate shared objects or attach metaclasses.
    # Such programs retain the previous whole-file cache behavior.
    for node in tree.body:
        modules = (
            [node.module or ""]
            if isinstance(node, ast.ImportFrom)
            else (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else []
            )
        )
        if any(
            module.split(".")[0] not in {"manim", "numpy", "math"} for module in modules
        ):
            return text
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            if node.module == "manim":
                if any(alias.name == "*" for alias in node.names):
                    known_bases.update(standard_bases)
                known_bases.update(
                    alias.asname or alias.name
                    for alias in node.names
                    if alias.name in standard_bases
                )
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            module_values.update(
                item.id
                for target in targets
                for item in ast.walk(target)
                if isinstance(item, ast.Name)
            )
            # Calls evaluated at import time may register/modify other classes.
            # Numeric array construction is inert; unknown factories are not.
            for call in (item for item in ast.walk(node) if isinstance(item, ast.Call)):
                func = call.func
                if not (
                    isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Name)
                    and func.value.id in numpy_aliases
                    and func.attr == "array"
                ):
                    return text
    # Without an explicit Manim import, the base may use custom metaclass hooks.
    if not known_bases:
        return text
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in {
            "__subclasses__",
            "__globals__",
            "__dict__",
            "__mro__",
            "mro",
        }:
            return text
        root = node.func if isinstance(node, ast.Call) else node
        while isinstance(root, (ast.Attribute, ast.Subscript)):
            root = root.value
        if isinstance(root, ast.Name) and root.id in module_values:
            if isinstance(node, ast.Call) or (
                isinstance(node, (ast.Attribute, ast.Subscript))
                and isinstance(node.ctx, (ast.Store, ast.Del))
            ):
                return text
    candidates = set()
    changed = True
    while changed:
        changed = False
        for name, node in classes.items():
            if name in candidates:
                continue
            bases = [
                base.id
                if isinstance(base, ast.Name)
                else base.attr
                if isinstance(base, ast.Attribute)
                else ""
                for base in node.bases
            ]
            if bases and all(
                base in known_bases or base in candidates for base in bases
            ):
                candidates.add(name)
                changed = True
    if scene not in candidates:
        return text
    for name in candidates:
        node = classes[name]
        if node.decorator_list or node.keywords:
            return text
        for member in node.body:
            if isinstance(member, ast.Expr) and isinstance(member.value, ast.Constant):
                continue
            if not isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return text
            # Class creation must be inert when its body is omitted from a hash.
            if member.name in {"__init_subclass__", "__class_getitem__"}:
                return text
            annotations = [member.returns] + [
                arg.annotation
                for arg in (
                    member.args.posonlyargs + member.args.args + member.args.kwonlyargs
                )
            ]
            if any(
                isinstance(item, ast.Call)
                for annotation in annotations
                if annotation
                for item in ast.walk(annotation)
            ):
                return text
            if member.decorator_list or any(
                not isinstance(value, ast.Constant)
                for value in member.args.defaults
                + [v for v in member.args.kw_defaults if v]
            ):
                return text
    shared = [
        node
        for node in tree.body
        if not isinstance(node, ast.ClassDef) or node.name not in candidates
    ]
    required = {scene}
    pending = [*shared, classes[scene]]
    while pending:
        node = pending.pop()
        names = {item.id for item in ast.walk(node) if isinstance(item, ast.Name)}
        for name in (names & candidates) - required:
            required.add(name)
            pending.append(classes[name])
    selected = [
        node
        for node in tree.body
        if not isinstance(node, ast.ClassDef)
        or node.name not in candidates
        or node.name in required
    ]
    return ast.dump(
        ast.Module(body=selected, type_ignores=[]), include_attributes=False
    )


def _atomic_json(path, value):
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as file:
        json.dump(value, file, indent=2)
        temporary = Path(file.name)
    temporary.replace(path)


def render(source, scenes, quality="preview", dependencies=(), output=None):
    source = Path(source).resolve()
    if not scenes or len(set(scenes)) != len(scenes):
        raise ValueError("Provide distinct scene names")
    # Adjacent Python helpers participate in invalidation. Audio does not unless
    # explicitly named as a dependency: mixing it should not rerender visuals.
    inputs = sorted(
        set(source.parent.glob("*.py"))
        | {source}
        | {Path(p).resolve() for p in dependencies}
    )
    resolution = {"preview": (960, 540, 15), "final": (1920, 1080, 30)}[quality]
    try:
        renderer_version = version("manim")
    except PackageNotFoundError:
        renderer_version = "unknown"
    settings = {"resolution": resolution, "manim": renderer_version, "cache_schema": 2}
    fingerprint = _inputs_digest(inputs, settings)
    base = Path(output or source.parent / "media" / "video-use-cache").resolve()
    root = base / fingerprint
    root.mkdir(parents=True, exist_ok=True)
    # A stable working directory indexes immutable whole-scene snapshots. Changes
    # to external inputs/helpers invalidate that index as well as source snapshots.
    # Manim partial-animation reuse is disabled: it can skip updater state changes.
    working_key = _inputs_digest(
        [path for path in inputs if path != source], settings | {"source": str(source)}
    )
    work = base / ".work" / working_key
    work.mkdir(parents=True, exist_ok=True)
    # A pair of component commands can target this same source concurrently.
    # Serialize shared cache writes; separate source files still render in parallel.
    with (work / "render.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if fingerprint != _inputs_digest(inputs, settings):
            raise RuntimeError(
                "Animation sources changed while waiting to render; retry"
            )
        manifest = root / "manifest.json"
        cached = json.loads(manifest.read_text()) if manifest.exists() else {}
        missing = [
            name
            for name in scenes
            if not cached.get(name) or not Path(cached[name]).is_file()
        ]
        scene_index = work / "scenes.json"
        previous = json.loads(scene_index.read_text()) if scene_index.exists() else {}
        scene_keys = {
            name: hashlib.sha256(_scene_source(source, name).encode()).hexdigest()
            for name in scenes
        }
        for name in list(missing):
            prior = previous.get(name, {})
            if (
                prior.get("fingerprint") == scene_keys[name]
                and Path(prior.get("path", "")).is_file()
            ):
                cached[name] = prior["path"]
                missing.remove(name)
        if missing:
            width, height, fps = resolution
            subprocess.run(
                [
                    "manim",
                    "-r",
                    f"{width},{height}",
                    "--frame_rate",
                    str(fps),
                    "--progress_bar",
                    "none",
                    "--media_dir",
                    str(work),
                    # Cached animation chunks can skip updater time accumulation,
                    # including updaters attached by imported helpers. Reuse whole
                    # immutable scenes above; always render changed scenes from zero.
                    "--disable_caching",
                    str(source),
                    *missing,
                ],
                check=True,
                stdout=__import__("sys").stderr,
            )
            if fingerprint != _inputs_digest(inputs, settings):
                raise RuntimeError("Animation sources changed during rendering; retry")
            for name in missing:
                files = list(work.glob(f"videos/{source.stem}/*/{name}.mp4"))
                if len(files) != 1:
                    raise RuntimeError(f"Expected one rendered output for {name}")
                # Never point a saved source-version manifest at mutable working
                # outputs. Later renders cannot replace an earlier draft's frames.
                target = (
                    root / "videos" / source.stem / f"{height}p{fps}" / f"{name}.mp4"
                )
                target.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    dir=target.parent, delete=False
                ) as temp:
                    temporary = Path(temp.name)
                try:
                    shutil.copyfile(files[0], temporary)
                    temporary.replace(target)
                finally:
                    temporary.unlink(missing_ok=True)
                cached[name] = str(target)
        for name in scenes:
            previous[name] = {"fingerprint": scene_keys[name], "path": cached[name]}
        _atomic_json(manifest, cached)
        _atomic_json(scene_index, previous)
        return {
            "quality": quality,
            "rendered": missing,
            "reused": [s for s in scenes if s not in missing],
            "videos": [cached[s] for s in scenes],
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("scenes", nargs="+")
    parser.add_argument("--quality", choices=("preview", "final"), default="preview")
    parser.add_argument("--dependency", action="append", default=[])
    parser.add_argument("--output")
    args = parser.parse_args()
    print(
        json.dumps(
            render(args.source, args.scenes, args.quality, args.dependency, args.output)
        )
    )


if __name__ == "__main__":
    main()
