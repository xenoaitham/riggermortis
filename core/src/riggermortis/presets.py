"""Per-rig mapping presets.

A preset is a small JSON file recording a rig's fingerprint and its reviewed
role mapping. Re-running the tool on the same rig applies the preset in one
step; a changed rig (different bones or rest pose) refuses to load silently
and asks for ``force`` instead.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .errors import PresetError
from .mapper import RigMapping, map_rig
from .types import RigData

PRESET_FORMAT = 1


@dataclass
class Preset:
    format: int
    rig_name: str
    fingerprint: str
    core_version: str
    mapping: dict[str, str] = field(default_factory=dict)
    confidences: dict[str, float] = field(default_factory=dict)
    manual_overrides: list[str] = field(default_factory=list)
    created: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "format": self.format,
            "rig_name": self.rig_name,
            "fingerprint": self.fingerprint,
            "core_version": self.core_version,
            "mapping": dict(sorted(self.mapping.items())),
            "confidences": {k: round(v, 3) for k, v in sorted(self.confidences.items())},
            "manual_overrides": list(self.manual_overrides),
            "created": self.created,
        }

    @staticmethod
    def from_dict(d: dict[str, object]) -> Preset:
        try:
            fmt = int(d.get("format", 0))  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise PresetError("preset is malformed (no integer format)") from exc
        if fmt != PRESET_FORMAT:
            raise PresetError(
                f"unsupported preset format {fmt}",
                hint=f"this build reads format {PRESET_FORMAT}",
            )
        return Preset(
            format=fmt,
            rig_name=str(d.get("rig_name", "")),
            fingerprint=str(d.get("fingerprint", "")),
            core_version=str(d.get("core_version", "")),
            mapping={str(k): str(v) for k, v in dict(d.get("mapping", {})).items()},  # type: ignore[arg-type]
            confidences={str(k): float(v) for k, v in dict(d.get("confidences", {})).items()},  # type: ignore[arg-type]
            manual_overrides=[str(x) for x in list(d.get("manual_overrides", []))],  # type: ignore[arg-type]
            created=str(d.get("created", "")),
        )


def preset_from_mapping(rig: RigData, mapping: RigMapping, manual_overrides: list[str] | None = None) -> Preset:
    return Preset(
        format=PRESET_FORMAT,
        rig_name=rig.name,
        fingerprint=rig.fingerprint(),
        core_version=__version__,
        mapping={role: a.bone for role, a in sorted(mapping.assignments.items())},
        confidences={role: a.confidence for role, a in sorted(mapping.assignments.items())},
        manual_overrides=list(manual_overrides or []),
        created=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def save_preset(preset: Preset, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(preset.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return p


def load_preset(path: str | Path) -> Preset:
    p = Path(path)
    if not p.exists():
        raise PresetError(f"preset not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PresetError(f"invalid JSON in preset {p}: {exc}") from exc
    return Preset.from_dict(data)


def apply_preset(rig: RigData, preset: Preset, *, force: bool = False) -> RigMapping:
    """Apply a saved mapping; automatic roles are re-solved, preset roles win."""
    if preset.fingerprint != rig.fingerprint():
        msg = (
            f"preset {preset.rig_name!r} does not match this rig "
            f"(fingerprint {preset.fingerprint} vs {rig.fingerprint()})"
        )
        if not force:
            raise PresetError(
                msg,
                hint="the rig changed since the preset was saved; re-map it or pass force=True",
            )
    mapping = map_rig(rig, preset_mapping=preset.mapping)
    mapping.notes.append(f"applied preset with {len(preset.mapping)} pinned roles (force={force})")
    return mapping


def default_preset_path(preset_dir: str | Path, rig: RigData) -> Path:
    return Path(preset_dir) / f"{rig.fingerprint()}.rigpreset.json"
