"""Diskless local packet relay to isolated cloud acquisition/ASR staging.

Raw media exists only in bounded memory chunks on the client and in Modal.
No creative worker or production lock is touched. Archive the verified cloud paths separately with archive_cloud_media.py.

Usage:
  python experiments/source_relay.py --plan plan.json --batch my-batch --output receipts
  python experiments/source_relay.py --plan plan.json --batch my-batch --output receipts --validate-only

A plan is 1–16 objects with id, public YouTube url, optional range [start,end]
(max180seconds), speech boolean, and brief_id. Whole sources are <=360seconds.
Local prerequisites: yt-dlp with a working JS runtime, ffmpeg, Modal and requests.
The Modal video-use-elevenlabs secret supplies Scribe credentials only in cloud.
Local output contains JSON/transcripts only. Cloud receipts include contact sheets.

reuse_video optionally names an existing complete cloud video by source/sha256/
bytes, allowing a new whole-source audio track to be fetched and cloud-remuxed.
Use a fresh source ID for retries; existing source media is never overwritten.
A failed acquisition can leave cloud partials for inspection. No media is purged
from the authoritative source namespace by this helper.
"""

import argparse
import concurrent.futures
import hashlib
import json
import math
import os
import re
import secrets
import subprocess
import sys
import threading
import time
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import modal
import requests
from fastapi import Request, HTTPException

ROOT = Path(__file__).resolve().parents[1]
OUT = None
TOKEN = secrets.token_hex(32)
PREFIX = None
MAX_BYTES = 1024**3
CHUNK_BYTES = 8 * 1024 * 1024


def validate_spec(spec):
    """Bound public YouTube acquisition before any provider or endpoint call."""
    if (
        not isinstance(spec, dict)
        or not {"id", "url"} <= set(spec)
        or set(spec) - {"id", "url", "range", "speech", "brief_id", "reuse_video"}
    ):
        raise ValueError(
            "Each source requires id/url and optional range/speech/brief_id/reuse_video"
        )
    for key in ("id", "brief_id"):
        if key in spec and (
            not isinstance(spec[key], str)
            or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,99}", spec[key])
        ):
            raise ValueError("Invalid source or brief identifier")
    if not isinstance(spec["url"], str):
        raise ValueError("Public YouTube URL required")
    url = urlparse(spec["url"])
    host = url.hostname
    if (
        url.scheme != "https"
        or url.username
        or url.password
        or url.port
        or url.fragment
    ):
        raise ValueError("Public HTTPS YouTube URL required")
    if host == "youtu.be":
        video = url.path.strip("/")
        valid = not url.query
    else:
        query = parse_qs(url.query, keep_blank_values=True)
        video = query.get("v", [""])[0]
        valid = (
            host in ("youtube.com", "www.youtube.com")
            and url.path == "/watch"
            and set(query) == {"v"}
            and len(query["v"]) == 1
        )
    if not valid or not re.fullmatch(r"[A-Za-z0-9_-]{11}", video):
        raise ValueError("Select one explicit YouTube video URL")
    if "speech" in spec and type(spec["speech"]) is not bool:
        raise ValueError("speech must be boolean")
    if "range" in spec:
        times = spec["range"]
        if (
            not isinstance(times, list)
            or len(times) != 2
            or any(
                isinstance(t, bool)
                or not isinstance(t, (int, float))
                or not math.isfinite(t)
                for t in times
            )
            or not 0 <= times[0] < times[1]
            or times[1] - times[0] > 180
        ):
            raise ValueError("Select a finite ordered section of at most 180 seconds")
    if "reuse_video" in spec:
        reuse = spec["reuse_video"]
        if (
            "range" in spec
            or not isinstance(reuse, dict)
            or set(reuse) != {"source", "sha256", "bytes"}
        ):
            raise ValueError("Reuse requires a complete source path/hash/bytes")
        if not isinstance(reuse["source"], str) or not isinstance(reuse["sha256"], str):
            raise ValueError("Invalid verified cloud video reference")
        path = Path(reuse["source"])
        if (
            path.is_absolute()
            or ".." in path.parts
            or len(path.parts) < 3
            or path.parts[0] != "prepared-assets"
            or not re.fullmatch(r"[a-f0-9]{64}", reuse["sha256"])
            or type(reuse["bytes"]) is not int
            or not 0 < reuse["bytes"] <= MAX_BYTES
        ):
            raise ValueError("Invalid verified cloud video reference")
    return dict(spec)


