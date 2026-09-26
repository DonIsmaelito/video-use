# Jev fast components: where a 0.2 s classifier fits in video-use

Branch `experiment/jev-fast-components`, study date 2026-09-25. Jev is TypeSafe's System One:
text-only state plus typed questions (`choice`, `noul`, `score`), ~0.15-0.4 s and ~$0.00002 per
call, no system prompt, no images, no text generation, weak on many-way choices (needs a
probability-plus-margin gate). Reference client: `~/Developer/jev-computer-use/jev-cu/jev_cu/jev_client.py`.

Trace study material lives in `~/Movies/video-use-tests/jev-trace-study/` (condensed transcripts,
observer exports, `condense.py`).

## TL;DR

- Across seven full Jensen keynote-to-TikTok runs, the LLM spent 9% of its time choosing the moment
  and 65-80% on plumbing: waiting on renders (32%), inspecting frames (16%), writing EDL/scripts (15%),
  re-reading SKILL.md and helper source (12%). A 15-20 minute run has about 10 editorial generations
  and about 57 reading/polling/verifying generations.
- The editorial micro-decisions (is this answer-unit standalone, is the hook early, does it end on a
  punchline, is this gap a safe cut, is this phrase a false start, keep the laugh, caption style) are
  all text-only yes/no or short-choice judgments made from the packed transcript. That is Jev's
  natural territory, and running it per unit over the whole transcript gives full coverage where the
  LLM used keyword grep and read 12% of the file.
- The three edge defects that forced re-renders (a 20 ms word leak, an "indus-" fragment, an "Oh"
  interjection) were all detectable from word JSON before rendering. Rule first, classifier second.
- In the fast motion-design lane the agent never looked at a single image; every "visual review" came
  from measured layout rectangles, lint output or its own code. Those judgments (real collision vs
  bounding-box artifact, is this warning fatal, render now or wait for QC, is this hold intentional)
  are already text and map directly onto Jev questions.
- Verification is mostly deterministic (ffprobe, loudness, decode, SRT stats, frame counts). Jev's
  role there is one gate over the text QC report ("is any of this a real blocker") plus the
  interpretation calls (traceback is a sampler artifact vs a media failure).
- What must stay with a vision-capable LLM: who is on camera at a cut, material/lighting quality,
  caption readability at phone size, anything the trace decided from pixels with no text proxy.

## 1. What was studied

| Type | Source | Runs | Model |
|---|---|---|---|
| Raw speech footage to clip | Codex benchmark rollouts (`~/.codex/sessions/2026/08/30`), 103-minute Jensen interview | 7 (4 completed) | gpt-5.6-sol high |
| Same task, other harness | `~/Downloads/harness-q1/notes.md`, recovered lane summaries | 4 lanes | sol, luna, terra, 5.4-mini |
| Motion design (fast runtime) | Observer sqlite `~/Developer/video-use-fast-runtime/evidence/*.sqlite3` | paper airplane, ball-to-sun, seed-to-tree, Stratum film, plus 17 more | gpt-6-astra low |
| Motion design (authored films) | Codex sessions 2026-09-13 (HiggsField study; Jelly Chair, Optical, Blood Orange, Zipper) | 2 | Codex |
| Motion design (collection) | `~/Movies/Motion Design Collection 2026-09-16/edit/Projects/*/{brief,review}.md` | 24 scenes | local |
| Narrated explainer | Claude lane transcripts (jet engine 150 calls, hash map 65 calls), observer Cache run, hardware-accelerators project.md | 4 | fable, opus, astra |

Lost: `~/Movies/video-use-tests/` (harness runs, Jensen source and Scribe transcript, benchmark
workspaces) was deleted before this study. No word-level transcript survives on disk, so the first
raw-footage experiment needs new long footage transcribed once (ElevenLabs key is in `.env`).

## 2. Video types and their unique components

| Type | Unique components (from routing table and showcase) | Where Jev fits | Where it does not |
|---|---|---|---|
| Raw speech footage to clip (keynote, interview, tutorial, travel) | transcript packing, moment selection, cut boundaries, dead air and filler removal, captions, vertical reframe, text QC | per-phrase and per-unit judgments, pairwise ranking, caption style, QC gate | who is on camera, framing bugs, caption legibility |
| Music-led cinematic and fight edits (Topuria, Peso Pluma, motivational) | footage sourcing, track scan and beat grid, anchor frames, speed ramps, tint, flash, letterbox | candidate relevance from title/channel/duration text, keep-searching decisions, treatment consistency checks over numbers | impact-frame detection, rendered-vs-real footage, beat alignment is arithmetic not classification |
| Narrated explainer (Manim + footage + diagrams) | script, TTS and alignment, chapters, layout manifest QC, sourcing gates, preflight, self-eval | needs-footage routing, narration-fits, continue-sourcing, boundary continuity from diffs, stream-spec gate, re-render decision | label clipping under zoom, transient labels not in manifest, clip in-points |
| Motion design (typography, 3D, illustrated) | creative contract, renderer choice, authoring, render-environment bring-up, lint and layout QC, proof frames, repair, packaging | check gate, failure-class router, lint triage, collision adjudication, render-now gate, warning fatality, delivery readiness, intentional-hold check | material, lighting, reflection, composition taste, asset sufficiency |
| Tech brief, screen-recording polish, video-generation footage | not studied (no traces on disk) | likely the same QC and routing gates | |

