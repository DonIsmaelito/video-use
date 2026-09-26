# Jev experiments

Scripts that test whether Jev (TypeSafe System One, a 0.1-0.5 s text-only classifier) can take over
specific decisions the LLM agent makes while producing (1) a postable clip from long raw speech footage
and (2) a motion-design piece. Each script builds its instances from real traces, asks Jev, scores the
answers against what the LLM did or against a rule, and reports Jev's latency next to the LLM's think
time for the same decision measured from the trace timestamps.

Setup: `helpers/jev.py` (wrapper) over the vendored `helpers/jev_client.py`; keys are read from
`~/Developer/jev-computer-use/jev-cu/.env` (`JEV_ENV_FILE` to override). Every call is logged to
`results/jev_decisions.jsonl`. Run any experiment with `python3 experiments/jev/<script>.py`.

| Script | Decision | Instances | Result | Jev latency | LLM baseline |
|---|---|---|---|---|---|
| `exp_motion_failure_router.py` (M1) | failure class of a failed command; next action | 103 failed commands, 21 runs | class agrees with regex labels 49/74 (66%); next action agrees with the LLM's eventual action 21/103 (20%) | median 136 ms | median 7.5 s, p90 17.6 s before the next command |
| `exp_motion_check_gate.py` (M2) | proceed / fix source / fix env / inspect after `motion_slot.py check` | 22 check runs | 0/18 agreement with the eventual action | median 126 ms | median 9.7 s |
| `exp_motion_qc_adjudicate.py` (M3) | real collision vs bounding-box artifact vs tooling error | 9 QC failures (8 labelled) | 2/8; too few and labels are noisy | median 470 ms | median 9.7 s |
| `exp_motion_ready_gate.py` (M4) | export satisfies the collection contract | 24 real exports + 120 perturbed | all 120 defects rejected (max p 0.04); real exports p 0.18-0.67, so 100% separable at p >= 0.15, only 7/24 at p >= 0.5 | median 131 ms | delivery check is a script today |
| same (M4b) | near-identical frame range is an intentional hold per the beat table | 12 ranges, 8 scenes | 10/12 | same | review notes written by hand |
| `exp_speech_qc_blocker.py` (S3) | post-render QC report contains a real blocker | 16 reconstructed reports | 14/16 (misses the 124 ms caption drift and a 0.7 s black lead-in, both threshold rules) | median 353 ms | 11-17 verification calls per run, 20-33% of all calls |
| `exp_speech_select.py` (S1) | standalone / hook / payoff per answer-unit, then a pairwise tournament | 94 clip-sized answer-units of the 103-minute Jensen interview | the six moments the LLM runs picked rank 8, 12, 14, 34, 57, 62 of 94 on the combined score (3/6 in the top 20; random mean rank 47); ranking by `payoff` alone puts 3/6 in the top 10 and 4/6 in the top 30; `standalone` carries no signal (mean rank 46); the tournament made it worse | 94 calls in 2.1 s wall, median 130 ms; tournament 45 pairs in 1.1 s | 1.9-4.7 model-minutes per run for reading + selecting + filmstrip drill |
| `exp_speech_cuts.py` (S2) | safe internal cut per gap, disposable per phrase | the two passages the LLM cut internally (T1: 20 gaps, 21 phrases; T4: 14 gaps, 23 phrases) | gaps: Jev has no signal (mean p 0.43 on removed vs 0.42 on kept gaps) but a plain rule `gap >= 0.9 s` reproduces all 10 of T1's cuts with no false positives; phrases: Jev at p >= 0.6 matches T4's filler/repetition removals with precision 0.67 and recall 0.75 and, like the LLM, removes nothing in T1 | 41 + 37 calls in 1.3 + 0.6 s | 1.4-2.6 model-minutes writing the EDL; edge leaks found only after render |

## Reading the motion results

- M1 and M2 fail as "predict the LLM's next command". The failure *class* is fine (66% against regex
  labels, and the disagreements are mostly browser-vs-library ambiguity in the labels themselves), but
  the next action in these traces is driven by things the state does not contain: what the agent
  already tried, whether it has sudo, which files exist. Both need an explicit retry ledger and file
  facts in the state before they are worth another run; as built they are not promising.
- M3 has nine instances and the heuristic labels contradict the trace in at least one row
  (`paperBody`/`spark` was fixed in source, which Jev called correctly). Needs raw rectangles in the
  state and hand labels; inconclusive.
- M4 is promising. Jev never accepted a broken export, and a calibrated threshold accepts every real
  one. Jev is under-confident on positives (0.18-0.67), so gates should be calibrated per question,
  not fixed at 0.5. The intentional-hold check works from the beat table alone (10/12).
- S3 is promising for the qualitative part of the gate (fragments, cut inside a word, silent audio,
  landscape, decode errors, tooling artifacts) and confirms the doc's rule: numeric thresholds
  (drift ms, black frames) stay deterministic and only the interpretation goes to Jev.

## Reading the raw-footage results

