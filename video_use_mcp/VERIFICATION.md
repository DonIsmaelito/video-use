# Verification record

Verified on September 20, 2026, on the `video-use-mcp` branch.

## Automated checks

- Existing harness and GUI: 254 Python tests passed, one skipped, 46 subtests passed.
- Existing motion runtime: 40 Node tests passed.
- MCP service: 20 tests passed. These exercise actual OAuth/PKCE and MCP HTTP
  requests, scope enforcement, account isolation, encrypted credential storage,
  upload limits, idempotent jobs, cancellation, failure cleanup, download expiry,
  provider tool/image protocols, and a mandatory model turn for final frame review.
- Python Ruff checks and JavaScript syntax checks passed.

## Hosted execution

All three completed jobs used `openai/gpt-6-astra` through the owner's OpenRouter
key. They ran the checked-out harness in isolated Modal sandboxes, rather than
using a stub renderer. The coordinator used MCP SDK 1.30.0 and Modal SDK 1.5.5.

| Scenario | Entry point | Verified result |
| --- | --- | --- |
| Original launch film | Authenticated MCP client | 8.000 s, 1920×1080, 30 fps H.264, silent; original typography animation; nine images reviewed by the worker |
| Focused revision | MCP, same project ID | 10.000 s; restored source, changed tagline to “Create. Edit. Repeat.”, extended final hold; four images reviewed |
| Uploaded-media edit | Public studio in Chrome | Real MP4 upload; 9.000 s, 1080×1920; preserved landscape footage, generated narration and timed captions; five images reviewed |

Each delivered MP4 passed a separate full FFmpeg decode after download. Output
frames were visually inspected. Each editable ZIP was downloaded and inspected;
the revised source contains the requested new tagline.

The upload/edit job called both ElevenLabs narration and transcription. The
transcript matches the requested spoken words. Encoded audio measured -18.71 LUFS
and -1.48 dBTP. Audio evaluation used transcription and signal measurements;
it did not include a listening review.

The original, revision and upload/edit jobs reported 605,146, 242,816 and 324,640
cumulative model tokens respectively. These include repeatedly sent context and
are not dollar charges; provider caching and output-token rates affect billing.

## Browser and client checks

- Desktop and mobile signup, project creation, settings and connection guide:
  no JavaScript errors and no horizontal overflow at a 390 px viewport.
- Hosted Chrome session: login, real media upload and job submission succeeded.
- After the final service restart, both delivered formats loaded and played in
  Chrome; mobile layout still had no horizontal overflow or JavaScript errors.
- OAuth access, saved provider settings, projects and outputs survived redeploy;
  MP4 byte-range streaming returned HTTP 206 with the requested bytes.
- A deliberately delayed project-list response could not replace a newly
  created project or send its upload to another project after the fix.
- A live MCP SDK client completed dynamic registration, consent, PKCE exchange,
  initialization, tool discovery and production calls over the public endpoint.
- Claude Code's HTTP connection was registered locally for this checkout.

ChatGPT and Claude web account-level connection flows were not exercised in
signed-in accounts. Their current official connection requirements informed the
implementation; users still complete OAuth in their chosen client. Public
directory submission is separate.

## Problems caught during validation

Live checks exposed and resolved remote asset-path resolution, worker image
handoff, mixing Modal filesystem APIs, and delayed browser-response races.
An early run exhausted available provider credit. Lower-cost model trials
reached the configured token limit while iterating; those were not reported as
successful deliveries. After credit was replenished, all three quality-model
scenarios above completed. Budget feedback now encourages final delivery before
the limit, and errors distinguish insufficient credit from temporary rate limits.

This is a tested pilot, not a guarantee that every creative brief will succeed.
The deployment retains one coordinator and one SQLite writer. Its scaling and
operating limits are documented in [README.md](README.md).
