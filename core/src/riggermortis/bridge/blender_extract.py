#!/usr/bin/env python
"""Headless Blender bridge: dump armature data from a .blend file as JSON.

Run inside Blender (any Python it bundles works, no riggermortis import needed):

    blender -b model.blend -P blender_extract.py -- --out /tmp/rig.json [--rig NAME]

The output feeds :func:`riggermortis.load_rig`. This script must stay
self-contained — it runs in Blender's interpreter, which may not have the
package installed.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


def _safe_out_path(raw: str) -> Path:
    """Normalize the requested output path and confine where it may land.

    This edge script runs with user-provided CLI arguments, so the output is
    restricted to the current working directory or the system temp dir, with
    parent-walk segments refused outright.
    """
    path = Path(raw).expanduser()
    if any(part == os.pardir for part in path.parts):
        raise SystemExit(f"error: --out must not contain {os.pardir} segments: {raw}")
    resolved = path.resolve()
    allowed = [Path.cwd().resolve(), Path(tempfile.gettempdir()).resolve()]
    if not any(resolved == base or base in resolved.parents for base in allowed):
        raise SystemExit(
            "error: --out must be inside the current directory or the system temp dir: "
            f"{raw}"
        )
    return resolved


def _parse_args(argv: list[str]) -> tuple[str | None, str | None]:
    out = None
    rig = None
    i = 0
    while i < len(argv):
        if argv[i] == "--out" and i + 1 < len(argv):
            out = argv[i + 1]
            i += 2
        elif argv[i] == "--rig" and i + 1 < len(argv):
            rig = argv[i + 1]
            i += 2
        else:
            i += 1
    return (out, rig)


def collect(rig_filter: str | None = None) -> list[dict[str, object]]:
    rigs: list[dict[str, object]] = []
    for obj in bpy.data.objects:  # type: ignore[name-defined]
        if obj.type != "ARMATURE":
            continue
        if rig_filter is not None and obj.name != rig_filter:
            continue
        bones = []
        for b in obj.data.bones:
            parent = b.parent.name if b.parent is not None else None
            bones.append(
                {
                    "name": b.name,
                    "parent": parent,
                    "head": [round(v, 6) for v in b.head_local],
                    "tail": [round(v, 6) for v in b.tail_local],
                }
            )
        rigs.append({"name": obj.name, "source": "blender", "bones": bones})
    return rigs


def main() -> int:
    out, rig_filter = _parse_args(
        sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    )
    rigs = collect(rig_filter)
    if not rigs:
        available = [o.name for o in bpy.data.objects if o.type == "ARMATURE"]  # type: ignore[name-defined]
        if rig_filter:
            print(
                f"blender_extract: no armature named {rig_filter!r}; "
                f"available: {', '.join(available) or '(none)'}",
                file=sys.stderr,
            )
        else:
            print("blender_extract: no armature objects found in file", file=sys.stderr)
        return 3
    payload = {"format": 1, "source": "blender", "rigs": rigs}
    text = json.dumps(payload, indent=2, sort_keys=True)
    if out:
        out_path = _safe_out_path(out)
        out_path.write_text(text, encoding="utf-8")
        print(f"blender_extract: wrote {len(rigs)} rig(s) to {out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    import bpy  # type: ignore[name-defined]  # noqa: E402  (only exists inside Blender)

    sys.exit(main())
