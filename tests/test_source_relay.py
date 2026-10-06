import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "source_relay", Path(__file__).parents[1] / "experiments/source_relay.py"
)
relay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(relay)
URL = "https://www.youtube.com/watch?v=hI9HQfCAw64"


def test_plan_and_source_clock_contract():
    item = {"id": "source-60", "url": URL, "range": [993, 1053], "speech": True}
    assert relay.validate_plan([item]) == [item]
    assert relay.section_offset(item, 989) == 4
    with pytest.raises(ValueError):
        relay.section_offset(item, 0)
    command = relay.capture_command(item, {"url": "video"}, {"url": "audio"})
    assert command[-2:] == ["matroska", "pipe:1"]
    assert command.count("-ss") == 2
    assert command[command.index("-to") + 1] == "1056"
    assert "-copyts" in command and "-xerror" in command


@pytest.mark.parametrize(
    "change",
    [
        {"id": "../escape"},
        {"url": "http://www.youtube.com/watch?v=hI9HQfCAw64"},
        {"url": URL + "&list=other"},
        {"url": "https://evil.test/watch?v=hI9HQfCAw64"},
        {"range": [0, float("nan")]},
        {"range": [True, 10]},
        {"range": [10, 0]},
        {"range": [0, 181]},
        {"speech": "yes"},
        {"unknown": 1},
        {"reuse_video": {"source": "../secret", "bytes": 1, "sha256": "0" * 64}},
    ],
)
def test_rejects_unsafe_or_ambiguous_inputs(change):
    with pytest.raises(ValueError):
        relay.validate_plan([{"id": "source-60", "url": URL, **change}])


def test_duplicate_sources_and_bounds():
    source = {"id": "a", "url": URL}
    for plan in ([], [source, source], [dict(source, id=str(i)) for i in range(17)]):
        with pytest.raises(ValueError):
            relay.validate_plan(plan)


def test_original_audio_beats_louder_dub_and_standard_beats_drc():
    base = {"protocol": "https", "url": "https://rr1.googlevideo.com/videoplayback"}
    video = dict(base, vcodec="avc1", acodec="none", height=1080)
    dubbed = dict(base, vcodec="none", acodec="mp4a", language="en", abr=200)
    original = dict(
        base,
        vcodec="none",
        acodec="mp4a",
        language="en",
        abr=100,
        format_note="original",
    )
    drc = dict(original, format_note="original DRC", abr=150)
    assert relay.select_formats({"formats": [video, dubbed, drc, original]}) == (
        video,
        original,
    )


def test_stream_coverage_rejects_real_truncation_and_shifted_clock():
    def probe(audio_duration=208, audio_start=0):
        return {
            "streams": [
                {"codec_type": "video", "start_time": "0", "duration": "207.957"},
                {
                    "codec_type": "audio",
                    "start_time": str(audio_start),
                    "duration": str(audio_duration),
                },
            ]
        }

    assert relay.validate_coverage(probe(), 208)["audio"]["end"] == 208
    for info in (probe(156.8), probe(208, 1), probe(float("nan")), {"streams": []}):
        with pytest.raises(ValueError):
            relay.validate_coverage(info, 208)


def test_http_range_integrity_and_no_disk(monkeypatch):
    import io

    calls = []

    class Response:
        status_code = 206
        headers = {"Content-Range": "bytes 0-5/6"}
        raw = io.BytesIO(b"abcdef")

        def raise_for_status(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    def get(url, **kwargs):
        calls.append(kwargs)
        return Response()

    monkeypatch.setattr(relay.requests, "get", get)
    assert (
        b"".join(relay.format_chunks({"url": "https://example.test", "filesize": 6}))
        == b"abcdef"
    )
    assert calls[0]["headers"]["Range"] == "bytes=0-5"
    Response.headers = {"Content-Range": "bytes 0-3/6"}
    with pytest.raises(ValueError, match="exact byte range"):
        list(relay.format_chunks({"url": "https://example.test", "filesize": 6}))


def test_validate_only_never_starts_cloud(tmp_path, monkeypatch):
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps([{"id": "test", "url": URL}]))
    monkeypatch.setattr(relay.app, "run", lambda **kw: pytest.fail("cloud started"))
    assert (
        relay.main(
            [
                "--plan",
                str(plan),
                "--batch",
                "test",
                "--output",
                str(tmp_path),
                "--validate-only",
            ]
        )
        == 0
    )
    with pytest.raises(SystemExit):
        relay.main(
            [
                "--plan",
                str(plan),
                "--batch",
                "test",
                "--output",
                str(tmp_path),
                "--parallel",
                "5",
            ]
        )


def test_ranges_cover_chunk_boundary_exactly(monkeypatch):
    import io

    monkeypatch.setattr(relay, "CHUNK_BYTES", 4)
    seen = []

    class Response:
        status_code = 206

        def __init__(self, start, end):
            self.headers = {"Content-Range": f"bytes {start}-{end}/6"}
            self.raw = io.BytesIO(b"abcdef"[start : end + 1])

        def raise_for_status(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    def get(url, **kwargs):
        header = kwargs["headers"]["Range"]
        seen.append(header)
        start, end = map(int, header.removeprefix("bytes=").split("-"))
        return Response(start, end)

    monkeypatch.setattr(relay.requests, "get", get)
    assert list(relay.format_chunks({"url": "unused", "filesize": 6})) == [
        b"abcd",
        b"ef",
    ]
    assert seen == ["bytes=0-3", "bytes=4-5"]


def test_truncated_http_body_never_passes(monkeypatch):
    import io

    class Response:
        status_code = 206
        headers = {"Content-Range": "bytes 0-5/6"}

        def __init__(self):
            self.raw = io.BytesIO(b"ab")

        def raise_for_status(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(relay.requests, "get", lambda *a, **kw: Response())
    with pytest.raises(ValueError, match="truncated"):
        list(relay.format_chunks({"url": "unused", "filesize": 6}))
