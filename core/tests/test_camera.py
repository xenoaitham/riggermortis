"""P8-5 camera-solve contract tests (docs/CAMERA.md, the FACE.md pattern).

The solve is PURE core (positions + confidences + scale + bbox in, camera
params or a LOUD refusal out). These tests pin: the declared rulers, the
closed-form yaw + its sign convention, the gradient pitch + sign, the
distance/height closure on prior-consistent GT, every refusal class's
verbatim shape, twin determinism, and the consensus's circular mean.
SYNTHETIC GT: joints projected through the declared pinhole model.
"""
from __future__ import annotations

import math

import pytest

from riggermortis.camera import (
    CAMERA_CONF_FLOOR,
    R_HIP,
    R_SHOULDER,
    R_STAND,
    R_TORSO,
    consensus_camera,
    solve_camera_figure,
)
from riggermortis.canonical import rest_skeleton
from riggermortis.canonical_pose import observations_from_keypoints, solve_pose
from riggermortis.inference.poses import (
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
    WRIST_L,
    WRIST_R,
)

LENS_MM = 50.0
SENSOR_W_MM = 36.0
IMG_W, IMG_H = 640, 960


def _project(points, cam, target, img_w=IMG_W, img_h=IMG_H):
    """The declared composed yaw+pitch pinhole model (docs/CAMERA.md,
    A10/A11: right = fw x up IS the screen-right axis -> plus-sign u; the
    sensor's LONG edge fits the frame's LONG side)."""
    fw = [t - c for t, c in zip(target, cam, strict=True)]
    ln = math.sqrt(sum(v * v for v in fw))
    fw = [v / ln for v in fw]
    right = [fw[1], -fw[0], 0.0]
    rl = math.hypot(right[0], right[1]) or 1.0
    right = [v / rl for v in right]
    up = [
        right[1] * fw[2] - right[2] * fw[1],
        right[2] * fw[0] - right[0] * fw[2],
        right[0] * fw[1] - right[1] * fw[0],
    ]
    if img_w >= img_h:
        sw, sh = SENSOR_W_MM, SENSOR_W_MM * img_h / img_w
    else:
        sw, sh = SENSOR_W_MM * img_w / img_h, SENSOR_W_MM
    out = []
    for p in points:
        rel = [p[i] - cam[i] for i in range(3)]
        d = sum(rel[i] * fw[i] for i in range(3))
        ru = sum(rel[i] * right[i] for i in range(3))
        rv = sum(rel[i] * up[i] for i in range(3))
        out.append((0.5 + ru / d * LENS_MM / sw,
                    0.5 + rv / d * LENS_MM / sh))
    return out


def _rest_points():
    rest = rest_skeleton(2.0, hip_height_frac=0.5)
    pts = {r: tuple(float(v) for v in hv[0]) for r, hv in rest.items()}
    keep = (
        "hips", "spine", "chest", "neck", "head",
        "shoulder.L", "upper_arm.L", "forearm.L", "hand.L",
        "shoulder.R", "upper_arm.R", "forearm.R", "hand.R",
        "upper_leg.L", "lower_leg.L", "foot.L", "toe.L",
        "upper_leg.R", "lower_leg.R", "foot.R", "toe.R",
    )
    return {r: pts[r] for r in keep}


_KP = {
    "head": NOSE, "upper_arm.L": SHOULDER_L, "upper_arm.R": SHOULDER_R,
    "forearm.L": ELBOW_L, "forearm.R": ELBOW_R, "hand.L": WRIST_L,
    "hand.R": WRIST_R, "upper_leg.L": HIP_L, "upper_leg.R": HIP_R,
    "lower_leg.L": KNEE_L, "lower_leg.R": KNEE_R, "foot.L": ANKLE_L,
    "foot.R": ANKLE_R, "toe.L": BIG_TOE_L, "toe.R": BIG_TOE_R,
}