## 3. Measured time budget

Seven Jensen runs, every minute attributed to the phase of the next tool call
(`~/.codex/sessions/2026/08/30`, computed from item timestamps):

| Phase | Calls | Tool time | Model time | Share |
|---|---|---|---|---|
| Waiting on ffmpeg render (`write_stdin` polls) | 76 | 22.5 min | 4.7 min | 32% |
| Inspecting frames (`timeline_view`, `view_image`, single frames) | 76 | 2.9 min | 10.6 min | 16% |
| Writing EDL, scripts, plan (`apply_patch`, `update_plan`) | 28 | 0.1 min | 12.5 min | 15% |
| Reading SKILL.md and helper source | 53 | 1.0 min | 9.1 min | 12% |
| Reading transcript and selecting the moment | 35 | 0.3 min | 7.8 min | 9% |
| Text-only verification (ffprobe, loudness, SRT, decode) | 26 | 2.3 min | 4.8 min | 8% |
| Environment probes and other | 19 | 0.1 min | 4.3 min | 5% |

Completed runs took 13-18 minutes wall; the other harness measured 24-37 minutes per lane for a
one-minute clip, "dominated by agent turns not by rendering". Fast-runtime motion-design runs took
8.8-9.2 minutes wall with roughly 85 s of environment bring-up, 100 s of authoring, 2 minutes of render
waits, 75 s of repair-loop interpretation and 110 s of packaging.

## 4. Type 1: raw footage to postable clip

### 4.1 Phase map as it actually ran (five completed or near-completed Jensen runs, T1-T5)

| Phase | What happened | Calls (T1 / T2 / T3 / T4 / T5) |
|---|---|---|
| Context load | SKILL.md in two `sed` calls, then 400-700 lines of `render.py` (T3 also `captions.py`, `visuals.py`; T5 `grade.py --list-presets`) | 5 / 6 / 7 / 6 / 7 |
| Inventory | file list, `ffprobe` source (854x480, 29.97 fps, 6192 s), `pack_transcripts.py` (1,639 phrases, ~35k tokens packed) | 2 / 1 / 2 / 2 / 2 |
| Transcript reading | no run read the whole packed file. T1: head 80 lines + `rg` of 25 keywords + four `sed` windows (~12% of file). T2: own `jq/awk` regrouping + keyword `rg`. T3: first 120 lines only. T4: truncated full dump + `rg` + `jq` word window. T5: one window + `rg -C 8` | 4 / 4 / 1 / 4 / 2 |
| Candidate drill | `timeline_view` filmstrips and single frames of 1-3 candidate windows, viewed as images | 4 / 4 / 3 / 2 / 1 |
| EDL authoring + text validation | word-boundary ranges, `jq` sums, boundary scripts | 4 / 0 / 2 / 5 / 2 |
| Environment probes + custom tooling | `ffmpeg -filters` (no `subtitles` filter), fonts, PIL; T1 wrote `render_vertical.sh` + `build_graphics.py`, T2 `verticalize.py`, each with two failed starts | 8 / 8 / 0 / 0 / 0 |
| Render + polling | `render.py --preview` or own pipeline, then `write_stdin` yields every 30 s | 12 / 19 / 25 / 13 / 25 |
| Fix after QC | patches | 0 / 0 / 2 / 1 / 3 |
| Verification | ffprobe, segment sums, decode, loudness, SRT parse, frame views | 13 / 11 / 17 / 16 / 7 |
| Persist | project.md, copies, shasum | 4 / 2 / 1 / 1 / 1 |

Moments picked across five runs plus three harness lanes: seven distinct ones (electrons-to-tokens
4x, plumbers/radiologists 3x, AI job-vs-task 3x, CPU vs F1, agents, NVIDIA-without-AI, bottleneck).
Selection language: "strong standalone", "self-contained answer", "strong hook and complete payoff",
"surprising claim", "humorous", "clean speech boundaries". Cut edges were always Scribe word
boundaries plus 30-80 ms padding; T1 and T4 removed internal silences of 0.87-2.37 s and an
opening false start; T2, T3 and T5 used single continuous ranges. Reframe was always a blurred
1080x1920 canvas with the full 16:9 frame as a sharp strip (the other harness's sol and terra lanes
cropped tight on the speaker instead).

### 4.2 Decision inventory

Jev fit: YES = closed-set or yes/no from text state available at that moment. MAYBE = needs a text
proxy. NO = pixels, generative, or deterministic code (no classifier needed).

