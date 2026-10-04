"""Platform choices, honest inspection failures and actual media regressions."""

import shutil
import subprocess

import pytest

from video_use_mcp.pilot.reference_browser import BrowserOperation, prepare_operations
from video_use_mcp.pilot.reference_browser_worker import validate_request
from video_use_mcp.pilot.reference_download_worker import failure_details, inspect_media
from video_use_mcp.pilot.reference_sources import validate_reference_source
from video_use_mcp.pilot.tests.test_reference_direction import (
    args,
    failure,
    invoke,
    refs,
    saved,
)
from video_use_mcp.pilot.tests.test_reference_direction import project as project
from video_use_mcp.pilot.tests.test_reference_direction import registry as registry

pytest_plugins = ["video_use_mcp.pilot.tests.test_oauth_discovery"]


@pytest.mark.parametrize(
    "platform,url",
    [
        ("youtube", "https://m.youtube.com/watch?v=Diagram0001"),
        ("tiktok", "https://m.tiktok.com/@creator/video/6718335390845095173"),
        ("x", "https://mobile.twitter.com/creator/status/1234567890123456789"),
        ("x", "https://x.com/i/web/status/1234567890123456789"),
    ],
)
def test_mobile_post_aliases_keep_their_platform_discovery_identity(platform, url):
    validate_reference_source({"source_id": platform, "discovery_url": url})


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=Diagram0001",
        "https://youtu.be/Diagram0001",
        "https://www.youtube.com/shorts/Diagram0001",
        "https://www.tiktok.com/@creator/video/6718335390845095173",
        "https://x.com/creator/status/1234567890123456789",
        "https://twitter.com/creator/status/1234567890123456789/video/1",
    ],
)
def test_all_three_platforms_can_be_offered(pilot, project, url):
    reference = refs()[0] | {"url": url, "source": "user_supplied"}
    offered = invoke(pilot, project, references=[reference])
    assert offered["reference_direction"]["references"][0]["url"] == url


@pytest.mark.parametrize(
    "url",
    [
        "https://vimeo.com/123456789",
        "https://studio.example/film",
        "https://cdn.example/video.mp4",
        "https://www.youtube.com/results?search_query=motion",
        "https://www.tiktok.com/@creator",
        "https://x.com/search?q=motion",
        "https://youtube.com.evil.example/watch?v=Diagram0001",
    ],
)
def test_only_individual_supported_posts_are_reference_choices(pilot, project, url):
    reference = refs()[0] | {"url": url, "source": "user_supplied"}
    before = saved(pilot, project)
    failure(pilot, args(pilot, project, references=[reference]))
    assert saved(pilot, project) == before


@pytest.mark.parametrize("matching", [True, False])
def test_frame_evidence_accepts_same_post_alias_but_not_another_video(
    pilot, project, matching
):
    reference = refs()[0] | {"evidence_ids": ["actual-frame"]}
    pilot[1].state.store.put(
        "reference_browser_evidence",
        "actual-frame",
        {
            "owner": "tester",
            "project": project,
            "kind": "video_frame",
            "page_url": "https://youtu.be/"
            + ("Diagram0001" if matching else "OtherVid001"),
        },
    )
    if matching:
        invoke(pilot, project, references=[reference])
    else:
        assert "cited reference" in failure(
            pilot, args(pilot, project, references=[reference])
        )


@pytest.mark.parametrize(
    "message,code",
    [
        (
            "Sign in to confirm you are not a bot https://cdn.example/signed?secret=abc",
            "access_restricted",
        ),
        ("Unexpected response from webpage request", "platform_unavailable"),
        ("HTTP Error 403: Forbidden", "platform_unavailable"),
        ("Connection timed out", "network_error"),
    ],
)
def test_download_failures_are_actionable_without_returning_remote_text(message, code):
    result = failure_details(ValueError(message), "download")
    assert result["error_code"] == code
    assert "secret" not in str(result) and "https://" not in str(result)
    assert (
        failure_details(ValueError(message), "inspection")["error_code"]
        == "inspection_failed"
    )


def test_decoded_capture_is_an_explicit_bounded_browser_operation():
    operation = BrowserOperation(
        action="sample_video", timestamps=[1, 3], video_index=2, capture_mode="decoded"
    )
    prepared = prepare_operations([operation])
    assert prepared == [
        {
            "action": "sample_video",
            "timestamps": [1, 3],
            "video_index": 2,
            "capture_mode": "decoded",
        }
    ]
    assert validate_request({"operations": prepared})["operations"] == prepared
    with pytest.raises(ValueError):
        validate_request({"operations": [prepared[0] | {"capture_mode": "bypass"}]})


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg needed"
)
def test_audio_tail_does_not_make_a_downloaded_video_fail_inspection(tmp_path):
    source = tmp_path / "audio-tail.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=160x90:rate=12:duration=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            str(source),
        ],
        check=True,
    )
    result = inspect_media(source, tmp_path)
    assert result["duration_seconds"] >= 2
    assert result["video_duration_seconds"] == 1
    assert result["has_audio"]
    assert max(result["sample_times"]) < 1
    assert len(result["sample_times"]) == 12
    assert (tmp_path / "contact-sheet.jpg").is_file()
