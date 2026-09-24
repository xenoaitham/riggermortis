"""CanonicalScene (P8-1): N named figures + contact pins as DATA.

A scene is the multi-figure counterpart of :class:`CanonicalPose`: named
figures (each a FULL canonical pose), optional ``ContactPin`` links between
them, and — from P8-2 on — the coupling pass that enforces AUTHORED pins.
P8-1 ships the model, the payload v3 carrier, the casting validator, and
the loud honesty rules:

- pins are carried and reported, NEVER enforced here (P8-2's coupling pass
  is the enforcer; enforcing a pin would move bones — nothing in this
  module mutates a pose);
- ``origin="suggested"`` pins are inference DATA the artist confirms —
  they carry a confidence and are never auto-promoted to authored;
- every output shape is deterministic: figures sorted by label, pins in
  AUTHORED order (P8-2's conflict rule resolves them in authored order —
  reordering would silently rewrite the artist's precedence), sorted dict
  keys in ``to_dict``.

Validation is loud (the ChainSpec discipline): unknown fields refuse with
an actionable hint; pin endpoints must reference existing figure labels and
known canonical roles; the two pin figures must differ (self-contact within
one figure is not a scene pin — author the pose directly).

Pure stdlib (D-003). One validator implementation shared by the add-on,
the session executor, and the CLI (the payload.py rule).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import payload as payload_mod
from .canonical import ALL_ROLES
from .canonical_pose import CanonicalPose
from .errors import PayloadError, SceneError

#: Scene schema format written by this build.
SCENE_FORMAT = 1

#: Pin origins. ``authored`` = the artist's word (enforceable from P8-2);
#: ``suggested`` = inferred data awaiting confirmation (never enforced).
PIN_ORIGINS = ("authored", "suggested")


def _require_mapping(raw: object, where: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise SceneError(
            f"{where}: expected a JSON object, got {type(raw).__name__}",
            hint="scene JSON is {\"figures\": [...], \"pins\": [...]}",
        )
    return raw


def _reject_unknown(raw: dict[str, Any], known: tuple[str, ...], where: str) -> None:
    unknown = sorted(set(raw) - set(known))
    if unknown:
        raise SceneError(
            f"{where}: unknown field(s) {', '.join(repr(u) for u in unknown)}",
            hint=f"known fields: {', '.join(known)}",
        )


# -- ContactPin ------------------------------------------------------------------

@dataclass(frozen=True)
class ContactPin:
    """One contact link: (figure_a, role_a) <-> (figure_b, role_b).

    Carried as DATA in P8-1 — enforcement is P8-2's coupling pass. Pins
    keep AUTHORED ORDER (never sorted) because that order is precedence.
    """

    figure_a: str
    role_a: str
    figure_b: str
    role_b: str
    origin: str = "authored"
    confidence: float = 1.0
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        out = {
            "figure_a": self.figure_a,
            "role_a": self.role_a,
            "figure_b": self.figure_b,
            "role_b": self.role_b,
            "origin": self.origin,
            "confidence": round(self.confidence, 4),
        }
        if self.note:
            out["note"] = self.note
        return out

    @staticmethod
    def from_dict(raw: object, where: str = "pin") -> ContactPin:
        d = _require_mapping(raw, where)
        _reject_unknown(
            d,
            ("figure_a", "role_a", "figure_b", "role_b", "origin",
             "confidence", "note"),
            where,
        )
        for key in ("figure_a", "role_a", "figure_b", "role_b"):
            if not isinstance(d.get(key), str) or not d[key]:
                raise SceneError(
                    f"{where}: {key!r} must be a non-empty string",
                    hint=f"a pin links role_a of figure_a to role_b of figure_b "
                         f"(got {key!r}: {d.get(key)!r})",
                )
        origin = d.get("origin", "authored")
        if origin not in PIN_ORIGINS:
            raise SceneError(
                f"{where}: unknown origin {origin!r}",
                hint=f"origins: {', '.join(PIN_ORIGINS)} "
                     "('suggested' pins are data the artist confirms)",
            )
        try:
            confidence = float(d.get("confidence", 1.0))
        except (TypeError, ValueError) as exc:
            raise SceneError(
                f"{where}: confidence must be a number, got {d.get('confidence')!r}",
                hint="confidence is in [0, 1]",
            ) from exc
        if isinstance(d.get("confidence"), bool) or not 0.0 <= confidence <= 1.0:
            raise SceneError(
                f"{where}: confidence must be in [0, 1], got {confidence}",
                hint="suggested pins carry the inference's confidence; "
                     "authored pins default 1.0",
            )
        note = d.get("note", "")
        if not isinstance(note, str):
            raise SceneError(
                f"{where}: note must be a string, got {type(note).__name__}",
                hint="notes travel with the pin verbatim",
            )
        return ContactPin(
            figure_a=d["figure_a"], role_a=d["role_a"],
            figure_b=d["figure_b"], role_b=d["role_b"],
            origin=origin, confidence=confidence, note=note,
        )


# -- SceneFigure -----------------------------------------------------------------

@dataclass(frozen=True)
class SceneFigure:
    """One named figure: a stable label plus its FULL canonical pose."""

    label: str
    pose: CanonicalPose

    def to_dict(self) -> dict[str, Any]:
        return {"label": self.label, "pose": self.pose.to_dict()}

    @staticmethod
    def from_dict(raw: object, where: str = "figure") -> SceneFigure:
        d = _require_mapping(raw, where)
        _reject_unknown(d, ("label", "pose"), where)
        label = d.get("label")
        if not isinstance(label, str) or not label:
            raise SceneError(
                f"{where}: 'label' must be a non-empty string",
                hint="figures are addressed by label (pins reference them)",
            )
        pose_raw = d.get("pose")
        if not isinstance(pose_raw, dict):
            raise SceneError(
                f"{where}: figure {label!r} carries no pose dict",
                hint="each figure embeds a full CanonicalPose.to_dict()",
            )
        try:
            pose = CanonicalPose.from_dict(pose_raw)
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise SceneError(
                f"{where}: figure {label!r} pose is not a valid CanonicalPose: {exc}",
                hint="regenerate the payload with: rigpose pose <image> <rig.json> "
                     "--all-figures",
            ) from exc
        return SceneFigure(label=label, pose=pose)


# -- ScenePose -------------------------------------------------------------------

@dataclass
class ScenePose:
    """The scene: named figures + contact pins (carried, not enforced)."""

    name: str
    figures: list[SceneFigure] = field(default_factory=list)
    pins: list[ContactPin] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.figures = sorted(self.figures, key=lambda f: f.label)  # keyed order
        labels = [f.label for f in self.figures]
        if len(set(labels)) != len(labels):
            dupes = sorted({lab for lab in labels if labels.count(lab) > 1})
            raise SceneError(
                f"scene {self.name!r}: duplicate figure label(s) {dupes}",
                hint="figures are addressed by label; labels must be unique",
            )
        by_label = {f.label: f for f in self.figures}
        for i, pin in enumerate(self.pins):  # AUTHORED order, never sorted
            where = f"scene {self.name!r} pin[{i}]"
            for side in ("a", "b"):
                label = getattr(pin, f"figure_{side}")
                if label not in by_label:
                    raise SceneError(
                        f"{where}: references unknown figure {label!r}",
                        hint=f"figures in this scene: {', '.join(sorted(by_label))}",
                    )
                role = getattr(pin, f"role_{side}")
                if role not in ALL_ROLES:
                    raise SceneError(
                        f"{where}: unknown canonical role {role!r}",
                        hint="roles are the frozen canonical API (hips, chest, "
                             "hand.L, ...) — nothing scene-local",
                    )
            if pin.figure_a == pin.figure_b:
                raise SceneError(
                    f"{where}: both endpoints are figure {pin.figure_a!r}",
                    hint="self-contact within one figure is not a scene pin — "
                         "author the pose directly",
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": SCENE_FORMAT,
            "name": self.name,
            "figures": [f.to_dict() for f in self.figures],  # label-sorted
            "pins": [p.to_dict() for p in self.pins],        # authored order
        }

    @staticmethod
    def from_dict(raw: object) -> ScenePose:
        d = _require_mapping(raw, "scene")
        _reject_unknown(d, ("format", "name", "figures", "pins"), "scene")
        fmt = d.get("format", SCENE_FORMAT)
        if fmt != SCENE_FORMAT:
            raise SceneError(
                f"scene: unsupported format {fmt!r}",
                hint=f"this build reads scene format {SCENE_FORMAT}",
            )
        name = d.get("name")
        if not isinstance(name, str) or not name:
            raise SceneError(
                "scene: 'name' must be a non-empty string",
                hint="the scene name keys reports and bake action names",
            )
        figures_raw = d.get("figures", [])
        if not isinstance(figures_raw, list):
            raise SceneError(
                "scene: 'figures' must be a list",
                hint="each entry is {\"label\": ..., \"pose\": {...}}",
            )
        pins_raw = d.get("pins", [])
        if not isinstance(pins_raw, list):
            raise SceneError(
                "scene: 'pins' must be a list",
                hint="each pin is {figure_a, role_a, figure_b, role_b, origin, "
                     "confidence}",
            )
        return ScenePose(
            name=name,
            figures=[
                SceneFigure.from_dict(f, f"scene figure[{i}]")
                for i, f in enumerate(figures_raw)
            ],
            pins=[
                ContactPin.from_dict(p, f"scene pin[{i}]")
                for i, p in enumerate(pins_raw)
            ],
        )


# -- payload <-> scene ------------------------------------------------------------

def pins_of(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """The raw ``pins`` entries of a payload (empty when absent).

    Validation happens in :meth:`ContactPin.from_dict` — this only reads.
    """
    pins = payload.get("pins", [])
    if not isinstance(pins, list):
        raise PayloadError(
            "payload 'pins' is not a list",
            hint="pins are [{figure_a, role_a, figure_b, role_b, origin}]",
        )
    return pins


def scene_from_payload(payload: dict[str, Any]) -> ScenePose:
    """Build a ScenePose from a pose payload (the ONE builder; D-009).

    Figures come from ``payload.figure_entries`` (v1/v2 payloads synthesize
    entries exactly as the apply path does), pins from the v3 ``pins`` key.
    A v2 payload IS a valid scene: N figures, zero pins.
    """
    label = payload.get("image", {}).get("path", "payload") \
        if isinstance(payload.get("image"), dict) else "payload"
    figures = [
        SceneFigure(
            label=str(entry.get("label") or f"figure {i}"),
            pose=CanonicalPose.from_dict(entry["pose"]),
        )
        for i, entry in enumerate(payload_mod.figure_entries(payload))
        if isinstance(entry.get("pose"), dict)
    ]
    missing = [
        str(entry.get("label") or f"figure {i}")
        for i, entry in enumerate(payload_mod.figure_entries(payload))
        if not isinstance(entry.get("pose"), dict)
    ]
    if missing:
        raise SceneError(
            f"payload figure(s) carry no pose dict: {', '.join(missing)}",
            hint="regenerate with: rigpose pose <image> <rig.json> --all-figures",
        )
    return ScenePose(
        name=str(label),
        figures=figures,
        pins=[
            ContactPin.from_dict(p, f"payload pin[{i}]")
            for i, p in enumerate(pins_of(payload))
        ],
    )


# -- casting validation -----------------------------------------------------------

def validate_casting(
    scene: ScenePose,
    assignments: dict[str, str],
    available: list[str],
) -> dict[str, str]:
    """Validate figure->armature casting; returns the normalized mapping.

    SUBSET-CASTING (the S26 as-built amendment): the artist may pair any
    subset of the scene's figures — only the PAIRED figures are posed, and
    the apply REPORTS the uncast labels (never silently). Loud refusals
    (the honesty law applied to casting): no unknown labels, no armature
    cast twice (two figures on one rig = the second silently overwrites
    the first), armature names exist in ``available``. The desk NEVER
    guesses identity — the artist pairs.
    """
    unknown = sorted(set(assignments) - {f.label for f in scene.figures})
    if unknown:
        raise SceneError(
            f"assignment(s) reference unknown figure(s): {', '.join(unknown)}",
            hint=f"figures in this scene: {', '.join(sorted(f.label for f in scene.figures))}",
        )
    missing_rigs = sorted(
        {arm for arm in assignments.values() if arm not in available}
    )
    if missing_rigs:
        raise SceneError(
            f"armature(s) not in the scene: {', '.join(missing_rigs)}",
            hint=f"armatures available: {', '.join(sorted(available)) or 'none'}",
        )
    by_arm: dict[str, list[str]] = {}
    for label in sorted(assignments):
        by_arm.setdefault(assignments[label], []).append(label)
    double = sorted((arm, labels) for arm, labels in by_arm.items() if len(labels) > 1)
    if double:
        detail = "; ".join(f"{arm} <- {', '.join(labels)}" for arm, labels in double)
        raise SceneError(
            f"armature(s) cast to multiple figures: {detail}",
            hint="one rig per figure — a second apply would silently "
                 "overwrite the first",
        )
    return {label: assignments[label] for label in sorted(assignments)}
