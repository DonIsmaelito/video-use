"""Server/tool metadata is additive; the authentic logo remains self contained."""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.types import Icon, Tool, ToolAnnotations
from PIL import Image

from video_use_mcp.pilot.branding import (
    BRAND_WEBSITE,
    PNG_PATH,
    PNG_ROUTE,
    SVG_PATH,
    SVG_ROUTE,
    brand_tools,
    browser_use_icons,
)
from video_use_mcp.pilot.interaction import UI_URI
from video_use_mcp.pilot.tests.test_cards import rpc

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]


def test_icons_are_same_origin_and_supported_raster_first():
    icons = browser_use_icons("https://video.example/")
    assert [icon.src for icon in icons] == [
        "https://video.example" + PNG_ROUTE,
        "https://video.example" + SVG_ROUTE,
    ]
    assert icons[0].mimeType == "image/png"
    assert icons[0].sizes == ["256x256"]
    assert icons[1].mimeType == "image/svg+xml"
    assert icons[1].sizes == ["any"]


@pytest.mark.parametrize(
    "url",
    ["javascript:alert(1)", "https://u:p@host.test", "https://host.test/?key=x"],
)
def test_icons_reject_nonpublic_or_credential_urls(url):
    with pytest.raises(ValueError):
        browser_use_icons(url)


def test_sdk_accepts_server_and_tool_icons_without_changing_permissions():
    icons = browser_use_icons("https://video.example")
    mcp = FastMCP("video-use", icons=icons, website_url=BRAND_WEBSITE)
    assert mcp._mcp_server.icons == icons
    assert str(mcp._mcp_server.website_url) == BRAND_WEBSITE
    tool = Tool(
        name="preview",
        inputSchema={"type": "object"},
        annotations=ToolAnnotations(readOnlyHint=True),
        _meta={"ui": {"resourceUri": "ui://video-use/media.html"}},
    )
    existing = tool.model_copy(
        update={"icons": [Icon(src="https://video.example/specific.png")]}
    )
    branded, retained = brand_tools([tool, existing], "https://video.example")
    assert tool.icons is None
    assert retained is existing
    assert branded.icons == icons
    assert branded.model_dump(exclude={"icons"}) == tool.model_dump(exclude={"icons"})
    assert branded.model_dump(by_alias=True)["_meta"] == tool.meta


def test_assets_preserve_logo_geometry_and_have_no_external_dependencies():
    original = Path(__file__).parents[3] / "website/public/brand/browser-use.svg"

    def paths(path):
        return [
            element.attrib
            for element in ET.parse(path).iter()
            if element.tag.endswith("}path")
        ]
    assert paths(SVG_PATH) == paths(original)
    assert len(paths(SVG_PATH)) == 4
    svg = SVG_PATH.read_text()
    assert "<script" not in svg and "href=" not in svg
    with Image.open(PNG_PATH) as image:
        assert image.size == (256, 256)
        assert image.convert("RGBA").getpixel((0, 0))[3] == 0
        colors = image.convert("RGB").getextrema()
        assert all(low < 32 and high == 255 for low, high in colors)


def test_public_brand_routes_are_cacheable_without_authentication(pilot):
    client, app = pilot
    client.headers.pop("Authorization", None)
    for route, path, mime in (
        (PNG_ROUTE, PNG_PATH, "image/png"),
        (SVG_ROUTE, SVG_PATH, "image/svg+xml"),
    ):
        response = client.get(route)
        assert response.status_code == 200
        assert response.content == path.read_bytes()
        assert response.headers["Content-Type"] == mime
        assert response.headers["Cache-Control"] == "public, max-age=86400"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
    app.state.store.identity.assert_not_called()
    app.state.store.member.assert_not_called()
    missing = client.get("/brand/not-an-asset.png")
    assert missing.status_code == 404
    assert missing.headers["Cache-Control"] == "no-store"
    # Public branding must not make the actual MCP endpoint public or cacheable.
    denied = client.post("/mcp", json={})
    assert denied.status_code == 401
    assert denied.headers["Cache-Control"] == "no-store"


def test_wire_metadata_advertises_branding_and_retains_tool_policy(pilot):
    expected = [
        icon.model_dump(exclude_none=True)
        for icon in browser_use_icons("http://localhost:8787")
    ]
    initialized = rpc(
        pilot,
        "initialize",
        dict(
            protocolVersion="2025-11-25",
            capabilities={},
            clientInfo={"name": "branding-test", "version": "1"},
        ),
    )
    assert initialized["serverInfo"]["name"] == "video-use"
    assert initialized["serverInfo"]["icons"] == expected
    assert initialized["serverInfo"]["websiteUrl"] == BRAND_WEBSITE
    tools = {tool["name"]: tool for tool in rpc(pilot, "tools/list", {})["tools"]}
    assert tools and all(tool["icons"] == expected for tool in tools.values())
    assert "create_video_project" not in tools
    assert tools["get_video_project"]["annotations"]["readOnlyHint"] is True
    assert tools["save_video_widget"]["annotations"]["readOnlyHint"] is False
    assert tools["save_video_widget"]["_meta"]["ui"]["visibility"] == ["app"]
    assert tools["show_video_preview"]["_meta"]["ui"]["resourceUri"] == UI_URI