def validate_plan(values):
    if not isinstance(values, list) or not 1 <= len(values) <= 16:
        raise ValueError("Select 1 to 16 explicit sources")
    specs = [validate_spec(s) for s in values]
    if len({s["id"] for s in specs}) != len(specs):
        raise ValueError("Duplicate source identifier")
    return specs


def select_formats(info):
    """Prefer 1080p H264 and original AAC audio; never fall back to a dubbed track silently."""
    formats = [
        f
        for f in info.get("formats", [])
        if f.get("url") and f.get("protocol") == "https"
    ]
    videos = [
        f
        for f in formats
        if str(f.get("vcodec", "")).startswith("avc")
        and 0 < (f.get("height") or 0) <= 1080
    ]
    audios = [
        f
        for f in formats
        if f.get("vcodec") == "none" and str(f.get("acodec", "")).startswith("mp4a")
    ]
    if not videos or not audios:
        raise ValueError("Required H264 video and AAC audio formats are unavailable")
    video = max(
        videos,
        key=lambda f: (f.get("height") or 0, f.get("fps") or 0, f.get("tbr") or 0),
    )
    audio = max(
        audios,
        key=lambda f: (
            "original" in (f.get("format_note") or "").lower(),
            str(f.get("language") or "").startswith("en"),
            "drc" not in (f.get("format_note") or "").lower(),
            f.get("abr") or 0,
        ),
    )
    for f in (video, audio):
        url = urlparse(f["url"])
        if (
            url.scheme != "https"
            or not (url.hostname or "").endswith(".googlevideo.com")
            or url.username
            or url.password
        ):
            raise ValueError("Unexpected media host in extracted metadata")
    return video, audio


def capture_command(spec, video, audio):
    command = ["ffmpeg", "-v", "error", "-xerror", "-nostdin", "-copyts"]
    for stream in (video, audio):
        if spec.get("range"):
            command += ["-ss", str(max(0, spec["range"][0] - 3))]
        command += ["-rw_timeout", "30000000", "-i", stream["url"]]
    command += [
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c",
        "copy",
        "-avoid_negative_ts",
        "disabled",
    ]
    if spec.get("range"):
        command += ["-to", str(spec["range"][1] + 3)]
    return command + ["-f", "matroska", "pipe:1"]


def section_offset(spec, raw_start):
    if not spec.get("range"):
        return None
    offset = spec["range"][0] - raw_start
    if not math.isfinite(offset) or not -0.05 <= offset <= 12:
        raise ValueError("Unexpected preserved source capture clock")
    return max(0, offset)


def file_sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_coverage(info, expected):
    """Reject truncated native audio, missing streams, and nonzero output clocks."""
    result = {}
    for kind in ("video", "audio"):
        streams = [s for s in info.get("streams", []) if s.get("codec_type") == kind]
        if len(streams) != 1:
            raise ValueError(f"Expected exactly one {kind} stream")
        start = float(streams[0].get("start_time", "nan"))
        duration = float(streams[0].get("duration", "nan"))
        if (
            not math.isfinite(start)
            or not math.isfinite(duration)
            or not -0.001 <= start <= 0.1
            or abs(duration - expected) > 0.55
        ):
            raise ValueError(
                f"{kind} coverage mismatch: start={start} duration={duration} expected={expected}"
            )
        result[kind] = {"start": start, "duration": duration, "end": start + duration}
    return result


def format_chunks(fmt):
    """Independent bounded HTTP ranges prevent idle parallel input connections."""
    total = fmt.get("filesize")
    if type(total) is not int or not 0 < total <= MAX_BYTES:
        raise ValueError("Exact bounded format filesize required")
    for offset in range(0, total, CHUNK_BYTES):
        end = min(total, offset + CHUNK_BYTES) - 1
        for attempt in range(3):
            try:
                with requests.get(
                    fmt["url"],
                    headers={"Range": f"bytes={offset}-{end}"},
                    stream=True,
                    timeout=(15, 45),
                ) as response:
                    response.raise_for_status()
                    if (
                        response.status_code != 206
                        or response.headers.get("Content-Range")
                        != f"bytes {offset}-{end}/{total}"
                    ):
                        raise ValueError("Source server did not honor exact byte range")
                    data = response.raw.read(end - offset + 2)
                    if len(data) != end - offset + 1:
                        raise ValueError("Source range was truncated or oversized")
                break
            except (requests.RequestException, OSError, ValueError):
                if attempt == 2:
                    raise
        yield data


