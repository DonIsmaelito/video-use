import asyncio
import hashlib
from io import BytesIO
from unittest.mock import Mock, AsyncMock, patch
import time

import pytest
from video_use_mcp.pilot.sources import public_target, fetch_source, source_name
from video_use_mcp.pilot.tests.test_cards import rpc, PID

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]


def address(ip):
    return [(2, 1, 6, "", (ip, 443))]


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/a.mp4",
        "https://user:pass@example.com/a.mp4",
        "https://example.com:444/a.mp4",
    ],
)
def test_public_download_requires_https_no_credentials(url):
    with pytest.raises(ValueError):
        public_target(url)


@pytest.mark.parametrize(
    "ip", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "192.0.2.1", "0.0.0.0"]
)
def test_private_and_reserved_dns_are_rejected(ip):
    with patch("socket.getaddrinfo", return_value=address(ip)), pytest.raises(
        ValueError, match="addresses"
    ):
        public_target("https://example.com/media.mp4")


def test_redirects_are_revalidated_and_dns_address_pinned(tmp_path):
    response = Mock(status=302)
    response.getheader.side_effect = (
        lambda k, *a: "https://internal.example/file.mp4" if k == "Location" else None
    )
    conn = Mock()
    conn.getresponse.return_value = response
    with patch(
        "socket.getaddrinfo", side_effect=[address("1.1.1.1"), address("127.0.0.1")]
    ), patch(
        "video_use_mcp.pilot.sources.PinnedHTTPS", return_value=conn
    ) as connection:
        with pytest.raises(ValueError, match="addresses"):
            fetch_source("https://public.example/file.mp4", tmp_path / "x")
        assert connection.call_args.args[:2] == ("public.example", "1.1.1.1")
        conn.close.assert_called_once()


def test_stream_limit_and_query_credentials_not_in_provenance(tmp_path):
    def response(body):
        r = Mock(status=200)
        r.getheader.side_effect = lambda k, default=None: {
            "Content-Type": "video/mp4"
        }.get(k, default)
        buf = BytesIO(body)
        r.read1.side_effect = buf.read
        return r

    connection = Mock()
    connection.getresponse.return_value = response(b"content")
    with patch("socket.getaddrinfo", return_value=address("1.1.1.1")), patch(
        "video_use_mcp.pilot.sources.PinnedHTTPS", return_value=connection
    ):
        out = fetch_source(
            "https://public.example/file.mp4?secret=private", tmp_path / "x"
        )
        assert out["sha256"] == hashlib.sha256(b"content").hexdigest()
        assert "private" not in str(out) and "secret" not in str(out)
        connection.getresponse.return_value = response(b"large")
        with pytest.raises(ValueError, match="size limit"):
            fetch_source("https://public.example/f", tmp_path / "y", limit=3)


@pytest.mark.parametrize(
    "name", ["../x.pdf", "/tmp/x.mp4", ".hidden.json", "a.exe", "x\\y.mp4"]
)
def test_source_filename_boundaries(name):
    with pytest.raises(ValueError):
        source_name(name)


@pytest.mark.parametrize(
    "name",
    [
        "brief.pdf",
        "deck.pptx",
        "table.csv",
        "asset.glb",
        "captions.srt",
        "voice.flac",
        "font.ttf",
    ],
)
def test_new_supported_sources(name):
    assert source_name(name) == name


def test_common_unicode_filenames_are_normalized_and_fit_worker_filesystem():
    assert source_name("re\u0301sume\u0301 (final).pdf") == "résumé (final).pdf"
    assert source_name("产品 [3].glb") == "产品 [3].glb"
    with pytest.raises(ValueError):
        source_name("产" * 100 + ".pdf")


def test_upload_capability_is_hidden_from_model_and_project_scoped(pilot):
    client, app = pilot
    app.state.manager.lock = lambda pid: asyncio.Lock()
    app.state.manager.sessions = {}
    app.state.manager.save_object = AsyncMock(
        return_value={"id": "obj", "name": "brief.txt", "size": 5}
    )
    response = rpc(
        pilot,
        "tools/call",
        dict(name="request_video_sources", arguments=dict(project_id=PID)),
    )
    assert not response.get("isError"), response
    token = response["_meta"]["source_upload_token"]
    url = response["_meta"]["source_upload_url"]
    assert token not in str(response["content"]) and token not in str(
        response["structuredContent"]
    )
    headers = {"X-Upload-Token": token, "X-Filename": "brief.txt", "Origin": "null"}
    options = client.options(
        url,
        headers={
            "Origin": "null",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-filename,x-upload-token",
        },
    )
    assert (
        options.status_code == 200
        and options.headers["access-control-allow-origin"] == "*"
    )
    assert (
        client.post(
            url.replace(PID, "other"), headers=headers, content=b"hello"
        ).status_code
        == 400
    )
    result = client.post(url, headers=headers, content=b"hello")
    assert result.status_code == 200, result.text
    assert result.json()["source"]["path"] == "sources/brief.txt"
    assert result.headers["access-control-allow-origin"] == "*"
    key = hashlib.sha256(token.encode()).hexdigest()
    state = app.state.store.get("source_upload", key)
    assert state["remaining"] == 200000000 - 5
    state["remaining"] = 3
    app.state.store.put("source_upload", key, state)
    assert client.post(url, headers=headers, content=b"hello").status_code == 400
    state["expires"] = time.time() - 1
    app.state.store.put("source_upload", key, state)
    assert client.post(url, headers=headers, content=b"x").status_code == 400
    app.state.manager.save_object.assert_awaited_once()