def _gt_case(yaw_deg, dist, elev):
    """Noiseless tier-1 GT: project the rest fixture through the GT camera,
    run the REAL observations+pose solve, return the solve inputs."""
    pts = _rest_points()
    zs = [p[2] for p in pts.values()]
    target = (0.0, 0.0, (max(zs) + min(zs)) / 2.0)
    y = math.radians(yaw_deg)
    cam = (
        target[0] - dist * math.sin(y),
        target[1] - dist * math.cos(y),
        target[2] + elev,
    )
    roles = sorted(_KP, key=lambda r: _KP[r])
    world = [pts[r] for r in roles] + [
        (pts["head"][0], pts["head"][1] - 0.10, pts["head"][2])
    ]
    proj = _project(world, cam, target)
    kps = [(0.0, 0.0)] * KEYPOINT_COUNT
    for i, r in enumerate(roles):
        u, v = proj[i]
        kps[_KP[r]] = (u * IMG_W, (1.0 - v) * IMG_H)
    # the nose kp carries the declared forward offset (the yaw signal)
    u, v = proj[-1]
    kps[NOSE] = (u * IMG_W, (1.0 - v) * IMG_H)
    confs = [1.0 if kps[i] != (0.0, 0.0) else 0.0 for i in range(KEYPOINT_COUNT)]
    obs = observations_from_keypoints(kps, confs)
    pose = solve_pose(obs)
    xs = [kps[i][0] for i in range(KEYPOINT_COUNT) if confs[i] > 0.0]
    ys = [kps[i][1] for i in range(KEYPOINT_COUNT) if confs[i] > 0.0]
    bbox = (min(xs), min(ys), max(xs), max(ys))
    return pose, bbox, cam


def test_rulers_derive_from_the_declared_skeleton():
    assert abs(R_SHOULDER - 0.26) < 1e-9
    assert abs(R_HIP - 0.16) < 1e-9
    assert abs(R_TORSO - 0.45) < 1e-9
    assert abs(R_STAND - 1.53) < 1e-9


@pytest.mark.parametrize(
    "yaw_gt,dist,elev",
    [(0.0, 4.0, 0.0), (20.0, 4.0, 0.0), (-30.0, 3.0, 0.5), (20.0, 2.6, -1.0),
     (-20.0, 4.0, 1.0)],
)
def test_gt_solve_holds_the_annex_family(yaw_gt, dist, elev):
    pose, bbox, _cam = _gt_case(yaw_gt, dist, elev)
    res = solve_camera_figure(
        pose.positions, pose.joint_confidence, pose.scale, bbox, IMG_W, IMG_H
    )
    assert res.ok, res.reason
    assert abs(res.yaw_deg - yaw_gt) <= 7.5
    pitch_true = math.degrees(math.atan2(-elev, dist))
    assert abs(res.pitch_deg - pitch_true) <= 5.0
    assert abs(res.distance / dist - 1.0) <= 0.12
    assert res.confidence >= CAMERA_CONF_FLOOR


def test_yaw_sign_follows_the_nose_direction():
    pose_r, bbox_r, _ = _gt_case(20.0, 4.0, 0.0)
    pose_l, bbox_l, _ = _gt_case(-20.0, 4.0, 0.0)
    r_r = solve_camera_figure(pose_r.positions, pose_r.joint_confidence, pose_r.scale, bbox_r, IMG_W, IMG_H)
    r_l = solve_camera_figure(pose_l.positions, pose_l.joint_confidence, pose_l.scale, bbox_l, IMG_W, IMG_H)
    assert r_r.ok and r_l.ok
    assert r_r.yaw_deg > 0.0
    assert r_l.yaw_deg < 0.0


def test_pitch_sign_follows_the_camera_elevation():
    pose_hi, bbox_hi, _ = _gt_case(0.0, 4.0, 1.0)   # camera above -> theta < 0
    pose_lo, bbox_lo, _ = _gt_case(0.0, 4.0, -1.0)  # camera below -> theta > 0
    r_hi = solve_camera_figure(pose_hi.positions, pose_hi.joint_confidence, pose_hi.scale, bbox_hi, IMG_W, IMG_H)
    r_lo = solve_camera_figure(pose_lo.positions, pose_lo.joint_confidence, pose_lo.scale, bbox_lo, IMG_W, IMG_H)
    assert r_hi.ok and r_lo.ok
    assert r_hi.pitch_deg < 0.0
    assert r_lo.pitch_deg > 0.0


def test_twin_solves_identical():
    pose, bbox, _ = _gt_case(15.0, 3.4, 0.5)
    a = solve_camera_figure(pose.positions, pose.joint_confidence, pose.scale, bbox, IMG_W, IMG_H)
    b = solve_camera_figure(pose.positions, pose.joint_confidence, pose.scale, bbox, IMG_W, IMG_H)
    assert a == b


