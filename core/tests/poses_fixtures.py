"""20 synthetic posed figures with known ground truth (P1-4 flip accept).

Each fixture is a hand-built canonical-space pose (exact canonical bone
lengths, so the solver's rigid-bone assumption holds by construction),
projected orthographically into pixel observations. Ground-truth flips are
the sign of the distal segment's depth offset (y_distal_joint - y_mid_joint);
``None`` marks a straight distal segment (|dy| < 0.06 units) where either
flip is visually equivalent — the solver's tie-break must not count against
it.

Scope note (honest): proximal limb segments keep a forward-or-neutral depth
bias across the set — the solver's fixed forward prior on upper arms/thighs
is the documented v1 limitation for limbs swung behind the torso plane.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

Vec3 = tuple[float, float, float]

L_UPPER_ARM = 0.32
L_FOREARM = 0.28
L_THIGH = 0.50
L_SHANK = 0.47

SHOULDER_L_ANCHOR: Vec3 = (0.13, 0.0, 0.45)
SHOULDER_R_ANCHOR: Vec3 = (-0.13, 0.0, 0.45)
HIP_L_ANCHOR: Vec3 = (0.08, 0.0, 0.0)
HIP_R_ANCHOR: Vec3 = (-0.08, 0.0, 0.0)

_FLIP_TOL = 0.06


def _d(x: float, y: float, z: float) -> Vec3:
    n = math.sqrt(x * x + y * y + z * z)
    return (x / n, y / n, z / n)


@dataclass
class PoseFixture:
    name: str
    positions: dict[str, Vec3]
    gt_flips: dict[str, int | None] = field(default_factory=dict)


def _chain(start: Vec3, prox: Vec3, dist: Vec3, l_prox: float, l_dist: float) -> tuple[Vec3, Vec3]:
    mid = (start[0] + prox[0] * l_prox, start[1] + prox[1] * l_prox, start[2] + prox[2] * l_prox)
    end = (mid[0] + dist[0] * l_dist, mid[1] + dist[1] * l_dist, mid[2] + dist[2] * l_dist)
    return mid, end


def _flip_of(dist_dir: Vec3, l_dist: float) -> int | None:
    dy = dist_dir[1] * l_dist
    if abs(dy) < _FLIP_TOL:
        return None
    return -1 if dy < 0 else 1  # -1 = forward (-y), matching the solver encoding


def build_pose(
    name: str,
    arm_l: tuple[Vec3, Vec3],
    arm_r: tuple[Vec3, Vec3],
    leg_l: tuple[Vec3, Vec3],
    leg_r: tuple[Vec3, Vec3],
    torso_tilt: float = 0.0,
) -> PoseFixture:
    """Build a full pose from limb direction pairs (proximal, distal)."""
    # Torso tilt (bow): rotate the shoulder line about X (forward = -y).
    st = math.sin(torso_tilt)
    ct = math.cos(torso_tilt)

    def rot(p: Vec3) -> Vec3:
        return (p[0], p[1] * ct - p[2] * st, p[1] * st + p[2] * ct)

    shoulder_l = rot(SHOULDER_L_ANCHOR)
    shoulder_r = rot(SHOULDER_R_ANCHOR)

    positions: dict[str, Vec3] = {
        "hips": (0.0, 0.0, 0.0),
        "root": (0.0, 0.0, 0.0),
        "spine": (0.0, 0.0, 0.09),
        "chest": (0.0, 0.0, 0.26),
        "upper_arm.L": shoulder_l,
        "upper_arm.R": shoulder_r,
        "upper_leg.L": HIP_L_ANCHOR,
        "upper_leg.R": HIP_R_ANCHOR,
    }
    # Mid-shoulders hosts the start of the neck bone; the head joint rides
    # 0.11 further along the (tilted) torso axis.
    midshould = (
        (shoulder_l[0] + shoulder_r[0]) / 2,
        (shoulder_l[1] + shoulder_r[1]) / 2,
        (shoulder_l[2] + shoulder_r[2]) / 2,
    )
    positions["neck"] = midshould
    up_axis = rot((0.0, 0.0, 1.0))
    positions["head"] = (
        midshould[0] + up_axis[0] * 0.11,
        midshould[1] + up_axis[1] * 0.11,
        midshould[2] + up_axis[2] * 0.11,
    )

    gt: dict[str, int | None] = {}
    for side, (prox, dist), anchor, lp, ld, mid_role, end_role in (
        ("L", arm_l, shoulder_l, L_UPPER_ARM, L_FOREARM, "forearm.L", "hand.L"),
        ("R", arm_r, shoulder_r, L_UPPER_ARM, L_FOREARM, "forearm.R", "hand.R"),
        ("L", leg_l, HIP_L_ANCHOR, L_THIGH, L_SHANK, "lower_leg.L", "foot.L"),
        ("R", leg_r, HIP_R_ANCHOR, L_THIGH, L_SHANK, "lower_leg.R", "foot.R"),
    ):
        mid, end = _chain(anchor, prox, dist, lp, ld)
        positions[mid_role] = mid
        positions[end_role] = end
        flip_key = f"forearm.{side}" if mid_role.startswith("forearm") else f"lower_leg.{side}"
        gt[flip_key] = _flip_of(dist, ld)
    # Toes continue straight forward from the ankle (fixture convention).
    positions["toe.L"] = (positions["foot.L"][0], positions["foot.L"][1] - 0.12, positions["foot.L"][2])
    positions["toe.R"] = (positions["foot.R"][0], positions["foot.R"][1] - 0.12, positions["foot.R"][2])
    return PoseFixture(name=name, positions=positions, gt_flips=gt)


_DOWN = (0.0, 0.0, -1.0)


def _all_poses() -> list[PoseFixture]:
    poses = [
        build_pose("t_pose", (_d(1, 0, 0), _d(1, 0, 0)), (_d(1, 0, 0), _d(1, 0, 0)),
                   (_DOWN, _DOWN), (_DOWN, _DOWN)),
        build_pose("a_pose", (_d(0.5, 0, -0.87), _d(0.5, 0, -0.87)),
                   (_d(-0.5, 0, -0.87), _d(-0.5, 0, -0.87)), (_DOWN, _DOWN), (_DOWN, _DOWN)),
        build_pose("arms_down_relaxed", (_d(0.1, 0, -1), _d(0.35, -0.35, -0.87)),
                   (_d(-0.1, 0, -1), _d(-0.35, -0.35, -0.87)), (_DOWN, _DOWN), (_DOWN, _DOWN)),
        build_pose("arms_crossed", (_d(0.05, 0, -1), _d(-0.85, -0.5, -0.2)),
                   (_d(-0.05, 0, -1), _d(0.85, -0.5, -0.2)), (_DOWN, _DOWN), (_DOWN, _DOWN)),
        build_pose("hands_on_hips", (_d(0.75, 0, -0.66), _d(-0.45, -0.5, -0.74)),
                   (_d(-0.75, 0, -0.66), _d(0.45, -0.5, -0.74)), (_DOWN, _DOWN), (_DOWN, _DOWN)),
        build_pose("wave_right", (_d(0.1, 0, -1), _d(0.35, -0.35, -0.87)),
                   (_d(0.35, -0.1, 0.93), _d(-0.25, -0.5, 0.83)), (_DOWN, _DOWN), (_DOWN, _DOWN)),
        build_pose("v_up", (_d(0.5, 0, 0.87), _d(0.5, 0, 0.87)),
                   (_d(-0.5, 0, 0.87), _d(-0.5, 0, 0.87)), (_DOWN, _DOWN), (_DOWN, _DOWN)),
        build_pose("kneel", (_d(0.1, 0, -1), _d(0.35, -0.35, -0.87)),
                   (_d(-0.1, 0, -1), _d(-0.35, -0.35, -0.87)),
                   (_d(0, -0.15, -0.99), _d(0, 0.98, -0.2)), (_d(0, -0.15, -0.99), _d(0, 0.98, -0.2))),
        build_pose("kick_front_r", (_d(0.3, -0.4, -0.87), _d(0.2, -0.8, -0.57)),
                   (_d(-0.4, 0.3, -0.87), _d(-0.3, 0.2, -0.93)),
                   (_DOWN, _DOWN), (_d(0, -0.7, -0.71), _d(0, -0.3, -0.95))),
        build_pose("lunge", (_d(0.3, -0.3, -0.9), _d(0.3, -0.6, -0.74)),
                   (_d(-0.3, 0.15, -0.94), _d(-0.3, 0, -0.95)),
                   (_d(0, 0.1, -0.99), _d(0, 0.05, -1)), (_d(0, -0.64, -0.77), _d(0, 0, -1))),
        build_pose("crouch", (_d(0.5, -0.3, -0.81), _d(0.3, -0.7, -0.65)),
                   (_d(-0.5, -0.3, -0.81), _d(-0.3, -0.7, -0.65)),
                   (_d(0, -0.7, -0.71), _d(0, 0.6, -0.8)), (_d(0, -0.7, -0.71), _d(0, 0.6, -0.8))),
        build_pose("squat_deep", (_d(0.95, -0.2, -0.24), _d(0.2, -0.97, -0.12)),
                   (_d(-0.95, -0.2, -0.24), _d(-0.2, -0.97, -0.12)),
                   (_d(0, -0.85, -0.53), _d(0, 0.5, -0.87)), (_d(0, -0.85, -0.53), _d(0, 0.5, -0.87))),
        build_pose("punch_r", (_d(0.3, -0.2, -0.93), _d(-0.45, -0.55, -0.7)),
                   (_d(0, -0.37, -0.93), _d(0, -1, -0.05)), (_DOWN, _DOWN),
                   (_d(0, -0.2, -0.98), _d(0, 0.1, -1))),
        build_pose("walk_stride", (_d(0, -0.5, -0.87), _d(0, -0.5, -0.87)),
                   (_d(0, 0.15, -0.99), _d(0, 0, -1)),
                   (_d(0, -0.45, -0.89), _d(0, 0, -1)), (_d(0, 0.08, -1), _d(0, 0.03, -1))),
        build_pose("reach_forward", (_d(0, -0.97, -0.26), _d(0, -1, 0)),
                   (_d(0, -0.97, -0.26), _d(0, -1, 0)), (_DOWN, _DOWN), (_DOWN, _DOWN)),
        build_pose("bow", (_d(0.1, 0.1, -1), _d(0.2, 0, -1)), (_d(-0.1, 0.1, -1), _d(-0.2, 0, -1)),
                   (_DOWN, _DOWN), (_DOWN, _DOWN), torso_tilt=0.35),
        build_pose("sit", (_d(0.1, 0, -1), _d(0.35, -0.35, -0.87)),
                   (_d(-0.1, 0, -1), _d(-0.35, -0.35, -0.87)),
                   (_d(0, -1, 0), _d(0, 0, -1)), (_d(0, -1, 0), _d(0, 0, -1))),
        build_pose("jump", (_d(0.4, -0.2, 0.89), _d(0.2, -0.6, 0.78)),
                   (_d(-0.4, -0.2, 0.89), _d(-0.2, -0.6, 0.78)),
                   (_d(0, -0.2, -0.98), _d(0, 0.85, -0.53)), (_d(0, -0.2, -0.98), _d(0, 0.85, -0.53))),
        build_pose("hero_landing", (_d(0.2, -0.3, -0.93), _d(0.4, -0.5, -0.77)),
                   (_d(-0.6, -0.2, 0.78), _d(-0.3, -0.5, 0.82)),
                   (_d(0, -0.8, -0.6), _d(0, 0.5, -0.87)), (_d(-0.9, 0, -0.44), _d(-0.95, 0, -0.3))),
        # Deliberately hard: wrists held behind the back — the documented
        # single-view limitation; the solver is expected to prefer forward.
        build_pose("arms_back", (_d(0.1, 0, -1), _d(0, 0.6, -0.8)),
                   (_d(-0.1, 0, -1), _d(0, 0.6, -0.8)), (_DOWN, _DOWN), (_DOWN, _DOWN)),
    ]
    return poses


POSES: list[PoseFixture] = _all_poses()


def project_fixture(fx: PoseFixture, scale: float = 200.0, center: tuple[float, float] = (500.0, 700.0)):
    """Orthographic projection -> canonical_pose observation dict."""
    obs: dict[str, tuple[tuple[float, float], float]] = {}

    def proj(p: Vec3) -> tuple[tuple[float, float], float]:
        return ((center[0] + scale * p[0], center[1] - scale * p[2]), 0.95)

    for role in (
        "upper_arm.L", "upper_arm.R", "forearm.L", "forearm.R",
        "hand.L", "hand.R", "upper_leg.L", "upper_leg.R",
        "lower_leg.L", "lower_leg.R", "foot.L", "foot.R", "head",
    ):
        if role in fx.positions:
            obs[role] = proj(fx.positions[role])
    sl, sr = fx.positions["upper_arm.L"], fx.positions["upper_arm.R"]
    neck = ((sl[0] + sr[0]) / 2, (sl[2] + sr[2]) / 2)
    obs["neck"] = ((center[0] + scale * neck[0], center[1] - scale * neck[1]), 0.95)
    hl, hr = fx.positions["upper_leg.L"], fx.positions["upper_leg.R"]
    hips = ((hl[0] + hr[0]) / 2, (hl[2] + hr[2]) / 2)
    obs["hips"] = ((center[0] + scale * hips[0], center[1] - scale * hips[1]), 0.95)
    return obs


def fixture_to_keypoints(fx: PoseFixture):
    """Project to a full 133-keypoint array (body indices filled, rest empty)."""
    kps: list[tuple[float, float]] = [(0.0, 0.0)] * 133
    conf: list[float] = [0.0] * 133
    scale, center = 200.0, (500.0, 700.0)

    def put(idx: int, p: Vec3, c: float = 0.95) -> None:
        kps[idx] = (center[0] + scale * p[0], center[1] - scale * p[2])
        conf[idx] = c

    import riggermortis.inference.poses as K

    put(K.NOSE, fx.positions.get("head", (0, 0, 0.7)), 0.9)
    put(K.SHOULDER_L, fx.positions["upper_arm.L"])
    put(K.SHOULDER_R, fx.positions["upper_arm.R"])
    put(K.ELBOW_L, fx.positions["forearm.L"])
    put(K.ELBOW_R, fx.positions["forearm.R"])
    put(K.WRIST_L, fx.positions["hand.L"])
    put(K.WRIST_R, fx.positions["hand.R"])
    put(K.HIP_L, fx.positions["upper_leg.L"])
    put(K.HIP_R, fx.positions["upper_leg.R"])
    put(K.KNEE_L, fx.positions["lower_leg.L"])
    put(K.KNEE_R, fx.positions["lower_leg.R"])
    put(K.ANKLE_L, fx.positions["foot.L"])
    put(K.ANKLE_R, fx.positions["foot.R"])
    return kps, conf
