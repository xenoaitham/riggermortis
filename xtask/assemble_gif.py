#!/usr/bin/env python
"""Assemble the BOOM GIF from render_demos.py frames (system Python, pillow).

Reads <out>/boom/manifest.json, composites each rest/posed frame pair
side-by-side ("before | after"), downscales, and writes <out>/boom.gif.

    python3 xtask/assemble_gif.py --manifest media/boom/manifest.json --out media/boom.gif

Output paths are confined to cwd or the temp dir (Mimosa gate, same rule as
the other edge scripts). Pillow comes from the [inference] extra.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path


def _safe_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    if any(part == os.pardir for part in path.parts):
        raise SystemExit(f"error: path must not contain {os.pardir} segments: {raw}")
    resolved = path.resolve()
    allowed = [Path.cwd().resolve(), Path(tempfile.gettempdir()).resolve()]
    if not any(resolved == base or base in resolved.parents for base in allowed):
        raise SystemExit(
            "error: path must be inside the current directory or the system "
            f"temp dir: {raw}"
        )
    return resolved


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, help="path to boom/manifest.json")
    parser.add_argument("--out", default="media/boom.gif", help="output GIF path")
    parser.add_argument("--fps", type=int, default=8, help="GIF frame rate")
    parser.add_argument("--width", type=int, default=960, help="output GIF width")
    args = parser.parse_args(argv)

    try:
        from PIL import Image
    except ImportError as exc:
        raise SystemExit(
            f"GIF assembly needs pillow ({exc}); install with: "
            "pip install -e 'core[inference]'"
        ) from exc

    manifest_path = _safe_path(args.manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rest, posed = manifest["rest"], manifest["posed"]
    if len(rest) != len(posed) or not rest:
        raise SystemExit(f"manifest mismatch: {len(rest)} rest vs {len(posed)} posed frames")

    out = _safe_path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    frames = []
    for a_path, b_path in zip(rest, posed, strict=True):
        a, b = Image.open(a_path), Image.open(b_path)
        h = min(a.height, b.height)
        a = a.resize((int(a.width * h / a.height), h))
        b = b.resize((int(b.width * h / b.height), h))
        combo = Image.new("RGB", (a.width + b.width + 8, h), (18, 18, 22))
        combo.paste(a, (0, 0))
        combo.paste(b, (a.width + 8, 0))
        scale = args.width / combo.width
        frames.append(combo.resize((args.width, int(combo.height * scale))))

    duration = max(int(1000 / max(args.fps, 1)), 20)
    frames[0].save(
        out, save_all=True, append_images=frames[1:], duration=duration, loop=0,
    )
    print(f"BOOM GIF written: {out} ({len(frames)} frames, {args.fps} fps)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
