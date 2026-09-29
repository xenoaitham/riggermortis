"""P9-1 proportion auto-sculpt — the pure target math (the selected
mechanism's core half).

Design of record: docs/AUTO_SCULPT.md (the SCENE_TEST.md sibling, with the
probe-earned amendments A1/A2 the build followed). The honest physics:
body keypoints give SKELETON positions, not VOLUME — v1 matches SKELETON
proportions (segment lengths and girdle widths as ratios to the torso
span); volume is P9-2's separate third-model decision and is never claimed
here.

The MECHANISM (the probe's pre-declared selection, measured on the
metarig-class AND a Mixamo-class rig at the Annex A.1 5% bar):
``armature_scale_correctives`` — per-joint offsets delivered as POSE-bone
locations (amendment A1: the rest-edit delivery is refuted — armature
skinning re-binds to the new rest, so the mesh does not follow; the
pose-translation delivery rides real LBS). The bpy half of the mechanism
lives in the add-on (``riggermortis_addon.auto_sculpt``); this module is
the PURE half: ratio measurement, target construction, achieved-vs-intent
validation, and the loud capability lines (the P8-4 pattern). Everything
here is stdlib, deterministic (keyed sorts, plain-float tuples), and free
of payload-format change — the target is derived from an existing payload
at apply time, the report is a returned object (the camera-solve pattern).

NO new pose field ships with this module, so no DECISIONS number was
consumed at this landing (D-025 stays the next free number for whichever
landing actually adds one).
"""
from __future__ import annotations

import math

from .errors import AutoSculptError

BAR_FRAC = 0.05  # Annex A.1 verbatim: within 5% of the segment's length

# The ruler set (declared): the torso is the 1.0 anchor; every other ruler
# is a ratio to it. Role semantics per D-008: a role's position = the joint
# at the HEAD of that role's bone.
SIDES = ("L", "R")
GIRDLES = {
    "shoulder_w": ("upper_arm.L", "upper_arm.R"),
    "hip_w": ("upper_leg.L", "upper_leg.R"),
}
LIMB_SEGMENTS = {
    "upper_arm": ("upper_arm", "forearm"),
    "forearm": ("forearm", "hand"),
    "thigh": ("upper_leg", "lower_leg"),
    "shin": ("lower_leg", "foot"),
}
RULER_NAMES = ("shoulder_w", "hip_w", "upper_arm", "forearm", "thigh", "shin")

Vec3 = tuple[float, float, float]


def _add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _scale(a: Vec3, s: float) -> Vec3:
    return (a[0] * s, a[1] * s, a[2] * s)


def _dist(a: Vec3, b: Vec3) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def _norm(a: Vec3) -> Vec3:
    n = math.sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2)
    if n <= 1e-12:
        return (0.0, 0.0, 0.0)
    return (a[0] / n, a[1] / n, a[2] / n)


def movable_roles() -> set[str]:
    """The joints a proportion sculpt may move (the ruler endpoints)."""
    out: set[str] = set()
    for g in GIRDLES.values():
        out.update(g)
    for top, bot in LIMB_SEGMENTS.values():
        out.update(f"{top}.{s}" for s in SIDES)
        out.update(f"{bot}.{s}" for s in SIDES)
    return out


def measure_proportion_ratios(pos: dict[str, Vec3]) -> dict[str, float]:
    """Ruler ratios vs the torso span (unit-free; the torso == 1.0 anchor)."""
    if "hips" not in pos or "neck" not in pos:
        raise AutoSculptError(
            "torso anchor roles missing (hint: a proportion measurement needs "
            "the hips and neck roles solved)"
        )
    torso = _dist(pos["hips"], pos["neck"])
    if torso <= 1e-12:
        raise AutoSculptError(
            f"torso span degenerate ({torso}) (hint: the reference pose's "
            "torso ruler collapsed — cannot measure proportions)"
        )
    out = {"torso": 1.0}
    for name, (role_l, role_r) in GIRDLES.items():
        out[name] = _dist(pos[role_l], pos[role_r]) / torso
    for seg, (top_role, bot_role) in LIMB_SEGMENTS.items():
        vals = [_dist(pos[f"{top_role}.{s}"], pos[f"{bot_role}.{s}"]) for s in SIDES]
        out[seg] = (vals[0] + vals[1]) / 2.0 / torso
    return out


def build_proportion_target(
    base: dict[str, Vec3],
    ref_ratios: dict[str, float],
    base_ratios: dict[str, float],
) -> tuple[dict[str, Vec3], dict[str, float], list[str]]:
    """Intended joint positions — the shared target the apply half consumes.

    Hips + neck FIXED (the torso anchor; no proportion is introduced into
    the torso line); girdles re-placed symmetrically along the base girdle
    axis (center kept); limb chains re-placed along the BASE chain
    directions at the scaled segment lengths (the sculpt adjusts lengths;
    the pose is applied afterwards by the certified FK path, which derives
    rotations — direction lives in the pose, not the rest). Returns
    (target, per-ruler scale factors, adjusted roles sorted)."""
    factors: dict[str, float] = {}
    adjusted: set[str] = set()
    for ruler in RULER_NAMES:
        b = base_ratios[ruler]
        if b <= 1e-12:
            raise AutoSculptError(
                f"base ratio degenerate for {ruler} ({b}) "
                "(hint: the rig's own ruler collapsed — nothing to scale)"
            )
        factors[ruler] = ref_ratios[ruler] / b
        if abs(factors[ruler] - 1.0) > 1e-9:
            adjusted.update(_ruler_roles(ruler))

    target = dict(base)
    for ruler in ("shoulder_w", "hip_w"):
        role_l, role_r = GIRDLES[ruler]
        center = _scale(_add(base[role_l], base[role_r]), 0.5)
        axis = _norm(_sub(base[role_l], base[role_r]))
        half = _dist(base[role_l], base[role_r]) * factors[ruler] * 0.5
        target[role_l] = _add(center, _scale(axis, half))
        target[role_r] = _sub(center, _scale(axis, half))
    for seg in ("upper_arm", "forearm", "thigh", "shin"):
        top_role, bot_role = LIMB_SEGMENTS[seg]
        for s in SIDES:
            top = f"{top_role}.{s}"
            bot = f"{bot_role}.{s}"
            direction = _norm(_sub(base[bot], base[top]))
            length = _dist(base[top], base[bot]) * factors[seg]
            target[bot] = _add(target[top], _scale(direction, length))
    return target, factors, sorted(adjusted)


