# Motivational edits and presenter overlays

Five footage-based edits extend the Video Editing gallery. The new opening order alternates character stories with practical presenter examples: Rocky Balboa, Modular Phones, Miles Morales, Explain to Learn, and Kobe Bryant. The eight featured workflow cards remain unchanged.

| Demo | Length | Authored editing idea |
| --- | --- | --- |
| Rocky Balboa | 25 seconds | A dialogue-led motivational story with a restrained diptych, animated line and aligned closing portrait |
| Modular Phones | 28 seconds | MKBHD's seated explanation becomes an exploded component diagram, generation comparison and timed lanyard exception |
| Miles Morales | 26 seconds | A coherent rooftop exchange leads into the leap and a title placed behind the held character silhouette |
| Explain to Learn | 32.4 seconds | Ali Abdaal's explanation becomes a connected teaching diagram, simplification graphic and three-step takeaway |
| Kobe Bryant | 24 seconds | Original interview dialogue accompanies raw practice, tracked symmetric panels and a source-aligned closing hero |

The presenter graphics follow the existing Product Launches reference: dark surfaces, generous spacing, cream serif headings and restrained orange emphasis. Their original dialogue remains intact. Gallery previews stay muted; the full Video Editing demos retain their source audio. Existing silent Creation and 3D examples are preserved.

`data/examples.json` contains the published videos, posters, exact prompts, source credits and editable project links. `data/media-sources.json` records the media hashes and production provenance. `lib/sectors.ts` and `components/gallery.tsx` control the category and home-page ordering.

Each composition was authored in the Codex session using the pinned Video Use framework and rendered in Modal. The framework commit is `fc57ba94265bf3cdd7722bfc3f4940d31b780bea`, with runtime snapshot `1e88fe8266c28110ac090ce09490651c801ce7bf7faaeada908604b77813eea9`. No remote language-model invocation is claimed. Each displayed prompt matches the frozen prompt used for that composition.

The downloadable projects include original render code, editable timing and design controls, licensed fonts, credited source URLs and replay instructions. Publisher footage and source audio are reacquired separately. Native source resolutions are recorded; a 1080p delivery does not imply every source was native 1080p.

Release evidence belongs to batch `motivation-overlays-20261007`; each published demo also links its review and editable project. Encoded-frame visual inspection, audio coverage checks and uninterrupted normal-speed browser transport are separate checks. Transport logs do not claim that a reviewer watched continuously or listened to the audio.

All 4,062 encoded frames were inspected across 136 chronological pages, with additional native-resolution details. All five final movies completed uninterrupted normal-speed browser playback, and all 40 public assets passed hash checks. The existing 197 examples and 110 silent Creation/3D films are preserved. The production build, lint, TypeScript, gallery checks and 30 importer tests pass.

Local browser checks pass at 1440, 1100, 768, 390 and 320 pixels: no card overlaps or page overflow, ten desktop/mobile dialogs, exact prompt copying, source archive links, five click-starts and five touch-starts. One initial interaction timeout did not reproduce in the focused five-film diagnostic or the complete rerun; the original failure evidence is retained with the batch.
