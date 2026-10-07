# Words into motion

## Exact request

“Okay, so there are a couple UI things I want to change up within the site, and the first one is the blank container. I'll send you a screenshot in. This container will include i don't really know yet, and I need an idea and just want you to take the vibes of the whole page and put something there thta is animated and moving. Your call”

## Creative contract

An original twelve-second, silent, native browser composition fills the left panel beside the six agent cards. A typed prompt awakens a folded orange sculpture in a floating video frame. An editing timeline scans underneath. The headline is “Just say it. See it move.” It should feel tactile, playful and controlled beside the black/white/orange page, without adding another call to action or stretching the section.

The strongest frame is the fully unfolded sculpture at 5.5 seconds: orange fins, warm edge light, dark floating frame, white/orange headline and the completed prompt. The repeated fins open as the prompt sends, preserving their orange material through the sequence. The prompt has a reading hold before the reset; the sculpture keeps its orientation across the 12-second loop seam. Candidate ideas included a conveyor of sample films and an orbit of app logos; the selected folded sculpture adds original motion without repeating the neighboring cards or downloading more media.

Typography uses the site's local Space Grotesk and Inter. CSS gradients author the satin orange material and soft shadows; no new raster, stock, font or video assets are required. Lucide's existing Sparkles, ArrowUp and AudioLines are decorative. No new dependencies. Small painted interface elements are illustrative, not interactive controls. Failure conditions: overlap with the headline, changing panel height, a blank playback frame, a visible loop snap, or animations continuing behind a connection dialog.

## Source and replay

`prompt-motion.tsx` renders the scene and pauses its clocks while offscreen, while the document is hidden, or while a Video Use overlay is open. `prompt-motion.module.css` owns layout, materials and the shared 12-second animation clock. Reduced motion presents the fully composed still. The component is mounted by `AgentShortcuts` in the previously blank left panel.

Run the website normally with its existing `package-lock.json` (Next 16.3.5 / React 19.2.6). Open `/` and scroll to `#agents`. For a deterministic proof frame, use the browser's native animation clock: select `[data-prompt-motion]`, obtain `getAnimations({subtree:true})`, pause each animation and set each `currentTime` to `seconds * 1000`. The same timestamp reconstructs every layer independently; there is no accumulated JavaScript animation state. Reload for normal looping playback. Proof targets: 0, 1.5, 3, 4, 5.5, 8, 10.5, 11.95 and 12.05 seconds.

QA evidence and visual repair notes: `/tmp/video-use-prompt-motion-20261007/`. Review of rendered frames and behavioral checks are separate from any claim of commercial design parity.

## Review notes

The first rendered proof established the orange folded material and left/right composition. The headline and sculpture are capped on wide panels; their size still follows the panel on phones. A small footer caption was removed after the 2048px proof showed it crowding the sculpture. Review covers a full half-second frame sequence, start/end seam frames, and 25 samples over a normal elapsed twelve-second loop. No all-blank frame or loop jump was found. The first functional harness mixed manual clock seeking with CSS playback checks; these now use separate page loads so a test's `Animation.play()` override cannot mask normal CSS pause behavior. Anchor checks wait for smooth scrolling to finish before testing offscreen suspension.

Functional checks cover 320, 390, 768, 1024, 1440 and 2048px, unchanged desktop row alignment, every agent action, hidden-document/dialog/offscreen suspension, resume without a reset, reduced motion and no horizontal overflow. Tests isolate this new scene from the existing streamed films; their files and playback implementation are unchanged. Production build, lint, type/catalog checks and the thirty existing importer tests pass. Local disk exhaustion interrupted several build attempts; generated preview output and disposable test-browser dependencies were cleared, the original deployment config was restored, and the completed build passes. No new production configuration or dependency was introduced.
