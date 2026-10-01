"""Package local Three.js modules and render the original 3D proof.

python tests/fixtures/browser_workflows/render_product_3d.py
Default evidence directory: .pilot-workflow-proofs/product-3d (gitignored).
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir")
    parser.add_argument("--chrome")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[3]
    runtime = repo / "skills/motion-design/runtime"
    package = runtime / "node_modules/three"
    if json.loads((package / "package.json").read_text())["version"] != "0.186.0":
        raise RuntimeError("This proof requires the pinned Three.js 0.186.0 runtime")
    output = Path(
        args.output_dir or repo / ".pilot-workflow-proofs/product-3d"
    ).resolve()
    vendor = output / "vendor/three"
    (vendor / "addons/environments").mkdir(parents=True, exist_ok=True)
    for name in ["three.module.js", "three.core.js"]:
        shutil.copy2(package / "build" / name, vendor / name)
    shutil.copy2(package / "LICENSE", vendor / "LICENSE")
    shutil.copy2(
        package / "examples/jsm/environments/RoomEnvironment.js",
        vendor / "addons/environments/RoomEnvironment.js",
    )
    shutil.copy2(
        Path(__file__).with_name("product_3d.html"), output / "product_3d.html"
    )
    (output / "contract.json").write_text(
        json.dumps(
            {
                "exact_request": "A polished original procedural 3D speaker assembly proof",
                "premise": "A compact speaker opens along its acoustic axis to expose the copper coil and graphite cone",
                "impression": "Tactile and understandable product construction",
                "palette": "Warm stone background, muted green metal shell, graphite driver and copper winding",
                "hero_frame_seconds": 2.5,
                "rhythm": "0–0.28 assembled recognition; 0.28–1.95 staggered separation; 1.95–3 exploded hold",
                "assets": "Original procedural geometry; Three.js 0.186.0 including RoomEnvironment under MIT",
                "limits": "Stylized nonengineering model; silent 640x360 12fps proof, not a production video or reusable creative template",
                "failure_conditions": [
                    "parts overlap enough to hide the coil",
                    "no visible 3D depth",
                    "clipped silhouettes",
                    "nonrepeatable seeks",
                ],
            },
            indent=2,
        )
        + "\n"
    )
    command = [
        "node",
        str(repo / "helpers/motion_render.mjs"),
        str(output / "product_3d.html"),
        "-o",
        str(output / "product_3d.mp4"),
        "--duration",
        "3",
        "--width",
        "640",
        "--height",
        "360",
        "--fps",
        "12",
        "--deps",
        str(runtime),
        "--stills",
        "0,0.75,1.5,2.5,2.9166666667",
        "--poster-time",
        "2.5",
        "--overwrite",
    ]
    if args.chrome:
        command += ["--chrome", args.chrome]
    subprocess.run(command, check=True)
    subprocess.run(
        [
            sys.executable,
            str(repo / "helpers/motion_qa.py"),
            str(output / "product_3d.mp4"),
            "--expect-width",
            "640",
            "--expect-height",
            "360",
            "--expect-fps",
            "12",
            "--expect-duration",
            "3",
        ],
        check=True,
    )
    print(json.dumps({"project": str(output), "video": str(output / "product_3d.mp4")}))


if __name__ == "__main__":
    main()
