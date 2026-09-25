"""Per-rig mapping presets.

A preset is a small JSON file recording a rig's fingerprint and its reviewed
role mapping. Re-running the tool on the same rig applies the preset in one
step; a changed rig (different bones or rest pose) refuses to load silently
and asks for ``force`` instead.

Format 2 (P6-1a) adds an optional ``secondary`` list: chain bindings for the
P6-1 spring-chain system (docs/SECONDARY_MOTION.md) — each binding pairs a
validated ``ChainSpec`` (role-level DATA) with the rig's appendage bones that
implement it, parent-first. Format 1 files still read (they carry no chains);
format 2 files read by an older build refuse with the unsupported-format
hint. The bindings ride the SAME fingerprint gate as the mapping — a changed
rig must not silently keep pointing at tail bones it no longer has.

P8-3 adds an optional ``hands`` object to format 2 (ADDITIVE, the pins-in-v3
pattern — the format integer stays 2, older builds ignore the unknown field):
finger role -> bone name (docs/FINGERS.md, the D-021 namespace), authored
once per rig. Keys validate as finger segment roles (mcp/pip/dip — a .tip
has no segment), values must be unique bones that do not already carry a
body-role mapping. ``resolve_hands`` gates them with the SAME fingerprint
contract as the mapping and the secondary chains.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .errors import PresetError
from .mapper import RigMapping, map_rig
from .secondary import ChainSpec
from .types import RigData

PRESET_FORMAT = 2
#: Formats this build reads: 1 (legacy, mapping-only) and 2 (+ secondary /
#: hands bindings — additive fields, loud-validated when present).
_READ_FORMATS = (1, 2)


@dataclass(frozen=True)
class SecondaryBinding:
    """One chain binding inside a preset: the validated spring-chain spec
    plus the rig's appendage bones implementing it, parent-first —
    ``bones[0]`` is parented under the anchor role's mapped bone (the
    contract ``bake_action`` validates against the live rig)."""

    chain: ChainSpec
    bones: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {"chain": self.chain.to_dict(), "bones": list(self.bones)}

    @staticmethod
    def from_dict(d: object) -> SecondaryBinding:
        """Validate loudly: unknown fields, missing halves, wrong bone counts,
        duplicate bone names — every refusal carries an actionable hint."""
        if not isinstance(d, dict):
            raise PresetError(
                "secondary binding must be a JSON object",
                hint='expected {"chain": {...}, "bones": ["bone", ...]}',
            )
        unknown = sorted(set(d) - {"chain", "bones"})
        if unknown:
            raise PresetError(
                f"secondary binding has unknown field(s): {', '.join(unknown)}",
                hint="known fields: bones, chain",
            )
        raw_chain = d.get("chain")
        if not isinstance(raw_chain, dict):
            raise PresetError(
                "secondary binding needs a 'chain' object",
                hint="the chain spec validates through "
                "riggermortis.secondary.ChainSpec (docs/SECONDARY_MOTION.md)",
            )
        chain = ChainSpec.from_dict(raw_chain)
        bones = d.get("bones")
        if (
            not isinstance(bones, list)
            or not bones
            or not all(isinstance(b, str) and b for b in bones)
        ):
            raise PresetError(
                f"chain {chain.name!r}: 'bones' must be a non-empty list of "
                f"bone-name strings, got {bones!r}",
                hint="parent-first; bones[0] is parented under the anchor "
                "role's mapped bone",
            )
        if len(bones) != chain.links:
            raise PresetError(
                f"chain {chain.name!r}: {len(bones)} bone(s) for "
                f"{chain.links} link(s)",
                hint="the binding lists exactly one bone per chain link",
            )
        if len(set(bones)) != len(bones):
            raise PresetError(
                f"chain {chain.name!r}: duplicate bone name in 'bones'",
                hint="one bone per link — a repeated name double-keys the chain",
            )
        return SecondaryBinding(chain=chain, bones=tuple(bones))


def _check_bindings(bindings: list[SecondaryBinding]) -> list[SecondaryBinding]:
    """Shared guard for every path that assembles a binding list (file load
    and direct construction): names unique (they key the tracks), no bone
    shared between two chains, stored sorted by chain name."""
    names = [b.chain.name for b in bindings]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        raise PresetError(
            f"duplicate secondary chain name(s): {', '.join(dupes)}",
            hint="chain names key the simulation's output tracks — unique "
            "names only",
        )
    owner: dict[str, str] = {}
    for b in bindings:
        for bone in b.bones:
            if bone in owner:
                raise PresetError(
                    f"bone {bone!r} is bound to chains {owner[bone]!r} and "
                    f"{b.chain.name!r}",
                    hint="a bone implements ONE chain — double-binding lets "
                    "one chain overwrite the other's keys",
                )
            owner[bone] = b.chain.name
    return sorted(bindings, key=lambda b: b.chain.name)


def _secondary_from_dict(d: dict[str, object]) -> list[SecondaryBinding]:
    """Validate the optional ``secondary`` list (present in formats 1+2,
    only ever populated in 2)."""
    raw = d.get("secondary", [])
    if not isinstance(raw, list):
        raise PresetError(
            f"'secondary' must be a list of bindings, got {type(raw).__name__}",
            hint='each binding: {"chain": {...}, "bones": ["bone", ...]}',
        )
    return _check_bindings([SecondaryBinding.from_dict(entry) for entry in raw])


def _hands_from_dict(d: dict[str, object]) -> dict[str, str]:
    """Validate the optional ``hands`` bindings (P8-3, additive in format 2):
    finger segment roles -> unique bones, no bone double-keyed with the body
    mapping or the secondary chains."""
    from .fk_apply import ALL_ROLES  # noqa: F401  (import guard mirrors above)
    from .fingers import is_finger_role

    raw = d.get("hands")
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise PresetError(
            f"'hands' must be an object of finger role -> bone name, got {type(raw).__name__}",
            hint='example: {"hand.L.finger.index.mcp": "thumb.01.L"} '
                 "(docs/FINGERS.md, the D-021 namespace)",
        )
    out: dict[str, str] = {}
    for key in sorted(raw):
        value = raw[key]
        if not is_finger_role(str(key)) or str(key).endswith(".tip"):
            raise PresetError(
                f"hands binding key {key!r} is not a finger segment role",
                hint="finger roles look like hand.L.finger.index.mcp; a .tip "
                     "role has no segment and cannot bind",
            )
        if not isinstance(value, str) or not value:
            raise PresetError(
                f"hands binding for {key!r} must be a non-empty bone name, got {value!r}",
                hint="the bone implements exactly one finger segment",
            )
        if str(key) in out:
            raise PresetError(
                f"duplicate hands binding for {key!r}",
                hint="one bone per role, one role per key",
            )
        out[str(key)] = value
    dupes = sorted(b for b in set(out.values()) if list(out.values()).count(b) > 1)
    if dupes:
        raise PresetError(
            f"bone(s) {', '.join(repr(b) for b in dupes)} bound to multiple finger roles",
            hint="a bone implements ONE segment — double-binding lets one "
                 "overwrite the other's rotation",
        )
    return out


def _check_hands_against_mapping(hands: dict[str, str], mapping: dict[str, str]) -> None:
    """A bone carrying a body role must not also implement a finger segment
    (the cross-binding double-key class the secondary guard refuses)."""
    if not hands:
        return
    clash = sorted(set(hands.values()) & set(mapping.values()))
    if clash:
        raise PresetError(
            f"bone(s) {', '.join(repr(b) for b in clash)} already carry a body-role mapping",
            hint="finger bones implement finger segments only — pick the "
                 "chain's distal bones",
        )


@dataclass
class Preset:
    format: int
    rig_name: str
    fingerprint: str
    core_version: str
    mapping: dict[str, str] = field(default_factory=dict)
    confidences: dict[str, float] = field(default_factory=dict)
    manual_overrides: list[str] = field(default_factory=list)
    secondary: list[SecondaryBinding] = field(default_factory=list)
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
            "secondary": [b.to_dict() for b in self.secondary],
            "created": self.created,
        }

    @staticmethod
    def from_dict(d: dict[str, object]) -> Preset:
        try:
            fmt = int(d.get("format", 0))  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise PresetError("preset is malformed (no integer format)") from exc
        if fmt not in _READ_FORMATS:
            raise PresetError(
                f"unsupported preset format {fmt}",
                hint="this build reads formats 1-2 (2 = mapping + optional "
                "secondary chains)",
            )
        return Preset(
            format=fmt,
            rig_name=str(d.get("rig_name", "")),
            fingerprint=str(d.get("fingerprint", "")),
            core_version=str(d.get("core_version", "")),
            mapping={str(k): str(v) for k, v in dict(d.get("mapping", {})).items()},  # type: ignore[arg-type]
            confidences={str(k): float(v) for k, v in dict(d.get("confidences", {})).items()},  # type: ignore[arg-type]
            manual_overrides=[str(x) for x in list(d.get("manual_overrides", []))],  # type: ignore[arg-type]
            secondary=_secondary_from_dict(d),
            created=str(d.get("created", "")),
        )


def preset_from_mapping(
    rig: RigData,
    mapping: RigMapping,
    manual_overrides: list[str] | None = None,
    secondary: list[SecondaryBinding] | None = None,
) -> Preset:
    from . import __version__  # deferred: presets is package-imported (P6-1a)

    return Preset(
        format=PRESET_FORMAT,
        rig_name=rig.name,
        fingerprint=rig.fingerprint(),
        core_version=__version__,
        mapping={role: a.bone for role, a in sorted(mapping.assignments.items())},
        confidences={role: a.confidence for role, a in sorted(mapping.assignments.items())},
        manual_overrides=list(manual_overrides or []),
        secondary=_check_bindings(list(secondary or [])),
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


def load_secondary_bindings(path: str | Path) -> list[SecondaryBinding]:
    """Load a bindings file — ``{"format": 1, "secondary": [binding, …]}`` —
    for ``preset save --secondary`` / ``preset set-secondary``. Same loud
    validation as the in-preset list (one implementation, both shapes)."""
    p = Path(path)
    if not p.exists():
        raise PresetError(f"bindings file not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PresetError(f"invalid JSON in bindings file {p}: {exc}") from exc
    if not isinstance(data, dict):
        raise PresetError(
            "bindings file must be a JSON object",
            hint='{"format": 1, "secondary": [{"chain": {...}, "bones": [...]}]}',
        )
    unknown = sorted(set(data) - {"format", "secondary"})
    if unknown:
        raise PresetError(
            f"bindings file has unknown field(s): {', '.join(unknown)}",
            hint="known fields: format, secondary",
        )
    if data.get("format", 1) != 1:
        raise PresetError(
            f"unsupported bindings format {data.get('format')!r}",
            hint="this build reads bindings format 1",
        )
    return _secondary_from_dict(data)


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


def resolve_secondary(
    preset: Preset, rig_fingerprint: str, *, force: bool = False
) -> list[SecondaryBinding]:
    """Fingerprint-gate a preset's chain bindings (P6-1a) and return them
    bake-ready. The bindings ride the SAME gate as the mapping — and the
    refusal matters more here: a changed rig may have lost the very tail
    bones the binding names. ``force=True`` proceeds (the bake's per-bone
    validation stays the last word)."""
    if preset.fingerprint != rig_fingerprint:
        msg = (
            f"preset {preset.rig_name!r} does not match this rig "
            f"(fingerprint {preset.fingerprint} vs {rig_fingerprint})"
        )
        if not force:
            raise PresetError(
                msg,
                hint="the rig changed since the preset was saved; re-map it "
                "or pass force=True",
            )
    return list(preset.secondary)


def default_preset_path(preset_dir: str | Path, rig: RigData) -> Path:
    return Path(preset_dir) / f"{rig.fingerprint()}.rigpreset.json"
