"""Plan bounded native zooms from real OpenScreen cursor interactions.

This pure helper neither invents pointer events nor changes the recording timeline.
Coverage means the observed interaction occurs while the camera is settled; entry
and exit animation alone do not count as having showcased an interaction.
"""

from __future__ import annotations

import math


ZOOM_IN_S = 1.01505 * 1.5
ZOOM_OUT_S = 1.01505
EDGE_OVERVIEW_S = 1.0
BETWEEN_OVERVIEW_S = 2.0
CLICK_HOLD_S = 1.0
CLICK_CLUSTER_HOLD_S = 3.0
DRAG_HOLD_S = 10.0
ACTIVITY_GAP_S = 1.5
TIMESTAMP_TOLERANCE_MS = 50.0


def _finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be finite")
    return float(value)


def interaction_zooms(sidecar: dict, duration_s: float, depth: int = 1) -> dict:
    """Return v2 native zoom regions and honest observed-interaction coverage.

    Unknown capture fields/event names are tolerated. Samples must be in capture
    order; only timestamps at most 50 ms past the video's end may be clamped.
    A drag requires down, movement and up, with at least 150 ms elapsed and 1% of
    frame displacement, so pointer jitter during a click does not create a hold.
    """
    duration_s = _finite(duration_s, "duration_s")
    if duration_s <= 0:
        raise ValueError("duration_s must be positive")
    if type(depth) is not int or not 1 <= depth <= 6:
        raise ValueError("depth must be an integer from 1 to 6")
    if not isinstance(sidecar, dict) or not isinstance(sidecar.get("samples"), list) or not sidecar["samples"]:
        raise ValueError("sidecar must contain nonempty samples")

    samples, previous_ms, clamped = [], -1.0, 0
    ignored_types = {}
    for index, raw in enumerate(sidecar["samples"]):
        if not isinstance(raw, dict):
            raise ValueError(f"samples[{index}] must be an object")
        time_ms = _finite(raw.get("timeMs"), f"samples[{index}].timeMs")
        cx = _finite(raw.get("cx"), f"samples[{index}].cx")
        cy = _finite(raw.get("cy"), f"samples[{index}].cy")
        if time_ms < 0 or time_ms < previous_ms or time_ms > duration_s * 1000 + TIMESTAMP_TOLERANCE_MS:
            raise ValueError("Sample timestamps must be sorted, nonnegative and within the recording")
        if not 0 <= cx <= 1 or not 0 <= cy <= 1:
            raise ValueError("Sample coordinates must be within [0, 1]")
        previous_ms = time_ms
        clamped += int(time_ms > duration_s * 1000)
        kind = raw.get("interactionType", "move")
        if kind not in ("move", "click", "mouseup"):
            name = str(kind)
            ignored_types[name] = ignored_types.get(name, 0) + 1
        samples.append({"time_s": min(time_ms / 1000, duration_s), "cx": cx, "cy": cy, "kind": kind})

    interactions, pending = [], None
    unmatched_downs, unmatched_ups = 0, 0
    for sample in samples:
        if sample["kind"] == "click":
            if pending is not None:
                unmatched_downs += 1
            interaction = {"id": f"interaction-{len(interactions) + 1}", "kind": "click",
                           "start_s": sample["time_s"], "end_s": sample["time_s"],
                           "focus": {"cx": sample["cx"], "cy": sample["cy"]}}
            interactions.append(interaction)
            pending = {"interaction": interaction, "max_displacement": 0.0}
        elif pending is not None and sample["kind"] in ("move", "mouseup"):
            interaction = pending["interaction"]
            distance = math.hypot(sample["cx"] - interaction["focus"]["cx"],
                                  sample["cy"] - interaction["focus"]["cy"])
            pending["max_displacement"] = max(pending["max_displacement"], distance)
            if sample["kind"] == "mouseup":
                if sample["time_s"] - interaction["start_s"] >= 0.15 and pending["max_displacement"] >= 0.01:
                    interaction.update(kind="drag", end_s=sample["time_s"])
                pending = None
        elif sample["kind"] == "mouseup":
            unmatched_ups += 1
    unmatched_downs += int(pending is not None)

    # Work in settled-camera time; native startMs includes the 500 ms overlap.
    # Candidate order is input order, so this scheduling never moves a click.
    planned = []
    omission_reasons = {}
    max_end = duration_s - EDGE_OVERVIEW_S - ZOOM_OUT_S
    for interaction in interactions:
        start, end = interaction["start_s"], interaction["end_s"]
        drag = interaction["kind"] == "drag"
        desired_end = end + (0.35 if drag else CLICK_HOLD_S)
        prior = planned[-1] if planned else None
        if prior and start - prior["last_activity_s"] <= ACTIVITY_GAP_S:
            cap = DRAG_HOLD_S if prior["has_drag"] or drag else CLICK_CLUSTER_HOLD_S
            extended_end = min(desired_end, prior["settle_s"] + cap, max_end)
            # Never lengthen a click cluster merely to wait for a later click.
            if prior["settle_s"] <= start <= max(prior["end_s"], extended_end):
                prior["end_s"] = max(prior["end_s"], extended_end)
                prior["last_activity_s"] = end
                prior["has_drag"] = prior["has_drag"] or drag
                continue
        earliest = EDGE_OVERVIEW_S + ZOOM_IN_S
        if prior:
            earliest = max(earliest, prior["end_s"] + ZOOM_OUT_S + BETWEEN_OVERVIEW_S + ZOOM_IN_S)
        if not drag and start < earliest:
            omission_reasons[interaction["id"]] = "opening overview" if not prior else "overview between zooms"
            continue
        settle = max(start, earliest) if drag else start
        hold_end = min(desired_end, settle + (DRAG_HOLD_S if drag else CLICK_HOLD_S), max_end)
        if hold_end - settle < 0.25 or (drag and settle >= end):
            omission_reasons[interaction["id"]] = "final overview or no remaining active drag"
            continue
        planned.append({"settle_s": settle, "end_s": hold_end, "last_activity_s": end,
                        "has_drag": drag, "focus": interaction["focus"]})

    regions = []
    for index, plan in enumerate(planned):
        # Inward rounding keeps required overview gaps intact at millisecond resolution.
        regions.append({"id": f"interaction-focus-{index + 1}",
                        "startMs": math.ceil(plan["settle_s"] * 1000 - 1e-7) - 500,
                        "endMs": math.floor(plan["end_s"] * 1000 + 1e-7),
                        "depth": depth, "focus": dict(plan["focus"]),
                        "focusMode": "auto", "source": "auto"})

    coverage = []
    for interaction in interactions:
        start, end = interaction["start_s"], interaction["end_s"]
        spans = []
        for region in regions:
            settled = (region["startMs"] + 500) / 1000
            # Capture uses fractional milliseconds; native regions use integers.
            if start == end:
                if settled - 0.001 <= start <= region["endMs"] / 1000 + 0.001:
                    spans.append({"start_s": start, "end_s": end, "zoom_id": region["id"]})
                continue
            left = max(start, settled)
            right = min(end, region["endMs"] / 1000)
            if right > left:
                spans.append({"start_s": left, "end_s": right, "zoom_id": region["id"]})
        covered_duration = sum(s["end_s"] - s["start_s"] for s in spans)
        complete = bool(spans) and (start == end or covered_duration >= end - start - 0.002)
        state = "covered" if complete else "partial" if spans else "omitted"
        reason = (None if complete else "bounded drag hold or overview leaves part of the drag uncovered"
                  if spans else omission_reasons.get(interaction["id"], "bounded hold or overview"))
        coverage.append({"id": interaction["id"], "kind": interaction["kind"],
                         "start_s": start, "end_s": end, "status": state,
                         "covered_spans": spans, **({"reason": reason} if reason else {})})

    return {"zoom_regions": regions, "summary": {
        "source_samples": len(samples), "source_clicks": len(interactions),
        "source_drags": sum(i["kind"] == "drag" for i in interactions),
        "covered_interactions": sum(i["status"] == "covered" for i in coverage),
        "partially_covered_interactions": sum(i["status"] == "partial" for i in coverage),
        "omitted_interactions": sum(i["status"] == "omitted" for i in coverage),
        "interactions": coverage, "unmatched_downs": unmatched_downs, "unmatched_ups": unmatched_ups,
        "clamped_end_samples": clamped, "ignored_event_types": ignored_types,
        "policy": {"click_cluster_max_hold_s": CLICK_CLUSTER_HOLD_S,
                   "drag_max_hold_s": DRAG_HOLD_S, "overview_between_s": BETWEEN_OVERVIEW_S,
                   "overview_at_edges_s": EDGE_OVERVIEW_S,
                   "timestamp_rounding_tolerance_ms": 1,
                   "coverage": "observed interaction within settled camera span"},
    }}
