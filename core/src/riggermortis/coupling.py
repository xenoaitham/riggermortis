"""Contact coupling (P8-2): the deterministic pass enforcing AUTHORED pins.

Design of record: docs/SCENES.md § Contact coupling (written before this
module; constants pre-declared there, D-008 style — order-of-magnitude
choices, never fixture-fitted). The one architectural fact everything rides
on: :class:`~riggermortis.canonical_pose.CanonicalPose` carries POSITIONS
only — per-rig rotations are derived at apply time from positions — so the
coupling pass is pure position-space surgery and the certified apply path
consumes coupled poses unchanged.

The declared solve (see the design page for the full tables):

- **Enforcement gate**: a pin is enforced iff ``origin == "authored"`` AND
  ``confidence >= ENFORCE_CONF_FLOOR`` (the CONVENTIONS ambiguity bar,
  reused, declared untuned). Everything else is REPORTED LOUD and moves
  nothing: suggested pins, below-floor pins, pins whose figures have no
  placement, pins with both endpoints girdle/anchor-rigid.
- **Movable chains**: the distal limb chains only (endpoint hand/forearm →
  upper_arm+forearm; endpoint lower_leg/foot/toe → upper_leg+lower_leg;
  endpoint chest → spine; endpoint neck/head → spine+chest; everything
  else girdle/anchor-rigid). Rotating a joint moves its DESCENDANTS (a
  role's position is its bone's head), never itself.
- **Iteration**: per pass, per enforceable pin in AUTHORED order (the
  scene model stores pins unsorted — that order is precedence), the gap
  splits confidence-weighted across the two endpoints (``w ∝ 1 − c``; the
  better-observed role is trusted more and moves less), then each
  endpoint's chain carries toward its target root→leaf, each joint taking
  1/n of the currently-needed carry angle about its own position
  (sequential — bends the chain instead of swinging it rigidly).
- **Residuals**: measured after the final pass for EVERY pin, in scene
  space, normalized by the mean scene torso span of the two pinned
  figures; ``closed`` = frac < BAR_FRAC (the Annex A.1 2% bar). Over-bar
  pins stay in ``unclosable`` — loud, never silently absorbed.

Pure stdlib (D-003), deterministic (keyed orders everywhere — pins in
authored order by DESIGN, joints by chain order, sorted() on every set
crossing into output), and PURE: the input :class:`ScenePose` is never
mutated (pinned by test, the certified-composition discipline).

Known v1 honesty lines (docs/SCENES.md § What coupling does NOT do): pins
close JOINT-to-JOINT distances (no skin model); the solver moves LIMBS,
never whole figures; suggested pins are never enforced.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Any

from .canonical import children_of
from .canonical_pose import TORSO_SPAN, CanonicalPose, Vec3
from .errors import SceneError
from .scene import SceneFigure, ScenePose

#: Iteration cap for the redistribution (declared; convergence is geometric).
MAX_ITERS = 32

#: Early-exit residual (fraction of torso span) — three orders under the bar.
EARLY_EXIT_FRAC = 2e-4

#: A pin below this confidence is carried, never enforced (CONVENTIONS bar).
ENFORCE_CONF_FLOOR = 0.55

#: The Annex A.1 acceptance bar: residual < 2% of torso span.
BAR_FRAC = 0.02

Quaternion = tuple[float, float, float, float]  # (w, x, y, z)


# -- placements --------------------------------------------------------------------


@dataclass(frozen=True)
class Placement:
    """Where a figure stands in the shared scene space.

    ``scene_p = t + s * (R * canonical_p)`` with ``R`` a unit quaternion.
    Pure geometry — validation is loud (a zero quaternion or non-positive
    scale refuses with a hint). The core takes placements as explicit
    arguments; the add-on MEASURES them from the posed rigs (docs/SCENES.md
    § Scene space and placements).
    """

    quat: Quaternion = (1.0, 0.0, 0.0, 0.0)
    t: Vec3 = (0.0, 0.0, 0.0)
    s: float = 1.0

    def __post_init__(self) -> None:
        n = math.sqrt(sum(c * c for c in self.quat))
        if not math.isfinite(n) or n <= 1e-12:
            raise SceneError(
                f"placement quaternion is degenerate (norm {n!r})",
                hint="pass a non-zero (w, x, y, z) rotation — identity is "
                     "(1, 0, 0, 0)",
            )
        if not all(math.isfinite(v) for v in self.t) or not math.isfinite(self.s):
            raise SceneError(
                "placement translation/scale must be finite",
                hint="placements come from the posed rig (t = anchor joint "
                     "world position, s = torso-span ratio)",
            )
        if self.s <= 0.0:
            raise SceneError(
                f"placement scale must be positive, got {self.s}",
                hint="s maps canonical units to scene units "
                     "(posed torso span / 0.45)",
            )

    def place(self, p: Vec3) -> Vec3:
        return _add(self.t, _scale(q_rotate(self.quat, p), self.s))

    def unplace(self, p: Vec3) -> Vec3:
        inv = (self.quat[0], -self.quat[1], -self.quat[2], -self.quat[3])
        return q_rotate(inv, _scale(_sub(p, self.t), 1.0 / self.s))


# -- vec + quaternion helpers (stdlib; same conventions as fk_apply) ---------------


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(a: Vec3, k: float) -> Vec3:
    return (a[0] * k, a[1] * k, a[2] * k)


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _norm(a: Vec3) -> float:
    return math.sqrt(_dot(a, a))


def _unit(a: Vec3) -> Vec3:
    n = _norm(a)
    return (0.0, 0.0, 0.0) if n <= 1e-12 else (a[0] / n, a[1] / n, a[2] / n)


def q_rotate(q: Quaternion, v: Vec3) -> Vec3:
    w, x, y, z = q
    uvx = 2.0 * (y * v[2] - z * v[1])
    uvy = 2.0 * (z * v[0] - x * v[2])
    uvz = 2.0 * (x * v[1] - y * v[0])
    return (
        v[0] + w * uvx + (y * uvz - z * uvy),
        v[1] + w * uvy + (z * uvx - x * uvz),
        v[2] + w * uvz + (x * uvy - y * uvx),
    )


def q_axis_angle(axis: Vec3, angle: float) -> Quaternion:
    s = math.sin(angle / 2.0)
    return (math.cos(angle / 2.0), axis[0] * s, axis[1] * s, axis[2] * s)


# -- the declared v1 movable-chain table --------------------------------------------


def movable_joints(role: str, positions: dict[str, Vec3]) -> list[str]:
    """Joints that may rotate to carry ``role``'s position, root->leaf.

    The declared v1 table (docs/SCENES.md): distal limb chains only; the
    girdle/anchor joints stay rigid (D-008's solve anchors). Roles absent
    from the pose are filtered out. Rotating a joint moves its descendants
    — a role's position is its bone's HEAD — so this never contains the
    endpoint role itself.
    """
    base, _, side = role.partition(".")
    if side:
        if base in ("hand", "forearm"):
            chain = [f"upper_arm.{side}", f"forearm.{side}"]
        elif base in ("lower_leg", "foot", "toe"):
            chain = [f"upper_leg.{side}", f"lower_leg.{side}"]
        else:
            chain = []  # upper_arm/shoulder/upper_leg endpoints: girdle-rigid
    elif role == "chest":
        chain = ["spine"]
    elif role in ("neck", "head"):
        chain = ["spine", "chest"]
    else:
        chain = []  # spine/hips/root: anchor-rigid endpoints
    return [j for j in chain if j in positions]


def _subtree(positions: dict[str, Vec3], joint: str) -> list[str]:
    """Descendants of ``joint`` present in the pose, sorted (keyed)."""
    out: list[str] = []
    stack = [joint]
    while stack:
        r = stack.pop()
        for c in children_of(r):
            if c in positions:
                out.append(c)
                stack.append(c)
    return sorted(out)


def _carry(
    positions: dict[str, Vec3], endpoint: str, target: Vec3, joints: list[str],
) -> None:
    """One redistribution pass on one endpoint's chain.

    Root->leaf, keyed: each joint rotates its whole subtree about its OWN
    position by 1/n of the currently-needed carry angle (recomputed after
    every joint — the sequential pass bends the chain instead of swinging
    it rigidly). Beyond-reach targets straighten the chain toward the
    target and stop improving (clamped-by-reach, reported — the P2-5
    ladder's honesty).
    """
    n = max(len(joints), 1)
    for j in joints:
        cur = positions[endpoint]
        piv = positions[j]
        u, v = _sub(cur, piv), _sub(target, piv)
        if _norm(u) < 1e-12 or _norm(v) < 1e-12:
            continue
        nu, nv = _unit(u), _unit(v)
        angle = math.acos(max(-1.0, min(1.0, _dot(nu, nv))))
        if angle < 1e-9:
            continue
        axis = _cross(nu, nv)
        if _norm(axis) < 1e-9:
            continue  # collinear: already on the target direction
        q = q_axis_angle(_unit(axis), angle / n)
        for d in _subtree(positions, j):
            positions[d] = _add(piv, q_rotate(q, _sub(positions[d], piv)))


def _joint_conf(pose: CanonicalPose, role: str) -> float:
    """Per-role confidence (the weights) — observation confidence, falling
    back to the whole-solve confidence for derived roles (declared)."""
    return float(pose.joint_confidence.get(role, pose.confidence))


def _figure_span(pose: CanonicalPose, pl: Placement) -> float:
    """Scene-space torso span of one figure (hips -> neck joints)."""
    if "hips" in pose.positions and "neck" in pose.positions:
        return pl.s * _norm(_sub(pose.positions["neck"], pose.positions["hips"]))
    return pl.s * TORSO_SPAN


# -- report -------------------------------------------------------------------------


@dataclass(frozen=True)
class PinCoupleRow:
    """One pin's coupling outcome (report row, authored order preserved)."""

    figure_a: str
    role_a: str
    figure_b: str
    role_b: str
    origin: str
    confidence: float
    enforced: bool
    reason: str
    residual: float
    residual_frac: float
    closed: bool
    iterations: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "figure_a": self.figure_a,
            "role_a": self.role_a,
            "figure_b": self.figure_b,
            "role_b": self.role_b,
            "origin": self.origin,
            "confidence": round(self.confidence, 4),
            "enforced": self.enforced,
            "reason": self.reason,
            "residual": round(self.residual, 6),
            "residual_frac": round(self.residual_frac, 6),
            "closed": self.closed,
            "iterations": self.iterations,
        }


@dataclass
class CoupleReport:
    """The coupling report: per-pin rows (authored order) + loud ledgers."""

    rows: list[PinCoupleRow] = field(default_factory=list)
    moved_roles: dict[str, list[str]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def unclosable(self) -> list[PinCoupleRow]:
        """Pins at/over the bar — loud, authored order (the precedence view)."""
        return [r for r in self.rows if not r.closed]

    def to_dict(self) -> dict[str, Any]:
        return {
            "rows": [r.to_dict() for r in self.rows],
            "unclosable": [r.to_dict() for r in self.unclosable],
            "moved_roles": {k: list(v) for k, v in sorted(self.moved_roles.items())},
            "notes": list(self.notes),
            "bar_frac": BAR_FRAC,
        }


# -- the pass -----------------------------------------------------------------------


def couple_scene(
    scene: ScenePose, placements: dict[str, Placement],
) -> tuple[ScenePose, CoupleReport]:
    """Enforce AUTHORED pins over the scene; returns (coupled scene, report).

    Pure: ``scene`` is never mutated (the coupled figures are copies).
    Deterministic: same inputs -> byte-identical outputs (pinned by test).
    Scenes without enforceable pins pass through byte-identically.
    """
    if not isinstance(placements, dict) or not all(
        isinstance(k, str) and isinstance(v, Placement) for k, v in placements.items()
    ):
        raise SceneError(
            "placements must map figure labels to Placement objects",
            hint="placements[\"A\"] = Placement(quat=..., t=..., s=...); "
                 "the add-on measures them from the posed rigs",
        )

    figures = {f.label: f.pose for f in scene.figures}
    pos = {lab: dict(p.positions) for lab, p in figures.items()}
    chains = {
        (lab, role): movable_joints(role, pos[lab])
        for pin in scene.pins
        for lab, role in ((pin.figure_a, pin.role_a), (pin.figure_b, pin.role_b))
    }

    report = CoupleReport()
    enforceable: list[tuple[int, Any, float, float, list[str], list[str]]] = []
    for pin in scene.pins:  # AUTHORED order (the precedence rule)
        conf_a = _joint_conf(figures[pin.figure_a], pin.role_a)
        conf_b = _joint_conf(figures[pin.figure_b], pin.role_b)
        chain_a = chains[(pin.figure_a, pin.role_a)]
        chain_b = chains[(pin.figure_b, pin.role_b)]
        missing = [
            lab for lab in (pin.figure_a, pin.figure_b) if lab not in placements
        ]
        row = PinCoupleRow(
            figure_a=pin.figure_a, role_a=pin.role_a,
            figure_b=pin.figure_b, role_b=pin.role_b,
            origin=pin.origin, confidence=pin.confidence,
            enforced=False, reason="", residual=0.0, residual_frac=0.0,
            closed=False, iterations=0,
        )
        wa = wb = 0.0
        if pin.origin != "authored":
            row = replace(row, reason="suggested pin (never auto-enforced)")
        elif missing:
            row = replace(row, reason=f"no placement for figure {missing[0]!r} "
                          "(uncast or unmeasured)")
        elif pin.confidence < ENFORCE_CONF_FLOOR:
            row = replace(row, reason=f"pin confidence below floor {ENFORCE_CONF_FLOOR}")
        elif not chain_a and not chain_b:
            row = replace(row, reason="both endpoints immovable (girdle/anchor-rigid)")
        else:
            if not chain_a:
                wa, wb = 0.0, 1.0
            elif not chain_b:
                wa, wb = 1.0, 0.0
            else:
                da, db = 1.0 - conf_a, 1.0 - conf_b
                if da + db < 1e-12:
                    wa = wb = 0.5  # declared edge rule
                else:
                    wa, wb = da / (da + db), db / (da + db)
            row = replace(row, enforced=True)
            enforceable.append((len(report.rows), pin, wa, wb, chain_a, chain_b))
        report.rows.append(row)

    for it in range(MAX_ITERS):
        done = True
        for row_idx, pin, wa, wb, chain_a, chain_b in enforceable:  # authored order
            pa = pos[pin.figure_a][pin.role_a]
            pb = pos[pin.figure_b][pin.role_b]
            pl_a = placements[pin.figure_a]
            pl_b = placements[pin.figure_b]
            gap = _sub(pl_a.place(pa), pl_b.place(pb))
            span = 0.5 * (_figure_span(figures[pin.figure_a], pl_a)
                          + _figure_span(figures[pin.figure_b], pl_b))
            if _norm(gap) / span < EARLY_EXIT_FRAC:
                continue
            done = False
            report.rows[row_idx] = replace(report.rows[row_idx], iterations=it + 1)
            if wa > 0.0:
                target = pl_a.unplace(_sub(pl_a.place(pa), _scale(gap, wa)))
                _carry(pos[pin.figure_a], pin.role_a, target, chain_a)
            if wb > 0.0:
                target = pl_b.unplace(_add(pl_b.place(pb), _scale(gap, wb)))
                _carry(pos[pin.figure_b], pin.role_b, target, chain_b)
        if done:
            break

    for i, row in enumerate(report.rows):  # residuals for EVERY pin — loud
        pl_a = placements.get(row.figure_a)
        pl_b = placements.get(row.figure_b)
        if pl_a is None or pl_b is None:
            continue  # unmeasurable without both placements; the reason says why
        resid = _norm(_sub(
            pl_a.place(pos[row.figure_a][row.role_a]),
            pl_b.place(pos[row.figure_b][row.role_b]),
        ))
        span = 0.5 * (_figure_span(figures[row.figure_a], pl_a)
                      + _figure_span(figures[row.figure_b], pl_b))
        report.rows[i] = replace(
            row, residual=resid, residual_frac=resid / span,
            closed=(resid / span) < BAR_FRAC,
        )

    moved_roles: dict[str, list[str]] = {}
    for lab in sorted(pos):
        changed = sorted(r for r in pos[lab] if pos[lab][r] != figures[lab].positions[r])
        if changed:
            moved_roles[lab] = changed
    report.moved_roles = moved_roles

    coupled = ScenePose(
        name=scene.name,
        figures=[
            SceneFigure(label=f.label, pose=CanonicalPose(
                positions=pos[f.label], flips=dict(f.pose.flips),
                confidence=f.pose.confidence, reliable=f.pose.reliable,
                scale=f.pose.scale, anchor=f.pose.anchor,
                notes=list(f.pose.notes),
                joint_confidence=dict(f.pose.joint_confidence),
            ))
            for f in scene.figures
        ],
        pins=list(scene.pins),  # authored order, carried unchanged
    )
    if not enforceable:
        report.notes.append("no enforceable pins: scene passed through unchanged")
    return coupled, report
