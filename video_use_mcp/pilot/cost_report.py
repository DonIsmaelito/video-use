"""Read-only pilot cost snapshots. Does not restart or alter a running edit.

Run with the owner's local environment and Modal login. Project figures are
estimates from recorded sandbox lifetimes, not invoices or task quota reservations.
"""

import argparse
import json
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

from .config import Config
from .store import Store

SNAPSHOT_SQL = """
SELECT json_build_object(
 'projects',(SELECT coalesce(json_agg(p),'[]') FROM
   (SELECT id,title,sandbox_id,touched,created FROM public.vp_projects ORDER BY created) p),
 'tasks',(SELECT coalesce(json_agg(t),'[]') FROM
   (SELECT t.project,t.operation,t.status,t.created,t.updated,u.amount,u.settled
    FROM public.vp_tasks t LEFT JOIN public.vp_usage u ON t.usage_id=u.id) t),
 'speech',(SELECT coalesce(json_agg(s),'[]') FROM
   (SELECT t.project,u.kind,sum(u.amount) AS amount,bool_and(u.settled) AS settled
    FROM public.vp_usage u JOIN public.vp_tasks t ON u.request_id=t.id::text
    WHERE u.kind IN ('narrate','transcribe') GROUP BY t.project,u.kind) s),
 'objects',(SELECT coalesce(json_agg(o),'[]') FROM
   (SELECT project,sum(size) AS bytes FROM public.vp_objects GROUP BY project) o),
 'lifetimes',(SELECT coalesce(json_agg(l),'[]') FROM
   (SELECT value FROM public.vp_kv WHERE kind='lifetime') l),
 'reference_lifetimes',(SELECT coalesce(json_agg(l),'[]') FROM
   (SELECT value FROM public.vp_kv WHERE kind='reference_browser_lifetime') l),
 'reference_sessions',(SELECT coalesce(json_agg(l),'[]') FROM
   (SELECT value FROM public.vp_kv WHERE kind='reference_browser_session') l),
 'reference_evidence',(SELECT coalesce(json_agg(l),'[]') FROM
   (SELECT value FROM public.vp_kv WHERE kind='reference_browser_evidence') l)
) AS snapshot
"""


def estimate(seconds, rates):
    """Account rates are per physical core-hour and GiB-hour, not vCPU-hour."""
    hours = Decimal(str(max(0, seconds))) / 3600
    cpu = Decimal(str(rates["cpu_hour_cost_sandbox"]))
    memory = Decimal(str(rates["mem_gib_hour_cost_sandbox"]))
    return {
        "usd_at_requested_resources": float(hours * (2 * cpu + 4 * memory)),
        "usd_at_resource_limits": float(hours * (4 * cpu + 8 * memory)),
    }


