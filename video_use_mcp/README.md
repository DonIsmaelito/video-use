# video-use MCP and browser studio

Create original videos or edit uploaded footage from a browser, ChatGPT, Claude
web, or Claude Code. All interfaces use the same persistent projects and jobs.
The production agent reads this checkout's `SKILL.md`, motion-design and Manim
skills, authors editable source, renders in a private Modal sandbox, sees encoded
output frames, and returns an MP4 plus the editable project ZIP.

## Quick start

Run from a checkout of this repository. Requires Python 3.10+, uv, and a Modal
account. Model and speech keys are entered
in the studio; the server operator supplies the Modal compute account.

```sh
uv sync --extra mcp
uv run modal setup
uv run python -m video_use_mcp
```

Open **http://localhost:8787**, create an account, and open **Settings**. Choose
OpenAI, Anthropic, or OpenRouter, enter its API key and a model ID available to
your account. Add ElevenLabs for narration and speech transcription; an OpenAI
key also supports word-timed Whisper transcription. Keys are encrypted at rest
and are never returned to the browser, MCP client, or generated-code sandbox.
The service operator controls the encryption key and can technically decrypt
stored credentials. Run your own instance when that trust is inappropriate.

Create a project, optionally upload video/audio/images, and describe what to make.
The first job builds its render image, including FFmpeg, Node 22, Chromium,
Manim, Pillow and the branch's current helper code. Subsequent jobs reuse it.
Save a deployment with the commands below to build the image ahead of time.

## Connect an assistant

The public endpoint is **`https://YOUR-HOST/mcp`**. The same endpoint handles all
clients; it uses the official Python MCP SDK's Streamable HTTP transport and
OAuth authorization-code flow with PKCE, dynamic client registration, refresh
rotation, revocation, resource binding, and per-user tool access.

- **ChatGPT:** In Settings → Security and login, enable developer mode if
  available to your account/workspace. In Plugins, use the plus button to
  add this URL, choose OAuth, and sign in to the
  video-use account. Account policy may limit access. Public directory listing
  is a separate submission and is not part of this server.
- **Claude web:** Add a custom connector with this URL under Connectors. Complete
  OAuth and enable the connector in the conversation.
- **Claude Code:** Run the following, then use `/mcp` to sign in:

```sh
claude mcp add --transport http video-use https://YOUR-HOST/mcp
```

For desktop development, the HTTP URL can be `http://localhost:8787/mcp`.
Web clients need a reachable HTTPS service. An HTTPS development tunnel works
too: set `VIDEO_USE_PUBLIC_URL` to that origin and restart the server so OAuth
metadata, callbacks, links and origin validation agree.

Try: “Create a video-use project for a 12 second launch film. Make a beautiful
typographic introduction to a coffee brand called Still Morning.”

For footage: “Create a project for editing my interview and give me the upload
link.” Upload in the studio, then ask the assistant to inspect the project and
start the edit. Chat attachments are not automatically copied to this server.

## Tools

| Tool | Purpose |
| --- | --- |
| `video_use_setup` | Account setup status and private browser workspace link |
| `list_video_projects` | Discover the current user's projects |
| `create_video_project` | Create a project and return its upload workspace |
| `get_video_project` | List uploaded media and previous revisions |
| `start_video_job` | Start an autonomous production job; returns immediately |
| `get_video_job` | Progress, outcome, one-hour MP4/source download links |
| `cancel_video_job` | Stop work while preserving earlier successful revisions |

Retry an ambiguous start with the **same `request_id` and brief** to avoid duplicate
charges. Reuse a project ID for revisions. The latest successful source archive
is restored into each new sandbox, alongside the original uploaded media.
Long jobs continue when the browser closes. Assistants should return the live
workspace link and check status on follow-up, instead of polling in a tight loop.

## Deploy on Modal

The deployment uses a persistent Volume and **one always-on coordinator**. Each
job starts an independent network-isolated sandbox without secrets or other
users' media. The coordinator makes provider requests on each user's behalf.

Create an ignored `.env.mcp` configuration file (not the root `.env.example`):

```dotenv
VIDEO_USE_PUBLIC_URL=https://YOUR-WORKSPACE--video-use-mcp-web.modal.run
VIDEO_USE_ENCRYPTION_KEY=GENERATED_FERNET_KEY
VIDEO_USE_INVITE_CODE=YOUR_PRIVATE_INVITATION_CODE
```