| # | Phase | Decision | Text state at that moment | How the traces decided it | Set | Jev | Why |
|---|---|---|---|---|---|---|---|
| 1 | Context | Does the prompt already authorize autonomous execution? | prompt + Hard Rule 11 | T2 asked three times then self-approved; others posted `needs_approval` | noul | YES | text judgment; T2 burned 4 turns |
| 2 | Context | Read helper source or trust a schema? | SKILL.md | every run read 400-700 lines of `render.py` | policy | NO | give a schema card instead |
| 3 | Inventory | Is the cached transcript valid word-level Scribe? | `jq '.words[0:8]'` | "valid word-level data" | noul | NO | deterministic schema check |
| 4 | Inventory | Which speaker is the guest? | words per speaker, sample phrases | implicit | choice(2) | YES | or deterministic: most words |
| 5 | Inventory | Canvas fit: blur-canvas full frame vs crop to speaker | ffprobe 854x480 | T4 "low-resolution 16:9, preserve framing"; lanes 1/3 cropped | choice(3) | YES | resolution drives it; "is the speaker centered" is pixels |
| 6 | Transcript | Which keywords to grep | none | model-invented 20-25 terms | open | NO | replaced by per-unit scoring |
| 7 | Transcript | Which windows of the packed file to read | line count | T1 four windows; T3 first 120 lines | open | NO | coverage problem, not classification |
| 8 | Selection | Is this answer-unit a standalone postable moment? | unit phrases + preceding host phrase | "self-contained answer", "strong standalone clip" | noul | YES | text per candidate |
| 9 | Selection | Is the hook inside the first 2-5 s? | first two phrases | T4 opens on "Plumbers"; T1 removed the false start to reach the hook | score | YES | time-to-first-claim is text |
| 10 | Selection | Does the unit end on a complete thought or punchline? | last phrases + next host phrase | T4 "end on 'Guess what we're short of? Radiologists.'" | noul | YES | text |
| 11 | Selection | Which of two candidates is stronger? | two unit summaries | T1 picked jobs over plumbers after viewing both filmstrips | choice(2) | YES | pairwise with margin gate |
| 12 | Selection | Which of N candidates (N >= 3) | | T2 "narrowing to the cleanest one or two" then shipped all three | choice(N) | MAYBE | reduce to a tournament of #11 |
| 13 | Selection | How many clips to make | task text, units passing the bar | 1, 1, 2, 3, 3 | choice(1-3) | MAYBE | better as per-unit "adds a distinct idea" |
| 14 | Selection | Include the host's question as lead-in? | host phrase + guest first phrase | T4 kept "Which is?"; T3 dropped it | noul | YES | text |
| 15 | Selection | Does the trimmed excerpt stand alone? | unit text | "standalone ideas" | noul | YES | #8 asked of the trimmed range |
| 16 | Boundaries | Which word does the clip open on? | word JSON near start | T3 "first clean silence at 32.08s" | choice(<=5) | YES | short list of first phrases |
| 17 | Boundaries | Which word does it end on? | word JSON near end | T5 end 834.19; T4 "Radiologists." | choice(<=5) | YES | |
| 18 | Boundaries | Padding values | Hard Rule 7 | 50/30-80 ms | numeric | NO | constant |
| 19 | Boundaries | Is this silence gap a safe internal cut? | gap length, words either side, speaker | T1 cut ten 0.87-2.37 s gaps; T4 "clean pauses" | noul | YES | text per gap |
| 20 | Boundaries | Is this phrase a filler, false start or repetition? | phrase text ("Uh, we, we, uh, built up...") | T1 "opening false start" | noul | YES | text per phrase |
| 21 | Boundaries | Keep the laugh or reaction after the punchline? | `(laughs)` token, host reaction phrase | T4 "preserve the laugh" | noul | YES | text |
| 22 | Boundaries | Does another speaker's token sit inside the padded edge? | word JSON with speaker_id | T3 (20 ms overlap), T5 ("indus-", "Oh") found from rendered frames | noul | NO | deterministic overlap test; never reach a classifier |
| 23 | Boundaries | Is a leaked token harmful or ignorable? | token text + overlap ms | T3 and T5 tightened | noul | YES | only if #22 is not a hard rule |
| 24 | Boundaries | Does a cut fall inside a word? | EDL + word JSON | T4 script caught "start 790.72 cuts in[side]" | noul | NO | deterministic (Hard Rule 6) |
| 25 | Boundaries | Is total duration within 20-90 s? | EDL arithmetic | jq/awk sums | noul | NO | arithmetic |
| 26 | Boundaries | Keep the tail camera change? | none (14 frames) | T4 "intentional reaction angle, retaining it" (5 calls) | noul | NO | pixel-only |
| 27 | Captions | Chunk size (2 / 3 / 4-7 words) | words per second, sentence length, tone | T1 2-3 words; T3 sentence-case; lane 4 tiny | choice(3) | YES | SKILL's own criteria are text |
| 28 | Captions | Case | same | T3 sentence; lane 1 upper | choice(2) | YES | |
| 29 | Captions | Vertical position | canvas spec | "TikTok-safe", "mid frame", "bottom edge" | choice(3) | YES | closed set |
| 30 | Captions | Font size and stroke | canvas height | lane 4 "tiny" | score | MAYBE | better a deterministic cap-height ratio |
| 31 | Captions | Renderer (libass / drawtext / PIL) | `ffmpeg -filters` | T1 four probes, T2 five probes + two failed renders | choice | NO | deterministic env probe |
| 32 | Captions | Add a title label, and its text | unit summary | T1 "compact AI-and-jobs headline"; T3 none | noul + open | YES / NO | yes/no is Jev; text is generative |
| 33 | Layout | Punch-in to mask an intra-speaker jump cut? | same speaker both sides, gap length | T1 "restrained punch-ins" | noul | MAYBE | proxy exists; effect unverified |
| 34 | Layout | Does the crop follow the speaker / who is on camera at the cut? | none | T2 frame grabs of Jensen vs host | noul | NO | pixels |
| 35 | Layout | Grade preset | `grade.py --list-presets` | "subtle contrast", "neutral" | choice(3) | YES | trivial |
| 36 | Render | Preview first or final directly | | mixed | policy | NO | constant |
| 37 | Render | Poll cadence | | 10 s vs 30 s | numeric | NO | harness should block |
| 38 | Render | Re-render after a fix? | fix type | T1 recomposited captions only; T3 full | noul | NO | deterministic by fix type |
| 39 | Verify | Is ffprobe JSON a pass? | JSON | 1080x1920/h264/aac | noul | NO | deterministic vs task validation block |
| 40 | Verify | Is loudness a pass? | "I: -14.0 LUFS Peak: -0.9" | | noul | NO | threshold |
| 41 | Verify | Is caption drift acceptable? | segment sums vs EDL (124 ms) | T1 rebuilt SRT | noul | NO | threshold; rebuild is cheap |
| 42 | Verify | Is a traceback a media failure or a sampler artifact? | traceback text | T3 "a QC sampling adjustment, not a media failure" | noul | YES | text |
| 43 | Verify | Are cut boundaries visually clean, no waveform spike? | none (PNGs) | T1 "all 10 cut boundaries are visually clean" | noul | NO | pixels; no proxy used |
| 44 | Verify | Captions readable, framing centered? | none | T3 x=0.5 bug | noul | NO | pixels |
| 45 | Verify | Does the ending feel intentional? | last cue text | T3 | noul | MAYBE | proxy = last cue ends a sentence (#10) |
| 46 | Verify | Stop verifying now? | checklist of text results | T1 one pass; SKILL caps at 3 | noul | YES | aggregate of text checks |
| 47 | Deliver | File names, project.md, summary | | generative | open | NO | LLM |

### 4.3 Verification checks and whether text alone decided them

| Check | Text returned | Conclusion | Text-derivable? |
|---|---|---|---|
| `ffprobe` source | 854x480, 30000/1001, aac, 6192 s | "103-minute interview" | yes |
| `pack_transcripts.py` | "1639 phrases" | | yes |
| `jq` speaker counts | `speaker_0: 5356` | host vs guest | yes |
| `timeline_view` candidate filmstrips | only a saved path | "two-shot setup", "holds on close-up after the cut" | no |
| `jq` word windows | start end text type speaker | exact edge times | yes |
| EDL arithmetic | declared 62.671 = calculated, 11 ranges | in range | yes |
| T4 boundary script | "segment 1 start 790.72 cuts in..." | fixed before render | yes |
| `ffmpeg -filters` | "Unknown filter 'subtitles'" | switch to PIL | yes |
| render stdout / exit codes | "extracting 10 segment(s)", exit 1 / 234 | retry after patch | yes |
| `ffprobe` outputs | 1080x1920 h264, aac 48k, durations | pass | yes |
| cumulative segment durations | "7 50.117 / 8 51.218" | 124 ms drift, rebuild SRT | yes |
| decode `-f null` | empty stderr | decodes clean | yes |
| loudness (`loudnorm` json, `ebur128`, `volumedetect`) | numbers | -14 LUFS | yes |
| `blackdetect` | none | no black frames | yes |
| SRT parse | cues, first/last, monotonic | valid; "no interviewer word leakage" | yes |
| rendered-frame views (6-25 per run) | none | T1 "clean"; T3 offset bug; T3 20 ms leak; T5 fragments; T4 "end-frame flash" | mostly no; the word-leak findings were derivable from word JSON + EDL |
| T4 tail investigation (`-read_intervals`, 14 frames) | PTS list + images | keep reaction angle | no (5 calls) |
| audio excerpt (T4 mp3 to base64) | "[omitted]" | nothing; model cannot hear | wasted call |

### 4.4 Proposed fast pipeline

Deterministic prep, no model: `ffprobe`; `pack_transcripts.py`; guest = speaker with most words;
split guest speech into answer-units (runs of guest phrases between host phrases, host phrase attached
as `question`; roughly 150-250 units per 100 minutes); per unit compute `duration_s`, words per
second, gaps >= 0.4 s, filler count, `(laughs)` tokens. Then Jev in batch over every unit, the LLM
only for the EDL JSON, label text and summary, `render.py` blocking, a deterministic QC report, one
Jev gate, one optional contact sheet for the LLM.

| # | Question | State | Type and criteria | Gate | Fires | Replaces (grounding) |
|---|---|---|---|---|---|---|
| 1 | `unit.standalone` | question, text head 400 chars, tail 200, duration | noul "a viewer who has heard nothing before this would understand it" | p >= 0.7 | every unit | keyword grep + window reads ("strong standalone clip") |
| 2 | `unit.hook` | first two phrases, seconds to first claim | score 0-10: 0 generic setup, 5 interesting claim, 10 surprising/funny/quotable first line | keep top 8 | every unit | T4 "surprising claim that the bottleneck is plumbers" |
| 3 | `unit.payoff` | last three phrases, next host phrase | noul "ends on a complete thought or punchline" | p >= 0.7 | every unit | T4 "end on 'Radiologists.'" |
| 4 | `pair.stronger` | A and B: hook line, one-line summary, duration | choice [A, B] "more postable TikTok moment" | margin >= 0.2 else escalate pair to LLM | tournament over top 8 | T1 jobs over plumbers; T2 "narrowing to the cleanest" |
| 5 | `unit.ship` | summary, rank, summaries already selected | noul "adds a distinct idea not covered by selected clips" | p >= 0.6, cap 3 | after ranking | clip-count decision (T2 asked the user) |
| 6 | `unit.include_question` | host phrase, guest first phrase | noul "the answer needs the question to make sense" | | per selected unit | T4 kept "Which is?", T3 dropped it |
| 7 | `gap.safe_cut` | gap s, five words before/after, same speaker, filler adjacent | noul "removing this gap leaves a natural sentence" | p >= 0.75; 150-400 ms gaps with mid p go to LLM | per internal silence >= 0.4 s | T1's ten cuts, T4 "clean pauses" |
| 8 | `phrase.disposable` | phrase, prev, next, speaker | noul "false start, filler-only or verbatim repetition" | p >= 0.8 | per phrase in selected units | T1 "opening false start" |
| 9 | `edge.keep_reaction` | punchline, reaction token, reaction s | noul "extend past the punchline to include this reaction" | | per end boundary with `(laughs)` or <= 1 s host reaction | T4 "preserve the laugh". Foreign-speaker fragments are excluded deterministically first (would have removed T3's and T5's fix loops) |
| 10 | `clip.caption_style` | wps, mean sentence length, hook score, duration | choice [2-word UPPER bold-overlay mid-lower, 3-word upper, 4-7-word sentence-case lower safe area] | p >= 0.5 else option 2 | per clip | lane 1 vs lane 4; SKILL bold-overlay vs natural-sentence |
| 11 | `cut.punch_in` | gap s, same speaker, s since last punch-in | noul "mask this jump cut with a 1.08x punch-in" | | per internal cut | T1 "restrained punch-ins" (visual payoff unverified) |
| 12 | `qc.blocker` | ffprobe summary, LUFS, peak, decode stderr, SRT stats, edge overlaps, drift ms, tracebacks | noul "contains a defect that must be fixed before delivery, not a tooling artifact" | p >= 0.6 to LLM, else ship | after render | T3 "not a media failure"; T1 124 ms drift |

Expected effect: LLM generations drop from about 67 to about 4-6 per clip and wall time becomes
render-bound (2-4 minutes for preview plus final) against 13-33 minutes observed. Roughly 200 units
times 3 questions is about 600 Jev calls, about $0.012, seconds when batched.

## 5. Type 2: motion design

### 5.1 Phase map (fast runtime, paper airplane; ball-to-sun and Codex deltas noted)

| # | Phase | Calls | Wall | Loops | Evidence |
|---|---|---|---|---|---|
| 1 | Orientation | 7 (18%) | ~20 s | 1 | SKILL.md, routing, motion-design, layout-qc refs; `motion_slot.py init`; `render --help`. Identical prologue in the ball run |
| 2 | Creative contract | 0 | ~5 s | 1 | one message ("cream paper sheet folding into a plane... coral, blue, yellow doorways... text-free"). No library or reference lookup, no hero-still comparison in either fast run |
| 3 | Authoring | 4 (10%) | ~100 s | 1 | one heredoc `index.html` (SVG + GSAP + motion-kit); `npm install` alongside |
| 4 | Render-environment bring-up | 10 (26%) | ~85 s | 3 (ball: 4) | "Failed to download chrome-headless-shell... no zip archiver" -> `npm install yauzl`; "Chrome cannot launch (missing libnspr4, libnss3)" -> `apt-get download` + `dpkg-deb -x` + `LD_LIBRARY_PATH` |
| 5 | First render + check + live preview | 4 (10%) | ~95 s | 1 | render 33.8 s; check "Layout 0 issues across 9 sample(s)" |
| 6 | Review | 1 (3%) | ~20 s | 1 | "plane silhouette and doorway depth read clearly" plus an `ffmpeg -ss 7.3` still that was never read back |
| 7 | Repair loop (measured-layout QC) | 5 (13%) | ~75 s | 2 | `measure.cjs` dumps rects for 360 frames -> `layout_qc.py` "paperBody and spark overlap at 10.700s" -> move spark -> "passed: 360 frame(s), 1065 elements". One engine render started before QC passed and was wasted |
| 8 | Packaging, final render, technical QA | 8 (21%) | ~110 s | 1 | EDL v2, final render, `check`, `publish.py`, `render.py` ("loudnorm measurement failed, falling back to 1-pass"), ffprobe |

Ball run: two failed render starts, one design repair (SVG pivot offset; tween `.7` to `.699` to
clear a lint overlap), seven attempts at the measurement script (Code 127 x3, wrong manifest path,
`waitForFunction` hang x2), and QC passed only after the allow-list was widened. The 409 warnings in
that trace are observer-side file watches the agent never saw. Codex sessions add real phases:
library search (`motion_library.py search soft|contact|pinterest|HDRI`), hero and component proof
stills viewed before the full render, a control-variant render, `motion_qa.py` contact sheets and
independent critic passes; repair cycles per film 1-3.

Key finding: in both observer runs the only tool item types are `agentMessage`, `commandExecution`,
`reasoning`. No image was ever viewed. Every fast-lane "review" came from code, `check` text or
measured rectangles.

### 5.2 Decision inventory

| # | Phase | Decision | State at that moment | How decided | Set | Jev | Why |
|---|---|---|---|---|---|---|---|
| 1 | 1 | Which references to read | prompt + SKILL index | reasoning | closed | YES | fixed prologue; gain nil |
| 2 | 1 | Renderer: HTML+SVG+GSAP vs Three.js vs Manim vs Remotion | prompt, skill's 4-option list | "2.5D SVG folding scene" | choice(4) | YES | prompt text alone |
| 3 | 1 | Slot name, 1920x1080, 30 fps, duration | prompt | copied | closed | YES (trivial) | |
| 4 | 2 | Palette | prompt | reasoning | open | NO | generative |
| 5 | 2 | Text-free / wordless | prompt | identical in both runs | binary | YES | "prompt implies on-screen copy?" |
| 6 | 2 | Beat structure | prompt | reasoning | open | NO | authoring |
| 7 | 2 | Write a project.md contract or not | none | inconsistent between runs | binary | YES | should be a rule |
| 8 | 2 | Skip library/reference lookup | skill: "when the concept needs precedents" | fast runs never searched; Codex did | binary | MAYBE | noul on prompt |
| 9 | 3 | Post a progress message now | elapsed time, stage | "Limiting update frequency" | binary | YES | cadence rule |
| 10 | 4 | Is `check`'s "Runtime 1 error(s)" blocking? | check text | reasoning | binary | YES | env vs design class from stderr |
| 11 | 4 | Fix for missing unzip -> `npm install yauzl` | error text | reasoning | open-ish | MAYBE | choice among install options |
| 12 | 4 | Fix for missing libs (apt-get download, dpkg-deb, LD_LIBRARY_PATH) | .so names | reasoning | open | NO | generative shell work; only the classification is Jev |
| 13 | 4 | Draft quality and workers | help text, "Estimating render duration" | reasoning | closed | YES | choice from duration/frames/cores |
| 14 | 4 | Ignore "[WARN] 6 capture workers may exceed V8 heap" | render log | ignored | binary | YES | warning fatal? |
| 15 | 4 | Continue render despite lint warning | "overlapping_gsap_tweens on #hero y at 3.65s" | tool default, fixed later | binary | YES | fix-now vs fix-later by lint class |
| 16 | 5 | Is "Check passed / Layout 0 issues across 9 samples" enough for a draft? | check text | reasoning | binary | YES | gate on counts |
| 17 | 5 | Publish 720p live preview | file exists | rule-like | binary | YES | |
| 18 | 5 | Run check and render concurrently | none | reasoning | binary | YES | |
| 19 | 6 | Which time to extract as review still (7.3 s) | beat times in own code | reasoning | closed | MAYBE | per-beat "worth a proof frame?"; still never consumed |
| 20 | 6 | "Silhouette and doorway depth read clearly" | code + check text | reasoning, no pixels | binary | MAYBE | text-only in trace but hollow: no proxy carried silhouette info |
| 21 | 7 | "Small overlap between plane and yellow doorway in the ending pose" | own coords `translate(1740 360)` | reasoning from source before QC | binary | MAYBE | QC later confirmed; a Jev pass over rects at beat ends replaces it |
| 22 | 7 | Which elements to measure | DOM ids | reasoning | closed | YES | per id: hero/accent element? |
| 23 | 7 | Is "paperBody and spark overlap at 10.700s" a real defect? | rects for frames 321/359 | yes, moved spark | binary | YES | rect text + brief |
| 24 | 7 | Is "#disk and #ray1..#ray7 overlap at 7.400s" real? (ball) | rects, "settled ray inner edge is 166.875px from center" | bbox artifact, widened allow-list | binary | YES | text judgment; risk of rationalising |
| 25 | 7 | Re-run measurement after "Cannot find module measure.cjs" | stderr | "Correcting execution root path" | binary | YES | error class: path vs code |
| 26 | 7 | Start engine render before QC passes (wasted 33.8 s) | QC status failed | reasoning | binary | YES | gate "render now?" on QC pass |
| 27 | 7 | Re-render after source edit | source changed since render | reasoning | binary | YES | hash compare; the collection does it mechanically |
| 28 | 7 | Which GSAP fix (svgOrigin, .699, scale contact) | code | reasoning | open | NO | authoring |
| 29 | 7 | Give up on measure.cjs vs keep trying (7 attempts) | stderr stream | reasoning | binary | YES | "same failure class as last attempt?" |
| 30 | 8 | EDL v2 vs v3, task_context fields | skill docs | reasoning | closed | YES (trivial) | |
| 31 | 8 | Is "loudnorm measurement failed" fatal for a silent piece? | log tail, audioCount 0 | benign | binary | YES | |
| 32 | 8 | Ready to deliver? | ffprobe h264 1920x1080 30/1 nb_frames 360 12.0 s; check log; QC pass | reasoning | binary | YES | mirrors `finish_collection.py` asserts |
| 33 | 8 | What to claim in the final message | verify.json, QC text | reasoning | open | NO | text generation |
| 34 | Codex | Which library entries to load | catalog `--json` | reasoning | closed | YES | per entry given brief |
| 35 | Codex | Prove component pose before full render | skill rule | rule | binary | YES | |
| 36 | Codex | "Broad reflection turned the seat nearly white" -> soften | proof PNG | pixels | open | NO | |
| 37 | Codex | "Blade highlights lose surface detail; rear lens disappears" | critic on PNG | pixels | open | NO | |
| 38 | Codex | Use imagegen for cut-face texture | proof PNG "missing pulp detail" | pixels | binary | NO | |
| 39 | Codex | Control variant passes (six-blade, weaker squash) | `stills.json backwardSeekMatches` + PNG | mixed | binary | MAYBE | deterministic part is text |
| 40 | Codex / collection | Export accepted ("Full 240-frame QA passed", "zero audio streams") | `qa.json` technicalPass, decodedFrames, audioStreams, flat ranges | text | binary | YES | |
| 41 | Collection | Is a `nearIdenticalFrameRanges` hold intentional? (06: QA hold 4.33-6.33 s vs brief "4.8-6.2s holds") | qa.json + brief beats | "deliberate" | binary | YES | beat-table overlap |
| 42 | Collection | Repair required after proof? (01 "90px between word and plates"; 12 "raised by 0.28"; 24 "opaque door hiding the laundry") | proof PNGs | pixels | binary | NO | only 01's 90 px could become a rect proxy |
| 43 | Collection | Family/mechanism distinctness across 24 pieces | titles, mechanisms, colors in collection.json | reasoning + overview sheet | pairwise binary | MAYBE | pairwise "same mechanism?" on text |
| 44 | Collection | `ready: true` | review.md written, proof stills exist, seeks passed | author | binary | YES | |

### 5.3 Jev questions for motion design

| # | Question | State | Type and criteria | Fires | Replaces (grounding) |
|---|---|---|---|---|---|
| 1 | check gate | lint errors/warnings, runtime errors, layout issues and samples, motion errors, contrast pass/total, stderr head | choice [proceed-to-render, fix-source, fix-environment, rerun-check] | after every `motion_slot.py check` | rows 10, 16 ("Installing yauzl", then render) |
| 2 | failure-class router | command head, exit code, stderr tail 600, attempt number for same command, last error signature | choice [browser-binary, missing-shared-lib, node-module-path, script-timeout, python-traceback-in-QC, design-QC-failure]; plus noul "same signature as previous attempt, stop retrying" | any non-zero exit | rows 25, 29 (ball T24/T30/T35 all Code 127) |
| 3 | lint triage | rule id, selector, property, t range, fix hint, phase | noul "fix before next render?" | per lint line | row 15 (`.7` to `.699` fixed only later) |
| 4 | QC overlap adjudication | ids, t, both rects, intersection ratio, roles, brief line for t, shape kinds | choice [real-collision-fix-source, bbox-artifact-allow, out-of-frame-fix-camera]; margin-gated, escalate below threshold with rects | per `layout_qc` violation | rows 23/24 ("paperBody and spark" fix; "#disk and #ray1" allow). Give Jev the rects, never the agent's notes |
| 5 | render-now gate | source sha, last render source sha, qc status for source, check status, pending edits | noul "render now?" | before `motion_slot.py render` | rows 26/27 (wasted T29 render) |
| 6 | warning fatality | warning text, audio count, video count, quality, workers | noul "blocks delivery?" | on log tails | rows 14/31 |
| 7 | delivery readiness | qa.json / ffprobe fields: technicalPass, errors, width, height, fps, duration, decodedFrames, audioStreams, faststart, flat ranges, backwardSeekMatches, sourceMatchesVideo, expected duration and audio | noul "ready?" | before final message | rows 32/40/44 (`finish_collection.py` asserts) |
| 8 | intentional-hold check | hold start/end, brief beats, hero time, is final range | noul "intentional?" | per `nearIdenticalFrameRanges` entry | row 41 |
| 9 | proof-frame candidate | t, beat label, is boundary, is hero, is fastest motion, already sampled | noul "extract a proof at t?" | per beat boundary from a structured beat table | row 19; feeds question 4 |
| 10 | library entry relevance | brief sentence, entry id, kind, tags, summary, controls | noul "load this entry?" | per `motion_library.py search --json` hit | row 34 |

Prerequisite: questions 8 and 9 need the creative contract written as structured text (a beat
table). The fast runs do not write one today (row 7 is inconsistent).

## 6. Narrated explainer and verification (shared with type 1)

Phase map (jet engine, 150 calls): context and toolchain 17%, script and narration 2%, footage
sourcing 32% (12 candidates skipped by the captions gate before 2 cleared; one rejected `select`),
Manim authoring and draft renders 21% (3 crash/fix rounds, 13 renders), text-side layout and
continuity QC 3%, assembly and EDL 7%, self-eval 16% (36 PNG reads; two passes, fps defect found and
rebuilt). The hash map run skipped sourcing and spent six calls on narration length (four synth
rounds). The Cache run hit the three-pass self-eval cap.

Of 19 distinct verification checks, 15 were concluded from text: narrate dry-run estimate, synth
duration and wpm, captions gate, select gate, Manim exit and assertion text, chapter nb_frames,
layout manifest ("passed: 5 frame(s), 24 measured element(s)"), boundary frame diffs ("mean diff
0.591 max 106 px>40: 668" against a normal-motion baseline), ebur128, render.py preview, ffprobe fps
("921600/30719 isn't exactly 30" -> rebuild CFR), EDL validate, decode frame count (1049 vs 1050),
volumedetect, asset existence. Four came from pixels: overlay preflight PNG, filmstrip content,
preview stills, sheets. Every defect that changed the jet-engine output except two (a label clipped
under zoom; clip in-points one second early) was found in text.

Jev questions for this type: `needs_footage` (choice real-footage-helps / diagram-only / clip-existing
from prompt and file list); `dry_run_ok` (noul on words, estimated s, target before the paid TTS
call); `narration_fits` (choice accept / shorten / lengthen / adjust-speed from target, measured,
wpm, hold); `continue_sourcing` (choice search-again / inspect-cleared / diagram-only from unfilled
beats and skip counts); `candidate_rank` (score 0-3 per candidate from title, channel, duration, has
captions; margin-gated); `boundary_continuous` (noul from mean diff, px over 40, baseline);
`stream_spec_ok` (noul over ffprobe JSON vs expected fps and frames); `loudness_ok`; `rerender_needed`
(choice fix-and-rerender / accept / flag-to-user from defect list, pass index, cap 3); `caption_clear`
(noul over caption rect vs overlay rects and protected regions).

Caveat: the layout manifest passed four times in the Cache run while a transient "GET price" token
obscured the "cache hit" label, found only in a full-res still. Text gates cover measured elements
only.

## 7. Rules for the experiment

1. Deterministic before classifier. Speaker overlap at padded edges, cut-inside-word, duration
   range, ffprobe spec, loudness thresholds, SRT drift, source-hash-changed are code, not questions.
   Three of the observed re-render loops disappear with the first rule alone.
2. Never ask a many-way question. Per-unit `noul` and `score`, pairwise `choice` with a margin
   gate, and short fixed criteria lists only. Escalate low-margin items to the LLM with the same text.
3. Give Jev the evidence, not the agent's opinion. Rects, numbers and phrases, never the agent's
   "notes" string (the ball run passed QC by widening an allow-list and writing a justification).
4. Labels for evaluation come from outcomes, not from fast-lane reviews. The fast lane's "reads
   clearly" verdicts were emitted without any image; use later QC results, human picks (the seven
   Jensen moments, the four harness lanes' caption verdicts) and collection reviews as ground truth.
5. What stays with the LLM: EDL quotes and reasons, headline and label text, creative contract,
   scripts and code, the treatment paragraph, and every decision the traces made from pixels (who is
   on camera, material and lighting, caption legibility at phone size, tail camera changes).
6. Jev does not fix the biggest sink. Render polling (32%) and helper-source reading (12%) are
   harness fixes: blocking render calls, a schema card instead of `render.py` source, prepared
   environments. Do them alongside or the classifier's gain is hidden.

## 8. Suggested order on this branch

1. `helpers/jev.py`: thin wrapper over the jev-cu client (route from env, `ask_batch`, gate helpers,
   a JSONL decision log per project). Reuse the parser; do not rewrite it.
2. `helpers/units.py`: deterministic answer-unit splitter over `takes_packed.md` plus word JSON
   (question attached, gaps, fillers, laughs). Pure Python, testable without Jev.
3. `helpers/jev_select.py`: questions 1-6 of section 4.4 over every unit, shortlist JSON with
   probabilities. Evaluate recall against the seven moments the LLMs picked once a long transcript
   exists again (the Jensen source and transcript are gone; transcribe new footage once).
4. `helpers/jev_cuts.py`: questions 7-9 inside a selected unit, emitting EDL ranges with padding and
   the deterministic edge checks. Compare against T1's eleven ranges and T4's ten.
5. Text QC report + `qc.blocker` gate after `render.py`, replacing per-frame views with one optional
   contact sheet.
6. Motion side: `check` gate, failure-class router and render-now gate around `motion_slot.py`,
   then QC overlap adjudication fed with raw rects.

## Appendix: files

- Study folder: `~/Movies/video-use-tests/jev-trace-study/` (`condense.py`, `jensen-benchmark-*.md`,
  `jet-engine-lane4-fable.md`, `hashmap-lane3-opus.md`, `motion-higgsfield-*.md`, `observer/*.md`,
  `recovered-*.md`)
- Raw Jensen rollouts: `~/.codex/sessions/2026/08/30/rollout-*.jsonl` (cwd under `benchmark-runs/jensen-tiktok`)
- Observer database: `~/Developer/video-use-fast-runtime/evidence/video-use-fast-observer-before.sqlite3`
- Harness notes: `~/Downloads/harness-q{1,2,2b,3}/`
- Jev client and keys: `~/Developer/jev-computer-use/jev-cu/` (`jev_cu/jev_client.py`, `.env`)

## 9. Experiment results (2026-09-25)

Scripts and numbers live in `experiments/jev/` (see its README). Summary: Jev answers in ~130 ms
median against 4.5-18 s of LLM think time per decision in the motion traces and 1.4-4.7 minutes per
phase in the speech traces. Promising: delivery-readiness and intentional-hold gates on motion exports
(0/120 broken exports accepted, 24/24 real ones at a calibrated threshold; 10/12 holds), the post-render
QC blocker gate (14/16), and phrase disposability inside a chosen answer (precision 0.67, recall 0.75
against the LLM's removals). Not promising as built: next-action routing after failures or checks
(20% and 0%), QC overlap adjudication (9 instances, noisy labels), and moment selection as a
replacement (LLM picks rank 8-62 of 94; usable only as a payoff-first prefilter). Two findings changed
the plan: the LLM's internal pause cuts are a gap-length threshold (T1: every gap over 0.9 s, nothing
shorter), so pause tightening is deterministic; and Jev is systematically under-confident on positives,
so every gate needs its own calibrated threshold, not 0.5.