app = modal.App("video-use-source-relay-" + secrets.token_hex(4))
volume = modal.Volume.from_name("video-use-useful-library-20261003")
image = (
    modal.Image.from_registry(
        "node:22-bookworm-slim",
        add_python=f"{sys.version_info.major}.{sys.version_info.minor}",
    )
    .apt_install("ffmpeg")
    .pip_install("fastapi", "requests", "python-dotenv", "pillow")
    .add_local_file(
        ROOT / "helpers/transcribe.py", "/opt/probe/transcribe.py", copy=True
    )
    .add_local_file(
        ROOT / "experiments/prepared_inputs.py",
        "/opt/probe/prepared_inputs.py",
        copy=True,
    )
)


@app.function(
    image=image,
    cpu=1,
    memory=1024,
    timeout=120,
    max_containers=1,
    volumes={"/results": volume},
    secrets=[modal.Secret.from_dict({"SOURCE_RELAY_TOKEN": TOKEN})],
    serialized=True,
)
@modal.fastapi_endpoint(method="POST")
async def receive(request: Request):
    import hmac

    if not hmac.compare_digest(
        request.headers.get("Authorization", ""),
        "Bearer " + os.environ["SOURCE_RELAY_TOKEN"],
    ):
        raise HTTPException(401)
    ident = request.headers.get("X-Source-Id", "")
    number = request.headers.get("X-Part", "")
    if (
        not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,99}", ident)
        or not number.isdigit()
        or not 0 <= int(number) < 128
    ):
        raise HTTPException(400)
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > CHUNK_BYTES:
            raise HTTPException(413)
        data.extend(chunk)
    if not data:
        raise HTTPException(413)
    checksum = hashlib.sha256(data).hexdigest()
    if checksum != request.headers.get("X-SHA256"):
        raise HTTPException(422)
    await volume.reload.aio()
    folder = Path("/results") / PREFIX / ident / "relay-parts"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{int(number):04d}.bin"
    if path.exists():
        if hashlib.sha256(path.read_bytes()).hexdigest() != checksum:
            raise HTTPException(409)
    else:
        with path.open("xb") as stream:
            stream.write(data)
    await volume.commit.aio()
    return {"part": int(number), "bytes": len(data), "sha256": checksum}


