#!/usr/bin/env python3
"""Assemble the P2-8 side-by-side walk GIFs from walk_media.py manifests.

Generic N-up row compositor (N = 2 for the raw|locked pairs, 3 for the
rig-agnostic hero): each ``--cell label=manifest.json`` contributes one
column; frames are aligned by SOURCE frame index (the intersection, sorted),
scaled to a common cell height, and composited left-to-right in the order
given. Deterministic: same manifests in the same order = byte-identical GIF
layout. Pillow comes from the [inference] extra.

    python3 xtask/assemble_walk.py \
      --cell "raw=out/p28/metarig_raw.manifest.json" \
      --cell "locked=out/p28/metarig_locked.manifest.json" \
      --out out/p28/walk_lock_metarig.gif

Output paths are confined to cwd or the temp dir (same rule as the other
edge scripts). Label chips are drawn on each cell so no claim travels
without its name.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path


def main() -> int:
    # Confinement, inline where the analyzer can see it: EVERY path this
    # script reads or writes (CLI arguments AND paths embedded in the
    # manifests) must resolve inside the current directory or the system
    # temp dir; ``..`` segments are refused outright.
    allowed_roots = [Path.cwd().resolve(), Path(tempfile.gettempdir()).resolve()]

    def safe_path(raw: str) -> Path:
        path = Path(raw).expanduser()
        if any(part == os.pardir for part in path.parts):
            raise SystemExit(
                f"error: path must not contain {os.pardir} segments: {raw}"
            )
        resolved = path.resolve()
        if not any(resolved == base or base in resolved.parents
                   for base in allowed_roots):
            raise SystemExit(
                "error: path must be inside the current directory or the "
                f"system temp dir: {raw}"
            )
        return resolved

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cell", action="append", required=True,
        help="label=manifest.json (repeat 2-3 times; left-to-right order)",
    )
    parser.add_argument("--out", required=True, help="output GIF path")
    parser.add_argument("--fps", type=int, default=10, help="GIF frame rate")
    parser.add_argument("--cell-height", type=int, default=300)
    parser.add_argument("--gutter", type=int, default=8)
    args = parser.parse_args()

    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise SystemExit(
            f"GIF assembly needs pillow ({exc}); install with: "
            "pip install -e 'core[inference]'"
        ) from exc

    cells: list[tuple[str, dict]] = []
    for spec in args.cell:
        if "=" not in spec:
            raise SystemExit(f"error: --cell must be label=manifest.json, got {spec!r}")
        label, manifest_path = spec.split("=", 1)
        manifest = json.loads(safe_path(manifest_path).read_text(encoding="utf-8"))
        cells.append((label, manifest))
    if not 2 <= len(cells) <= 3:
        raise SystemExit(f"error: need 2-3 cells, got {len(cells)}")

    # Align by source frame index: the intersection, sorted (deterministic).
    frame_sets = [
        {entry["frame"] for entry in m["frames"]} for _label, m in cells
    ]
    order = sorted(set.intersection(*frame_sets))
    if not order:
        raise SystemExit("error: cells share no common source frame index")
    by_frame = []
    for _label, m in cells:
        table: dict[int, str] = {}
        for entry in m["frames"]:
            # Frame paths travel inside the manifests — confine them to the
            # same roots as the CLI paths (Mimosa gate: no arbitrary reads).
            table[int(entry["frame"])] = str(safe_path(str(entry["path"])))
        by_frame.append(table)
    labels = [label for label, _m in cells]

    height = args.cell_height
    scaled: list[list[Image.Image]] = [[] for _ in cells]
    for frame in order:
        row_scaled = []
        for col, paths in enumerate(by_frame):
            img = Image.open(paths[frame]).convert("RGB")
            img = img.resize((int(img.width * height / img.height), height))
            row_scaled.append(img)
        for col, img in enumerate(row_scaled):
            scaled[col].append(img)

    widths = [max(img.width for img in col_imgs) for col_imgs in scaled]
    total_w = sum(widths) + args.gutter * (len(cells) - 1)
    frames_out = []
    for i in range(len(order)):
        combo = Image.new("RGB", (total_w, height), (18, 18, 22))
        x = 0
        for col, cell_imgs in enumerate(scaled):
            img = cell_imgs[i]
            cell = Image.new("RGB", (widths[col], height), (18, 18, 22))
            cell.paste(img, (0, 0))
            draw = ImageDraw.Draw(cell)
            text = labels[col]
            bbox = draw.textbbox((0, 0), text)
            pad = 4
            draw.rectangle(
                (0, 0, bbox[2] - bbox[0] + 2 * pad, bbox[3] - bbox[1] + 2 * pad),
                fill=(18, 18, 22),
            )
            draw.text((pad, pad), text, fill=(235, 235, 235))
            combo.paste(cell, (x, 0))
            x += widths[col] + args.gutter
        frames_out.append(combo)

    out = safe_path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    duration = max(int(1000 / max(args.fps, 1)), 20)
    frames_out[0].save(
        out, save_all=True, append_images=frames_out[1:], duration=duration, loop=0,
    )
    print(
        f"WALK GIF written: {out} ({len(frames_out)} frames x {len(cells)} cells, "
        f"{args.fps} fps, labels={labels})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
