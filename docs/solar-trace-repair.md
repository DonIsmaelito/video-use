# Solar explainer trace repair

## Follow-up after the second solar run

The next trial reached its first player at 8m47s and final export at 10m04s.
The excerpt itself rendered in 13.3 seconds: Claude still spent 7m26s after
narration authoring all six scenes before submitting it. The user's transcript
confirmed that rendering less did not mean authoring less. There were no tool
errors, and the open player refreshed subsequent media successfully.

The next implementation adds:

- `render_video_scene`: compact editable 2D drawing/keyframe data renders,
  encodes and publishes through the existing private task runner. The host still
  supplies all creative decisions; no backend model or fixed scene template.
  Custom Manim, browser code, footage and 3D remain available. Scene JSON and
  runtime source persist in the ordinary editable archive.
- Shorter guidance discovery: a compact overview first, with technique references
  offered on demand rather than loading the complete workflow catalog each time.
- `production_timing`: actual ordered scene lengths and optional narration
  offset persist separately from rough creative beats. Encoded duration and hash
  are checked; review uses matching timing. Internal boundaries are reported by
  the editor, not independently inferred from speech. Failed work cannot overwrite
  successful saved timing.
- Player feedback: **Suggest an edit** captures the viewed time and exact media
  object. Explicit submission saves the note, updates creative revision and, when
  supported, informs the host. A replacement draft waits while a note is being
  written. No background messages or forced approval stops.
- Review findings: explicitly acknowledged unresolved meaning, correctness,
  layout or audio defects prevent publication. Optional style preferences do not.
  Findings survive retries/rerenders until explicitly resolved. This records the
  editor's assessment; it is not automated fact checking.
- Encoded audio evidence: bounded loudness, peak, silence, duration and stream
  timing measurements. Missing audio, partial coverage and analysis failure are
  explicit. Measurements do not prove listening quality or semantic alignment.

Local proofs cover a five-second diagram (3,249 input bytes; 7.08-second render)
and a four-second portrait typography composition (1,442 input bytes). These
measure renderer execution, not end-to-end Claude latency. Encoded output and
readable hold frames were inspected; a pale proof label was corrected. Text that
autofits below 12 pixels reports a warning. Exact scene retries are stable across
Python process hash seeds.

The larger wishlist—editable script/storyboard cards, voice auditions, a complete
timeline editor, automatic cut review, professional timeline interchange and
one-click format variants—is not implied by these changes. Existing versioned
exports and general editing primitives remain available. New browser conversations
still need account-level acceptance by the owner.

## First trial

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
| A long sequence of internal updates could evict the only draft | Keep the latest authored preview independently of the bounded event history. |
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

An additional encoded regression confirmed that changing shared Manim class
defaults can affect later scenes. Such source uses whole-file invalidation;
reusing an apparently unchanged later scene would otherwise preserve stale colors.

Live MCP verification replayed the actual 30.07-second export in a separate
diagnostic project. Complete preview playback and attachment download, generated
and cached narration timing, cross-operation request IDs, exact retries,
publication-only recovery, twelve-frame review, and player refresh to the final
export all passed. The diagnostic workspace was closed. This verifies service
behavior; it does not substitute for a fresh Claude/ChatGPT creative conversation.

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
