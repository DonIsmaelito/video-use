# Short social edits

This follow-on campaign adds three recovered screen demos from `x-demo-maker`
and twenty new, practical social edits to the free Video Use gallery.
`briefs.json` contains the twenty original creative prompts and their actual
source URLs, bounded selections, rights evidence and acquired-media hashes.

The screen demos are existing work, with reconstructed **Starter prompts**.
They are not counted among the twenty new productions. Their original files
remain untouched; the published copies omit music whose reuse was not cleared.

## Production and review

`experiments/useful_video_library.py` freezes the branch commit and individual
framework files before starting up to four creative containers. Each movie
keeps its actual producer snapshot; a later repair is a separate attempt.
Prepared source files and transcripts are checked against their recorded hashes.
YouTube excerpts were acquired with yt-dlp on the local machine and verified
again after upload. A blocked cloud acquisition is not treated as successful.

The examples cover captioned interviews, podcast exchanges, explanatory clips,
action replays, food and craft edits, nature/travel reels, licensed film scenes
and an enlarged-code tutorial. Public source packages retain editable decisions,
timed captions, credits, dependency versions and replay instructions. They omit
raw footage/audio, credentials, private agent traces and generated render caches.
An external URL does not guarantee that the same encoded rendition remains
available; replay instructions must check content, timing and source hashes.

Publication requires separate reviews of actual encoded pictures and playback,
source/word timing, attribution, package contents and editable replay behavior.
An explicit parent approval binds the exact MP4 and ZIP hashes before
`experiments/publish_useful_video.py` can upload. The website importer verifies
those receipts. Hosted checks cover players, phone layouts, prompt copying,
deep links, source downloads and the Short-form edits filter.

Speech checks combine source evidence, caption mappings and independent ASR of
the encoded delivery where useful. Audio decoding and levels are measured.
These checks are not a claim of subjective listening. Mechanical playback and
caption-box fit also do not establish aesthetic quality: weak compositions and
unreadably short cues are held for a preserved repair.

## Shared improvements

The campaign's reusable changes are in the actual production framework:

| Files | Purpose |
| --- | --- |
| `helpers/face_track.py`, `helpers/face_follow.py` | Measure a reviewed face target within a real shot, then compile bounded crop motion through the normal renderer. They do not identify people or infer active speakers. |
| `helpers/transcribe.py`, `video_use_mcp/transcription.py`, `video_use_mcp/runtime.py` | Preserve source audio offsets and gaps during ASR extraction and verify cache compatibility. The hosted MCP and standalone workflow share that policy; explicit `new_clock` recovery preserves historical caches and reuses a separately verified correction. |
| `helpers/silent_retime.py` | Create an explicit, frame-mapped slow replay from silent footage, without claiming optical flow or secretly discarding audio. |
| `helpers/ambient_audio.py` | Generate original bounded tonal/pulse beds with deterministic PCM and headroom checks. This is synthesis, not recorded location sound. |
| `helpers/caption_readability.py` | Report phrase density, overlap and optional fixed-font capacity without silently deleting words or automatically approving an edit. |
| `helpers/timeline_view.py` | Resolve the actual final decoded frame when inspecting an exact clip endpoint. |

The complete evidence and decisions remain in
[`../useful-library/TOOL-GAPS.md`](../useful-library/TOOL-GAPS.md).
Source-specific two-person stacks, animal framing, broadcast-window extraction,
audio-handle assembly and authored graphic layouts remain editable project code.
They are not advertised as general tracking, speaker recognition or arbitrary
input APIs. When a shared helper supersedes an early project proposal, the early
movie keeps its original implementation and producer identity.

Large deliveries, immutable approvals, independent reviews and deployment
receipts live in the campaign's `edit` directory outside Git. The public catalog
and media-source ledger retain the approved identities and links. Only verified,
cloud-backed fetched caches may be released locally; source recordings are not
deleted or rewritten.
