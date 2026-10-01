# Solar explainer trace repair

## Run that stopped after narration

Project `e84d7555-1a82-413d-a455-9269225440ac` started at 06:57:42 UTC
on October 1. Its narration completed in 12.56 seconds; the response reached the
host at 06:58:50, followed by a successful guidance call at 06:58:54. No render
request, tool error or subsequent MCP request appears in the persisted traces
or server logs. Normal idle workspace cleanup followed at 07:04:01. This is
not evidence of a slow renderer or proof of why the host stopped making calls.
The checkpoint contains the audio and all 74 word timings. Production restore
and full audio decoding succeeded in a separate local directory without changing
the user's project.

This follow-up repairs diagnostics and continuation, without claiming to resolve
an unobserved host failure:

- Targeted trace reports retain separately labeled unassigned calls from the
  same owner/client and time window. They show tool errors even when no task
  exists, and distinguish active backend jobs from a gap in incoming requests.
  Nearby calls are context, not proof that they belong to this project.
- Tool tracing handles omitted arguments, explicit error results and failed
  task-to-project lookups. It records start time, deployed harness version and
  known guidance topics; prompts, source code and results remain excluded.
  Non-content event metadata still reaches server logs if persistence fails.
- Successful narration returns an explicit continuation with the saved audio,
  timing path and current creative revision. It asks for one meaningful short
  excerpt using the appropriate rendering technique before authoring the whole
  film. It does not regenerate speech, invent a scene, create a placeholder,
  silently trim overlong narration or add an approval checkpoint.

Claude/ChatGPT still own tool discovery, permission prompts and turn scheduling.
The server cannot start a new host turn or observe the reason a host stopped.
Protocol/auth failures before tool dispatch remain outside tool telemetry and
require server logs or the host's error text.

## Repair from the browser agent's handoff

The third solar run reached its first real player in 1m49s and exported in
about 7m19s, but its account-level handoff reported no conversational prose until
the end. It then left the opening excerpt in the player for roughly five minutes.
Server traces confirm the assembled video had `review_path` but no `preview_path`.
The final file was 960×540, not native 1080p. A negative closing-scene keyframe
caused one failed batch; only the failed scene was rerendered. The transcript's
"agent time" combines authoring, untimed calls and gaps; it is not measured model
reasoning time. Wave `phase` was already supported, despite incomplete tool docs.

This release addresses the evidence with reusable primitives and response fixes:

| Problem | Change | Boundary |
| --- | --- | --- |
| Silent assumptions and a script voiced before being shown | Hosted guidance and tool responses ask for a short proposed direction/script in chat before narration, plus a brief sentence alongside meaningful drafts | No routine approval stops; the host still controls its prose and turn scheduling |
| Agent-expanded brief looked user-specified | `start_video.assumptions`, `brief_provenance`, and `plan_provenance` distinguish proposals from stated preferences | These are provenance labels, not proof that the user approved a proposal |
| Saved choices could be missed after narration | Every task returns current creative context; admitted tasks save a revision baseline outside their retry payload | Legacy tasks without a baseline report unknown, not unchanged |
| Reviewed full film never reached the player | A step with a movie in `review_path` automatically publishes that movie when no explicit preview is supplied | Private contact sheets still cannot replace playable media |
| Hand-written scene assembly and repeated-motion math | `assemble_video` accepts ordered saved scene IDs plus optional new scene data, validates all sources first, renders at most two concurrently, mixes existing narration and publishes the full draft | Custom Manim, footage and procedural work remain available; this does not force a genre template |
| Preview resolution became final delivery | Assembly has explicit draft/final quality; final rerenders original vector/text sources on a native 1080p canvas, preserving aspect and coordinates | Explicit dimensions remain available; no blind upscaling of a draft movie |
| Eight particles required duplicated keyframes | `motion_path` expresses constant-speed paths, loops, repetition, stagger and orientation | Bounded geometry, no arbitrary expressions; open loops deliberately wrap |
| Validation error hid the three bad marks | `validate_only` and the helper's `--validate` report every invalid keyframe with scene/mark/index/value before frames render | Normal rendering validates too, so validation need not become another mandatory tool call |
| Quiet unnormalized narration | Assembly's optional `web` preset measures and normalizes narration toward −16 LUFS with a −1.5 dBTP ceiling | This is a chosen delivery preset, not a universal platform standard or a listening check |
| Label cues ignored word timings | Narration returns bounded inline word timings as well as sentences, duration and timing-file path | Timing data does not establish semantic A/V agreement |
| Alternative voice offered without support | Optional public voice discovery and an explicit `voice_id`; narration reports the selected voice and caches by voice plus text | Host-private voice libraries are not listed; no cloning or audition UI |
| Root-level narration missing from source archive | Checkpoint/restore preserve generated workspace-relative audio, timings, fonts and source while excluding uploaded-source duplicates and render caches | Existing archives cannot recover files they never included |

Assembly caches compare source, output format and renderer fingerprints; identical
assemblies reuse scene renders, while changed scenes render again. A standalone
opening excerpt is not yet seeded into this cache. Narration that exceeds the
assembled timeline is rejected instead of silently trimmed. Successful timings
are measured on the output frame grid and bound to its encoded hash; rough story
beats remain a separate proposal.

Local verification includes a four-second 1080p/30fps loop-and-wave proof from
1,475 input bytes, repeated seek checks, all-mark validation, native-resolution
assembly, complete decoding, narration-level measurement, cache invalidation,
archive round trips, current-choice propagation and response-surface parity.
The loop proof rendered in 13.85s locally; this is not a Claude end-to-end latency
claim. Isolated live acceptance results are recorded in the ignored
`.pilot-handoff-fixes/live/` directory.

Still unresolved by automation: factual research, artistic judgment, full motion
and listening review, and whether the host assistant actually follows the chat
guidance. Do not label sampled frames as a complete playback review. Essential
content clipping is a layout defect; intentional edge bleed is not automatically
a defect. The user's existing solar export is retained unchanged for comparison.

Provider references: [public voice discovery](https://elevenlabs.io/docs/api-reference/voices/search)
and [FFmpeg loudness normalization](https://ffmpeg.org/ffmpeg-filters.html#loudnorm).

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
