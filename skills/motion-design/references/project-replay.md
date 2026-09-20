# Authored projects and replay

The project helper preserves the exact request, the agent's creative interpretation, and the authored source separately. It does not classify prompts, select fixed scenes, call a model API, or promise identical designs from repeated natural-language requests. New briefs still require design and authoring. A completed package lets another user render the specific authored design or inspect and edit it.

## Create and author

```sh
python3 helpers/motion_project.py init --prompt-file /path/to/request.txt --output /path/to/project --duration 18
```

Initialization creates a draft manifest, the unmodified prompt, an empty creative-contract document, and an HTML scaffold that deliberately refuses to render. Author arbitrary HTML, CSS, JavaScript, SVG, Canvas, or WebGL within the project; expose `window.seek(seconds)` and optional `window.motionReady` as described in [browser-rendering.md](browser-rendering.md). There is no mandatory shot structure, palette, text treatment, or asset family. Set `authoringStatus` to `ready` only after implementing the composition.

The manifest `motion-project.json` uses `schemaVersion: 1`:

- `prompt`: relative UTF-8 file containing the exact user's request.
- `creativeContract`: separate relative UTF-8 document containing the authored interpretation and design decisions.
- `entry`: relative HTML entry, including nested paths when needed.
- `render`: `width`, `height`, `fps`, `duration`, relative MP4 `output`, optional relative `audio`, `posterTime`, and `stills` times.
- `runtime`: human-readable Node, Chrome, and FFmpeg requirements plus relative `dependencyDirectory` (default `runtime`).
- `provenance`: asset records; an optional `file` points to the actual local asset. Include origin, creator, license, and any redistribution constraints in each record.
- Optional authored fields such as `title`, `id`, `content`, or `review` remain available to the project; the helper does not interpret them as scene instructions.

Paths are relative to the manifest directory, never the current shell directory. Parent traversal, absolute paths, drive names, and symlink inputs are rejected. Duration must produce a whole number of frames at the selected frame rate. Path validity and a ready status do not prove successful execution or good design: the renderer checks the time contract, and visual review remains necessary.

## Check and render

```sh
python3 helpers/motion_project.py check /path/to/project
python3 helpers/motion_project.py render /path/to/project --deps /path/to/existing/dependencies --stills-only
python3 helpers/motion_project.py render /path/to/project --deps /path/to/existing/dependencies --output /path/to/exports/final.mp4 --qa
```

The external `--output` override keeps large renders outside source without storing machine-specific paths in the distributed manifest. `--chrome` or `CHROME_PATH` selects a local browser. `--overwrite` explicitly replaces an existing final video. `--qa` requires the existing NumPy/Pillow QA environment and runs mechanical decoding and delivery checks; it does not grade creativity.

## Portable source package

```sh
python3 helpers/motion_project.py pack /path/to/project --output /path/to/project.zip --deps-manifest skills/motion-design/runtime
```

The ZIP includes source and local assets, the exact prompt and contract, all three replay helpers, dependency `package.json` and `package-lock.json`, instructions, and SHA-256 checksums of the packaged bytes. Runtime dependencies must use exact versions and agree with the lockfile. If `--deps-manifest` is omitted, the helper first looks in the project's declared dependency directory, then in the repository's motion runtime. It never bundles `node_modules` or installs packages automatically.

The selected output video, `.render`/`.qa` artifacts, dependency caches, Git data, and nested ZIP archives are excluded. Required inputs excluded by those rules cause an error. Files larger than 32 MB require an intentional `--max-file-mb` increase; source footage is never silently dropped solely for being video. Write the archive outside its source project. Existing archives are protected, and a failed pack does not publish a partial archive.

After extraction, follow `REPLAY.md`: install the recorded Node dependency lock with `npm ci`, run the bundled `check`, then `render`. Chrome/Chromium and FFmpeg remain external platform requirements. The output render manifest records actual tool versions and served assets. The standard-library Python project wrapper itself needs Python 3.10 or newer; optional QA additionally needs NumPy and Pillow. Rendering a preserved project is reproducible at the scene/time level, but different browser builds, graphics drivers, fonts, and operating systems may produce pixel differences.

Packaged checksums are checked before rendering. Intentional source edits require moving the old `checksums.json` outside the project, then checking and repackaging to create an updated inventory. Keep the original ZIP as the reference version. These hashes detect accidental change; they are not cryptographic proof of who authored a package.
