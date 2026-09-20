"""Build the exact checkout's worker image, then deploy its coordinator."""

import os

import modal

from .sandbox import worker_image


def main():
    with modal.enable_output():
        build_app = modal.App.lookup("video-use-mcp", create_if_missing=True)
        runtime = worker_image().build(build_app)
        # Carry an immutable image ID into the coordinator. Image definitions
        # containing local paths cannot be rebuilt from a remote API container.
        os.environ["VIDEO_USE_RUNTIME_IMAGE"] = runtime.object_id
        from .deploy_modal import app

        app.deploy()


if __name__ == "__main__":
    main()
