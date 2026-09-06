#!/usr/bin/env python
"""Headless Blender bridge: dump armature data from a .blend file as JSON.

Run inside Blender (any Python it bundles works, no riggermortis import needed):

    blender -b model.blend -P blender_extract.py -- --out /tmp/rig.json

The output feeds :func:`riggermortis.load_rig`. This script must stay
self-contained — it runs in Blender's interpreter, which may not have the
package installed.
"""
from __future__ import annotations

import json
import sys


def _parse_args(argv: list[str]) -> tuple[str | None]:
    out = None
    i = 0
    while i < len(argv):
        if argv[i] == "--out" and i + 1 < len(argv):
            out = argv[i + 1]
            i += 2
        else:
            i += 1
    return (out,)


def collect() -> list[dict[str, object]]:
    rigs: list[dict[str, object]] = []
    for obj in bpy.data.objects:  # type: ignore[name-defined]
        if obj.type != "ARMATURE":
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
    (out,) = _parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    rigs = collect()
    if not rigs:
        print("blender_extract: no armature objects found in file", file=sys.stderr)
        return 3
    payload = {"format": 1, "source": "blender", "rigs": rigs}
    text = json.dumps(payload, indent=2, sort_keys=True)
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"blender_extract: wrote {len(rigs)} rig(s) to {out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    import bpy  # type: ignore[name-defined]  # noqa: E402  (only exists inside Blender)

    sys.exit(main())