- S1: Jev is not a replacement for the LLM's moment choice but a usable prefilter. `payoff`
  ("ends on a complete thought or punchline") is the question that carries signal; `standalone` as
  phrased does not. The most popular LLM pick, the opening "electrons to tokens" answer (four of eight
  runs), ranked 62/94: it opens with hesitations and a technical framing, and Jev has no notion of
  "quotable" beyond the phrasing of the hook question. Next step is to rephrase the questions against
  the six known picks and to add the host question and the unit's position in the interview to the
  state, then re-run; the whole loop costs two seconds per attempt.
- S2: the LLM's internal pause cuts are a threshold policy, not a judgment. T1 removed exactly the
  gaps longer than 0.9 s and kept every shorter one; T4 removed nearly every gap over 0.5 s. That belongs
  in a deterministic tightening pass with one number. Where Jev adds value is phrase disposability
  (fillers, false starts, repetitions): 6 of T4's 8 removals found with 3 extra flags, one of which is the
  `([laughs])` token that the SKILL's "the laugh is the beat" rule protects.
- Edge leaks (host fragments inside padded edges) never need a model: S3 shows Jev recognises them when
  they are in the report, but the report itself comes from a word-JSON overlap check.

## Totals

All experiments together: 611 Jev calls (S1 ran once on a wrong-interview transcript too), median latency 130 ms, p90 257 ms, about 424k input tokens, roughly $0.012 at the
documented $0.00002 per call. The LLM decisions they stand in for took 4.5-18 s each in the motion traces
and 1.4-4.7 minutes per phase in the speech traces.

## What to build next (ranked by evidence)

1. Deterministic pass in the speech pipeline: answer-unit splitter (`speech_units.py`), pause
   tightening by threshold, cut-inside-word and other-speaker-edge checks, ffprobe/loudness/SRT rules.
2. Jev phrase disposability inside a chosen unit (S2 phrases) and the post-render blocker gate (S3).
3. Jev delivery-readiness and intentional-hold gates for motion exports (M4), with per-question
   calibrated thresholds (0.15 for readiness) rather than 0.5.
4. Jev payoff-first prefilter for moment selection (S1), only as a candidate reducer feeding the LLM.
5. Not yet: next-action routing after failures or checks (M1, M2) until the state carries a retry
   ledger and file facts; QC adjudication (M3) until rectangles are in the state and labels are by hand.

## Fast motion: a Jev-only path under 20 seconds

`helpers/fast_motion.py` (on this branch; it needs the newer motion toolkit: `motion_render.mjs`,
the recipe library and the examples). No language model runs. One Jev request answers six typed
questions about the prompt: which of five instant scenes (word-pop, kinetic-type, ink-octopus,
checker-zebra, paper-koi), which of six palettes, pace (calm 8 s / brisk 6 s / explosive 4.5 s),
arrival motion (spring / decisive / drift), ending (hold / exit / loop), and whether the background
should be dark. Words come from the prompt by rule (a quoted phrase, else emphasised words). The
scene is a parametrized template, rendered at 1280x720 30 fps with the deterministic browser
renderer, then checked by `motion_gate.py`. Results in `results/fast_motion_runs.json`; videos in
`~/Movies/video-use-tests/jev-trace-study/fastmotion/out2/`.

| Prompt | Jev choices | Jev | Render | Total |
|---|---|---|---|---|
| Make the word MELT drop in and bounce, warm and playful | word-pop, cream-vermilion, brisk, spring, hold, 6 s | 0.19 s | 12.9 s | 14.0 s |
| Launch title "OPEN FIELD" on a dark background, fast and confident | word-pop, charcoal-coral, explosive, decisive, hold, 4.5 s | 0.13 s | 9.5 s | 10.6 s |
| Too many tabs open in my head, then one clear thought | kinetic-type, midnight-neon, explosive, decisive, hold, 4.5 s | 0.13 s | 9.5 s | 10.7 s |
| A checkerboard peels into a galloping zebra on a lime field | checker-zebra, forest-lime, brisk, spring, exit, 6 s | 0.14 s | 11.8 s | 13.0 s |
| A blue ink droplet becomes an octopus on old paper | ink-octopus, paper-cobalt, brisk, drift, hold, 6 s | 0.25 s | 21.1 s | 22.4 s |
| A red paper square unfolds into a koi and swims away, calm and quiet | paper-koi, cream-vermilion, calm, drift, exit, 8 s | 0.14 s | 33.7 s | 35.5 s |

Jev routed all six prompts to the right scene with sensible palettes; the decisions cost 0.13 to
0.31 s. The budget is the render: the canvas-drawn recipes (octopus, koi) cost 15 to 34 s because
each frame is redrawn on the CPU, and a smaller frame size does not help (koi at 960x540 24 fps:
22.8 s). Under 20 s therefore holds for typography and light scenes at 4.5 to 6 s; the heavy
illustrated scenes need a faster capture path (GPU canvas, frame batching) or shorter pieces.

What this shows about Jev's fit: it is a content filter and an asset selector. Scene, palette,
pace, motion, ending are all closed sets and it picks well and instantly. It cannot invent the
scene, the words or the choreography, so the ceiling of this path is the catalog. Two omissions
that the traces made obvious: the 3D recipes (Three.js plus font assets) are not installed locally,
and the render step, not the decision step, is what stands between 10 s and 35 s.
