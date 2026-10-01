"""Timestamped player suggestions are durable user direction, not approval gates."""

import hashlib
import math
import time
from copy import deepcopy

from .store import ident
from .creative_state import creative_lock
from .widgets import creative_public


def feedback_context(store, project_id, limit=5):
    """Keep routine tool responses small; full history remains in private traces."""
    items = (store.get("feedback", project_id) or {}).get("items", [])
    return {"items": items[-limit:], "saved_count": len(items)}


def register_feedback(mcp, store, muser, write):
    @mcp.tool(
        annotations=write,
        meta={"ui": {"visibility": ["app"]}},
        title="Save an edit suggestion",
    )
    def add_video_feedback(
        project_id: str,
        object_id: str,
        seconds: float,
        note: str,
        request_id: str,
    ) -> dict:
        """Save the user's explicit suggestion at the current video timestamp."""
        uid = muser(True)
        store.project(uid, project_id)
        if (
            isinstance(seconds, bool)
            or not math.isfinite(seconds)
            or not 0 <= seconds <= 86400
        ):
            raise ValueError("Choose a valid video timestamp")
        if not note.strip() or len(note) > 1200:
            raise ValueError("Keep the suggestion between 1 and 1200 characters")
        if not 1 <= len(request_id) <= 120:
            raise ValueError("Provide a request ID of 1–120 characters")
        rows = store.sql(
            "SELECT id,kind,name FROM public.vp_objects WHERE id=$1 AND owner=$2 AND project=$3",
            object_id,
            uid,
            project_id,
        )
        if not rows or rows[0]["kind"] != "video":
            raise PermissionError("This video is not available in this project")
        payload = {
            "object_id": object_id,
            "seconds": round(float(seconds), 3),
            "note": note.strip(),
        }
        receipt_key = hashlib.sha256(
            (uid + ":" + project_id + ":" + request_id).encode()
        ).hexdigest()
        # These edits must remain responsive while a render holds its workspace
        # lock. Synchronous state mutations use their own short critical section.
        with creative_lock(project_id):
            previous = store.get("feedback_request", receipt_key)
            if previous:
                if previous["payload"] != payload:
                    raise ValueError(
                        "This request ID already saved a different suggestion; use a new request_id"
                    )
                return previous["result"] | {
                    "creative": creative_public(
                        store.get("creative", project_id)
                        or previous["result"]["creative"]
                    ),
                    "repeated": True,
                }
            state = deepcopy(store.get("creative", project_id) or {})
            if not state:
                raise ValueError(
                    "Start a creative brief for this project before suggesting edits"
                )
            history = store.get("feedback", project_id) or {"items": []}
            applied = next(
                (
                    item
                    for item in [state.get("latest_feedback", {})]
                    + history.get("items", [])
                    if item.get("request_id") == request_id
                ),
                None,
            )
            if applied:
                if {key: applied[key] for key in payload} != payload:
                    raise ValueError(
                        "This request ID already saved a different suggestion; use a new request_id"
                    )
                if not any(
                    item.get("id") == applied["id"] for item in history.get("items", [])
                ):
                    history["items"] = (history.get("items", []) + [applied])[-50:]
                    store.put("feedback", project_id, history)
                result = {
                    "project_id": project_id,
                    "feedback": applied,
                    "creative": creative_public(state),
                    "repeated": True,
                    "next_action": "Use the saved suggestion in the next edit.",
                }
                store.put(
                    "feedback_request",
                    receipt_key,
                    {"payload": payload, "result": result},
                    ttl=2592000,
                )
                return result
            revisions = store.sql(
                "SELECT metadata FROM public.vp_revisions WHERE project=$1 AND owner=$2 AND video=$3 ORDER BY created DESC LIMIT 1",
                project_id,
                uid,
                object_id,
            )
            metadata = (revisions[0].get("metadata") or {}) if revisions else {}
            progress = store.get("progress", project_id) or {}
            preview = next(
                (
                    update["preview"]
                    for update in reversed(progress.get("updates", []))
                    if (update.get("preview") or {}).get("object_id") == object_id
                ),
                {},
            )
            duration = metadata.get("duration", preview.get("duration"))
            if (
                isinstance(duration, (int, float))
                and math.isfinite(duration)
                and seconds > duration + 0.05
            ):
                raise ValueError(
                    "That timestamp is beyond this video; choose a moment inside it"
                )
            state["revision"] = int(state.get("revision", 0)) + 1
            item = payload | {
                "id": ident(),
                "request_id": request_id,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "creative_revision": state["revision"],
            }
            timing = store.get("production_timing", project_id) or {}
            # Preview encoding has a different digest from its source; never map
            # a timestamp to a scene merely because they belong to one project.
            if metadata.get("sha256") and metadata["sha256"] == timing.get("sha256"):
                start = 0.0
                for index, scene in enumerate(timing.get("scenes", [])):
                    end = start + float(scene["seconds"])
                    if start <= seconds < end:
                        item["scene"] = {
                            "index": index,
                            "title": scene["title"],
                            "start": start,
                            "end": end,
                        }
                        break
                    start = end
            latest = state.get("latest_feedback")
            if latest and not any(
                old.get("id") == latest["id"] for old in history.get("items", [])
            ):
                history["items"] = history.get("items", []) + [latest]
            history["items"] = (history.get("items", []) + [item])[-50:]
            state["latest_feedback"] = item
            # Store the suggestion in creative context as well, so every next
            # step sees both the new revision and the actual requested change.
            store.put("creative", project_id, state)
            store.put("feedback", project_id, history)
            result = {
                "project_id": project_id,
                "feedback": item,
                "creative": creative_public(state),
                "repeated": False,
                "next_action": "Apply this suggestion to the referenced video moment. Continue other work; do not ask for command approval.",
            }
            store.put(
                "feedback_request",
                receipt_key,
                {"payload": payload, "result": result},
                ttl=2592000,
            )
            return result

    return add_video_feedback
