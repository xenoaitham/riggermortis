"""Rig data model.

``RigData`` is the Blender-independent exchange format for armatures. The
add-on builds it straight from ``bpy`` armatures, the headless bridge dumps it
as JSON from a ``.blend`` file, and tests construct synthetic rigs directly.
Everything downstream (mapper, presets, pose application) consumes this and
never touches Blender.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from .errors import RigLoadError
from .linalg import Vec3

FORMAT_VERSION = 1


@dataclass
class BoneData:
    """One bone: name, parent, and joint locations in armature space (meters)."""

    name: str
    head: Vec3
    tail: Vec3
    parent: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "parent": self.parent,
            "head": list(self.head),
            "tail": list(self.tail),
        }

    @staticmethod
    def from_dict(d: dict[str, object]) -> BoneData:
        try:
            return BoneData(
                name=str(d["name"]),
                parent=(str(d["parent"]) if d.get("parent") is not None else None),
                head=(float(d["head"][0]), float(d["head"][1]), float(d["head"][2])),  # type: ignore[index]
                tail=(float(d["tail"][0]), float(d["tail"][1]), float(d["tail"][2])),  # type: ignore[index]
            )
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise RigLoadError(f"malformed bone entry: {exc}", hint="regenerate the rig JSON") from exc


@dataclass
class RigData:
    """An armature: bones keyed by name plus lightweight metadata."""

    name: str
    bones: dict[str, BoneData] = field(default_factory=dict)
    source: str = "synthetic"
    metadata: dict[str, object] = field(default_factory=dict)

    # -- structure ---------------------------------------------------------

    def sorted_bone_names(self) -> list[str]:
        return sorted(self.bones)

    def children(self, name: str) -> list[str]:
        return sorted(b.name for b in self.bones.values() if b.parent == name)

    def roots(self) -> list[str]:
        return sorted(b.name for b in self.bones.values() if b.parent is None or b.parent not in self.bones)

    def height(self) -> float:
        zs = [v for b in self.bones.values() for v in (b.head[2], b.tail[2])]
        return max(zs) - min(zs) if zs else 0.0

    def chain_depth(self, name: str) -> int:
        depth = 0
        seen: set[str] = set()
        cur = self.bones.get(name)
        while cur is not None and cur.parent and cur.parent in self.bones and cur.parent not in seen:
            seen.add(cur.name)
            cur = self.bones[cur.parent]
            depth += 1
        return depth

    # -- identity ----------------------------------------------------------

    def fingerprint(self) -> str:
        """Stable hash of bone names, parents and joint positions.

        Presets are keyed on this: if the rig changes, saved mappings are
        flagged instead of silently applied.
        """
        lines = []
        for name in self.sorted_bone_names():
            b = self.bones[name]
            coords = tuple(round(v, 4) for v in (*b.head, *b.tail))
            lines.append(f"{name}\t{b.parent}\t{coords}")
        payload = "\n".join(lines).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:16]

    # -- (de)serialisation ---------------------------------------------------

    def to_dict(self) -> dict[str, object]:
        return {
            "format": FORMAT_VERSION,
            "name": self.name,
            "source": self.source,
            "metadata": self.metadata,
            "bones": [self.bones[n].to_dict() for n in self.sorted_bone_names()],
        }

    def to_json(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return p

    @staticmethod
    def from_dict(d: dict[str, object]) -> RigData:
        fmt = d.get("format", 1)
        if int(fmt) != FORMAT_VERSION:  # type: ignore[arg-type]
            raise RigLoadError(
                f"unsupported rig format {fmt}",
                hint=f"this build reads format {FORMAT_VERSION}",
            )
        bones: dict[str, BoneData] = {}
        for entry in d.get("bones", []):  # type: ignore[union-attr]
            b = BoneData.from_dict(entry)  # type: ignore[arg-type]
            if b.name in bones:
                raise RigLoadError(f"duplicate bone name {b.name!r}")
            bones[b.name] = b
        if not bones:
            raise RigLoadError("rig contains no bones", hint="was the right armature exported?")
        rig = RigData(
            name=str(d.get("name", "rig")),
            bones=bones,
            source=str(d.get("source", "json")),
            metadata=dict(d.get("metadata", {})),  # type: ignore[arg-type]
        )
        # Dangling parents (e.g. filtered export) are demoted to roots, loudly.
        for b in bones.values():
            if b.parent is not None and b.parent not in bones:
                b.parent = None
        return rig

    @staticmethod
    def from_json(path: str | Path) -> RigData:
        p = Path(path)
        if not p.exists():
            raise RigLoadError(f"file not found: {p}")
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RigLoadError(f"invalid JSON in {p}: {exc}") from exc
        if isinstance(data, dict) and "rigs" in data:
            rigs = data["rigs"]
            if len(rigs) > 1:
                names = ", ".join(str(r.get("name", "?")) for r in rigs)
                raise RigLoadError(
                    f"file contains {len(rigs)} armatures ({names})",
                    hint="export a single armature or pick one via the add-on",
                )
            data = rigs[0]
        return RigData.from_dict(data)