@app.function(
    image=image,
    cpu=4,
    memory=4096,
    timeout=1200,
    max_containers=2,
    retries=0,
    volumes={"/results": volume},
    secrets=[modal.Secret.from_name("video-use-elevenlabs")],
    serialized=True,
)
def finish(
    spec: dict, metadata: dict, count: int, expected_sha: str, expected_bytes: int
):
    import shutil, math, io
    from PIL import Image, ImageDraw

    sys.path.insert(0, "/opt/probe")
    from prepared_inputs import stage_inputs
    from transcribe import transcribe_one, cached_transcript

    volume.reload()
    root = Path("/results") / PREFIX / spec["id"]
    raw = root / "raw-input.mkv"
    partial = root / "raw-input.mkv.part"
    if raw.exists():
        raise ValueError("Acquisition already exists; preserve it")
    digest = hashlib.sha256()
    size = 0
    with partial.open("xb") as output:
        for i in range(count):
            p = root / "relay-parts" / f"{i:04d}.bin"
            with p.open("rb") as incoming:
                for chunk in iter(lambda: incoming.read(1024 * 1024), b""):
                    output.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
    if size != expected_bytes or digest.hexdigest() != expected_sha:
        raise ValueError("Relay bytes differ")
    partial.rename(raw)
    transport_sha = expected_sha
    transport_bytes = expected_bytes
    if metadata.get("relay_tracks"):
        payload = root / "relay-payload.bin"
        raw.rename(payload)
        tracks = []
        with payload.open("rb") as incoming:
            for i, track in enumerate(metadata["relay_tracks"]):
                path = root / f"relay-track-{i}.mp4"
                remaining = track["bytes"]
                with path.open("xb") as output:
                    while remaining:
                        chunk = incoming.read(min(1024 * 1024, remaining))
                        if not chunk:
                            raise ValueError("Incomplete track payload")
                        output.write(chunk)
                        remaining -= len(chunk)
                if file_sha(path) != track["sha256"]:
                    raise ValueError("Track hash mismatch")
                tracks.append(path)
            if incoming.read(1):
                raise ValueError("Trailing track bytes")
        if spec.get("reuse_video"):
            reuse = spec["reuse_video"]
            video = Path("/results") / reuse["source"]
            if (
                video.is_symlink()
                or not video.resolve().is_relative_to(
                    Path("/results/prepared-assets").resolve()
                )
                or video.stat().st_size != reuse["bytes"]
                or file_sha(video) != reuse["sha256"]
            ):
                raise ValueError("Reused video hash/size mismatch")
            tracks.insert(0, video)
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-xerror",
                "-nostdin",
                "-i",
                str(tracks[0]),
                "-i",
                str(tracks[1]),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c",
                "copy",
                str(raw),
            ],
            capture_output=True,
            check=True,
            timeout=300,
        )
        expected_sha = file_sha(raw)
        size = raw.stat().st_size
        payload.unlink()
        for path in root.glob("relay-track-*.mp4"):
            path.unlink()

    def probe(path):
        return json.loads(
            subprocess.check_output(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_streams",
                    "-show_format",
                    "-of",
                    "json",
                    str(path),
                ]
            )
        )

    raw_probe = probe(raw)
    start = float(raw_probe["format"].get("start_time", 0))
    source = root / "source.mp4"
    args = ["ffmpeg", "-v", "error", "-nostdin"]
    if spec.get("range"):
        offset = section_offset(spec, start)
        args += ["-ss", str(max(0, offset))]
    args += ["-i", str(raw), "-map", "0:v:0", "-map", "0:a:0?"]
    if spec.get("range"):
        args += [
            "-t",
            str(spec["range"][1] - spec["range"][0]),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "18",
        ]
    else:
        args += ["-c:v", "copy"]
    args += ["-c:a", "copy", "-movflags", "+faststart", str(source)]
    subprocess.run(args, capture_output=True, check=True, timeout=600)
    info = probe(source)
    duration = float(info["format"]["duration"])
    if not 0 < duration <= 370:
        raise ValueError("Source duration outside bounded plan")
    coverage = validate_coverage(
        info,
        spec["range"][1] - spec["range"][0]
        if spec.get("range")
        else metadata["duration"],
    )
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-xerror",
            "-nostdin",
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        check=True,
        timeout=300,
    )
    sha = file_sha(source)
    prepared = [
        {
            "source": str(source.relative_to("/results")),
            "target": f"edit/downloads/{spec['id']}.mp4",
            "bytes": source.stat().st_size,
            "sha256": sha,
        }
    ]
    record = {
        "id": spec["id"],
        "brief_id": spec.get("brief_id"),
        "url": spec["url"],
        "title": metadata.get("title"),
        "channel": metadata.get("channel"),
        "license": metadata.get("license"),
        "source_duration": metadata.get("duration"),
        "source_range": spec.get("range"),
        "source_offset_seconds": spec.get("range", [0])[0],
        "coverage": coverage,
        "decoded_streams_verified": True,
        "reused_video": spec.get("reuse_video"),
        "relay_sha256": transport_sha,
        "relay_bytes": transport_bytes,
        "raw_sha256": expected_sha,
        "raw_bytes": size,
        "raw_cloud_path": str(raw),
        "raw_start_time": start,
        "prepared_input": prepared[0],
        "probe": {
            "streams": [
                {
                    k: s.get(k)
                    for k in (
                        "codec_type",
                        "codec_name",
                        "width",
                        "height",
                        "avg_frame_rate",
                        "sample_rate",
                        "channels",
                        "start_time",
                        "duration",
                    )
                }
                for s in info["streams"]
            ],
            "format": {
                k: info["format"].get(k) for k in ("duration", "size", "start_time")
            },
        },
        "selected_formats": metadata["selected_formats"],
        "acquisition": "Public yt-dlp metadata resolved locally; FFmpeg source packets relayed in bounded RAM chunks without local media files; complete whole-source tracks transferred independently with exact byte ranges; section normalization and ASR executed in Modal.",
        "speech": None,
    }
    if spec.get("speech"):
        try:
            transcript = transcribe_one(
                source,
                root,
                os.environ["ELEVENLABS_API_KEY"],
                language="en",
                verbose=False,
                model="scribe_v2",
            )
            payload = json.loads(transcript.read_text())
            words = [w for w in payload["words"] if w.get("type") == "word"]
            ready = (
                cached_transcript(source, root, language="en", model="scribe_v2")
                == transcript
            )
            if not words or not ready:
                raise ValueError(
                    "Transcript has no words or failed source cache verification"
                )
            dest = f"edit/transcripts/{spec['id']}.json"
            prepared.append(
                {
                    "source": str(transcript.relative_to("/results")),
                    "target": dest,
                    "bytes": transcript.stat().st_size,
                    "sha256": hashlib.sha256(transcript.read_bytes()).hexdigest(),
                }
            )
            record["speech"] = {
                "ok": True,
                "model": "scribe_v2",
                "word_count": len(words),
                "first_word_start": words[0].get("start") if words else None,
                "last_word_end": words[-1].get("end") if words else None,
                "verified_cache_reuse": ready,
                "clock": "seconds relative to staged source.mp4; add source_offset_seconds for requested original video clock",
                "transcript": payload,
            }
        except Exception as exc:
            record["speech"] = {
                "ok": False,
                "error_type": type(exc).__name__,
                "error": str(exc)
                if str(exc).startswith("Scribe returned HTTP")
                else "Transcription did not complete",
            }
    if spec.get("speech") and not record["speech"]["ok"]:
        raise RuntimeError("Requested Scribe transcription failed; source is not ready")
    # Small, actual decoded-frame sheet; all full frames stay in memory.
    thumbs = []
    samples = 16
    for i in range(samples):
        when = (duration - 0.15) * i / (samples - 1)
        data = subprocess.check_output(
            [
                "ffmpeg",
                "-v",
                "error",
                "-ss",
                str(when),
                "-i",
                str(source),
                "-frames:v",
                "1",
                "-vf",
                "scale=320:-2",
                "-f",
                "image2pipe",
                "-c:v",
                "mjpeg",
                "-",
            ],
            timeout=30,
        )
        thumb = Image.open(io.BytesIO(data)).convert("RGB")
        thumbs.append((when, thumb))
    sheet = Image.new("RGB", (1280, 4 * 210), "#171717")
    draw = ImageDraw.Draw(sheet)
    for i, (when, thumb) in enumerate(thumbs):
        x = (i % 4) * 320
        y = (i // 4) * 210
        sheet.paste(thumb, (x, y))
        draw.text(
            (x + 5, y + 183),
            f"local {when:.2f}s / source {when+record['source_offset_seconds']:.2f}s",
            fill="white",
        )
    sheet.save(root / "contact-sheet.jpg", quality=84)
    record["contact_sheet"] = str((root / "contact-sheet.jpg").relative_to("/results"))
    provenance = root / "source-evidence.json"
    public_record = {
        **record,
        "speech": (
            {k: v for k, v in record["speech"].items() if k != "transcript"}
            if record["speech"]
            else None
        ),
    }
    provenance.write_text(json.dumps(public_record, indent=2) + "\n")
    prepared.append(
        {
            "source": str(provenance.relative_to("/results")),
            "target": f"edit/references/{spec['id']}-source.json",
            "bytes": provenance.stat().st_size,
            "sha256": hashlib.sha256(provenance.read_bytes()).hexdigest(),
        }
    )
    stage_inputs(prepared, root / "staging-smoke")
    record["prepared_inputs"] = prepared
    record["staging_copy_verified"] = True
    (root / "acquisition.json").write_text(
        json.dumps({**record, "speech": public_record["speech"]}, indent=2) + "\n"
    )
    volume.commit()
    # Relay parts and staging smoke are exact cloud duplicates of verified raw/prepared bytes.
    shutil.rmtree(root / "relay-parts")
    shutil.rmtree(root / "staging-smoke")
    volume.commit()
    return record


cache = {}
lock = threading.Lock()


def metadata(url):
    with lock:
        if url not in cache:
            command = [
                "yt-dlp",
                "--skip-download",
                "--dump-single-json",
                "--no-playlist",
                "--no-warnings",
                "--js-runtimes",
                "node",
                "--socket-timeout",
                "20",
                url,
            ]
            cache[url] = json.loads(
                subprocess.check_output(
                    command, text=True, stderr=subprocess.DEVNULL, timeout=90
                )
            )
        return cache[url]


def stream_one(spec, url):
    info = metadata(spec["url"])
    duration = info.get("duration")
    if (
        not isinstance(duration, (int, float))
        or not math.isfinite(duration)
        or duration <= 0
        or info.get("is_live")
    ):
        raise ValueError("A finished source with measured duration is required")
    if spec.get("range"):
        if spec["range"][1] > duration:
            raise ValueError("Requested section exceeds source duration")
    elif duration > 360:
        raise ValueError(
            "Whole sources are limited to 360 seconds; select a bounded section"
        )
    video, audio = select_formats(info)
    small = {k: info.get(k) for k in ("id", "title", "channel", "duration", "license")}
    small["selected_formats"] = [
        {
            k: f.get(k)
            for k in (
                "format_id",
                "codec",
                "vcodec",
                "acodec",
                "height",
                "width",
                "fps",
                "language",
                "format_note",
            )
        }
        for f in (video, audio)
    ]
    process = None
    deadline = None
    checksum = hashlib.sha256()
    size = 0
    count = 0
    if spec.get("range"):
        process = subprocess.Popen(
            capture_command(spec, video, audio),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        deadline = threading.Timer(900, process.kill)
        deadline.start()
        chunks = iter(lambda: process.stdout.read(CHUNK_BYTES), b"")
    else:
        small["relay_tracks"] = []

        def independent_tracks():
            for fmt in [audio] if spec.get("reuse_video") else [video, audio]:
                track_sha = hashlib.sha256()
                track_size = 0
                for data in format_chunks(fmt):
                    track_sha.update(data)
                    track_size += len(data)
                    yield data
                small["relay_tracks"].append(
                    {"bytes": track_size, "sha256": track_sha.hexdigest()}
                )

        chunks = independent_tracks()
    try:
        for data in chunks:
            size += len(data)
            if size > MAX_BYTES:
                raise ValueError("Source exceeds 1 GiB cap")
            checksum.update(data)
            headers = {
                "Authorization": "Bearer " + TOKEN,
                "X-Source-Id": spec["id"],
                "X-Part": str(count),
                "X-SHA256": hashlib.sha256(data).hexdigest(),
            }
            for retry in range(3):
                try:
                    r = requests.post(url, data=data, headers=headers, timeout=120)
                    r.raise_for_status()
                    break
                except requests.RequestException:
                    if retry == 2:
                        raise
                    time.sleep(1)
            count += 1
        code = process.wait(timeout=10) if process else 0
        if code != 0 or size < 10000:
            raise RuntimeError(
                f"Source packet stream failed with exit {code}; bytes {size}"
            )
        print(
            json.dumps(
                {
                    "id": spec["id"],
                    "uploaded_bytes": size,
                    "parts": count,
                    "cloud_processing": True,
                }
            ),
            flush=True,
        )
        result = finish.remote(spec, small, count, checksum.hexdigest(), size)
        if result.get("speech", {}):
            transcript = result["speech"].pop("transcript", None)
            if transcript:
                (OUT / (spec["id"] + "-transcript.json")).write_text(
                    json.dumps(transcript, indent=2) + "\n"
                )
        (OUT / (spec["id"] + ".json")).write_text(json.dumps(result, indent=2) + "\n")
        print(
            json.dumps(
                {
                    "id": spec["id"],
                    "completed": True,
                    "speech_ok": result["speech"].get("ok")
                    if result["speech"]
                    else None,
                }
            ),
            flush=True,
        )
        return result
    finally:
        if deadline:
            deadline.cancel()
        if process and process.poll() is None:
            process.kill()
            process.wait()


def main(argv=None):
    global OUT, PREFIX
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--batch", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--parallel", type=int, choices=(1, 2), default=2)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,99}", args.batch):
        parser.error("Invalid batch identifier")
    specs = validate_plan(json.loads(args.plan.read_text()))
    if args.validate_only:
        print(
            json.dumps(
                {"valid": True, "sources": len(specs), "parallel": args.parallel}
            )
        )
        return 0
    OUT = args.output
    OUT.mkdir(parents=True, exist_ok=True)
    PREFIX = "prepared-assets/" + args.batch
    failed = False
    with modal.enable_output(), app.run(detach=True):
        endpoint = receive.get_web_url()
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.parallel) as pool:
            jobs = {pool.submit(stream_one, spec, endpoint): spec for spec in specs}
            for future in concurrent.futures.as_completed(jobs):
                spec = jobs[future]
                try:
                    future.result()
                except Exception as exc:
                    failed = True
                    record = {
                        "id": spec["id"],
                        "failed": True,
                        "error_type": type(exc).__name__,
                        "error": re.sub(r"https?://\S+", "[url]", str(exc))[-600:],
                    }
                    (OUT / (spec["id"] + "-failure.json")).write_text(
                        json.dumps(record, indent=2)
                    )
                    print(json.dumps(record), flush=True)
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
