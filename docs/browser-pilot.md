# Browser pilot

Live workspace: https://video-use-studio.insforge.site

MCP connector: https://iaredur--video-use-browser-pilot-web.modal.run/mcp

Current behavior and the latest real-run fixes are documented in
[Solar trace repair](solar-trace-repair.md). The iteration notes below are
historical: required first-frame approval and workspace-status cards are
superseded. Only real media opens a player; that player can refresh subsequent
drafts and the final export without assistant polling.

This private pilot lets the assistant in a tester's Claude or ChatGPT account drive the existing video-use harness. The host assistant reads guidance, writes editing code, runs commands, inspects returned images, and exports MP4s. It does not start a second LLM agent. InsForge provides email-code sign-in, private files, project state, and the hosted Studio. Modal provides one coordinator and isolated render workspaces. ElevenLabs supplies transcription and narration using the owner's server-side key.

## Invite a coworker

1. Share the workspace URL and the invitation code stored in the owner's ignored `.env.pilot-production` file (`PILOT_INVITE_CODE`). Do not share that file or any API keys.
2. They sign in using the six-digit code sent to their own email, then enter the invitation code.
3. Open **Connect your assistant** and copy the MCP URL. Connect using OAuth; client registration is automatic, so they do not need a client ID or secret.
4. In Claude, open **Customize → Connectors → + → Add custom connector**. On managed plans, an organization owner may first need to add it. Enable it in the conversation.
5. In ChatGPT, enable **Settings → Security and login → Developer mode**, then add the MCP URL from **Plugins**. Select the connection in a new conversation. Availability depends on account and workspace policy.
6. Approve video-use access on the Studio sign-in page.