Generate the encryption key and invitation code locally:

```sh
uv run python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
uv run python -c 'import secrets; print(secrets.token_urlsafe(24))'
uv run modal secret create video-use-mcp-config --from-dotenv .env.mcp
uv run python -m video_use_mcp.deploy
```

Use the actual URL printed by Modal. If it differs, update the secret's
`VIDEO_USE_PUBLIC_URL` and redeploy before connecting OAuth clients. Keep a
backup of the encryption key: losing it makes saved credentials unreadable.
Do not rotate it without re-encrypting the existing database records.

The checked-in deployment does **not** require the developer's private Modal
secrets. Every new account brings its own model keys. An operator can optionally
set `VIDEO_USE_OWNER_BOOTSTRAP` to a strong random token and provide provider
environment keys in the same Modal secret. This pre-creates an `owner` account
and connects those keys only to it. Visit `/#setup=TOKEN` once, then set an owner
password in Settings. This token is a password equivalent; do not publish it.

The pilot deliberately uses one SQLite writer and one coordinator. Avoid
redeploying during active production: interrupted jobs are marked failed with
an explanation, queued jobs resume, and previous outputs remain available.
For horizontal service scaling, replace the SQLite queue and volume metadata
with a transactional database and independently leased workers first. Do not
increase `max_containers` on the current coordinator.

## Costs and limits

MCP access does not include model inference or rendering. Users' saved API keys
pay for model/speech calls. The operator's Modal account pays for the coordinator,
sandbox execution and storage. Sandboxes have different rates from Modal
Functions. Keeping this deployment running has a baseline compute cost because
`min_containers=1`; stop the Modal app to stop its coordinator.

At Modal's published rates on September 20, 2026, the coordinator's reserved
0.25 CPU core and 1 GiB budget about **$14.24 per 30 days** before credits,
storage, traffic or CPU bursts. A ten-minute sandbox at 2 cores / 4 GiB budgets
about **$0.063**, rising to about **$0.127** at the configured 4-core / 8-GiB
ceiling. These are resource-rate estimates, not a bill or a price per finished
video; model tokens and speech are additional. See [Modal pricing](https://modal.com/pricing).

Default bounds: two concurrent jobs globally; two active jobs and ten jobs per
day per account; 30 minutes per job; 60 model turns; 800,000 cumulatively reported
tokens; 500 MB per uploaded file; 5 GB of uploaded media and completed outputs per
account. Token/time bounds are **not an exact dollar spending cap**. Provider
account limits remain the authoritative spending control. Use invitations for a
hosted pilot, since users' API keys do not pay the operator's compute bill.

Video creation here means agent-authored code, animation, composition and editing.
It does not currently call a generative video model or automatically acquire stock
footage. Speech tools depend on the configured providers. Browser previews and
finished output are subject to the actual model, brief and source material;
no quality guarantee is implied by successful technical checks.

## Code map

- `server.py`: browser API, uploads, MCP tools, per-account authorization and links.
- `auth.py`: persistent OAuth grants behind the SDK's protocol validation.
- `store.py`: accounts, encrypted credentials, projects, revisions and events.
- `jobs.py`: durable queue, cancellation, sandbox handoff and source preservation.
- `agent.py`: real harness instructions, creation tools, speech, visual feedback,
  and verification before final delivery.
- `providers.py`: OpenAI Responses, Anthropic Messages and OpenRouter adapters.
- `sandbox.py`: isolated render environment and bounded file/command operations.
- `static/`: browser setup, uploads, previews, job progress and connection guide.
- `deploy.py` and `deploy_modal.py`: build the current harness image, then deploy
  the hosted service with that exact image ID.

## Verification

```sh
uv run --with pytest python -m pytest video_use_mcp/tests -q
uv run --with pytest python -m pytest tests gui/tests -q
node --check video_use_mcp/static/studio.js
```

Tests cover real OAuth exchanges and MCP HTTP requests, secret privacy, account
isolation, upload rules, idempotent submission, signed download links, and restart
recovery. Live provider and Modal tests consume credits and are run separately.

Official integration references:
[OpenAI MCP authentication](https://developers.openai.com/plugins/build/auth),
[ChatGPT connection](https://developers.openai.com/plugins/deploy/connect-chatgpt),
[Claude connectors](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp),
[Modal sandboxes](https://modal.com/docs/guide/sandboxes).
