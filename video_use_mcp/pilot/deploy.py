"""Build the checked-out harness and deploy the isolated pilot coordinator."""

import os
import subprocess
import modal
from video_use_mcp.config import ROOT
from video_use_mcp.sandbox import worker_image


def main():
    with modal.enable_output():
        runtime = worker_image().build(
            modal.App.lookup("video-use-browser-pilot", create_if_missing=True)
        )
        os.environ["PILOT_RUNTIME_IMAGE"] = runtime.object_id
        os.environ["PILOT_HARNESS_VERSION"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        from .deployment import app

        app.deploy()


if __name__ == "__main__":
    main()
