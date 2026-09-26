#!/usr/bin/env python3
"""Mac client for the Modal live session: capture (camera+mic or replay), stream audio over WebSocket,
append the growing recording over HTTP, print the container's events, download the clips at the end.

  python experiments/jev/live_client.py --url https://<app>.modal.run --mode replay --source FILE --start 776 --duration 125 --frame contain
  python experiments/jev/live_client.py --url https://<app>.modal.run --mode mic --seconds 120
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

CHUNK = 8000  # 250 ms of 16 kHz mono int16


def api(url: str, path: str, body=None, method=None, raw: bytes | None = None, timeout=60):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(url.rstrip("/") + path, data=data, method=method or ("POST" if data is not None else "GET"),
                                 headers={"Content-Type": "application/octet-stream" if raw is not None else "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or "null")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True); ap.add_argument("--mode", choices=["mic", "replay"], default="replay"); ap.add_argument("--source"); ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--duration", type=float); ap.add_argument("--seconds", type=float, help="mic mode: stop after this many seconds"); ap.add_argument("--frame", default="crop"); ap.add_argument("--out", default="~/Movies/video-use-tests/live-sessions")
    ap.add_argument("--video-device", default="0"); ap.add_argument("--audio-device", default="0")
    a = ap.parse_args()
    import websocket  # websocket-client

    t_start = time.time()
    # the first request may have to boot the GPU container; wake it and time that separately
    try:
        api(a.url, "/", timeout=600)
    except Exception:  # noqa: BLE001
        pass
    print(f"container ready in {time.time() - t_start:.1f}s")
    sid = api(a.url, "/api/session", {"frame": a.frame, "container": "mp4"}, timeout=300)["id"]
    local = Path(a.out).expanduser() / f"remote-{sid}"; (local / "clips").mkdir(parents=True, exist_ok=True)
    rec = local / "recording.mp4"
    print(f"session {sid} on {a.url} (created in {time.time() - t_start:.1f}s); local copy {local}")
    ws_url = a.url.replace("https://", "wss://").replace("http://", "ws://").rstrip("/") + f"/ws/{sid}/audio"
    ws = websocket.create_connection(ws_url, timeout=30)
    # keep reading so the library answers the server's ping frames; otherwise the socket dies after ~40 s
    def ws_reader():
        try:
            while True:
                ws.recv()
        except Exception:
            pass
    threading.Thread(target=ws_reader, daemon=True).start()

    out = ["-map", "0:v", "-c:v", "h264_videotoolbox", "-b:v", "6M", "-g", "30", "-pix_fmt", "yuv420p", "-map", "0:a", "-c:a", "aac", "-b:a", "160k",
           "-movflags", "+frag_keyframe+empty_moov+default_base_moof", str(rec), "-map", "0:a", "-f", "s16le", "-ar", "16000", "-ac", "1", "pipe:1"]
    if a.mode == "replay":
        inp = ["-re", "-ss", str(a.start)] + (["-t", str(a.duration)] if a.duration else []) + ["-i", a.source]
    else:
        inp = ["-f", "avfoundation", "-framerate", "30", "-video_size", "1280x720", "-i", f"{a.video_device}:{a.audio_device}"]
    proc = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inp, *out], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stop_flag = threading.Event(); sent = {"audio": 0, "video": 0}

    def audio_pump():
        while True:
            data = proc.stdout.read(CHUNK)
            if not data:
                break
            try:
                ws.send_binary(data); sent["audio"] += len(data)
            except Exception as exc:  # noqa: BLE001
                print("audio send failed:", exc); break

    def video_pump():
        offset = 0
        while not stop_flag.is_set() or offset < rec.stat().st_size:
            size = rec.stat().st_size if rec.exists() else 0
            if size > offset:
                with open(rec, "rb") as f:
                    f.seek(offset); data = f.read(size - offset)
                for i in range(3):
                    try:
                        api(a.url, f"/api/session/{sid}/video?offset={offset}", raw=data, timeout=120); offset += len(data); sent["video"] = offset; break
                    except Exception as exc:  # noqa: BLE001
                        print("video upload retry:", exc); time.sleep(1)
            if stop_flag.is_set() and offset >= size:
                break
            time.sleep(1.5)

    def event_pump():
        since = 0
        while True:
            try:
                req = urllib.request.Request(a.url.rstrip("/") + f"/api/session/{sid}/events?since={since}&wait=50")
                with urllib.request.urlopen(req, timeout=90) as r:
                    for raw in r:
                        line = raw.decode().strip()
                        if not line.startswith("data: "):
                            continue
                        e = json.loads(line[6:]); since = e.get("i", since) + (0 if e.get("type") in ("more", "end") else 1)
                        if e.get("type") == "end":
                            return
                        if e.get("type") in ("more",):
                            break
                        if e.get("type") == "partial":
                            continue
                        lag = f" (+{time.time() - t_start - e['t']:.1f}s)" if e.get("type") in ("phrase", "clip_ready") else ""
                        print(f"[{time.time() - t_start:6.1f}s] {e.get('type'):10s} {str(e.get('msg'))[:150]}{lag}", flush=True)
            except Exception as exc:  # noqa: BLE001
                if stop_flag.is_set() and "end" in str(exc):
                    return
                time.sleep(1)

    threads = [threading.Thread(target=f, daemon=True) for f in (audio_pump, video_pump, event_pump)]
    for t in threads:
        t.start()
    limit = a.duration if a.mode == "replay" else a.seconds
    try:
        while proc.poll() is None and (limit is None or time.time() - t_start < limit + 2):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    print("stopping capture…")
    try:
        if proc.poll() is None:
            proc.stdin.write(b"q"); proc.stdin.flush()
        proc.wait(timeout=15)
    except Exception:  # noqa: BLE001
        proc.kill()
    threads[0].join(timeout=10); stop_flag.set(); threads[1].join(timeout=120)
    try:
        ws.send("stop"); ws.close()
    except Exception:  # noqa: BLE001
        pass
    t_stop = time.time()
    summary = api(a.url, f"/api/session/{sid}/stop", body={}, timeout=600)
    print(f"stop returned in {time.time() - t_stop:.1f}s: {json.dumps({k: v for k, v in summary.items() if k != 'clips'})[:400]}")
    for name in summary.get("clips", []):
        for ext in (".mp4", ".srt", ".json"):
            try:
                with urllib.request.urlopen(a.url.rstrip("/") + f"/clips/{sid}/{name}{ext}", timeout=300) as r:
                    (local / "clips" / f"{name}{ext}").write_bytes(r.read())
            except Exception as exc:  # noqa: BLE001
                print("download failed", name, ext, exc)
    threads[2].join(timeout=30)
    print(f"clips downloaded to {local / 'clips'}; audio sent {sent['audio'] / 32000:.1f}s, video {sent['video'] / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
