"""Spine arch + arm roll (P8-6): post-solve articulation passes.

Design of record: docs/SPINE.md (the CAMERA.md sibling, including the
probe-earned amendment A1 the first build followed). Both solves are PURE
post-solve passes over the already-solved :class:`CanonicalPose` — they
consume only what the payload already carries (``positions`` +
``joint_confidence``), so there is NO payload format change and the v3
contract plus the hands-free face-free byte-identity pins hold (pinned by
the existing tests).

The ARCH (closes L5): the in-plane misalignment between the torso chord
(hips→mid-shoulders) and the head axis (mid-shoulders→nose, recovered
EXACTLY from the stored derived head position through the declared
placement model's half-angle inverse) is distributed across the spine
chain by a cubic Hermite through the pinned endpoints — the same
positions-surgery class as the coupling pass. ``spine``/``chest`` move;
everything else (hips, neck, head, limbs, hands, face) is untouched;
depth stays the torso plane (y = 0).

The ROLL (closes L6): the from-to apply is direction-exact but builds the
forearm's frame INDEPENDENTLY of the upper arm's — the difference to the
frame-continuous chain (the elbow as a pure hinge) is a pure twist about
the forearm axis, computed in closed form from the wrist-vs-elbow
geometry. The correction rides the ADDITIVE ``CanonicalPose.roll``
namespace (D-023, written when this module landed — keys
``forearm.L``/``forearm.R``; ``upper_arm.L/R`` RESERVED, v1 has no
humeral-twist evidence); ``fk_apply`` composes any present entry. Poses
without entries apply BYTE-IDENTICALLY — the straight-arm no-op is
structural (a straight arm has no flexion plane, so no entry is
produced).

The honesty rules (the finger/face rules one pass up): a not-applied
arch/roll changes NO bytes (the ledger lives in the returned report);
every skip/refuse carries a verbatim reason; constants are declared
untuned (D-008 style); geometry-only confidence caps at 0.75; below
0.55 nothing moves. Pure stdlib (math only), deterministic everywhere.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .canonical import CANONICAL
from .canonical_pose import TORSO_SPAN
from .fk_apply import (
    q_conj,
    q_from_to,
    q_mul,
    q_rotate,
    v_norm,
)

if TYPE_CHECKING:  # deferred at runtime (canonical_pose imports siblings)
    from .canonical_pose import CanonicalPose

Vec3 = tuple[float, float, float]

# -- declared constants (docs/SPINE.md; D-008 style: untuned) ----------------------

#: The CONVENTIONS ambiguity bar, reused; untuned.
SPINE_CONF_FLOOR = 0.55
#: The CONVENTIONS geometry-only cap.
SPINE_CONF_CAP = 0.75
#: Below this in-plane misalignment the pose stays flat (byte-identical).
ARCH_MISALIGN_FLOOR_RAD = math.radians(5.0)
#: Above this the pose class is not representable — REFUSED, never guessed.
ARCH_ENVELOPE_RAD = math.radians(60.0)
#: Half the declared torso span: the heavily-foreshortened torso class.
ARCH_CHORD_FLOOR = 0.5 * TORSO_SPAN
#: The D-008 torso fractions, reused verbatim (no new proportions).
T_SPINE = 0.09 / TORSO_SPAN
T_CHEST = 0.26 / TORSO_SPAN
#: The A1 start-tangent gain (declared untuned): T0 = chord rotated by
#: gain*phi toward the head side, T1 = the head axis. The basis facts
#: (h11 <= 0; h10+h11 = t(1-t)(2t-1)) force an over-rotated start tangent
#: for the interior joints to bow toward the head side.
ARCH_TANGENT_GAIN = 2.0
#: Below this elbow bend the flexion plane is noise-dominated — the
#: structural straight-arm no-op band.
ROLL_BEND_MIN_RAD = math.radians(15.0)
#: The D-008 forward-bend hinge at rest: forearms bend forward (-Y), which
#: hinges the rest T-pose arm (+X) about (0,0,-1).
ROLL_REST_HINGE: Vec3 = (0.0, 0.0, -1.0)

#: The D-023 namespace keys: v1 writes the FOREARM entries (the
#: frame-continuation correction); upper_arm is RESERVED (no humeral-twist
#: evidence exists in point landmarks). Names are stable public API.
ROLL_ROLES: tuple[str, ...] = ("forearm.L", "forearm.R")
ROLL_RESERVED_ROLES: tuple[str, ...] = ("upper_arm.L", "upper_arm.R")


def is_roll_role(name: str) -> bool:
    """True for D-023 namespace keys (written or reserved)."""
    return name in ROLL_ROLES or name in ROLL_RESERVED_ROLES


# -- the D-023 namespace entry ------------------------------------------------------

@dataclass
class RollEntry:
    """One solved roll correction: the signed twist about the bone's
    target axis (radians) plus the solve confidence."""

    twist_rad: float
    confidence: float

    def to_dict(self) -> dict[str, object]:
        return {
            "twist_rad": round(self.twist_rad, 6),
            "confidence": round(self.confidence, 4),
        }

    @staticmethod
    def from_dict(d: dict[str, object]) -> RollEntry:
        return RollEntry(
            twist_rad=float(d["twist_rad"]),  # type: ignore[arg-type]
            confidence=float(d["confidence"]),  # type: ignore[arg-type]
        )


def validate_roll_map(roll: dict[str, RollEntry]) -> None:
    """Loud namespace validation (the D-021 pattern)."""
    for key in roll:
        if not is_roll_role(key):
            raise ValueError(
                f"roll key {key!r} is not a roll role "
                f"(hint: roll roles look like forearm.L "
                f"— docs/SPINE.md, D-023; upper_arm keys are reserved)"
            )


# -- the arch pass ------------------------------------------------------------------

@dataclass
class ArchReport:
    """The arch pass ledger: what was measured and what was done."""

    applied: bool
    reason: str
    misalign_deg: float | None = None
    confidence: float | None = None


def head_axis_in_plane(pose: CanonicalPose) -> tuple[Vec3, float] | None:
    """The observed nose direction in-plane, recovered from the STORED
    derived head position (the declared placement model inverted).

    Returns ((nx, nz), theta_rad) or None when the head/neck positions
    cannot support the inversion. v_x/v_z = dx/(dz+h) = tan(theta/2)
    (the CAMERA.md A3 identity — the bias normalization cancels in the
    ratio), so theta = 2*atan2(v_x, v_z) EXACTLY.
    """
    pos = pose.positions
    if "neck" not in pos or "head" not in pos:
        return None
    vx = pos["head"][0] - pos["neck"][0]
    vz = pos["head"][2] - pos["neck"][2]
    if abs(vx) < 1e-12 and abs(vz) < 1e-12:
        return None
    theta = 2.0 * math.atan2(vx, vz)
    return (math.sin(theta), math.cos(theta)), theta


def solve_spine_arch(pose: CanonicalPose) -> tuple[CanonicalPose, ArchReport]:
    """Distribute the hips→shoulders→head misalignment across the torso.

    Returns (pose, report). A not-applied arch returns the INPUT pose
    unchanged (byte-identical serialization) with the verbatim reason —
    the ledger lives in the report, never in pose.notes. The applied pose
    differs in ``spine``/``chest`` only (plus one honest note).
    """
    pos = pose.positions
    if not all(r in pos for r in ("hips", "neck", "head")):
        return pose, ArchReport(False, "spine arch skipped: hips/neck/head positions incomplete")
    head_conf = pose.joint_confidence.get("head", 0.0)
    if head_conf < SPINE_CONF_FLOOR:
        return pose, ArchReport(
            False,
            f"spine arch skipped: head unobserved or below floor "
            f"({head_conf:.2f} < {SPINE_CONF_FLOOR})",
        )
    hx, _hy, hz = pos["hips"]
    nx, _ny, nz = pos["neck"]
    cx, cz = nx - hx, nz - hz
    chord_len = math.hypot(cx, cz)
    if chord_len < ARCH_CHORD_FLOOR:
        return pose, ArchReport(
            False,
            f"spine arch refused: torso chord degenerate "
            f"({chord_len:.3f} canon < {ARCH_CHORD_FLOOR:.3f})",
        )
    recovered = head_axis_in_plane(pose)
    if recovered is None:
        return pose, ArchReport(False, "spine arch refused: head-axis direction degenerate")
    (ndx, ndz), _theta = recovered
    phi = math.atan2(cz * ndx - cx * ndz, cx * ndx + cz * ndz)
    misalign_deg = round(math.degrees(phi), 2)
    if abs(phi) < ARCH_MISALIGN_FLOOR_RAD:
        return pose, ArchReport(
            False,
            f"spine arch skipped: flat (misalignment {math.degrees(abs(phi)):.1f} deg "
            f"below the {math.degrees(ARCH_MISALIGN_FLOOR_RAD):.0f} deg floor)",
            misalign_deg=misalign_deg,
        )
    if abs(phi) > ARCH_ENVELOPE_RAD:
        return pose, ArchReport(
            False,
            f"spine arch refused: misalignment {math.degrees(abs(phi)):.1f} deg beyond "
            f"the {math.degrees(ARCH_ENVELOPE_RAD):.0f} deg envelope - pose class not "
            "representable; spine stays flat",
            misalign_deg=misalign_deg,
        )
    conf = min(pose.joint_confidence.get(r, 0.0) for r in ("hips", "neck", "head"))
    conf = min(conf, SPINE_CONF_CAP)
    if conf < SPINE_CONF_FLOOR:
        return pose, ArchReport(
            False,
            f"spine arch skipped: confidence {conf:.2f} below floor {SPINE_CONF_FLOOR}",
            misalign_deg=misalign_deg,
            confidence=round(conf, 4),
        )

    # A1: T0 = the chord rotated by gain*phi toward the head side,
    # T1 = the head axis. Interior joints at the D-008 fractions.
    ux, uz = cx / chord_len, cz / chord_len
    ga = phi * ARCH_TANGENT_GAIN
    cg, sg = math.cos(ga), math.sin(ga)
    tx0 = chord_len * (ux * cg + uz * sg)
    tz0 = chord_len * (-ux * sg + uz * cg)
    tx1, tz1 = chord_len * ndx, chord_len * ndz

    def hermite(t: float) -> tuple[float, float]:
        t2 = t * t
        t3 = t2 * t
        h00 = 2.0 * t3 - 3.0 * t2 + 1.0
        h10 = t3 - 2.0 * t2 + t
        h01 = -2.0 * t3 + 3.0 * t2
        h11 = t3 - t2
        return (h00 * hx + h10 * tx0 + h01 * nx + h11 * tx1,
                h00 * hz + h10 * tz0 + h01 * nz + h11 * tz1)

    sx, sz = hermite(T_SPINE)
    chx, chz = hermite(T_CHEST)
    positions = dict(pos)
    positions["spine"] = (sx, 0.0, sz)
    positions["chest"] = (chx, 0.0, chz)
    applied = _pose_with(pose, positions)
    applied.notes.append(
        f"spine: arch applied (misalignment {math.degrees(phi):.1f} deg, "
        f"confidence {conf:.2f})"
    )
    return applied, ArchReport(
        True, "applied", misalign_deg=misalign_deg, confidence=round(conf, 4)
    )


def _pose_with(pose: CanonicalPose, positions: dict[str, Vec3]) -> CanonicalPose:
    """A new CanonicalPose sharing everything but the positions. Carries
    the additive namespaces (hands/face/roll)."""
    return pose.__class__(
        positions=positions,
        flips=dict(pose.flips),
        confidence=pose.confidence,
        reliable=pose.reliable,
        scale=pose.scale,
        anchor=pose.anchor,
        notes=list(pose.notes),
        joint_confidence=dict(pose.joint_confidence),
        hands=dict(pose.hands),
        face=pose.face,
        roll=dict(pose.roll),
    )


# -- the roll pass ------------------------------------------------------------------

def roll_correction(u: Vec3, f: Vec3, r_u: Vec3, r_f: Vec3) -> float:
    """The signed twist about ``f`` from the minimal forearm frame to the
    frame-continuous one (docs/SPINE.md § The ROLL model). Pure function
    of the observed chain directions and the declared rest directions."""
    q_u = q_from_to(r_u, u)
    q_f = q_from_to(r_f, f)
    hinge_local = q_from_to(r_f, q_rotate(q_conj(q_u), f))
    q_c = q_mul(q_u, hinge_local)
    d = sum(a * b for a, b in zip(ROLL_REST_HINGE, r_f, strict=True))
    v0 = v_norm(tuple(ROLL_REST_HINGE[i] - d * r_f[i] for i in range(3)))
    a = q_rotate(q_f, v0)
    b = q_rotate(q_c, v0)
    cross = (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )
    return math.atan2(
        sum(x * y for x, y in zip(f, cross, strict=True)),
        sum(x * y for x, y in zip(a, b, strict=True)),
    )


@dataclass
class RollReport:
    """The roll pass ledger: per-side entries, skips with verbatim
    reasons, and the entry map written into the pose."""

    entries: dict[str, RollEntry]
    rows: list[str]


def solve_arm_roll(pose: CanonicalPose) -> tuple[CanonicalPose, RollReport]:
    """Solve per-side forearm roll corrections into ``pose.roll``.

    Returns (pose, report). Straight/low-confidence sides produce NO
    entry (skips are ledgered in the report rows); a pose with no entries
    at all is returned UNCHANGED (byte-identical serialization)."""
    pos = pose.positions
    entries: dict[str, RollEntry] = {}
    rows: list[str] = []
    for side in ("L", "R"):
        up, fo, ha = f"upper_arm.{side}", f"forearm.{side}", f"hand.{side}"
        if not all(r in pos for r in (up, fo, ha)):
            rows.append(f"roll.{side}: skipped - chain incomplete ({up}/{fo}/{ha})")
            continue
        u = v_norm((pos[fo][0] - pos[up][0], pos[fo][1] - pos[up][1], pos[fo][2] - pos[up][2]))
        f = v_norm((pos[ha][0] - pos[fo][0], pos[ha][1] - pos[fo][1], pos[ha][2] - pos[fo][2]))
        dot = max(-1.0, min(1.0, u[0] * f[0] + u[1] * f[1] + u[2] * f[2]))
        beta = math.acos(dot)
        conf = min(
            pose.joint_confidence.get(fo, 0.0), pose.joint_confidence.get(ha, 0.0)
        )
        conf = min(conf, SPINE_CONF_CAP)
        if beta < ROLL_BEND_MIN_RAD:
            rows.append(
                f"roll.{side}: skipped - bend {math.degrees(beta):.1f} deg below the "
                f"{math.degrees(ROLL_BEND_MIN_RAD):.0f} deg floor - flexion plane "
                "noise-dominated, no entry"
            )
            continue
        if conf < SPINE_CONF_FLOOR:
            rows.append(
                f"roll.{side}: skipped - confidence {conf:.2f} below floor "
                f"{SPINE_CONF_FLOOR}, no entry"
            )
            continue
        twist = roll_correction(u, f, CANONICAL[up].direction, CANONICAL[fo].direction)
        entries[fo] = RollEntry(twist_rad=twist, confidence=round(conf, 4))
        rows.append(
            f"roll.{side}: twist {math.degrees(twist):+.1f} deg, conf {conf:.2f}"
        )
    if not entries:
        return pose, RollReport(entries=entries, rows=rows)
    merged = dict(pose.roll)
    merged.update(entries)
    validate_roll_map(merged)
    applied = _pose_with(pose, dict(pos))
    applied.roll = merged
    for fo in sorted(entries):
        applied.notes.append(
            f"arm roll: {fo} twist {math.degrees(entries[fo].twist_rad):+.1f} deg "
            f"applied at apply time (confidence {entries[fo].confidence:.2f})"
        )
    return applied, RollReport(entries=entries, rows=rows)


__all__ = [
    "ARCH_CHORD_FLOOR",
    "ARCH_ENVELOPE_RAD",
    "ARCH_MISALIGN_FLOOR_RAD",
    "ARCH_TANGENT_GAIN",
    "ArchReport",
    "ROLL_RESERVED_ROLES",
    "ROLL_REST_HINGE",
    "ROLL_BEND_MIN_RAD",
    "ROLL_ROLES",
    "RollEntry",
    "RollReport",
    "SPINE_CONF_CAP",
    "SPINE_CONF_FLOOR",
    "T_CHEST",
    "T_SPINE",
    "head_axis_in_plane",
    "is_roll_role",
    "roll_correction",
    "solve_arm_roll",
    "solve_spine_arch",
    "validate_roll_map",
]
