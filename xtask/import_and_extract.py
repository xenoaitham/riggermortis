#!/usr/bin/env python
"""Headless Blender edge script: import a model file, dump armatures as JSON.

Run inside Blender (self-contained, like the bridge scripts — no riggermortis
import, Blender's bundled Python may not have the package):

    blender -b --python xtask/import_and_extract.py -- model.vrm out.rig.json [--rig NAME]

Accepts any format Blender's importers handle: .glb/.gltf/.vrm (VRM is glTF 2.0
— the stock glTF importer brings in the ``J_Bip_*`` armature without any VRM
add-on) and .fbx. Output JSON matches the bridge schema and feeds
:func:`riggermortis.load_rig`.
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
        raise SystemExit(f"error: output path must not contain {os.pardir} segments: {raw}")
    resolved = path.resolve()
    allowed = [Path.cwd().resolve(), Path(tempfile.gettempdir()).resolve()]
    if not any(resolved == base or base in resolved.parents for base in allowed):
        raise SystemExit(
            "error: output path must be inside the current directory or the system temp "
            f"dir: {raw}"
        )
    return resolved


def _parse_args(argv: list[str]) -> tuple[str, str, str | None]:
    if not argv:
        print("usage: import_and_extract.py <model> <out.json> [--rig NAME]", file=sys.stderr)
        raise SystemExit(64)
    model = argv[0]
    out = argv[1] if len(argv) > 1 else None
    rig = None
    i = 2
    while i < len(argv):
        if argv[i] == "--rig" and i + 1 < len(argv):
            rig = argv[i + 1]
            i += 2
        else:
            i += 1
    if out is None:
        print("error: missing <out.json> argument", file=sys.stderr)
        raise SystemExit(64)
    return model, out, rig


def _import_model(path: str) -> None:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".glb", ".gltf", ".vrm"):
        bpy.ops.import_scene.gltf(filepath=path)  # type: ignore[name-defined]
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)  # type: ignore[name-defined]
    else:
        print(f"error: unsupported import type {ext!r} (supported: .glb .gltf .vrm .fbx)", file=sys.stderr)
        raise SystemExit(64)


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
        rigs.append({"name": obj.name, "source": "blender-import", "bones": bones})
    return rigs


def main() -> int:
    model, out, rig_filter = _parse_args(
        sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    )
    if not os.path.isfile(model):
        print(f"error: no such file: {model}", file=sys.stderr)
        return 66
    _import_model(model)
    rigs = collect(rig_filter)
    if not rigs:
        available = [o.name for o in bpy.data.objects if o.type == "ARMATURE"]  # type: ignore[name-defined]
        if rig_filter:
            print(
                f"import_and_extract: no armature named {rig_filter!r}; "
                f"available: {', '.join(available) or '(none)'}",
                file=sys.stderr,
            )
        else:
            print("import_and_extract: no armatures found in imported file", file=sys.stderr)
        return 3
    payload = {"format": 1, "source": "blender-import", "rigs": rigs}
    text = json.dumps(payload, indent=2, sort_keys=True)
    out_path = _safe_out_path(out)
    out_path.write_text(text, encoding="utf-8")
    print(f"import_and_extract: wrote {len(rigs)} rig(s) to {out}")
    return 0


if __name__ == "__main__":
    import bpy  # type: ignore[name-defined]  # noqa: E402  (only exists inside Blender)

    sys.exit(main())
