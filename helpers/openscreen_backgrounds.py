"""Portable, versioned wallpapers drawn by OpenScreen's native compositor.

Assets are unmodified upstream files. Keep their license and provenance manifest
alongside them when packaging this helper outside the full Video Use checkout.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


DEFAULT_PRESET = "aurora"
BACKGROUND_DIR = Path(__file__).resolve().parents[1] / "integrations" / "openscreen" / "backgrounds"


def list_backgrounds() -> list[dict]:
    """Return a fresh JSON-compatible catalog, including original asset metadata."""
    manifest = json.loads((BACKGROUND_DIR / "manifest.json").read_text(encoding="utf-8"))
    return [
        {**asset, "path": str(BACKGROUND_DIR / asset["file"]),
         "default": asset["name"] == DEFAULT_PRESET,
         "license": manifest["license"],
         "upstream_repository": manifest["upstream_repository"],
         "upstream_revision": manifest["upstream_revision"]}
        for asset in manifest["assets"]
    ]


def resolve_preset(name: str) -> Path:
    """Resolve a known preset to an absolute image path and verify its bytes.

    Custom paths and URLs are intentionally not accepted as preset identifiers.
    Missing or changed bundled images fail before native export is started.
    """
    catalog = list_backgrounds()
    preset = next((asset for asset in catalog if asset["name"] == name), None)
    if preset is None:
        choices = ", ".join(asset["name"] for asset in catalog)
        raise ValueError(f"Unknown OpenScreen background preset {name!r}; choose {choices}")
    path = (BACKGROUND_DIR / preset["file"]).resolve(strict=True)
    if path.parent != BACKGROUND_DIR.resolve():
        raise ValueError("OpenScreen background preset must be a bundled image")
    if hashlib.sha256(path.read_bytes()).hexdigest() != preset["sha256"]:
        raise ValueError(f"OpenScreen background preset {name!r} has changed; restore its pinned asset")
    return path