def project_report(snapshot, rates, now, tts_per_1000, scribe_per_hour):
    result = []
    for p in snapshot["projects"]:
        tasks = [t for t in snapshot["tasks"] if t["project"] == p["id"]]
        seconds = sum(
            x["seconds"] for x in snapshot["lifetimes"] if x["project"] == p["id"]
        )
        # The current service writes touched at workspace creation. It is not
        # updated on individual tool calls. Cap stale pointers at sandbox TTL.
        if p["sandbox_id"]:
            seconds += min(3600, max(0, now - p["touched"]))
        speech = {
            x["kind"]: x["amount"]
            for x in snapshot["speech"]
            if x["project"] == p["id"]
        }
        narration = speech.get("narrate", 0)
        transcription = speech.get("transcribe", 0)
        research = [
            x
            for x in snapshot.get("reference_lifetimes", [])
            if x["project"] == p["id"]
        ]
        settled = {x.get("reservation") for x in research}
        research_seconds = sum(x["seconds"] for x in research)
        research_seconds += sum(
            min(180, max(0, now - x["created"]))
            for x in snapshot.get("reference_sessions", [])
            if x["project"] == p["id"] and x.get("reservation") not in settled
        )
        research_cost = (
            Decimal(str(research_seconds))
            / 3600
            * (
                Decimal(str(rates["cpu_hour_cost_sandbox"]))
                + 2 * Decimal(str(rates["mem_gib_hour_cost_sandbox"]))
            )
        )
        result.append(
            {
                "id": p["id"],
                "title": p["title"],
                "workspace_seconds_recorded": round(seconds, 2),
                "workspace_open": bool(p["sandbox_id"]),
                "render_estimate": estimate(seconds, rates),
                "reference_browser_seconds_recorded": round(research_seconds, 3),
                "reference_browser_estimate_usd": float(research_cost),
                "reference_capture_bytes": sum(
                    x.get("bytes", 0)
                    for x in snapshot.get("reference_evidence", [])
                    if x["project"] == p["id"]
                ),
                "completed_task_seconds": sum(
                    t["amount"] or 0 for t in tasks if t["settled"]
                ),
                "reserved_task_seconds": sum(
                    t["amount"] or 0 for t in tasks if not t["settled"]
                ),
                "task_counts": {
                    s: sum(t["status"] == s for t in tasks)
                    for s in ("queued", "running", "succeeded", "failed", "cancelled")
                },
                "stored_bytes": sum(
                    o["bytes"] for o in snapshot["objects"] if o["project"] == p["id"]
                ),
                "narration_characters_reserved_or_used": narration,
                "narration_list_price_estimate_usd": narration / 1000 * tts_per_1000,
                "transcription_seconds_reserved_or_used": transcription,
                "transcription_estimate_usd": transcription / 3600 * scribe_per_hour
                if scribe_per_hour is not None
                else (0 if not transcription else None),
            }
        )
    return result


def collect(store, start, tts_per_1000=0.08, scribe_per_hour=None):
    import modal

    now = datetime.now(timezone.utc)
    snapshot = store.sql(SNAPSHOT_SQL)[0]["snapshot"]
    for field in (
        "lifetimes",
        "reference_lifetimes",
        "reference_sessions",
        "reference_evidence",
    ):
        snapshot[field] = [
            json.loads(store.vault.decrypt(x["value"].encode()))
            for x in snapshot.get(field, [])
        ]
    workspace = modal.Workspace.from_context()
    rates = {
        k: str(v)
        for k, v in workspace.billing.rates().items()
        if k.startswith(("cpu_", "mem_"))
    }
    app_id = modal.App.lookup(store.config.modal_app).app_id
    billed = [
        dict(r.items())
        for r in workspace.billing.report(start=start, resolution="h")
        if r.object_id == app_id
    ]
    baseline = Decimal(rates["cpu_hour_cost"]) * Decimal("0.25") + Decimal(
        rates["mem_gib_hour_cost"]
    )
    return {
        "observed_at": now.isoformat(),
        "app_id": app_id,
        "projects": project_report(
            snapshot, rates, now.timestamp(), tts_per_1000, scribe_per_hour
        ),
        "modal_account_rates_usd_per_hour": rates,
        "modal_reported_app_cost_usd": str(
            sum((r["cost"] for r in billed), Decimal(0))
        ),
        "modal_report_start": start.isoformat(),
        "modal_report_excludes_current_hour_after": now.replace(
            minute=0, second=0, microsecond=0
        ).isoformat(),
        "modal_report_rows": billed,
        "coordinator_minimum_usd_per_hour": str(baseline),
        "coordinator_minimum_usd_per_30_days": str(baseline * 24 * 30),
        "speech_reference": {
            "tts_model": "eleven_multilingual_v2",
            "tts_usd_per_1000_characters": tts_per_1000,
            "scribe_model": "scribe_v1",
            "scribe_usd_per_hour": scribe_per_hour,
            "list_price_checked": "2026-09-30",
            "source": "https://elevenlabs.io/pricing/api",
        },
        "limitations": [
            "Render estimates use recorded workspace wall time including idle time; startup and restart gaps can be missing. Bounds apply to recorded time only.",
            "Task allowances are reservations and are not added to workspace cost.",
            "Reference browser estimates use recorded sandbox lifetime at 1 CPU and 2 GiB including idle time, separately from rendering. Evidence bytes exclude page metadata. Startup/restart gaps and storage/network charges are not fully allocated.",
            "Modal provider reports cover completed UTC hours, may lag, and cover the shared app including earlier testing. Do not add them to the overlapping project estimates.",
            "Speech quantities can include failed-call reservations. These are list-price estimates, not account credit invoices. Scribe v1 pricing is left unknown unless supplied.",
            "InsForge subscription, dedicated backend compute, storage, bandwidth, Modal image builds, account credits, discounts and taxes are not allocated to individual videos.",
            "Claude or ChatGPT reasoning uses the connected user account. Browser Harness executes host-directed actions; this pilot makes no additional LLM inference API calls.",
        ],
    }


