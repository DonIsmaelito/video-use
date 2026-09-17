"""Contact sheets labeled with decoded source frame indices and presentation times."""

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from source_scan import catalog, selected_frames
from edit_io import save_json


# build paginated thumbnails with labels tied to decoded source frames
def build(source, out, frames=None, every=1, width=320, columns=5):
    index = catalog(source)
    rows = index["frames"]
    if every <= 0 or width < 32 or columns < 1:
        raise ValueError("invalid sheet geometry or sample interval")
    if frames is None:
        frames = []
        next_time = rows[0]["pts"]
        for row in rows:
            if row["pts"] >= next_time:
                frames.append(row["frame"])
                next_time = row["pts"] + every
    if not frames or min(frames) < 0 or max(frames) >= len(rows):
        raise ValueError("selected frame is outside source")
    out = Path(out)
    if out.resolve() == Path(source).resolve():
        raise ValueError("sheet cannot overwrite source")
    out.parent.mkdir(parents=True, exist_ok=True)
    font = ImageFont.load_default()
    page = []
    paths = []
    page_size = columns * 6

    # write one page without retaining thumbnails for the whole video
    def flush(items):
        h = items[0][1].height
        sheet = Image.new(
            "RGB",
            (columns * width, math.ceil(len(items) / columns) * (h + 24)),
            "#151515",
        )
        draw = ImageDraw.Draw(sheet)
        for i, (frame, im) in enumerate(items):
            x = i % columns * width
            y = i // columns * (h + 24)
            sheet.paste(im, (x, y + 24))
            draw.text(
                (x + 3, y + 4),
                f'f{frame}  PTS {rows[frame]["pts"]:.6f}s',
                font=font,
                fill="white",
            )
        target = (
            out
            if not paths
            else out.with_name(f"{out.stem}_{len(paths)+1:03}{out.suffix}")
        )
        sheet.save(target)
        paths.append(str(target))

    for item in selected_frames(source, frames, width):
        page.append(item)
        if len(page) == page_size:
            flush(page)
            page = []
    if page:
        flush(page)
    result = {
        "source_sha256": index["sha256"],
        "frames": [rows[f] for f in sorted(set(frames))],
        "sheets": paths,
        "visual_review": "pending",
    }
    save_json(str(out) + ".json", result)
    return result


# parse source and contact sheet options while surfacing media errors clearly
def main():
    """Write a paginated contact sheet and its source-frame manifest."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("-o", "--out", required=True)
    parser.add_argument("--frames", type=int, nargs="+")
    parser.add_argument("--every", type=float, default=1)
    parser.add_argument("--width", type=int, default=320)
    parser.add_argument("--columns", type=int, default=5)
    args = parser.parse_args()
    try:
        result = build(
            args.source, args.out, args.frames, args.every, args.width, args.columns
        )
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(1, f"sheet: {exc}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
