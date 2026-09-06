"""Rig loading for the core library.

The library is deliberately process-free: :func:`load_rig` reads the native
JSON rig format. ``.blend`` files are converted to that format out-of-process
by the bundled bridge (see ``xtask/extract_blend.sh`` or run
``core/src/riggermortis/bridge/blender_extract.py`` inside Blender), which
keeps the importable core safe to embed (the add-on runs it inside Blender,
the MCP server may run it inside a sandbox) and keeps every process spawn in
auditable edge scripts. Everything stays local: no network access happens in
this module — the CI network-audit test relies on that.
"""
from __future__ import annotations

import json
from pathlib import Path

from .errors import RigLoadError
from .types import RigData

BLEND_SUFFIXES = {".blend", ".blend1"}


def load_rig(path: str | Path) -> RigData:
    p = Path(path)
    if not p.exists():
        raise RigLoadError(f"file not found: {p}")
    suffix = p.suffix.lower()
    if suffix == ".json":
        return RigData.from_json(p)
    if suffix in BLEND_SUFFIXES:
        raise RigLoadError(
            f"the core library reads rig JSON only; {p.name} is a Blender file",
            hint=(
                "convert it first, fully local: "
                "xtask/extract_blend.sh model.blend model.rig.json  (uses your own Blender)"
            ),
        )
    raise RigLoadError(
        f"unsupported rig file type {suffix!r}: {p.name}",
        hint="supported: .json (rig data; export .blend via xtask/extract_blend.sh)",
    )


def write_rig(rig: RigData, path: str | Path) -> Path:
    return rig.to_json(path)


def load_rig_json_text(text: str) -> RigData:
    """Parse a rig from JSON text (bridge stdout, MCP payloads, tests)."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RigLoadError(f"invalid rig JSON: {exc}") from exc
    if isinstance(data, dict) and "rigs" in data:
        rigs = data["rigs"]
        if len(rigs) > 1:
            names = ", ".join(str(r.get("name", "?")) for r in rigs)
            raise RigLoadError(
                f"payload contains {len(rigs)} armatures ({names})",
                hint="export a single armature or pick one via the add-on",
            )
        data = rigs[0]
    return RigData.from_dict(data)
