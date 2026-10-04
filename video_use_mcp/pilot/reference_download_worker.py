"""Trusted media acquisition inside a public-egress-only, secret-free sandbox.

Never run this network worker in the coordinator or the production sandbox.
The Modal CIDR policy applies to extractor redirects and FFmpeg requests too.
"""

import hashlib
import json
import math
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

MAX_BYTES = 200_000_000
MAX_DURATION = 600


class ReferenceMediaError(ValueError):
    """A safe, actionable failure without remote page text or signed URLs."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def failure_details(error, stage):
    if isinstance(error, ReferenceMediaError):
        return {"error_code": error.code, "error": str(error)}
    if stage == "inspection":
        return {
            "error_code": "inspection_failed",
            "error": "The media arrived, but its video frames could not be inspected. No visual or motion claims were verified.",
        }
    # Classify locally; never return extractor messages containing remote content.
    message = str(error).lower()
    if any(
        token in message
        for token in (
            "sign in",
            "login",
            "log in",
            "private video",
            "not a bot",
            "captcha",
        )
    ):
        code, reason = (
            "access_restricted",
            "The platform requires login or an access check.",
        )
    elif any(
        token in message
        for token in ("403", "429", "unexpected response", "unable to extract webpage")
    ):
        code, reason = (
            "platform_unavailable",
            "The platform did not provide accessible public media to the downloader.",
        )
    elif any(
        token in message
        for token in ("timed out", "timeout", "connection", "temporary failure")
    ):
        code, reason = (
            "network_error",
            "The public media request failed because of a network error.",
        )
    else:
        code, reason = (
            "download_failed",
            "No complete public video could be downloaded.",
        )
    return {"error_code": code, "error": reason}


def positive_seconds(value):
    try:
        number = float(value)
        return number if math.isfinite(number) and number > 0 else None
    except (TypeError, ValueError):
        return None


def inspect_media(path, output_dir):
    """Probe the actual file and produce a timestamped, aspect-preserving sheet."""
    from PIL import Image, ImageDraw, ImageOps

    raw = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-protocol_whitelist",
            "file,pipe",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    probe = json.loads(raw.stdout)
    video = next(
        (
            s
            for s in probe.get("streams", [])
            if s.get("codec_type") == "video"
            and not s.get("disposition", {}).get("attached_pic")
        ),
        None,
    )
    duration = float(probe.get("format", {}).get("duration", 0))
    if not video or not math.isfinite(duration) or not 0 < duration <= MAX_DURATION:
        raise ReferenceMediaError(
            "unsupported_media", "Reference must be a video of at most ten minutes"
        )
    if not 0 < path.stat().st_size <= MAX_BYTES:
        raise ReferenceMediaError("size_limit", "Reference exceeds 200 MB or is empty")
    width, height = int(video["width"]), int(video["height"])
    if not 0 < width <= 8192 or not 0 < height <= 8192:
        raise ValueError("Reference dimensions exceed inspection limits")
    # Container duration may include an audio tail after the final video frame.
    video_duration = min(duration, positive_seconds(video.get("duration")) or duration)
    try:
        frame_interval = 1 / float(Fraction(video.get("avg_frame_rate", "0/1")))
    except (ValueError, TypeError, ZeroDivisionError):
        frame_interval = 0.1
    end = max(0, video_duration - max(0.25, 2 * frame_interval))
    times = [round(i * end / 11, 3) for i in range(12)]
    sheet = Image.new("RGB", (960, 4 * 210), "#171717")
    draw = ImageDraw.Draw(sheet)
    for i, t in enumerate(times):
        frame = output_dir / f"frame-{i}.png"
        command = [
            "ffmpeg",
            "-v",
            "error",
            "-nostdin",
            "-y",
            "-protocol_whitelist",
            "file,pipe",
            "-ss",
            str(t),
            "-i",
            str(path),
            "-frames:v",
            "1",
            "-vf",
            "scale=320:180:force_original_aspect_ratio=decrease",
            str(frame),
        ]
        subprocess.run(command, capture_output=True, check=True, timeout=20)
        # Some containers omit video duration. FFmpeg exits successfully even
        # when an end seek yields no frame. Retry once earlier and label it honestly.
        if not frame.is_file():
            t = times[i] = round(max(0, t - max(0.5, video_duration * 0.05)), 3)
            command[command.index("-ss") + 1] = str(t)
            subprocess.run(command, capture_output=True, check=True, timeout=20)
        if not frame.is_file():
            raise ReferenceMediaError(
                "inspection_failed",
                "The media arrived, but a requested video frame could not be decoded",
            )
        with Image.open(frame) as image:
            image = ImageOps.contain(image.convert("RGB"), (320, 180))
            x, y = (i % 3) * 320, (i // 3) * 210
            sheet.paste(
                image, (x + (320 - image.width) // 2, y + (180 - image.height) // 2)
            )
        draw.text((x + 8, y + 187), f"{t:.3f}s", fill="white")
        frame.unlink()
    sheet.save(output_dir / "contact-sheet.jpg", quality=90)
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(chunk)
    return dict(
        duration_seconds=duration,
        video_duration_seconds=video_duration,
        width=width,
        height=height,
        fps=video.get("avg_frame_rate"),
        has_audio=any(s.get("codec_type") == "audio" for s in probe["streams"]),
        size=path.stat().st_size,
        sha256=sha.hexdigest(),
        sample_times=times,
        inspection_limit="Overview frames only; inspect dense windows at cuts and motion events, and analyze audio separately.",
    )


def acquire(url, output_dir):
    """Download one public work, without cookies, playlists or executable hooks."""
    from yt_dlp import YoutubeDL

    def bounded(progress):
        total = sum(p.stat().st_size for p in output_dir.iterdir() if p.is_file())
        if total > MAX_BYTES or progress.get("downloaded_bytes", 0) > MAX_BYTES:
            raise ReferenceMediaError(
                "size_limit", "Reference exceeds the 200 MB download limit"
            )

    def suitable(info, *, incomplete=False):
        if info.get("is_live") or info.get("live_status") in {"is_live", "is_upcoming"}:
            raise ReferenceMediaError(
                "unsupported_media", "Live references cannot be downloaded"
            )
        if info.get("duration") and info["duration"] > MAX_DURATION:
            raise ReferenceMediaError(
                "duration_limit", "Choose a finished reference of at most ten minutes"
            )

    options = dict(
        quiet=True,
        no_warnings=True,
        noprogress=True,
        noplaylist=True,
        playlistend=1,
        format="bv*[height<=1080]+ba/b[height<=1080]/b",
        outtmpl=str(output_dir / "reference.%(ext)s"),
        merge_output_format="mp4",
        max_filesize=MAX_BYTES,
        socket_timeout=15,
        retries=1,
        fragment_retries=1,
        concurrent_fragment_downloads=1,
        cachedir=False,
        source_address="0.0.0.0",
        progress_hooks=[bounded],
        match_filter=suitable,
        restrictfilenames=True,
        js_runtimes={"deno": {}},
    )
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        if not info or info.get("_type") in {"playlist", "multi_video"}:
            raise ValueError("Choose one finished video, not a collection")
    files = [
        p
        for p in output_dir.glob("reference.*")
        if p.suffix in {".mp4", ".webm", ".mkv", ".mov"}
    ]
    if len(files) != 1:
        raise ValueError("No complete downloadable video was available")
    return files[0]


def main():
    output = Path("/workspace/reference-download")
    output.mkdir(parents=True, exist_ok=True)
    stage = "download"
    try:
        payload = json.loads(sys.stdin.read(12000))
        # Input URLs were validated against the saved selection by the coordinator.
        path = (
            output / "uploaded.mp4"
            if payload.get("uploaded")
            else acquire(payload["url"], output)
        )
        stage = "inspection"
        result = inspect_media(path, output)
        result["filename"] = path.name
        print(json.dumps(result))
    except Exception as error:
        # Extractors can print signed URLs or remote page contents in exceptions.
        print(json.dumps(failure_details(error, stage)))
        sys.exit(1)


if __name__ == "__main__":
    main()
