"""Read-only narration allowance snapshots from the admission source of truth."""

from datetime import datetime


def narration_allowance(store, uid, *, requested_characters=None):
    """Check daily capacity without reserving it, starting work, or calling speech.

    The database owns both limits and accounting. A missing migration or failed
    read is unknown capacity, never zero capacity or permission to exceed a cap.
    """
    if requested_characters is not None and (
        type(requested_characters) is not int or requested_characters < 0
    ):
        raise ValueError("requested_characters must be a nonnegative integer")
    result = {
        "status": "unknown",
        "unit": "characters",
        "period": "UTC day",
        "next_action": (
            "Narration allowance could not be checked. Do not promise available "
            "speech capacity; the normal atomic allowance check still applies. "
            "Continue independent planning or visual work."
        ),
    }
    try:
        rows = store.sql(
            "SELECT public.vp_narration_allowance($1::uuid) AS allowance", uid
        )
        value = rows[0]["allowance"]
        dates = {}
        for key in ("checked_at", "resets_at"):
            date = datetime.fromisoformat(value[key].replace("Z", "+00:00"))
            if date.tzinfo is None:
                raise ValueError("Allowance timestamp must include its time zone")
            dates[key] = date
        if dates["resets_at"] <= dates["checked_at"]:
            raise ValueError("Allowance reset must follow the snapshot")
        pools = {}
        for scope in ("user", "shared"):
            pool = {
                key: value[scope][key] for key in ("limit", "committed", "reserved")
            }
            if any(type(v) is not int or v < 0 for v in pool.values()):
                raise ValueError("Invalid allowance counters")
            pool["remaining"] = max(
                0, pool["limit"] - pool["committed"] - pool["reserved"]
            )
            pools[scope] = pool
        result.update(
            status="known",
            checked_at=value["checked_at"],
            resets_at=value["resets_at"],
            **pools,
            remaining=min(pool["remaining"] for pool in pools.values()),
            next_action=(
                "Compare the proposed script's character count with remaining "
                "before new narration. This snapshot is not a reservation or "
                "provider bill; concurrent work can consume it. Reusing cached "
                "same-user, same-voice, identical-text narration needs no new "
                "narration characters. Do not split calls to bypass daily limits."
            ),
        )
        if result["remaining"] == 0:
            result["next_action"] = (
                "No daily allowance remains for new narration. Explain this before "
                "starting speech; reuse existing audio when appropriate or continue "
                "independent visual work. Do not silently omit requested voiceover. "
                "Settled and reserved usage both count until the shown UTC reset; "
                "this is an allowance snapshot, not a provider bill."
            )
    except Exception:
        # Database failures may contain queries or credentials; neither belongs
        # in model-visible creative context. A snapshot is advisory, not admission.
        pass
    if requested_characters is not None:
        result["requested_characters"] = requested_characters
        result["fits_available"] = (
            requested_characters <= result["remaining"]
            if result["status"] == "known"
            else None
        )
        result["estimate_basis"] = (
            "Exact supplied character count for uncached narration; daily allowance only, not a reservation or provider bill."
        )
    return result
