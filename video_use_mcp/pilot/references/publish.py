"""Publish inspected reference samples using the linked InsForge CLI project."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
build = Path(sys.argv[1]).resolve()
manifest = json.loads((build / "manifest.json").read_text())
for key, sample in manifest["samples"].items():
    sample["sha256"] = hashlib.sha256((build / sample["file"]).read_bytes()).hexdigest()
    for field, path, mime in [
        ("url", build / sample["file"], "video/mp4"),
        ("poster_url", build / (key + ".render") / "poster.png", "image/png"),
    ]:
        name = f"{key}-{sample['sha256'][:12]}" + (".mp4" if field == "url" else ".png")
        result = subprocess.check_output(
            [
                "npx",
                "-y",
                "@insforge/cli",
                "storage",
                "upload",
                str(path),
                "--bucket",
                "video-references",
                "--key",
                "starter-v1/" + name,
                "--content-type",
                mime,
                "--json",
            ],
            cwd=root / "studio",
            text=True,
        )
        sample[field] = json.loads(result)["url"]
    print("Uploaded", key, flush=True)
manifest_path = root / "video_use_mcp/pilot/references/manifest.json"
existing = (
    json.loads(manifest_path.read_text()) if manifest_path.exists() else {"samples": {}}
)
manifest["samples"] = existing["samples"] | manifest["samples"]
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
