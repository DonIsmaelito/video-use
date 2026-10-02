"""Build the checked-out harness and deploy the isolated pilot coordinator."""

import os
import subprocess
import time
import modal
from dotenv import load_dotenv
from video_use_mcp.config import ROOT
from video_use_mcp.sandbox import worker_image
from .config import Config
from .store import Store
from .reference_browser_image import reference_browser_image


def ensure_quiet(store):
    if store.sql(
        "SELECT id FROM public.vp_tasks WHERE status IN ('queued','running') LIMIT 1"
    ):
        raise RuntimeError("Deployment deferred: a video task is running")
    if store.sql(
        "SELECT id FROM public.vp_projects WHERE sandbox_id IS NOT NULL LIMIT 1"
    ):
        raise RuntimeError(
            "Deployment deferred: a project workspace is still active between calls. Finish or close it first."
        )
    if store.sql(
        "SELECT key FROM public.vp_kv WHERE kind=$1 AND expires > $2 LIMIT 1",
        "reference_browser_session",
        time.time(),
    ):
        raise RuntimeError(
            "Deployment deferred: a reference browser session is still active. Close it or let it expire first."
        )


def main():
    load_dotenv(ROOT / ".env.pilot-production", interpolate=False)
    store = Store(Config.env())
    ensure_quiet(store)
    with modal.enable_output():
        build_app = modal.App.lookup("video-use-browser-pilot", create_if_missing=True)
        runtime = worker_image().build(build_app)
        reference_browser = reference_browser_image().build(build_app)
        os.environ["PILOT_RUNTIME_IMAGE"] = runtime.object_id
        os.environ["PILOT_REFERENCE_BROWSER_IMAGE"] = reference_browser.object_id
        os.environ["PILOT_HARNESS_VERSION"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        from .deployment import app

        # Recheck after the image build; a user may have started a project meanwhile.
        ensure_quiet(store)
        if store.get("control", "paused"):
            raise RuntimeError(
                "Execution is paused by the owner; preserve that control setting"
            )
        store.put("control", "paused", True, ttl=600)
        try:
            ensure_quiet(store)
            app.deploy()
        finally:
            store.put("control", "paused", False)
            store.http.close()


if __name__ == "__main__":
    main()
