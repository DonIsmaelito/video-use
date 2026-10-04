"""Speech-clock bridge; audio and cache inspection run in the isolated worker.

Provider keys remain in the controller. Reuse the same extraction and legacy
clock proof as the standalone helper instead of a second FFmpeg timing policy.
"""

import json
import shlex

NEW_CLOCK_SUFFIX = "-clock-v2"
RECOVERY_HINT = (
    "Call transcribe_video with cache_mode='new_clock' to create a separate "
    "corrected transcript using the normal speech allowance. The original "
    "transcript is preserved, and a verified corrected cache is reused."
)


async def worker_python(sandbox, code, *arguments, timeout=180):
    result = await sandbox.run(
        "python -c " + shlex.quote(code)
        + " " + " ".join(shlex.quote(str(value)) for value in arguments),
        timeout,
    )
    if result["exit_code"]:
        # Worker/provider output can contain source text. The caller supplies
        # a bounded explanation instead of forwarding arbitrary stderr.
        raise ValueError("Speech source or cache inspection failed")
    return result["stdout"]


async def source_identity(sandbox, path, *, elevenlabs):
    result = await worker_python(
        sandbox,
        "import json,sys; from pathlib import Path; "
        "from helpers.transcribe import audio_source_identity; "
        "print(json.dumps(audio_source_identity(Path(sys.argv[1]))))",
        path,
    )
    return json.loads(result) | {
        "adapter": "hosted",
        "provider": "elevenlabs" if elevenlabs else "openai",
        # Preserve the existing hosted provider/model contract. This release
        # changes extraction and cache safety, not model selection or billing.
        "model_id": "scribe_v1" if elevenlabs else "whisper-1",
        "diarize": bool(elevenlabs),
        "tag_audio_events": bool(elevenlabs),
        "timestamps_granularity": "word",
    }


async def validate_cache(sandbox, path, payload, identity, *, legacy_source_sha256=""):
    if not isinstance(payload, dict) or not isinstance(payload.get("words"), list):
        raise ValueError("Transcript cache is invalid; preserve it and use a separate transcript")
    if payload.get("_video_use") == identity:
        return
    # Historical hosted payloads have no identity metadata. The pilot can bind
    # them using its existing owner:SHA256 database key or its digest-named
    # copied source. A generic basename cache alone cannot prove source identity.
    if "_video_use" in payload or legacy_source_sha256 != identity["source_sha256"]:
        raise ValueError("Transcript cache does not match these source bytes and settings; preserve it and use a separate transcript")
    try:
        await worker_python(
            sandbox,
            "import sys; from pathlib import Path; "
            "from helpers.transcribe import legacy_audio_clock; "
            "legacy_audio_clock(Path(sys.argv[1]))",
            path, timeout=1800,
        )
    except ValueError:
        raise ValueError("Legacy transcript audio clock is not verified; preserve it and transcribe separately") from None
    # Recheck after the full decoded-clock proof; never bless changed source bytes.
    if await source_identity(sandbox, path, elevenlabs=identity["provider"] == "elevenlabs") != identity:
        raise ValueError("Speech source changed during cache verification")


async def read_cache(sandbox, path, output, identity, *, legacy_source_sha256=""):
    state = json.loads(await worker_python(
        sandbox,
        "import json,sys; from pathlib import Path; p=Path(sys.argv[1]); "
        "print(json.dumps({'exists':p.exists(),'symlink':p.is_symlink()}))",
        output, timeout=30,
    ))
    if state["symlink"]:
        raise ValueError("Transcript cache must not be a symlink")
    if not state["exists"]:
        return None
    raw = await sandbox.read(output, 2 * 1024 * 1024)
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeError):
        raise ValueError("Transcript cache is invalid JSON; preserve it and use a separate transcript") from None
    await validate_cache(sandbox, path, payload, identity, legacy_source_sha256=legacy_source_sha256)
    return raw


async def extract_audio(sandbox, path, output):
    await worker_python(
        sandbox,
        "import sys; from pathlib import Path; from helpers.transcribe import extract_audio; "
        "extract_audio(Path(sys.argv[1]),Path(sys.argv[2]))",
        path, output,
    )


async def pack_transcripts(sandbox):
    """Keep original JSONs, but prefer their verified hosted clock-v2 siblings."""
    await worker_python(sandbox, """
import json,re
from pathlib import Path
from helpers.transcribe import AUDIO_EXTRACTION
from helpers.pack_transcripts import pack_one_file, render_markdown
root=Path('/workspace/edit')
files=sorted((root/'transcripts').glob('*.json'))
superseded=set()
for path in files:
    match=re.fullmatch(r'([0-9a-f]{64})-clock-v2.json',path.name)
    if not match or path.is_symlink():
        continue
    identity=json.loads(path.read_text()).get('_video_use',{})
    if (isinstance(identity,dict) and identity.get('version')==2 and identity.get('adapter')=='hosted'
        and identity.get('source_sha256')==match[1]
        and identity.get('audio_extraction')==AUDIO_EXTRACTION):
        superseded.add(match[1]+'.json')
entries=[pack_one_file(p,0.5) for p in files if p.name not in superseded]
(root/'takes_packed.md').write_text(render_markdown(entries,0.5),encoding='utf-8')
""", timeout=30)
