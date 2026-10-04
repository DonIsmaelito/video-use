"""Opt-in public-media check for all three platforms, without a project database.

Runs the real isolated Modal downloader and file-transfer path. Requires Modal
credentials and incurs compute usage. URLs are explicit so removed posts can be
replaced without silently weakening the check. It does not test artistic quality.
"""

import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace

import modal

from video_use_mcp.pilot.reference_browser_image import reference_browser_image
from video_use_mcp.pilot.reference_clone import download_selected
from video_use_mcp.pilot.social_references import social_post


async def check_platforms(image, app_name, urls, output):
    os.environ["PILOT_REFERENCE_BROWSER_IMAGE"] = image.object_id
    # This test uses no customer quota or backend data. Modal accounts for the
    # actual worker usage; only the application's quota ledger is a stand-in.
    manager = SimpleNamespace(
        config=SimpleNamespace(modal_app=app_name),
        store=SimpleNamespace(reserve=lambda *a: "smoke", settle=lambda *a: None),
    )
    report = dict(
        observed_at=datetime.now(timezone.utc).isoformat(),
        image_id=image.object_id,
        platforms=[],
    )
    for platform, url in urls.items():
        target = output / platform
        target.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        item = dict(platform=platform, url=url)
        try:
            video, sheet, metadata = await download_selected(
                manager,
                "smoke",
                "smoke",
                {"url": url},
                target,
            )
            item.update(
                status="succeeded",
                video=str(video),
                contact_sheet=str(sheet),
                metadata=metadata,
            )
        except Exception as error:
            item.update(status="failed", error=str(error))
        item["elapsed_seconds"] = round(time.monotonic() - started, 2)
        report["platforms"].append(item)
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(f"{platform}: {item['status']} ({item['elapsed_seconds']}s)", flush=True)
    print(f"Report: {output / 'report.json'}", flush=True)
    return all(item["status"] == "succeeded" for item in report["platforms"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for platform in ("youtube", "tiktok", "x"):
        parser.add_argument(f"--{platform}-url", required=True)
    parser.add_argument(
        "--image-id", help="Reuse a previously built current worker image"
    )
    parser.add_argument("--app", default="video-use-reference-smoke")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    urls = {
        platform: getattr(args, f"{platform}_url")
        for platform in ("youtube", "tiktok", "x")
    }
    for platform, url in urls.items():
        if social_post(url)["platform"] != platform:
            parser.error(f"--{platform}-url must identify a {platform} post")
    output = (
        args.output or Path(tempfile.mkdtemp(prefix="video-use-platforms-"))
    ).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with modal.enable_output():
        app = modal.App.lookup(args.app, create_if_missing=True)
        image = (
            modal.Image.from_id(args.image_id)
            if args.image_id
            else reference_browser_image().build(app)
        )
        success = asyncio.run(check_platforms(image, args.app, urls, output))
    raise SystemExit(0 if success else 1)


if __name__ == "__main__":
    main()
