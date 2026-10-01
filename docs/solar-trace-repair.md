# Solar explainer trace repair

The September 30 browser trial requested a 30-second narrated explanation of
solar panels. The final export succeeded, but success hid an unsatisfactory
process: the first draft existed after 8 minutes 27 seconds and the first player
was displayed only after export, about 12 minutes after project creation.

## Evidence and changes

| Observed failure | Change |
| --- | --- |
| Two published drafts never displayed during creation | Task text and structured results now agree, include actual media links and a specific `display_action`. The first real player can refresh subsequent drafts/final media without another assistant display call. |
| `next_action` was added after text serialization | Serialize after all actions and context are present; test both representations. |
| Every preview was silently cut at 20 seconds | Preserve complete drafts up to 120 seconds, retain low source frame rates, and label longer excerpts explicitly. |
| A request ID shared between speech and rendering failed | Scope exact retries by owner/project/operation, retaining compatibility with existing task IDs. Different arguments in the same operation still require a new ID. |
| Missing `preview_path` rejected an already authored large step | Execute and save valid work, report publication pending, then allow a small publication-only call. Never guess a filename or pretend media exists. |
| Narration supplied paths but forced another timing probe | Return measured duration and sentence timing for both generated and cached speech. |
| Entire film authored before useful visual feedback | Compact hosted guidance favors a reusable motion excerpt before implementing the complete film, without a mandatory approval pause. Detailed references remain available on demand. |
| A circuit-only correction rerendered every chapter | Conservative source fingerprints reuse immutable unchanged chapters; changed scenes render fresh so stateful updaters cannot skip accumulated time. Dynamic source falls back to broader invalidation. |
| QA contact sheets could replace a playable draft | Frame inspection no longer publishes user-facing progress; old generic inspection entries cannot displace video. |
| Four final-review frames skipped important teaching sections | Shared encoded review samples up to twelve frames, using saved beat timings when compatible with the output. |
| Tool traces omitted newly created task IDs | Infer IDs only from verified task-shaped results; distinguish player refreshes from assistant calls. |
| Workflow catalog advertised unavailable guidance aliases | `manim-video` and `motion-design` resolve to the compact corresponding browser guides. |

Actual output inspection also found small supporting labels and a panel caption
touching the support stand. The expanded review exposes these moments and asks
the editor to judge readability at chat-player size. Sampling does not automate
art direction, certify the entire movie, or validate every factual statement.

Replaying the captured solar source locally rendered the initial three chapters
in 10.30 seconds and the exact circuit correction in 6.22 seconds, reusing the
other two chapters byte-for-byte. An exact repeat took 0.15 seconds. These are
local renderer measurements, not end-to-end Claude latency or cloud guarantees.

## Boundaries

The host assistant still writes the creative code and chooses when to call tools.
The service cannot set Claude's reasoning duration, bypass its turn limits, or
force its first player to appear without a UI-capable tool call. Once a genuine
player exists, its bounded read-only refreshes do not require model polling and
do not send synthetic user messages. Source creation remains charged to the
user's host account; rendering/storage/speech remain owner-funded.

Private reproduction files and task payloads stay in the ignored
`.pilot-latest-debug/` directory. Do not commit signed media URLs, OAuth grants,
speech credentials or the user's raw task payloads.