def write_report(report, output):
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    text = json.dumps(report, indent=2, default=str)
    pending = output / "latest.json.tmp"
    pending.write_text(text + "\n")
    pending.chmod(0o600)
    pending.replace(output / "latest.json")
    with (output / "history.jsonl").open("a") as f:
        f.write(json.dumps(report, default=str) + "\n")
    (output / "history.jsonl").chmod(0o600)
    lines = [
        "# Video use cost tracking",
        "",
        "Updated: " + report["observed_at"],
        "",
        "| Project | Recorded workspace minutes | Render estimate USD | Reference browser estimate USD | Speech estimate USD | Stored MB | Tasks running |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for p in report["projects"]:
        r = p["render_estimate"]
        speech = p["transcription_estimate_usd"]
        speech = (
            "unknown transcription rate"
            if speech is None
            else f"{speech+p['narration_list_price_estimate_usd']:.4f}"
        )
        title = p["title"].replace("|", "/").replace("\n", " ")
        lines.append(
            f"| {title} | {p['workspace_seconds_recorded']/60:.2f} | {r['usd_at_requested_resources']:.4f}–{r['usd_at_resource_limits']:.4f} | {p['reference_browser_estimate_usd']:.4f} | {speech} | {p['stored_bytes']/1e6:.2f} | {p['task_counts']['running']} |"
        )
    lines += [
        "",
        f"Modal app cost reported for completed hours: **${report['modal_reported_app_cost_usd']}** (excludes current hour; includes earlier app activity).",
        "",
        f"Always-on coordinator baseline: **${report['coordinator_minimum_usd_per_hour']}/hour**, or **${report['coordinator_minimum_usd_per_30_days']}/30 days** before credits.",
        "",
        "## Interpretation",
        "",
        *("- " + x for x in report["limitations"]),
        "",
        "[Modal pricing](https://modal.com/pricing) · [ElevenLabs pricing](https://elevenlabs.io/pricing/api)",
    ]
    (output / "latest.md").write_text("\n".join(lines) + "\n")
    (output / "latest.md").chmod(0o600)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", default=".env.pilot-production")
    parser.add_argument("--output", type=Path, default=Path(".pilot-costs"))
    parser.add_argument(
        "--start", default=datetime.now(timezone.utc).date().isoformat()
    )
    parser.add_argument("--watch-seconds", type=int, default=0)
    parser.add_argument("--interval", type=int, default=30)
    parser.add_argument("--tts-per-1000", type=float, default=0.08)
    parser.add_argument("--scribe-per-hour", type=float)
    args = parser.parse_args()
    if args.interval < 15 or args.watch_seconds < 0:
        parser.error(
            "interval must be at least 15 seconds; duration must be nonnegative"
        )
    load_dotenv(args.env, interpolate=False)
    store = Store(Config.env())
    start = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
    deadline = time.monotonic() + args.watch_seconds
    try:
        while True:
            try:
                report = collect(store, start, args.tts_per_1000, args.scribe_per_hour)
                write_report(report, args.output)
                print(report["observed_at"], "cost snapshot saved", flush=True)
            except Exception as exc:
                # Exceptions from providers may embed credentials: log class only.
                print(
                    datetime.now(timezone.utc).isoformat(),
                    "snapshot failed",
                    type(exc).__name__,
                    flush=True,
                )
                if not args.watch_seconds:
                    raise SystemExit(1) from None
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(args.interval, remaining))
    finally:
        store.http.close()


if __name__ == "__main__":
    main()
