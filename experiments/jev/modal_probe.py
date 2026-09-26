import modal
app = modal.App("jev-live-probe")
image = modal.Image.debian_slim(python_version="3.12").apt_install("ffmpeg", "fonts-liberation", "fonts-dejavu-core").pip_install("fastapi[standard]", "websocket-client", "requests", "pillow")

@app.function(image=image, cpu=4, memory=4096, timeout=300)
def probe_cpu() -> str:
    import subprocess, os
    enc = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    filt = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    ver = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout.splitlines()[0]
    have = lambda s, t: ("yes" if s in t else "no")
    return f"{ver}\nlibx264 {have('libx264', enc)} | nvenc {have('h264_nvenc', enc)} | subtitles {have(' subtitles ', filt)} | drawtext {have(' drawtext ', filt)} | cpus {os.cpu_count()}"

@app.function(image=image, gpu="T4", cpu=4, memory=8192, timeout=300)
def probe_gpu() -> str:
    import subprocess
    nv = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"], capture_output=True, text=True).stdout.strip()
    # can ffmpeg actually encode with nvenc here?
    test = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=1080x1920:rate=30", "-t", "5", "-c:v", "h264_nvenc", "-preset", "p4", "/tmp/nv.mp4"], capture_output=True, text=True)
    return f"gpu {nv} | nvenc test {'ok' if test.returncode == 0 else 'failed: ' + test.stderr[-200:]}"

@app.local_entrypoint()
def main():
    print(probe_cpu.remote())
    try:
        print(probe_gpu.remote())
    except Exception as exc:
        print("gpu probe failed:", str(exc)[:300])
