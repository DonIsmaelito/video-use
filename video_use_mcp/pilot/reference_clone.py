"""Selected-reference acquisition and durable handoff to the cloning workflow."""

import asyncio
import hashlib
import json
import math
import os
import tempfile
import time
from copy import deepcopy
from pathlib import Path

from .creative_state import creative_lock
from .reference_direction import public_reference_url
from .sources import save_source

CLONE_GUIDE = "skills/video-workflows/reference-cloning.md"
DOWNLOAD_SECONDS = 300


def file_sha256(path):
    """Hash bounded media without allocating the whole video in coordinator RAM."""
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def selection_key(reference):
    """Bind work to a particular offer, selection and requested treatment."""
    return hashlib.sha256(
        json.dumps(
            {
                "round": (reference.get("rounds") or [{}])[-1].get("id")
                or reference.get("round_id"),
                "selected": reference.get("selected_references", []),
                "direction": reference.get("direction", ""),
                "user_message": reference.get("user_message", ""),
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()


def selected_reference(state, reference_id, expected_key=None):
    direction = (state or {}).get("intake", {}).get("reference_direction", {})
    if direction.get("status") != "accepted":
        raise ValueError("Choose a reference before downloading it")
    key = selection_key(direction)
    if expected_key and key != expected_key:
        raise ValueError(
            "Reference selection changed; read get_video_project before continuing"
        )
    reference = next(
        (
            r
            for r in direction.get("selected_references", [])
            if r["id"] == reference_id
        ),
        None,
    )
    if reference is None:
        raise ValueError("Download only a reference selected in this project")
    return direction, reference, key


def clone_context(direction, project_id=None):
    if direction.get("status") != "accepted":
        return None
    clone = direction.get("clone")
    if not clone:
        return None  # Earlier projects retain their already-approved workflow.
    media = (
        clone.get("media", {})
        if clone.get("selection_key") == selection_key(direction)
        else {}
    )
    pending = [
        r["id"] for r in direction["selected_references"] if r["id"] not in media
    ]
    return dict(
        version=1,
        selection_key=selection_key(direction),
        status="download_required" if pending else "ready_for_analysis",
        media=deepcopy(media),
        pending_reference_ids=pending,
        guidance=CLONE_GUIDE,
        prepare=[
            dict(
                name="prepare_video_reference",
                arguments=dict(project_id=project_id, reference_id=rid),
            )
            for rid in pending
        ]
        if project_id
        else [],
        next_action=(
            "Call prepare_video_reference for each selected reference. Wait for successful tasks; a link or thumbnail cannot replace the downloaded video. "
            if pending
            else "Read video_use_guidance topic=reference-cloning and inspect the saved contact sheets with view_video_frame. "
        )
        + "Measure the downloaded reference before planning. Save edit/reference-breakdown.md with timed beats, treatment and reference-to-brief substitutions. Recreate its structure, rhythm and visual mechanisms with the user's content. Render one representative snippet, compare it to the source, show_video_preview once, then show_video_checkpoint. Refine until explicitly accepted, then extend the accepted source to finish the full video.",
    )


def require_clone_download(state, operation):
    direction = (state or {}).get("intake", {}).get("reference_direction", {})
    context = clone_context(direction)
    if (
        context
        and context["pending_reference_ids"]
        and operation in {"step", "run", "narrate", "export"}
    ):
        raise ValueError(
            "Download the selected reference with prepare_video_reference before cloning the snippet. "
            + context["next_action"]
        )


async def download_selected(
    manager, uid, pid, reference, local_dir, source_object_id=""
):
    """Acquire/probe in a separate worker; only validated files reach production."""
    import modal

    from video_use_mcp.sandbox import ModalSandbox

    from .reference_browser_image import public_ipv4_allowlist

    image_id = os.getenv("PILOT_REFERENCE_BROWSER_IMAGE")
    if not image_id:
        raise ValueError("Reference download worker is not deployed")
    upload = None
    if source_object_id:
        rows = manager.store.sql(
            "SELECT * FROM public.vp_objects WHERE id=$1 AND owner=$2 AND project=$3 AND kind='source'",
            source_object_id,
            uid,
            pid,
        )
        if not rows:
            raise ValueError("Choose an uploaded source belonging to this project")
        upload = local_dir / "uploaded.mp4"
        await asyncio.to_thread(manager.store.download, rows[0]["key"], upload)
        if not 0 < upload.stat().st_size <= 200_000_000:
            raise ValueError("Uploaded reference is empty or exceeds 200 MB")
    # Only a persisted selected URL is accepted, never arbitrary caller commands.
    url = public_reference_url(reference["url"])
    reservation = manager.store.reserve(
        uid, "compute", DOWNLOAD_SECONDS, "reference-download-" + os.urandom(12).hex()
    )
    worker = None
    started = time.monotonic()
    try:
        app = await modal.App.lookup.aio(
            manager.config.modal_app, create_if_missing=True
        )
        worker = await modal.Sandbox.create.aio(
            app=app,
            image=modal.Image.from_id(image_id),
            timeout=DOWNLOAD_SECONDS,
            idle_timeout=60,
            cpu=1,
            memory=2048,
            workdir="/workspace",
            include_oidc_identity_token=False,
            outbound_cidr_allowlist=public_ipv4_allowlist(),
        )
        wrapper = ModalSandbox(manager.config)
        wrapper.instance = worker
        if upload:
            await wrapper.upload("reference-download/uploaded.mp4", upload)
        process = await worker.exec.aio(
            "python",
            "-m",
            "video_use_mcp.pilot.reference_download_worker",
            timeout=DOWNLOAD_SECONDS - 15,
            workdir="/workspace",
        )
        process.stdin.write(json.dumps(dict(url=url, uploaded=bool(upload))).encode())
        process.stdin.write_eof()
        await process.stdin.drain.aio()

        async def drain(stream):
            text = ""
            async for chunk in stream:
                text = (text + chunk)[-16000:]
            return text

        stdout, _ = await asyncio.gather(drain(process.stdout), drain(process.stderr))
        code = await process.wait.aio()
        try:
            result = json.loads(stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            raise ValueError(
                "Reference download did not return a verified media file"
            ) from None
        if code or result.get("error"):
            raise ValueError(
                "Reference download failed. Ask for an uploaded copy and retry with source_object_id, or choose another accessible reference. No snippet was generated."
            )
        name = result.get("filename", "")
        if name != Path(name).name or Path(name).suffix not in {
            ".mp4",
            ".webm",
            ".mkv",
            ".mov",
        }:
            raise ValueError("Invalid downloaded reference filename")
        target = local_dir / ("video" + Path(name).suffix)
        await wrapper.download("reference-download/" + name, target, 200_000_000)
        sheet = local_dir / "sheet.jpg"
        await wrapper.download("reference-download/contact-sheet.jpg", sheet, 3_000_000)
        actual = await asyncio.to_thread(file_sha256, target)
        if actual != result.get("sha256") or target.stat().st_size != result.get(
            "size"
        ):
            raise ValueError("Reference transfer failed integrity verification")
        return target, sheet, result
    finally:
        try:
            if worker:
                await worker.terminate.aio()
        finally:
            manager.store.settle(
                reservation,
                min(DOWNLOAD_SECONDS, math.ceil(time.monotonic() - started))
                if worker
                else 0,
            )


async def prepare_reference(manager, task, sb):
    """Persist reference assets; stale work must never replace a new choice."""
    uid, pid = task["owner"], task["project"]
    payload = task["payload"]
    direction, reference, key = selected_reference(
        manager.store.get("creative", pid),
        payload["reference_id"],
        payload["selection_key"],
    )
    previous_clone = direction.get("clone", {})
    previous = (
        previous_clone.get("media", {}).get(reference["id"])
        if previous_clone.get("selection_key") == key
        else None
    )
    if previous:
        if payload.get("source_object_id", "") != previous.get("source_object_id", ""):
            raise ValueError(
                "Reference already acquired; select it again before replacing its source copy"
            )
        return dict(
            reference=deepcopy(previous),
            cached=True,
            clone=clone_context(direction, pid),
        )
    with tempfile.TemporaryDirectory() as tmp:
        video, sheet, metadata = await download_selected(
            manager, uid, pid, reference, Path(tmp), payload.get("source_object_id", "")
        )
        selected_reference(manager.store.get("creative", pid), reference["id"], key)

        async def persist(path, name):
            existing = manager.store.sql(
                "SELECT * FROM public.vp_objects WHERE project=$1 AND owner=$2 AND kind='source' AND name=$3",
                pid,
                uid,
                name,
            )
            if existing:
                # Verify bytes before trusting an existing content-addressed filename.
                recovered = Path(tmp) / ("existing-" + name)
                await asyncio.to_thread(
                    manager.store.download, existing[0]["key"], recovered
                )
                if recovered.stat().st_size != path.stat().st_size or file_sha256(
                    recovered
                ) != file_sha256(path):
                    raise ValueError(
                        "An existing reference source failed integrity verification"
                    )
                return dict(
                    id=existing[0]["id"],
                    name=name,
                    path="sources/" + name,
                    size=existing[0]["size"],
                )
            return await save_source(manager.store, manager, uid, pid, name, path)

        prefix = "reference-" + metadata["sha256"]
        source = await persist(video, prefix + video.suffix)
        sheet_sha = hashlib.sha256(sheet.read_bytes()).hexdigest()
        sheet_source = await persist(sheet, "reference-sheet-" + sheet_sha + ".jpg")
        # Explicit upload also covers a cached object after workspace recreation.
        await sb.upload(source["path"], video)
        await sb.upload(sheet_source["path"], sheet)
        receipt = dict(
            reference_id=reference["id"],
            url=reference["url"],
            source=source,
            contact_sheet=sheet_source,
            metadata=metadata,
            usage="analysis_reference",
            source_object_id=payload.get("source_object_id", ""),
        )
        manager.store.put("source_provenance", source["id"], receipt)
        with creative_lock(pid):
            state = manager.store.get("creative", pid)
            direction, _, _ = selected_reference(state, reference["id"], key)
            if direction.get("clone", {}).get("selection_key") != key:
                direction["clone"] = dict(version=1, selection_key=key, media={})
            clone = direction["clone"]
            clone["media"][reference["id"]] = receipt
            manager.store.put("creative", pid, state)
        await sb.write(
            "edit/reference-clone.json",
            json.dumps(
                {
                    "brief": state.get("brief"),
                    "preferences": state.get("preferences"),
                    "direction": direction.get("direction"),
                    "references": clone["media"],
                    "guidance": CLONE_GUIDE,
                },
                ensure_ascii=False,
                indent=2,
            ).encode(),
        )
        return dict(
            reference=receipt,
            clone=clone_context(direction, pid),
            next_action="Inspect the contact sheet with view_video_frame, then read video_use_guidance topic=reference-cloning. Measure dense cut/motion windows from the downloaded source and save the adapted breakdown before rendering the snippet.",
        )
