# video-use GUI experiment harness

This is an internal output-discovery tool, not a required video-use interface or
deployment architecture. It runs four independent attempts in parallel so a
developer can inspect more strong outputs, ugly outputs, and failures before a
behavior is promoted into the public skill or reusable helpers.

The browser, Codex agents, and event broker run on the Mac; every lane invokes
its own one-container Modal Function pool for the final render with the current
video-use working tree mounted at `/opt/video-use`. Final MP4s and their poster
live in Cloudflare R2. The Mac keeps only a compact run index and text evidence;
supporting generated media stays in the Modal Volume.

## R2 setup

Create an R2 bucket, enable public access, and create an API token with object
read/write access to that bucket. Cloudflare documents both the development
`r2.dev` URL and custom-domain option in its
[public bucket guide](https://developers.cloudflare.com/r2/buckets/public-buckets/).
The `r2.dev` URL is suitable for this personal harness; set a custom domain
later without changing stored records.

Set these values in the local environment and in a scoped Modal secret named
`video-use-r2`:

```text
R2_ACCOUNT_ID
R2_ACCESS_KEY_ID
R2_SECRET_ACCESS_KEY
R2_BUCKET
R2_PUBLIC_BASE_URL
```

For example, after exporting the values locally:

```bash
modal secret create video-use-r2 \
  R2_ACCOUNT_ID="$R2_ACCOUNT_ID" \
  R2_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID" \
  R2_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY" \
  R2_BUCKET="$R2_BUCKET" \
  R2_PUBLIC_BASE_URL="$R2_PUBLIC_BASE_URL"
```

The public base URL is the only storage address sent to the browser. R2 API
endpoints and credentials remain server-side.

## Start

```bash
python -m pip install -r gui/requirements.txt
modal deploy gui/modal_app.py
python -m gui.server
```

Open `http://127.0.0.1:8765`.

Each lane accepts a task and an optional local video-project directory. The
server creates an isolated clone, starts a new ephemeral Codex thread, attaches
the current branch's `video-use` skill, and requires the agent to produce
`edit/edl.json`. That agent-produced project is uploaded and rendered with
`helpers/render.py --preview` in the lane's Modal worker.

Model choices come from the locally authenticated Codex app-server catalog.
Changing a model immediately refreshes that lane's supported reasoning levels;
the selected pair is captured when Run is clicked and cannot change mid-job.
Every submitted job uses the `fresh_ephemeral` context policy. The runner calls
`thread/start` with `ephemeral: true` and never resumes or forks another GUI or
Codex conversation. Previous `edit/runs`, project `.codex` data, Git metadata,
environment files, and credential files are excluded from the agent clone.
Global/project instruction-file loading is disabled for the subprocess and all
configured MCP servers are turned off. The submitted task, the runner's
clean-room instructions, and the attached branch copy of `video-use/SKILL.md`
are the only task-specific context sources. Host skill discovery and skill
search are disabled so a global `video-use` installation cannot replace the
working-tree copy bundled with this tool.

Codex command, file, network, or permission escalation requests pause only the
affected lane. Resolve them with the lane's Allow once, Allow lane, or Deny
buttons; the other lanes continue independently. A persistent Allow lane
shortcut in the lane header becomes active whenever an approval is waiting.
Each lane also has an `auto allow` setting, enabled by default in the browser.
It opts the next run into automatic approval before the first request and is
remembered per lane on that browser. The scope is one fresh run and is cleared
when its local Codex process exits. This setting applies to the local agent phase;
Modal workers only receive the completed, validated project and do not prompt for
interactive approval.

The small `expand` control above each Run button opens that lane's submitted
query and complete agent trace side by side. The trace remains live during a run
and scrolls independently from the four-lane grid.

EDLs are validated before project upload and again inside Modal. A blocked or
incomplete handoff therefore returns an actionable lane error without starting
an ffmpeg render. Declared multi-format deliverables render from one staged edit;
the first appears automatically and compact output labels switch the lane player
between the remaining videos.

Fresh lane handoffs also enforce the version-2 caption contract. Captions require
timestamped transcript or narration-alignment evidence for audible speech. A
music-only or silent handoff must omit subtitles and caption metadata, and Modal
does not build captions merely because transcript files happen to be present.

Absolute source paths in an EDL are rewritten only in the uploaded copy. Local
source media and the original project are never modified by the agent. Returned
videos are uploaded by the Modal worker directly to
`runs/<run-id>/<artifact-id>.mp4`; the primary poster is stored at
`runs/<run-id>/poster.jpg`. New outputs are never downloaded to the Mac. Runs
without a project path keep their small evidence record under the operating
system's durable application-data directory. Set `VIDEO_USE_GUI_DATA_DIR` to
override that location.

`gui/run_store.py` indexes every durable run and keeps its evidence together:

- `agent-edit/` contains the generated EDL and text-only supporting evidence.
- `trace.json` contains the prompt, selected agent configuration, and complete
  deduplicated event history.
- `run_summary.md` is a compact agent-readable account of the outcome,
  decisions, edit shape, and errors.
- `codex-protocol.jsonl` preserves every unabridged app-server request,
  response, notification, and streaming delta when available.
- `codex-app-server.stderr.log` keeps local subprocess diagnostics.
- `render.log` contains the complete remote renderer and FFmpeg output,
  including lines intentionally hidden from the live lane pane.
- R2 artifact URLs identify every returned deliverable and the primary poster.

Each fresh agent also writes a compact `task_context` object into its EDL. The
lane header and durable record show `create` or `edit` plus a short workflow
label, such as `social ad` or `talking head`. Older handoffs are classified from
their saved EDL structure rather than requiring the original prompt; the source
of that label is retained in `trace.json`.

The history gallery loads successful R2-backed runs newest first. One card is
shown per run; its shared player dialog switches between multiple deliverables
and uses native video controls for seeking and fullscreen. Deletion requires a
browser confirmation and removes the R2 prefix and Modal Volume run before the
local record. Any remote deletion failure keeps the history entry.

Legacy local outputs are never migrated automatically. Preview a migration:

```bash
python -m gui.migrate_history
```

Apply it explicitly after reviewing the plan:

```bash
python -m gui.migrate_history --apply
```

The command verifies every uploaded object before updating the index or removing
local `output*.mp4` and poster files. A failed or interrupted upload leaves local
media untouched, and rerunning the command safely overwrites the same R2 keys.

Modal credentials stay in the active local Modal profile. They are never read
by the browser or stored in this repository.
