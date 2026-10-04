"""An optional, public example library handoff after a creation approach is chosen."""

from urllib.parse import urlencode

LIBRARY_URL = "https://video-use.insforge.site"
APPROACH_TECHNIQUES = {
    "motion_design": "motion-design",
    "procedural_3d": "3d",
    "diagram_animation": "diagrams",
    "data_animation": "diagrams",
    "cinematic": "video-editing",
    "screen_demo": "video-editing",
    "footage_edit": "video-editing",
}


def example_library_context(intake, project_id=None):
    """Return navigation, never an inferred user choice or an intake mutation."""
    approach = intake.get("creation_approach", {})
    if approach.get("status") not in {"selected", "delegated"}:
        return None
    technique = APPROACH_TECHNIQUES.get(approach.get("id"))
    url = LIBRARY_URL + (
        "?" + urlencode({"technique": technique}) if technique else ""
    )
    return {
        "url": url,
        "title": "Browse Video Use examples",
        "presentation_key": f"example-library:{project_id or 'current'}:{technique or 'all'}",
        "optional": True,
        "instructions": (
            "After the user chooses a creation approach, offer this link once in a short "
            "sentence: browse useful examples, copy a prompt, and paste it back into this "
            "chat. The website has audience and workflow filters, full video previews, "
            "and free reusable prompts. Do not introduce a new required question or "
            "treat opening the website as a selection. Continue the existing reference "
            "flow unless the user says they want to browse first. If they paste an "
            "example prompt, combine its technique with their existing subject, brand, "
            "format and length; do not overwrite settled requirements with example "
            "names or numbers. When their pasted request explicitly chooses that "
            "workflow and asks to skip other references, record that actual message "
            "with record_video_references action=delegate and preserve its direction. "
            "An example choice never approves a snippet or the complete film. Keep "
            "the current involvement mode and the explicit hands-on snippet checkpoint."
        ),
    }