def _ruler_roles(ruler: str) -> set[str]:
    if ruler in GIRDLES:
        return set(GIRDLES[ruler])
    top, bot = LIMB_SEGMENTS[ruler]
    return {f"{top}.{s}" for s in SIDES} | {f"{bot}.{s}" for s in SIDES}


def validate_sculpt(
    achieved: dict[str, Vec3],
    intended: dict[str, Vec3],
    base: dict[str, Vec3],
    bar_frac: float = BAR_FRAC,
) -> tuple[float, dict[str, float], str, bool]:
    """The Annex A.1 bar, EVERY role vs its intent (unchanged roles' intent
    is their base position — a mechanism that smears deltas everywhere is
    judged on that drift too). Girdle roles reference the torso span; limb
    distal roles their own segment. Returns
    (worst frac, per-role fracs, worst role, within-bar)."""
    torso = _dist(base["hips"], base["neck"])
    girdle_roles = {r for g in GIRDLES.values() for r in g}
    seg_of: dict[str, float] = {}
    for top, bot in LIMB_SEGMENTS.values():
        for s in SIDES:
            seg_of[f"{bot}.{s}"] = _dist(base[f"{top}.{s}"], base[f"{bot}.{s}"])
    fracs: dict[str, float] = {}
    for role in sorted(intended):
        seg_len = torso if role in girdle_roles else seg_of.get(role, torso)
        err = _dist(achieved[role], intended[role])
        fracs[role] = err / max(seg_len, 1e-12)
    worst_role = max(sorted(fracs), key=lambda r: fracs[r])
    worst = fracs[worst_role]
    return worst, fracs, worst_role, worst <= bar_frac


def sculpt_capability_lines(roles_present: set[str]) -> list[str]:
    """The loud capability draft (the P8-4 verbatim pattern): a rig missing
    a movable role is REFUSED with the line, never silently skipped."""
    missing = sorted(movable_roles() - roles_present)
    if not missing:
        return []
    return [
        "auto-sculpt: rig has no viable proportion targets for: "
        + ", ".join(missing)
        + " — proportions not applied"
    ]


class ProportionReport:
    """The reference-proportion REPORT — ships as data regardless of any
    mechanism verdict (the roadmap's refuse branch keeps its value)."""

    def __init__(
        self,
        reference: dict[str, float],
        base: dict[str, float],
        factors: dict[str, float],
        adjusted: list[str],
        capability_lines: list[str],
    ) -> None:
        self.reference = dict(sorted(reference.items()))
        self.base = dict(sorted(base.items()))
        self.factors = dict(sorted(factors.items()))
        self.adjusted = list(adjusted)
        self.capability_lines = list(capability_lines)

    def to_dict(self) -> dict[str, object]:
        return {
            "reference_ratios": dict(self.reference),
            "base_ratios": dict(self.base),
            "factors": dict(self.factors),
            "adjusted_roles": list(self.adjusted),
            "capability_lines": list(self.capability_lines),
        }

    @classmethod
    def from_dict(cls, d: dict[str, object]) -> ProportionReport:
        return cls(
            reference=dict(d["reference_ratios"]),  # type: ignore[arg-type]
            base=dict(d["base_ratios"]),  # type: ignore[arg-type]
            factors=dict(d["factors"]),  # type: ignore[arg-type]
            adjusted=list(d["adjusted_roles"]),  # type: ignore[arg-type]
            capability_lines=list(d["capability_lines"]),  # type: ignore[arg-type]
        )


def proportion_report(
    base_positions: dict[str, Vec3],
    reference_positions: dict[str, Vec3],
) -> ProportionReport:
    """Measure the reference vs the base rig and report the deltas — pure
    data, no rig touched. A rig missing movable roles reports the loud
    capability lines IN the report (the refusal is the value). ``adjusted``
    lists RULERS with deltas (the report form); the apply target's
    ``adjusted`` lists ROLES (the validation form). A starved rig is
    refused BEFORE any measurement — the lines are the report."""
    lines = sculpt_capability_lines(set(base_positions))
    if lines:
        return ProportionReport(
            reference={},
            base={},
            factors={},
            adjusted=[],
            capability_lines=lines,
        )
    base_ratios = measure_proportion_ratios(base_positions)
    ref_ratios = measure_proportion_ratios(reference_positions)
    factors = {k: ref_ratios[k] / base_ratios[k] for k in RULER_NAMES}
    adjusted = sorted(k for k in RULER_NAMES if abs(factors[k] - 1.0) > 1e-9)
    return ProportionReport(
        reference=ref_ratios,
        base=base_ratios,
        factors=factors,
        adjusted=adjusted,
        capability_lines=[],
    )
