"""Canonical pose solve: 133 keypoints for one figure -> 3D canonical pose.

2.5D lift from an orthographic view. Coordinates: canonical convention (Z up,
facing -Y, character-left = +X), unit = hip height; bone lengths are the
canonical length ratios from :mod:`riggermortis.canonical`.

Role-position semantics (matching ``canonical.rest_skeleton``): a role's
position is the joint at the HEAD of that role's bone. Keypoints therefore
map as: shoulder kp -> ``upper_arm.*``, elbow kp -> ``forearm.*``, wrist kp
-> ``hand.*``, hip kp -> ``upper_leg.*``, knee kp -> ``lower_leg.*``, ankle
kp -> ``foot.*``. The torso line hips->mid-shoulders spans 0.45 units
(0.09 hips + 0.17 spine + 0.19 chest), which puts ``spine`` at 0.2 and
``chest`` at ~0.578 of that span; the neck bone starts at mid-shoulders.

Method (v1, documented honestly):
- In-plane (x, z) coordinates come from the image relative to an anchored
  root (the hips midpoint, or the neck midpoint if hips are unusable), scaled
  by pixels-per-canonical-unit.
- Scale is initialized from the hips->neck span (least pose-sensitive) and
  refined upward until every observed limb segment fits inside its canonical
  3D length (2D length is a LOWER bound under orthographic projection).
- Depth (y, toward camera = -Y) is the only unknown per joint. Shoulder and
  hip girdles anchor y = 0 (rigid by symmetry). Proximal limb segments
  (upper arm, thigh) take a fixed forward prior (y_child = -delta: limbs hang
  slightly in front of the torso plane). Distal segments (forearm, shank)
  are the classic elbow/knee flip ambiguity: all 16 sign combinations of the
  four distal segments are enumerated and scored by the depth-prior energy
  E = sum(conf_j * y_j^2) over flip-affected joints. Reprojection error is 0
  by construction (x/z are read off the image), so the depth prior is the
  discriminator and the winning margin feeds the reported confidence. A whole
  limb's global front/back mirror remains underdetermined from one view —
  the known single-view limitation, surfaced via ``confidence`` and the
  review overlay (P1-7) rather than hidden.
- Unobserved roles (root, spine, chest, shoulder.*) are placed from the
  anchor chain with canonical proportions; hands continue the forearm; head
  direction is biased by the nose observation when available.
- Symmetry is enforced structurally: paired girdle joints share the y = 0
  anchor and every paired bone uses the same canonical length.

Pure stdlib (math only) so the full solver runs and tests without numpy.
Deterministic: no randomness, keyed iteration, fixed tie-break (forward).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .canonical import CANONICAL, LEFT, RIGHT, mirror_role, rest_skeleton
from .inference.poses import (
    ANKLE_L,
    ANKLE_R,
    BIG_TOE_L,
    BIG_TOE_R,
    ELBOW_L,
    ELBOW_R,
    HIP_L,
    HIP_R,
    KEYPOINT_COUNT,
    KNEE_L,
    KNEE_R,
    NOSE,
    SHOULDER_L,
    SHOULDER_R,
    SMALL_TOE_L,
    SMALL_TOE_R,
    WRIST_L,
    WRIST_R,
)

#: Hips joint -> mid-shoulders in canonical units (see module docstring).
TORSO_SPAN = 0.09 + 0.17 + 0.19

Vec3 = tuple[float, float, float]

_MIN_CONF = 0.05
_SCALE_SAFETY = 1.02


# -- observations ---------------------------------------------------------------

def _mid(
    a: tuple[float, float], b: tuple[float, float], ca: float, cb: float
) -> tuple[tuple[float, float], float]:
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0), min(ca, cb)


def observations_from_keypoints(
    keypoints: list[tuple[float, float]], confidences: list[float]
) -> dict[str, tuple[tuple[float, float], float]]:
    """Map 133 COCO-WholeBody keypoints to canonical-role pixel observations.

    Returns ``{role: ((u, v), confidence)}`` for roles with usable confidence
    (>= 0.05). Midpoint roles (neck, hips, toes) take the minimum of their
    sources' confidence — both sources must be usable.
    """
    if len(keypoints) != KEYPOINT_COUNT or len(confidences) != KEYPOINT_COUNT:
        raise ValueError(
            f"expected {KEYPOINT_COUNT} keypoints/confidences, "
            f"got {len(keypoints)}/{len(confidences)}"
        )
    kp, cf = keypoints, confidences
    out: dict[str, tuple[tuple[float, float], float]] = {}
    single = {
        "upper_arm.L": ELBOW_L,
        "upper_arm.R": ELBOW_R,
        "forearm.L": WRIST_L,
        "forearm.R": WRIST_R,
        "upper_leg.L": HIP_L,
        "upper_leg.R": HIP_R,
        "lower_leg.L": KNEE_L,
        "lower_leg.R": KNEE_R,
        "foot.L": ANKLE_L,
        "foot.R": ANKLE_R,
        "head": NOSE,  # approximation: the nose marks the face, not the skull base
    }
    for role, idx in single.items():
        if cf[idx] >= _MIN_CONF:
            out[role] = (kp[idx], cf[idx])
    pairs = {
        "neck": (SHOULDER_L, SHOULDER_R),
        "hips": (HIP_L, HIP_R),
        "toe.L": (BIG_TOE_L, SMALL_TOE_L),
        "toe.R": (BIG_TOE_R, SMALL_TOE_R),
    }
    for role, (ia, ib) in pairs.items():
        if cf[ia] >= _MIN_CONF and cf[ib] >= _MIN_CONF:
            out[role] = _mid(kp[ia], kp[ib], cf[ia], cf[ib])
    return out


# -- result model ----------------------------------------------------------------

@dataclass
class CanonicalPose:
    """Solved pose: canonical role positions plus honest solve metadata."""

    positions: dict[str, Vec3]
    flips: dict[str, int]  # distal segment sign: -1 forward / +1 backward
    confidence: float
    reliable: bool
    scale: float  # pixels per canonical unit (hip height)
    anchor: str  # role anchoring the root ("hips" or "neck")
    notes: list[str] = field(default_factory=list)
    joint_confidence: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "positions": {r: list(p) for r, p in sorted(self.positions.items())},
            "flips": dict(sorted(self.flips.items())),
            "confidence": round(self.confidence, 4),
            "reliable": self.reliable,
            "scale": round(self.scale, 4),
            "anchor": self.anchor,
            "notes": list(self.notes),
            "joint_confidence": {
                r: round(c, 4) for r, c in sorted(self.joint_confidence.items())
            },
        }

    @staticmethod
    def from_dict(d: dict[str, object]) -> CanonicalPose:
        """Rebuild a pose from :meth:`to_dict` output (payload round-trip)."""
        return CanonicalPose(
            positions={
                str(role): (float(p[0]), float(p[1]), float(p[2]))  # type: ignore[index]
                for role, p in d["positions"].items()  # type: ignore[union-attr]
            },
            flips={str(k): int(v) for k, v in d["flips"].items()},  # type: ignore[union-attr]
            confidence=float(d["confidence"]),  # type: ignore[arg-type]
            reliable=bool(d["reliable"]),  # type: ignore[arg-type]
            scale=float(d["scale"]),  # type: ignore[arg-type]
            anchor=str(d["anchor"]),
            notes=[str(n) for n in d.get("notes", [])],  # type: ignore[union-attr]
            joint_confidence={
                str(k): float(v) for k, v in d.get("joint_confidence", {}).items()  # type: ignore[union-attr]
            },
        )

    def mirrored(self) -> CanonicalPose:
        """Mirror across the character's YZ plane: x -> -x, .L/.R roles swapped.

        Depth (y) semantics are unchanged — an x-mirror does not flip
        front/back — so flip values move with their side key untouched.
        Confidence, notes, and metadata carry over: this is a geometry
        operation, not a re-solve.
        """
        return CanonicalPose(
            positions={
                mirror_role(role): (-p[0], p[1], p[2])
                for role, p in self.positions.items()
            },
            flips={mirror_role(k): v for k, v in self.flips.items()},
            confidence=self.confidence,
            reliable=self.reliable,
            scale=self.scale,
            anchor=self.anchor,
            notes=list(self.notes),
            joint_confidence={
                mirror_role(k): v for k, v in self.joint_confidence.items()
            },
        )


# -- small vec helpers (stdlib) ---------------------------------------------------

def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _norm(a: Vec3) -> Vec3:
    n = math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])
    if n <= 1e-12:
        return (0.0, 0.0, 1.0)
    return (a[0] / n, a[1] / n, a[2] / n)


def _dist2d(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


# -- limb chains --------------------------------------------------------------------
#: flip key -> (girdle role, mid role, end role, proximal L, distal L).
#: Segments: girdle->mid is the proximal bone (fixed forward prior),
#: mid->end the distal bone (the flip-ambiguous one).

_FLIP_CHAINS: dict[str, tuple[str, str, str, float, float]] = {
    "forearm.L": ("upper_arm.L", "forearm.L", "hand.L", 0.32, 0.28),
    "forearm.R": ("upper_arm.R", "forearm.R", "hand.R", 0.32, 0.28),
    "lower_leg.L": ("upper_leg.L", "lower_leg.L", "foot.L", 0.50, 0.47),
    "lower_leg.R": ("upper_leg.R", "lower_leg.R", "foot.R", 0.50, 0.47),
}
_FLIP_KEYS = tuple(sorted(_FLIP_CHAINS))

#: Roles pinned to the torso plane (y = 0) by girdle rigidity.
_GIRDLE_ROLES = (
    "hips",
    "neck",
    "upper_arm.L",
    "upper_arm.R",
    "upper_leg.L",
    "upper_leg.R",
)


# -- solver ------------------------------------------------------------------------

def solve_pose(
    observations: dict[str, tuple[tuple[float, float], float]]
) -> CanonicalPose:
    """Lift one figure's 2D role observations to a canonical 3D pose.

    Never raises for weak input: it degrades to a low-confidence pose
    (``reliable=False``) so the review UI can show what happened.
    """
    notes: list[str] = []
    obs = {r: oc for r, oc in sorted(observations.items()) if oc[1] >= _MIN_CONF}

    if "hips" not in obs and "neck" not in obs:
        rest = rest_skeleton(1.0)
        return CanonicalPose(
            positions={r: v[0] for r, v in sorted(rest.items())},
            flips={k: -1 for k in _FLIP_KEYS},
            confidence=0.0,
            reliable=False,
            scale=1.0,
            anchor="none",
            notes=["no hips or neck observations; rest-pose fallback"],
            joint_confidence={},
        )

    anchor = "hips" if "hips" in obs else "neck"
    if anchor == "neck":
        notes.append("hips unobserved; anchored at neck, pelvis roles approximate")
    ax, ay = obs[anchor][0]
    joint_conf = {r: c for r, (_, c) in obs.items()}

    scale = _refine_scale(obs, _initial_scale(obs))
    if scale <= 1e-6:
        scale = 100.0
        notes.append("degenerate observation spread; scale forced to 100")

    plane = {r: ((u - ax) / scale, (ay - v) / scale) for r, ((u, v), _) in obs.items()}

    # Depth bones: (parent role, child role, canonical L, flip key or None).
    bones: list[tuple[str, str, float, str | None]] = []
    for flip_key, (girdle, mid, end, l_prox, l_dist) in sorted(_FLIP_CHAINS.items()):
        if girdle in obs and mid in obs:
            bones.append((girdle, mid, l_prox, None))
        if mid in obs and end in obs:
            bones.append((mid, end, l_dist, flip_key))

    ranked: list[tuple[float, tuple[int, ...]]] = []
    best_ys: dict[str, float] = {}
    best_energy = 0.0
    best_combo: tuple[int, ...] = (0,) * len(_FLIP_KEYS)
    for combo in _combos(len(_FLIP_KEYS)):
        ys: dict[str, float] = {r: 0.0 for r in _GIRDLE_ROLES}
        energy = 0.0
        for parent, child, length, flip_key in bones:
            dx = plane[child][0] - plane[parent][0]
            dz = plane[child][1] - plane[parent][1]
            delta_sq = length * length - (dx * dx + dz * dz)
            delta = math.sqrt(delta_sq) if delta_sq > 0.0 else 0.0
            sign = -1.0
            if flip_key is not None:
                sign = -1.0 if combo[_FLIP_KEYS.index(flip_key)] == 0 else 1.0
            y_child = ys.get(parent, 0.0) + sign * delta
            ys[child] = y_child
            if flip_key is not None:
                energy += obs[child][1] * _distal_energy(
                    parent, child, y_child, ys.get(parent, 0.0)
                )
        ranked.append((energy, combo))
        if len(ranked) == 1 or energy < best_energy:
            best_energy, best_combo, best_ys = energy, combo, ys
    ranked.sort(key=lambda t: (t[0], t[1]))

    flips = {k: (-1 if best_combo[i] == 0 else 1) for i, k in enumerate(_FLIP_KEYS)}
    flip_conf: dict[str, float] = {}
    for i, key in enumerate(_FLIP_KEYS):
        end_role = _FLIP_CHAINS[key][2]
        if end_role not in obs:
            flip_conf[key] = 0.0
            continue
        with_bit = min(e for e, c in ranked if c[i] == best_combo[i])
        without = min(e for e, c in ranked if c[i] != best_combo[i])
        margin = (without - with_bit) / (without + with_bit + 1e-9)
        flip_conf[key] = max(0.0, min(1.0, margin * 2.0))

    positions: dict[str, Vec3] = {
        r: (x, best_ys.get(r, 0.0), z) for r, (x, z) in sorted(plane.items())
    }
    _place_derived_roles(positions, plane, anchor, notes)

    core_obs = [
        r
        for r in (
            "hips", "neck", "upper_arm.L", "upper_arm.R", "forearm.L", "forearm.R",
            "upper_leg.L", "upper_leg.R", "lower_leg.L", "lower_leg.R",
        )
        if r in obs
    ]
    obs_quality = sum(obs[r][1] for r in core_obs) / len(core_obs) if core_obs else 0.0
    meaningful = [flip_conf[k] for k in _FLIP_KEYS if flip_conf[k] > 0.0]
    flip_quality = min(meaningful) if meaningful else 0.5
    confidence = max(0.0, min(1.0, 0.6 * obs_quality + 0.4 * flip_quality))
    reliable = confidence >= 0.55 and len(core_obs) >= 6

    return CanonicalPose(
        positions=positions,
        flips=flips,
        confidence=round(confidence, 4),
        reliable=reliable,
        scale=round(scale, 4),
        anchor=anchor,
        notes=notes,
        joint_confidence={
            **{r: round(c, 4) for r, c in sorted(joint_conf.items())},
            **{k: round(v, 4) for k, v in sorted(flip_conf.items())},
        },
    )


def _combos(n: int) -> list[tuple[int, ...]]:
    return [tuple((i >> b) & 1 for b in range(n)) for i in range(1 << n)]


#: Distal-pose priors (locked v1): depth-flattening plus anatomical flexion
#: asymmetry. Forearms do not rotate backward past straight (elbows bend
#: forward); shanks favor staying behind the knee line (knees bend backward,
#: small forward tolerance for standing/kicks). Weights are order-of-magnitude
#: choices, not fitted to the fixture set.
_FLATTEN_W = 0.5
_ELBOW_FLEX_W = 4.0
_KNEE_FLEX_W = 2.0
_KNEE_FWD_TOL = 0.05


def _distal_energy(parent: str, child: str, y_child: float, y_parent: float) -> float:
    _ = child
    energy = _FLATTEN_W * y_child * y_child
    if parent.startswith("forearm."):
        # Forearms bend forward: wrist behind the elbow is anatomically wrong.
        energy += _ELBOW_FLEX_W * max(0.0, y_child - y_parent) ** 2
    elif parent.startswith("lower_leg."):
        # Knees bend backward: allow a small forward tolerance (standing/kicks).
        energy += _KNEE_FLEX_W * max(0.0, (y_parent - y_child) - _KNEE_FWD_TOL) ** 2
    return energy


def _initial_scale(obs: dict[str, tuple[tuple[float, float], float]]) -> float:
    """Pixels per canonical unit from the hips->neck span (0.45 units)."""
    if "hips" in obs and "neck" in obs:
        d = _dist2d(obs["hips"][0], obs["neck"][0])
        if d > 1e-6:
            return d / TORSO_SPAN
    # Fallback: the longest observed limb segment vs its canonical length.
    best = 0.0
    for _girdle, mid, end, l_prox, l_dist in _FLIP_CHAINS.values():
        for a, b, length in ((mid, end, l_dist),):
            if a in obs and b in obs:
                best = max(best, _dist2d(obs[a][0], obs[b][0]) / length)
        if _girdle in obs and mid in obs:
            best = max(best, _dist2d(obs[_girdle][0], obs[mid][0]) / l_prox)
    return best if best > 1e-6 else 100.0


def _refine_scale(
    obs: dict[str, tuple[tuple[float, float], float]], scale: float
) -> float:
    """Grow the scale until every observed segment fits its 3D length.

    Under orthographic projection a 2D segment length is a lower bound on the
    3D length, so a segment longer (in pixels) than scale * L proves the
    scale is too small.
    """
    required = 0.0
    for _girdle, mid, end, l_prox, l_dist in _FLIP_CHAINS.values():
        if mid in obs and end in obs:
            required = max(required, _dist2d(obs[mid][0], obs[end][0]) / l_dist)
        if _girdle in obs and mid in obs:
            required = max(required, _dist2d(obs[_girdle][0], obs[mid][0]) / l_prox)
    if required > scale * (1.0 + 1e-9):
        return required * _SCALE_SAFETY
    return scale


def _place_derived_roles(
    positions: dict[str, Vec3],
    plane: dict[str, tuple[float, float]],
    anchor: str,
    notes: list[str],
) -> None:
    """Fill roles the keypoints cannot see: torso line, girdles, head, hands."""
    hips = positions.get("hips")
    neckobs = plane.get("neck")
    if hips is not None and neckobs is not None:
        # Torso line hips -> mid-shoulders (0.45 units): spine head at 0.09,
        # chest head at 0.26; the neck bone starts at mid-shoulders (0.45).
        positions["spine"] = (
            hips[0] + (neckobs[0] - hips[0]) * (0.09 / TORSO_SPAN),
            0.0,
            hips[2] + (neckobs[1] - hips[2]) * (0.09 / TORSO_SPAN),
        )
        positions["chest"] = (
            hips[0] + (neckobs[0] - hips[0]) * (0.26 / TORSO_SPAN),
            0.0,
            hips[2] + (neckobs[1] - hips[2]) * (0.26 / TORSO_SPAN),
        )
        positions.setdefault("neck", (neckobs[0], 0.0, neckobs[1]))
    elif "neck" in positions:
        notes.append("torso line unavailable; spine/chest placed below neck by canon ratios")
        nx, ny, nz = positions["neck"]
        positions["chest"] = (nx, ny, nz - 0.19)
        positions["spine"] = (nx, ny, nz - 0.19 - 0.17)
    if "hips" not in positions and anchor == "neck" and neckobs is not None:
        positions["hips"] = (neckobs[0], 0.0, neckobs[1] - TORSO_SPAN)
    if "hips" in positions:
        positions.setdefault("root", positions["hips"])

    # Head joint: the head bone starts one neck-length above mid-shoulders;
    # direction biased by the nose observation when available (flagged approx).
    if "neck" in positions:
        nx, ny, nz = positions["neck"]
        dirv = (0.0, -0.1, 1.0)
        hx, hz = plane.get("head", (nx, nz + 1.0))
        dx, dz = hx - nx, hz - nz
        if math.hypot(dx, dz) > 1e-6:
            dirv = _norm((0.5 * dx / math.hypot(dx, dz), -0.15, 0.5 * dz / math.hypot(dx, dz) + 0.5))
        positions["head"] = (
            nx + dirv[0] * 0.11,
            ny + dirv[1] * 0.11,
            nz + dirv[2] * 0.11,
        )

    # Shoulder girdle joints: slightly inboard of the arm joints, torso plane.
    for side, arm in ((LEFT, "upper_arm.L"), (RIGHT, "upper_arm.R")):
        if arm in positions and f"shoulder.{side}" not in positions:
            bx, _by, bz = positions[arm]
            inward = -0.05 if bx >= 0.0 else 0.05  # toward the torso line
            positions[f"shoulder.{side}"] = (bx + inward, 0.0, bz + 0.04)

    # Hands continue the forearm direction; toes continue the foot.
    for side in (LEFT, RIGHT):
        hand, forearm, upper = f"hand.{side}", f"forearm.{side}", f"upper_arm.{side}"
        if hand not in positions and forearm in positions and upper in positions:
            d = _norm(_sub(positions[forearm], positions[upper]))
            ln = CANONICAL[hand].length_ratio
            fx, fy, fz = positions[forearm]
            positions[hand] = (fx + d[0] * ln, fy + d[1] * ln, fz + d[2] * ln)
        toe, foot = f"toe.{side}", f"foot.{side}"
        if toe not in positions and foot in positions:
            fx, fy, fz = positions[foot]
            positions[toe] = (fx, fy - 0.08, fz - CANONICAL[toe].length_ratio)
        elif toe in positions and foot in positions:
            tx, tz = plane[toe]
            _fx, fy, _fz = positions[foot]
            positions[toe] = (tx, fy - 0.08, tz)