Current official setup references: [Claude custom connectors](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp), [ChatGPT developer connections](https://developers.openai.com/plugins/deploy/connect-chatgpt).

Suggested first prompt:

> Using video-use, create a project and make an eight-second typographic introduction for a coffee brand called Still Morning. Inspect the rendered frames before exporting.

For existing footage, create a project in Studio, upload a file, and click **Copy editing prompt**. Results appear in that project's page with playable MP4s and editable source archives. An exported archive contains edit code and supporting assets; original uploaded footage remains in the private project storage. When reopening a stopped workspace, the assistant restores these sources and can render again.

## Account acceptance checks

The owner opted to perform these checks in their signed-in browsers. They remain pending; automated protocol tests do not establish host-account compatibility.

- Sign in, join, reload Studio, and confirm the session restores.
- Connect separately from Claude and ChatGPT and allow OAuth access.
- Run the starter prompt. Confirm actual image review is visible to the assistant before export.
- Open and play the exported MP4 and download its editable source.
- Ask for a wording/color revision in the same project and confirm a second version appears.
- Upload a short clip, request transcription and captions, then export and play it.
- Ask for a short narration and a simple Manim explanation to exercise the additional harness tools.
- Cancel a running task in Studio. Reconnect the assistant and confirm saved projects persist.
- Sign in as a different invited email and confirm the first account's projects are absent.

A connector cannot read attachments from the chat automatically. Upload footage through Studio. Rendering tasks continue independently, but further editing decisions require the host assistant to call the next tool. There is no autonomous agent continuing a creative brief after the conversation stops.

## Owner controls and limits

Sign in using the owner email configured as `PILOT_OWNER_EMAIL`. **Manage pilot** rotates the shared invitation, pauses new execution, and revokes members. Rotation affects future admissions; existing members keep access until revoked. Revocation cancels active tasks and blocks file links.

- Five tester memberships plus the owner. Revoked memberships still occupy a slot in this initial pilot.
- One live workspace per person; two globally.
- Commands reserve up to 30 minutes per task, with daily UTC task-time allowances of 60 minutes per person and 120 minutes globally.
- Five GB of stored objects per person and six GB globally; 200 MB per upload/export/source checkpoint.
- Daily transcription: 30 minutes per person; 150 minutes globally.
- Daily narration: 2,000 characters per person; 10,000 globally. Identical speech requests can reuse cached results.
- Workspaces close after five idle minutes, with a one-hour absolute sandbox lifetime. Last saved edit source survives.

Task-time limits are application admission limits, not exact dollar spending limits: sandbox startup, restoration, checkpointing and idle time also cost money. The coordinator stays warm (`min_containers=1`); InsForge hosting/storage and speech are billed to the owner. These limits support a small trusted pilot, not an untrusted public launch.

On a coordinator restart, unfinished tasks are marked failed rather than replayed; the last saved source remains. Some incomplete storage transfers or interrupted task reservations conservatively retain allowance. Inspect `vp_usage` and actual stored objects before manually reconciling them; do not reset usage blindly. Exported video and source objects remain until deliberately removed. There is no automatic retention/deletion job in this pilot.

Emergency stop: pause from Studio, then stop Modal app `video-use-browser-pilot` if you need to stop the coordinator as well. Changing the encryption key invalidates OAuth grants and file links; preserve the existing key during normal deploys.

## Code map

| File | Responsibility |
| --- | --- |
| `video_use_mcp/pilot/server.py` | `create_app` exposes OAuth, direct MCP editing tools, Studio APIs, consent and owner controls. |
| `video_use_mcp/pilot/runtime.py` | `Manager` restores projects, runs bounded tasks in network-isolated Modal sandboxes, checkpoints source, returns review images and exports revisions. |
| `video_use_mcp/pilot/store.py` | `Store` uses parameterized SQL, encrypts OAuth records and transfers private InsForge objects. |
| `video_use_mcp/pilot/deployment.py` | Modal coordinator definition, separate from the existing MCP deployment. |
| `video_use_mcp/pilot/deploy.py` | Builds the existing harness image and deploys this coordinator. |
| `studio/src/main.js` | Email-code sign-in, invitations, connection setup, project uploads, outputs and owner UI. |
| `studio/vercel.json` | Hosting routes, same-origin auth proxy and response headers. |
| `studio/migrations/` | Tables, owner-scoped RLS, private storage policy and atomic admission/usage functions. |

This work is on `feature/browser-video-pilot` in the separate `video-use-browser-pilot` worktree. Existing local video-use editing stays available in the original checkout. The cloud image reuses `worker_image()` from `video_use_mcp/sandbox.py`, including the current core helpers, motion runtime and Manim. Experimental Jev/live-recording flows are outside this pilot.

## Deploy and maintain

The Studio CLI link points to project `650fa6c3-b28f-4a74-b1c5-1326f183cc36`, not the separate existing website project. Keep `.insforge/` and all environment files out of Git.

Frontend configuration uses `VITE_INSFORGE_URL`, `VITE_INSFORGE_ANON_KEY` and `VITE_API_URL`. Only the public anon key belongs in a browser build. Production auth requests use the same-origin `/api/auth` reverse proxy, which preserves httpOnly refresh cookies. The Vite development proxy uses `VITE_INSFORGE_URL` from local environment configuration.

```sh
# From the pilot worktree, with the existing Python environment activated
python -m video_use_mcp.pilot.deploy

# From studio/, after checking the linked project and deployment env names
npm ci
npm run build
npx -y @insforge/cli deployments deploy .
```

The Modal secret `video-use-browser-pilot-config` holds `PILOT_PUBLIC_URL`, `PILOT_STUDIO_URL`, `PILOT_INSFORGE_URL`, `PILOT_API_KEY`, `PILOT_ENCRYPTION_KEY`, `PILOT_INVITE_CODE`, `PILOT_OWNER_EMAIL` and `ELEVENLABS_API_KEY`. An ignored, owner-readable `.env.pilot-production` is the local recovery copy. Never log or embed those values in the app. Use the InsForge CLI/skills for backend changes; rehearse migrations and RLS on a backend branch before merging.

## Validation performed

- Existing regression suites: 254 passed, one skipped, plus 46 subtests; existing MCP suite: 20 passed.
- Four isolated-backend tests: owner isolation, real OAuth PKCE and code replay prevention, atomic concurrent quota admission, private object/download access.
- Four runtime tests: source checkpoint ordering, failure reporting and credential redaction, cancellation, timeout.
- Real Modal smoke: generated an MP4, returned actual review images over MCP, exported MP4 and source, verified HTTP byte ranges, closed/restored the workspace and exported a revision; real narration and transcription succeeded.
- Production database audit verified RLS, absence of anonymous table access, no direct authenticated writes, private storage policy and restricted quota/admission functions.
- Production frontend build, live API health, OAuth discovery and unauthenticated access denial.
- DOM simulation of email-code sign-in, invite admission, consent redirect, escaped project titles and arrival of new outputs on an idle project page. This is not visual browser QA.

The isolated backend fixtures bypass only email verification for two synthetic accounts after validating their actual backend JWTs; production identity checks reject unverified users. No signed-in Claude/ChatGPT account test or visual browser QA has been claimed. The owner performs those checks above.

The temporary backend branch was deleted after verification to avoid leaving another service running. To repeat the opt-in live tests, create a fresh isolated branch and fresh synthetic auth fixtures (`.env.pilot-test`, `.pilot-test-users.json`); never use the production URL. For the real render smoke, also build a Modal runtime image and save its ID in `.pilot-image`, then run `PILOT_LIVE_TEST=1 python -m video_use_mcp.pilot.tests.smoke_cloud`. This incurs render and speech usage.

## OAuth editing permission fix

The original pilot advertised only `video:read` in protected-resource metadata, so Claude registered read-only OAuth clients even though editing tools were listed. The pilot now advertises and requires both `video:read` and `video:write`, with explicit scope challenges on unauthorized MCP requests. Existing read-only tokens are never silently upgraded. If connected before this fix, remove the old connector entry and add it again so the host rediscovers scopes and registers a new client; approve access in Studio.

`test_oauth_discovery.py` follows resource discovery through PKCE consent, token exchange and project creation, and verifies old read-only grants receive an insufficient-scope challenge. The local MCP and pilot regression suites pass 26 tests after this fix.

## Cost tracking

`python -m video_use_mcp.pilot.cost_report` writes an owner-only local snapshot to `.pilot-costs/latest.md`, structured data to `latest.json`, and an append-only `history.jsonl`. Add `--watch-seconds 1800 --interval 30` to sample for 30 minutes. It uses `.env.pilot-production` and the local Modal login, performs read-only requests, and needs no service redeployment. The local tracking files are ignored by Git.

The tracker retrieves the workspace's current Modal rates and closed-hour billing report. Per-project estimates use recorded sandbox wall time (including idle), with the deployed 2-core/4-GiB request and 4-core/8-GiB limits. Task reservations are reported separately and never counted as billed runtime. Startup/restart gaps may be missing from lifetime telemetry; the range covers recorded time, not a guaranteed final invoice. Closed-hour app charges overlap these estimates and must not be added to them.

Narration uses the current Multilingual v2 list price ($0.08/1,000 characters checked September 30, 2026); override with `--tts-per-1000`. Scribe v1 cost is unknown when used unless its applicable rate is supplied through `--scribe-per-hour`. No speech use is reported as zero. Shared InsForge subscriptions/compute, storage, bandwidth, Modal builds, credits and taxes are excluded from per-video estimates. Claude/ChatGPT inference is supplied by the user's own chat account.

## Execution traces

`python -m video_use_mcp.pilot.trace_report` exports persisted task timelines to owner-only `.pilot-traces/latest.md` and `latest.json`. Filter using `--project UUID`; add `--include-logs` to include command results and task events in the JSON. These ignored local files can contain user content. The exporter uses the existing production configuration, performs read-only requests, and requires no deployment. `collect` gathers operation/status/timing and artifact IDs; `write_report` saves the reviewable timeline.

The initial task telemetry covers queued work, command exit codes, failures, reviews and exports. After the preview-card update, metadata-only tracing also covers MCP tool reads/status polls. Neither captures the host conversation, per-turn tool limits or subscription token usage. Historical tasks could be marked succeeded with a nonzero exit. New tasks with nonzero command exits are marked failed and retain stdout/stderr for correction. To diagnose a host interruption precisely, correlate this timeline and tool metadata with the user's chat.

The first owner title-card run completed 12 tasks (11 succeeded, one sandbox-shutdown failure), including two render passes and two reviews, then exported an eight-second 1920×1080 MP4. The next task after the shutdown restored the workspace. The trace does not establish the cause of that shutdown or the exact point where the host requested another turn.

The failed inspection command decoded all 240 RGB frames and called NumPy `astype(int)`. The 64-bit integer array alone requires about 11.1 GiB, exceeding the sandbox's 8-GiB limit. Memory exhaustion is a strong inference, not a provider-confirmed diagnosis. Future inspection guidance should require sampled or streamed frames rather than keeping the entire video in memory.

For the next interaction iteration, keep creative decisions in the host assistant, batch file changes and execution into fewer calls, and return completed short operations without extra polling. Persist a concise project handoff for continuation. An MCP Apps component can show style frames, draft playback and progress inside supported hosts; app-only status polling avoids asking the model to fetch every update. These recommendations motivated the implementation described below. Background rendering can finish while the assistant is paused; further model decisions still require a host turn within the user's allowance.

## In-chat progress cards and third-run workflow

The MCP Apps resource `ui://video-use/project-v1.html` provides a portable project card. Creating a project attaches it; `show_video_project` reopens it for existing projects. `video_project_updates` is app-only and refreshes the card every eight seconds while visible, for up to 30 minutes (manual Refresh remains available). It displays saved frames, draft clips, previous previews, latest tasks and final exports. Playback is preserved across automatic refreshes. Studio remains the fallback when a host does not display MCP Apps. Each host must still be tested in a signed-in account.

`run_video_step` batches up to 20 source-file writes, an optional command, optional preview publication, and checkpointing into one task. `update_video_progress` saves a milestone and continuation context, optionally publishing an existing frame/clip. The assistant should publish a style frame, a low-resolution motion draft, then review and export the final encode. These are deliberate milestones; arbitrary files appearing in a running command are not automatically published. The agent is instructed to send short chat updates and keep working without unsolicited approval pauses.

Mutation tools and `get_video_task` wait up to 25 seconds. Waiting is shielded so HTTP cancellation or a wait timeout cannot cancel the underlying render. A short task generally returns completed; a long task can require another bounded status call. This reduces polling but cannot change host tool/usage limits or force the host to start another reasoning turn. `get_video_task` defaults to abbreviated logs; `include_logs=true` retrieves diagnostic output.

Image previews are validated and resized PNGs; video previews are H.264 clips capped at 20 seconds, 960×540 bounding dimensions, and 25 MB. They use existing private storage and expiring, membership-checked file links. Drafts do not set the reviewed-video hash required for export. Finished style-image steps also return an actual MCP image for the assistant to inspect. Final export still requires the separate encoded review image.

The progress record preserves the brief, next action and 20 recent milestones in encrypted server-only storage. `get_video_project` returns it on continuation. New tool-call telemetry records tool name, project/task IDs, duration, input/output byte counts, hashed client identity and whether the call came from the card-specific tool. It excludes source code, arguments, tool outputs and credentials. Task logs remain separately available. The trace reporter includes these calls and counts, distinguishes card refreshes from assistant calls, and shows saved next steps. Traces have a 30-day retrieval window; the exporter caps its scan at 10,000 recent calls. Calls without a project ID are reported separately. It cannot observe the host's internal reasoning, turn boundaries or remaining subscription allowance.

Build the card with `npm ci && npm run build && npm test` from `video_use_mcp/pilot/ui`; the self-contained `card.html` is deployed with the coordinator. Dependencies are locked; no third-party scripts are fetched by the card. The Python protocol tests cover resource metadata, app-only visibility, ownership, trace redaction, non-cancelling waits and the final-review boundary. DOM tests cover image/video updates, safe text rendering, historical previews, stable playback and connection errors. Local protocol/DOM verification does not establish that a particular host/account renders the card.

Code: `cards.py` registers the tools and resource; `interaction.py` implements safe waits, progress persistence and metadata-only tool traces; `ui/` contains the card and its build/tests; `runtime.py` executes batched steps and bounded preview encoding.

Live verification on September 30: the deployed MCP resource returned the correct UI MIME type and CSP, a batched step published a real PNG and model-visible image, the next step published an MP4 supporting HTTP byte ranges, the card snapshot retained both previews and continuation context, and encoded review followed by final export succeeded. The verification workspace was closed. The final local suite passes 37 tests, plus the card DOM/bundle checks. Actual Claude/ChatGPT card display remains the owner's acceptance test.

## Minimal Studio appearance

Studio and the chat card now use a centered near-black/purple palette and a self-hosted Space Grotesk font (license under `studio/public/fonts/`). Studio opens on a creations gallery with final-video covers. Project pages feature one large player, a compact version selector and download action; files, activity and account controls are collapsed. Private intermediate previews are returned by the owner-checked project API alongside final exports. Gallery polling detects new creations, and project polling avoids repainting a playing video. The card resource moved to `ui://video-use/project-v2.html` to refresh host caches; its font is embedded in the HTML bundle. Refresh connector metadata to discover the new resource.


## Visual milestones and reliability fixes

The fourth browser iteration uses `ui://video-use/project-v3.html`. Project creation now returns an explicit MCP App result and saves the brief. Batched editing, direct frame viewing, review, export, and task completion carry card metadata. `run_video_step` requires `preview_path` for style/motion/draft milestones; completed results include the PNG for model inspection plus the live card snapshot. `review_path` combines final rendering and encoded review in one task. A completed review already unlocks the exact-file review gate after returning its image: no redundant status call is necessary. Export remains a separate decision after visual inspection.

Direct frame inspection publishes the image for the user as well as returning it to the model. Final cards include a native player and Download MP4 button. The download endpoint uses an explicit attachment response when `download=true`; inline playback and byte ranges remain available. Drafts are also downloadable. These are portable MCP Apps components; host/account support and refreshing cached connector metadata still determine whether a host displays them. The project page and links remain available as fallback.

`Manager.runtime_image` no longer shadows the frame-reading method. Nonzero commands become failed tasks. Request IDs are scoped to each project while existing exact retries retain their meaning. Redacted exception messages are retained in encrypted traces; credentials and signed URLs are removed, and messages are excluded from public service logging.

The deployment command checks both active tasks and open workspaces before and after building, then briefly gates new work during deployment. Checking task queues alone is insufficient while an agent is between calls. Idle live sandboxes are detached and reattached across coordinator changes, preserving temporary video files. Interrupted commands are never silently replayed. Sandbox idle and one-hour absolute limits still apply; source checkpoints and published artifacts survive expiration, but unpublished binaries are not part of the source ZIP.

`helpers/render_manim_cached.py SOURCE SCENE... --quality preview|final` returns ordered scene video paths and reuses unchanged outputs. Source and adjacent Python helpers affect the cache; non-Python visual inputs must be passed with `--dependency`. Audio mixing should be separate. Changing volume then remuxing cached visuals avoids another full Manim render. This helps when the host follows the workflow; it does not impose a fixed latency or bypass the host's tool limits.

Verification after the fourth iteration: 45 local Python tests pass (four opt-in isolated-backend tests skipped), the card DOM tests pass, and the deployed MCP flow passed real PNG delivery, draft MP4 byte-range playback, direct frame publication, combined render/review with immediate image delivery, final export using a previously used request ID in a different project, and an attachment download of the final MP4. The test workspace was closed. These checks validate the server and component; the owner still performs the signed-in Claude/ChatGPT visual acceptance test.

A real Modal Manim probe also confirmed cache reuse: the first helper invocation rendered its scene, and the second reported the same scene reused without another Manim invocation. Cost snapshots were enabled for the next hour of user acceptance testing.


## Conversational video branch

The owner rejected the workspace/dashboard experience in the fourth run. On `feature/conversational-video`, new discovery starts with `propose_video`: Claude supplies bounded drawing marks for a representative concept frame, which Pillow renders in the warm coordinator. It creates no render sandbox and buys no speech. The result is the actual PNG plus a media-only MCP App. There is no workspace title, brand, status placeholder, gallery, or auto-polling. The host can still draw its own tool attribution/border; `prefersBorder=false` requests minimal presentation but cannot override host chrome.

The normal first turn ends with one natural-language design question. `direction` state records the frame specification, artifact and brief as awaiting feedback; Manager.submit refuses production commands and narration until `accept_video_direction` records the user's real reply. The server cannot inspect the host transcript or independently verify that a model-supplied quote is real; this is a workflow gate, not proof of human authorization. Revising the proposal resets the gate. Explicit creative delegation can be honored using the actual delegation as feedback, rather than invented approval.

After agreement, the approved PNG and JSON are placed in `edit/direction.png` and `edit/direction.json`; the host develops the story and EDL, then a short draft. It shows completed media with `show_video_preview` and asks for creative feedback. Background execution, narration and status tools have no UI resource metadata, preventing empty setup cards. Final export remains subject to the exact encoded-frame review gate, and a completed media view provides the final player and attachment download. Legacy handlers stay callable for old conversations but setup/raw terminal tools are omitted from new discovery.

Write tools remain honestly marked as mutations. Isolated execution is annotated as closed-world because the sandbox has no network, credentials or local-machine access. The service cannot turn off Claude's approval dialogs; the user can select Always allow for trusted connector tools in Claude settings, subject to their organization's policy.

Trace export now supports `--watch-seconds 3600 --interval 30` and appends snapshots to private `history.jsonl`. This is a bounded local sampler, not an autonomous monitoring service; durable server traces still capture subsequent calls even when the sampler is not running.

Live conversational-flow verification passed on September 30: propose_video returned the authored PNG in 1.87 seconds measured from the API call (excluding host reasoning), with no sandbox and no tasks. A premature narration attempt was rejected without buying speech. Test feedback unlocked the draft; the approved PNG was restored into the sandbox, the media-only draft supported byte-range playback, and reviewed final export downloaded with attachment disposition. The test workspace was closed. Local verification passes 48 Python tests plus the no-placeholder/no-polling media-view tests; four optional isolated-backend tests remain skipped. Actual natural-language behavior in the owner's Claude account still requires the next chat.

## Adaptive creative workflow October 1

The mandatory first-frame proposal and approval workflow is superseded. New conversations
start with `start_video`, infer one of eight categories, and preserve the user's stated
preferences. They do not allocate a render sandbox or emit an empty card.

| Intent | Useful decision | Production route |
| --- | --- | --- |
| Educational explainer | Diagram-led versus editorial when unspecified | Claim, script, scene beats, independent scene renders, assembly |
| Social repurposing | Caption treatment if unspecified | Source, transcript, selects, reframing, independent clip renders |
| Precise edit | Only ambiguity in the requested change | Direct edit and boundary checks |
| Software demo | UI-focused versus product story | Real recording, action/result sequence, zooms and callouts |
| Brand motion | Visual premise and brand constraints | Asset proof, choreography, sound and delivery |
| Footage story | Emotional arc or a meaningful reference | Source selects, EDL, picture and sound edit |
| Data story | Claim and evidence presentation | Validate data, chart scenes, scale and number checks |
| Generative hybrid | Mood, continuity and actual provider availability | Shot list and asset inventory; generation unavailable until a provider is configured |

`show_video_choices` offers two cached playable references only where useful. Five original
samples and posters are hosted in the public InsForge `video-references` bucket with
content-hashed keys. User footage remains in the private bucket. These are visual references,
not promises that arbitrary 3D, real software recordings or generated footage already exist.
Source, provenance, rebuild and publish instructions live in `video_use_mcp/pilot/references`.

The app-only `choose_video_style` writes an owner-scoped explicit choice. It sends model
context and a user-initiated message only if the host advertises those SDK capabilities.
Unsupported hosts fall back to natural-language replies. There are no polling loops or
automatic assistant-continuation messages. The portable SDK names are `updateModelContext`
and `message` in the installed version; check local types before copying newer documentation.

`plan_video` stores flexible story beats. Plans and brief changes advance the creative
revision; planning does not expire an open style picker. The assistant can inspect media,
outline a story and develop shared assets while the user chooses. Reversible assumptions
are stated as defaults, never as user approval. A necessary source upload or a requested
checkpoint can still require a reply. Host turn scheduling, reasoning time, subscription
limits, native attribution and tool permission dialogs remain outside MCP server control.

`run_video_step` accepts up to six independent component commands, runs at most two
concurrently in the same bounded sandbox, and executes assembly only after all succeed.
Components must use distinct output/cache paths and low thread counts. This parallelizes
render execution, not hidden model agents. One total timeout and compute reservation cover
the step. Latest creative context returns with task results and is saved as
`edit/creative.json`; version mismatches prevent stale renders/exports. A failed component
retains its logs and prevents final assembly. Use preview resolution first, reuse visual
renders when mixing audio, and show only meaningful new motion and the final media player.

Legacy proposal handlers remain callable for cached conversations, but are hidden from new
discovery and no longer block production. Start a fresh host conversation to get the new
instructions and tools. A reconnect may be necessary if the host caches tool discovery.

Trace exports now include creative context and render preference revisions alongside task
logs. They still cannot see host reasoning, user chat messages or remaining subscription
allowance. Signed-in Claude and ChatGPT acceptance testing remains with the account owner.

Validation: deployed application revision `5d7cd16` on branch
`feature/conversational-video`; following commits only update tests/documentation.
52 Python tests pass; four opt-in isolated-backend tests remain skipped. Embedded UI tests
cover media-only rendering, no automatic messages, click persistence and capability fallback.
Five cached samples passed full decoding and deterministic seek checks. Live authenticated
MCP fixture `e0b1d0dd-76c2-44e1-93e6-5353b296924e` verified reference retrieval without a sandbox,
choice persistence across planning, two concurrent scene commands, review, ranged playback
and attachment download. The 22.08-second fixture is a two-second technical video, not an
explainer latency benchmark. The fixture sandbox was closed and its test grant revoked.