def test_refusal_kp_starved_is_loud():
    pose, bbox, _ = _gt_case(20.0, 4.0, 0.0)
    starved = dict(pose.joint_confidence)
    starved["upper_arm.R"] = 0.3
    res = solve_camera_figure(pose.positions, starved, pose.scale, bbox, IMG_W, IMG_H)
    assert not res.ok
    assert "kp-starved" in res.reason
    assert f"below floor {CAMERA_CONF_FLOOR}" in res.reason


def test_refusal_missing_roles_is_loud():
    pose, bbox, _ = _gt_case(0.0, 4.0, 0.0)
    no_hips = {r: p for r, p in pose.positions.items() if r != "hips"}
    res = solve_camera_figure(no_hips, pose.joint_confidence, pose.scale, bbox, IMG_W, IMG_H)
    assert not res.ok
    assert "roles unobserved" in res.reason and "hips" in res.reason


def test_refusal_torso_degenerate_is_loud():
    pose, bbox, _ = _gt_case(0.0, 4.0, 0.0)
    slumped = {
        r: (p[0], p[1], p[2] * 0.3 if r == "neck" else p[2])
        for r, p in pose.positions.items()
    }
    res = solve_camera_figure(slumped, pose.joint_confidence, pose.scale, bbox, IMG_W, IMG_H)
    assert not res.ok
    assert "torso-degenerate" in res.reason


def test_refusal_pose_class_breach_is_loud():
    pose, bbox, _ = _gt_case(0.0, 4.0, 0.0)
    half = (bbox[0], bbox[1], bbox[2], bbox[1] + (bbox[3] - bbox[1]) * 0.4)
    res = solve_camera_figure(pose.positions, pose.joint_confidence, pose.scale, half, IMG_W, IMG_H)
    assert not res.ok
    assert "pose-class breach" in res.reason or "envelope breach" in res.reason


def test_refusal_profile_envelope_is_loud():
    pose, bbox, _ = _gt_case(0.0, 4.0, 0.0)
    # rho at the model boundary: a head swung hard sideways
    swung = dict(pose.positions)
    nx, ny, nz = swung["neck"]
    swung["head"] = (nx + 0.28, ny - 0.02, nz + 0.005)
    res = solve_camera_figure(swung, pose.joint_confidence, pose.scale, bbox, IMG_W, IMG_H)
    assert not res.ok
    assert "envelope breach" in res.reason or "head placement degenerate" in res.reason


def test_consensus_circular_mean_never_collapses():
    ra = solve_camera_figure(*_gt_case_args(60.0))
    rb = solve_camera_figure(*_gt_case_args(-60.0))
    assert ra.ok and rb.ok, "GT cases must solve for the consensus test"
    out = consensus_camera([("A", ra), ("B", rb)])
    assert out["ok"]
    # +60/-60 must average toward 0, never wrap through the wrong side
    assert abs(float(out["yaw_deg"])) < 30.0


def _gt_case_args(yaw_deg):
    pose, bbox, _ = _gt_case(yaw_deg, 4.0, 0.0)
    return (
        pose.positions, pose.joint_confidence, pose.scale, bbox, IMG_W, IMG_H
    )


def test_consensus_refuses_when_no_figure_solves():
    pose, bbox, _ = _gt_case(0.0, 4.0, 0.0)
    starved = dict(pose.joint_confidence)
    starved["upper_arm.R"] = 0.3
    dead = solve_camera_figure(pose.positions, starved, pose.scale, bbox, IMG_W, IMG_H)
    out = consensus_camera([("A", dead)])
    assert not out["ok"]
    assert "no usable figure solves" in str(out["reason"])


def test_to_dict_round_shapes_are_stable():
    pose, bbox, _ = _gt_case(10.0, 4.0, 0.0)
    res = solve_camera_figure(pose.positions, pose.joint_confidence, pose.scale, bbox, IMG_W, IMG_H)
    d = res.to_dict()
    assert d["ok"] is True
    assert set(d) == {
        "ok", "reason", "yaw_deg", "pitch_deg", "distance", "height",
        "confidence", "ledgers",
    }
