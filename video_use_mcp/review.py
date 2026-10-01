"""Shared encoded-frame review for the hosted agent and browser connector."""

REVIEW_CODE = """
import sys
sys.path.insert(0, '/opt/video-use/helpers')
from review_video import main
main()
"""

REVIEW_INSTRUCTION = (
    "Inspect these sampled frames from the actual encoded video, covering the opening, "
    "story holds, transitions and ending. Check that labels are readable at chat-player "
    "size, diagrams explain the spoken idea, and important elements are not clipped or "
    "overlapping. This contact sheet is not proof of every frame or of motion/audio "
    "quality; inspect a specific full-size frame or short segment if anything is unclear. "
    "Check that arrows, labels, signs and transformations mean what the narration claims; "
    "a plausible-looking diagram does not establish correctness. Repair known meaning, "
    "readability or audio defects in the piece rather than listing them as chat caveats. "
    "Report concrete findings on export, distinguishing unresolved defects from optional "
    "style preferences. These are your inspection findings, not automated factual verification. "
    "A modified video requires a fresh review."
)
