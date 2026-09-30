# Browser pilot

Live workspace: https://video-use-studio.insforge.site

MCP connector: https://iaredur--video-use-browser-pilot-web.modal.run/mcp

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
