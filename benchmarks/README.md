# Video Use agent benchmark

This is an observational baseline harness for measuring Video Use agent behavior.
It runs each fixed workload in three clean workspaces, resumes one Codex session
through strategy approval and any later stops, validates the media, and writes an
aggregate report. It is intentionally manual and is not a CI quality gate.

The two versioned workloads live in `benchmarks/tasks/`:

- `jensen-tiktok`: edit the complete 6,192.414-second Jensen interview into one
  or more agent-selected vertical clips.
- `gpu-explainer`: create a 55-65 second Manim explainer called “How GPUs
  Accelerate AI,” with measured ElevenLabs narration.

## One-time setup

Use Python 3.10 or newer, install the project dependencies, and ensure `codex`,
`ffmpeg`, and `ffprobe` are on `PATH`. The explainer also needs Manim and LaTeX:

```bash
uv sync --extra animations
bash skills/manim-video/scripts/setup.sh
```

The runner automatically prepends the repository's `.venv/bin`, so Manim
installed by `uv sync` is available inside each clean benchmark workspace.
It also discovers `/Library/TeX/texbin` or the user-local BasicTeX extraction;
set `VIDEO_USE_TEX_BIN` when TeX lives somewhere else.

Prepare the Jensen transcript before starting the timer. This is a paid
ElevenLabs Scribe operation, but it is performed only once and is excluded from
every measured run:

```bash
export ELEVENLABS_API_KEY=your_key
python helpers/transcribe.py \
  /Users/ismaelito/Movies/video-use-tests/test-01/jensen_test1.mp4 \
  --edit-dir /Users/ismaelito/Movies/video-use-tests/test-01/edit
```

The expected immutable cache is
`/Users/ismaelito/Movies/video-use-tests/test-01/edit/transcripts/jensen_test1.json`.
Override either Jensen path with `VIDEO_USE_JENSEN_SOURCE` or
`VIDEO_USE_JENSEN_TRANSCRIPT`.

For the explainer, keep one voice ID fixed across baseline and candidate runs:

```bash
export ELEVENLABS_API_KEY=your_key
export ELEVENLABS_VOICE_ID=your_fixed_voice_id
```

The runner loads missing values from the repository's ignored `.env` without
overriding variables already exported by the shell.

The TTS model and output format are fixed in the task definition to
`eleven_multilingual_v2` and `mp3_44100_128`. To include an account-specific
monetary estimate, set `ELEVENLABS_USD_PER_1000_CHARACTERS`; the harness always
records the provider's character-cost response header even when no dollar rate
is configured. Request records are append-only, so narration retries and failed
requests remain visible instead of overwriting earlier cost and latency data.

## Running a baseline

First check inputs without invoking a model or paid service:

```bash
python benchmarks/run.py --task jensen-tiktok --repeat 3 --dry-run
python benchmarks/run.py --task gpu-explainer --repeat 3 --dry-run
```

Then run each measured workload:

```bash
python benchmarks/run.py --task jensen-tiktok --repeat 3
python benchmarks/run.py --task gpu-explainer --repeat 3
```

Override the model or reasoning effort for a comparison run without editing the
versioned workload:

```bash
python benchmarks/run.py --task jensen-tiktok --repeat 1 \
  --model gpt-5.6-luna --reasoning-effort high
```

Raw JSONL, timestamped events, stderr, copied transcript caches, and generated
media are written outside the repository by default under
`/Users/ismaelito/Movies/video-use-tests/benchmark-runs`. Override that location
with `VIDEO_USE_BENCH_ROOT` or `--bench-root`. Every actual run gets a new empty
workspace. Dependencies and the immutable transcript cache are the only reused
inputs.

To create a sanitized report suitable for review or Git:

```bash
python benchmarks/run.py --task jensen-tiktok --repeat 3 \
  --export-baseline benchmarks/baselines/jensen-tiktok-v1.json
```

The exported aggregate contains all three sanitized run summaries plus the
median, minimum, and maximum for each numeric metric. It excludes prompts, raw
events, command output, transcript text, media paths, media files, API keys, and
request IDs. Inspect the export before committing it.

Each run uses the versioned agent-neutral envelope in
`benchmarks/schemas/run-summary.schema.json`. Codex-specific collection is
identified as adapter `codex-exec-jsonl` version 1, leaving room for another
agent adapter without changing the task or comparison model.

## What is measured

The versioned tasks default to `gpt-5.6-sol` with high reasoning effort; explicit
comparison runs may override either setting. The runner records the effective
model and effort, Codex CLI version, task and prompt hashes, Git and skill
revisions, dirty state, source and transcript hashes, dependency versions,
operating system, architecture, and run ID.

Per turn, it retains exact input, cached-input, output, reasoning, and total token
counts reported by Codex. Planning and production turn labels come from the
required structured turn result. Reasoning tokens are reported as a subset of
output and are not charged a second time.

It also records agent and benchmark wall time, time to first item, turn latency,
command/tool/file-change/reasoning counts, failures and successful retries,
render and self-evaluation iterations, subagent count, and stop behavior. Tool
steps and latency are classified into the stable phases `inventory`,
`transcription_cache`, `transcript_packing`, `strategy`, `edl_creation`,
`animation`, `tts`, `rendering`, `verification`, and `finalization`. Tokens are
not attributed below the turn boundary because the Codex stream does not provide
that attribution.

`agent_wall_time_s` is the sum of Codex process time. `benchmark_wall_time_s`
also includes orchestration and post-run validation. Their difference is reported
as `harness_overhead_s`, while full media decoding is separately reported as
`validation_wall_time_s`.

TikTok reports include totals and values normalized per clip and per produced
minute. Setup and preflight happen before the benchmark timer. ElevenLabs TTS for
the explainer happens during the measured production turn.

Codex cost is explicitly labeled as an API-equivalent estimate, not actual
ChatGPT subscription billing. The versioned price table is `benchmarks/prices.json`.

## Artifact validation

Each MP4 is fully decoded with ffmpeg and inspected with ffprobe. Validation
checks duration, dimensions or aspect ratio, frame rate, H.264 video, AAC audio,
and audible signal. TikTok clips must have a matching SRT sidecar; the task prompt
also requires the agent to burn those captions into the picture. The structural
validator does not judge caption appearance or artistic quality in v1.

## Comparing changes

```bash
python benchmarks/compare.py \
  benchmarks/baselines/jensen-tiktok-v1.json \
  benchmarks/baselines/jensen-tiktok-v1-candidate.json
```

The comparison reports median absolute and percentage changes. Different task
definitions, source/input hashes, models, reasoning efforts, agent adapters, or
price-table versions are rejected unless
`--allow-incompatible` is supplied. A candidate is never marked eligible as an
improvement when its media-validation success rate is lower than the baseline.

## Offline tests

```bash
pytest -q
```

The tests use a fake Codex executable and tiny synthetic ffmpeg media. They do
not invoke a model, ElevenLabs, or the full Jensen source.
