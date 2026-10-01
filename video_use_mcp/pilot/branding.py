"""Optional MCP metadata using the repository's authentic Browser Use mark.

The four logo paths come unchanged from website/public/brand/browser-use.svg.
A dark backing keeps the white mark legible in either host theme. These assets
brand MCP metadata; the host controls its own permission dialog and may omit
custom icons. No app HTML can restyle that parent dialog.
"""

from pathlib import Path
from urllib.parse import urlsplit

from mcp.types import Icon, Tool

BRAND_WEBSITE = "https://browser-use.com"
PNG_ROUTE = "/brand/browser-use.png"
SVG_ROUTE = "/brand/browser-use.svg"
STATIC_DIR = Path(__file__).with_name("static")
PNG_PATH = STATIC_DIR / "browser-use.png"
SVG_PATH = STATIC_DIR / "browser-use.svg"


def browser_use_icons(public_url: str) -> list[Icon]:
    """Return same-origin PNG and vector choices for supporting MCP clients."""
    base = public_url.rstrip("/")
    parsed = urlsplit(base)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Use a public HTTP(S) server URL without credentials or query")
    # MCP requires PNG support when clients render icons; SVG support is optional.
    return [
        Icon(src=base + PNG_ROUTE, mimeType="image/png", sizes=["256x256"]),
        Icon(src=base + SVG_ROUTE, mimeType="image/svg+xml", sizes=["any"]),
    ]


def brand_tools(tools: list[Tool], public_url: str) -> list[Tool]:
    """Supply a fallback icon without changing tool permissions or app metadata."""
    icons = browser_use_icons(public_url)
    return [
        tool if tool.icons else tool.model_copy(update={"icons": icons})
        for tool in tools
    ]
