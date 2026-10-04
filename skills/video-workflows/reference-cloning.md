# Clone the selected reference with the user's content

Use this after the user selects a reference in Hands on mode. Selection authorizes
downloading and analyzing that example and making a short adapted snippet. The
full video still requires the user's explicit snippet acceptance. Do not add a
storyboard, script approval or another style questionnaire.

## Acquire the actual reference

Call `prepare_video_reference(project_id, reference_id, request_id)` for each
selected video. If the task is pending, use `get_video_task`; proceed only after
success. The result contains a persistent source path, SHA-256, measured runtime,
dimensions, frame rate, audio presence, and a timestamped contact sheet. View the
sheet with `view_video_frame`. The source is restored with the project's other
inputs after a workspace restart. Do not download unchosen candidates.

If a platform blocks downloads, explain that specific blocker and use
`request_video_sources` for an uploaded copy; retry `prepare_video_reference`
with that source's `source_object_id`. Alternatively let the user choose an
accessible reference. Never bypass login, pretend a thumbnail establishes
motion, or quietly switch to generic animation. The worker accepts one video
up to ten minutes and 200 MB. An image-only reference needs clarification or
explicit delegation instead of pretending there is a downloadable video.

## Measure before planning

The old Whiplash clone prompt's useful principle is: the breakdown is the
specification. Match what actually happens, measured rather than guessed.
The initial contact sheet is an overview, not a cut detector or motion analysis.
Use `run_video_step` with `production_stage="excerpt"` for internal analysis
commands and files, without `preview_path`. Use FFprobe/FFmpeg, the provided
timeline and audio helpers, and actual `view_video_frame` inspection. Do not show
analysis sheets as the user's snippet.

1. Inventory the local video's timebase, duration, canvas and audio. Map the full
   structure cheaply, then inspect dense frame windows around the representative
   passage, cuts, impacts, reveal starts, holds and transitions. Keep real source
   timestamps; sample both sides of cuts. Never report uniform sample times as
   detected cuts. Distinguish camera motion, object motion, deformation and masks.
2. Record composition and scale, type size/weight/placement, crop, palette,
   lighting, texture, motion paths, easing, overshoot and settling. Preserve the
   mechanics that make the reference recognizable, including deliberate absence
   of text or effects. Do not reduce the analysis to adjectives or a palette.
3. Inspect audio where accessible. Measure beat/impact and speech relationships;
   use word-timed transcription when speech drives the edit. A waveform or still
   cannot prove listening or continuous playback. State what was actually checked.
4. Save `edit/reference-breakdown.md`: source path/hash, inspected windows,
   timestamped beats, observed treatment, uncertainties, and an adaptation table
   mapping each reference beat to the user's content and required assets.

## Adapt the subject while preserving the treatment

The original query, explicit preferences, output length, audience and destination
remain authoritative. Replace the reference's subject, copy, product, imagery,
data and narration with the requested content. Preserve its narrative roles,
relative rhythm, transition mechanisms, spatial hierarchy and audio relationships
where compatible. Do not import stale facts, brands or claims from the example.
If length changes, map timing deliberately; do not compress every beat blindly.
If references are combined, follow the user's selected traits for each.

Rebuild the effect with editable source and appropriate assets. Use custom code
or available asset/production tools when needed; do not flatten a photographic
or material-rich reference into simple shapes merely because a helper is easier.
Record any missing capability or asset and the concrete substitution. Downloaded
reference video is analysis input, never the authored output. Do not pass through
its pictures or soundtrack as the new piece unless the user requested reuse.
Describe asset provenance honestly; don't claim everything is original by default.

## Prove the treatment in a snippet

Plan the full arc internally, then render a coherent short passage that includes
the signature action and a transition or payoff. Choose its length from the
reference and intended film; it must remain a limited excerpt, not the full video
relabeled as a sample. A static title or generic opening is insufficient when the
chosen reference's defining treatment occurs later. Preserve named shared controls
and reusable scene source so the accepted passage can become part of the final cut.

Compare encoded snippet frames against matching reference moments and inspect
the motion window. Check structure, composition, timing, text treatment, transitions,
audio synchronization and adaptation to the query. Fix visible errors before
showing it. Record specific divergences and avoid unsupported similarity scores.

Publish with `run_video_step(production_stage="excerpt", preview_path=...)` and
show it once with `show_video_preview`. Use `show_video_checkpoint` for one native
Continue/Refine question about that exact clip. Refinement reuses the download
and breakdown, applies actual feedback and returns to snippet review. Silence,
reference selection and technical QA success are not snippet approval.

After explicit acceptance, extend the accepted editable source and render the
remaining beats with `production_stage="full_video"`. Reuse the approved snippet,
maintain the same treatment, inspect the assembled film against the breakdown
and original brief, then deliver the final player and editable project.

## Prompt provenance

Adapted from the saved Whiplash GPT-6 clone prompt (retrieved September 15, 2026)
and the Verify You Are Human recreation's revision notes: reference download,
measured cut/motion/audio breakdown, editable reconstruction, dense comparison
at transitions, and explicit gaps. Their fixed subject, soundtrack, canvas and
full-film-first delivery are project-specific and are not carried into this flow.
