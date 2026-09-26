"""Measured reference-camera solve (P8-5): body keypoints -> camera params.

Design of record: docs/CAMERA.md (the FACE.md sibling — the draft solve is
`xtask/camera_probe.py`, this module lifts it, tests pin it). The solve fits
yaw/pitch/distance/height of the reference camera from quantities that
survive the front-prior pose lift: the in-plane canonical ruler lengths
(image-exact by D-008 role semantics), the payload's own scale field, the
derived head placement's direction, and the figure's framing box. Pure
stdlib, deterministic (fixed iteration rounds, keyed orders, no randomness).

The evidence chain (docs/CAMERA.md § The solve + amendment record A1-A9):
- yaw: CLOSED FORM from the derived head placement's direction ratio
  (sin Δ = 2.2·rho/(1 − rho²), rho = head_dx/head_dz — the pipeline's own
  declared head-placement model inverted; sign carried by rho's sign).
- pitch SIGN: the body's depth gradient g = (hp/H − sh/S)/(0.45·hp/H)
  = sinθcosθ/D — sign(g) is sign(sin θ).
- pitch MAGNITUDE, dual-regime: |2 g D| ≥ 0.15 → θ = asin(2gD)/2 (the
  gradient regime); below → the nose-to-ankle vertical ruler, clamped to
  the regime's own bound |θ| ≤ asin(0.15)/2 (2gD = sin 2θ exactly).
  A gradient read disagreeing with the vertical by > 7° while |2gD| < 0.4
  is contaminated g → the clamped vertical wins.
- distance: D = f·cosθ·img_w/(sensor_w·scale·κ), κ closed-form from the
  lateral ruler; cross-checked against the gradient's own D.
- height: the exact pitched inversion off the recovered anchor pixel.

Honesty law: every refusal is LOUD with a verbatim reason (kp-starved,
torso-degenerate, pose-class breach, envelope breach, head-placement
degenerate); a below-floor confidence REFUSES TO STAGE — a wrong silent
camera is the trust-killer this module exists to prevent. Cameras carry
no content (D-019 unchanged).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .canonical import rest_skeleton
from .canonical_pose import TORSO_SPAN

#: The CONVENTIONS ambiguity bar, reused (the coupling/finger/face floor
#: precedent) — declared untuned.
CAMERA_CONF_FLOOR = 0.55
FORESHORTEN_MIN = 0.5
ENVELOPE_YAW = 80.0
ENVELOPE_PITCH = 35.0
RULER_BAND_LO = 0.15
RULER_BAND_HI = 0.35
CAMERA_BAND_MARGIN = 0.1
SIGN_GRADIENT_DEADBAND = 0.02
DEPTH_MIX_A0 = 0.083
GRADIENT_SWITCH = 0.15
VERTICAL_BOUND_RAD = 0.5 * math.asin(0.15)
CROSSCHECK_DEG = 7.0
LENS_MM = 50.0
SENSOR_W_MM = 36.0
NOSE_FWD = 0.10

#: Rulers DERIVED from the declared skeleton (one source of truth; the
#: canonical unit is hip height = 1). The shoulder kps sit at the
#: upper-arm bone HEADS (the D-008 role semantics — amendment A4).
_REST = rest_skeleton(2.0, hip_height_frac=0.5)
R_SHOULDER = math.dist(
    tuple(float(v) for v in _REST["upper_arm.L"][0]),
    tuple(float(v) for v in _REST["upper_arm.R"][0]),
)
R_HIP = math.dist(
    tuple(float(v) for v in _REST["upper_leg.L"][0]),
    tuple(float(v) for v in _REST["upper_leg.R"][0]),
)
R_TORSO = TORSO_SPAN
R_STAND = float(_REST["head"][0][2]) - float(_REST["foot.L"][0][2])


def sensor_fit(img_w: int, img_h: int) -> tuple[float, float]:
    """The AUTO sensor fit, GENERAL (A11): the sensor's LONG edge (36 mm)
    fits the frame's LONG side — landscape (w >= h): 36 x 36*h/w; portrait:
    36*w/h x 36. Blender's default camera fit matches this rule."""
    if img_w >= img_h:
        return SENSOR_W_MM, SENSOR_W_MM * img_h / img_w
    return SENSOR_W_MM * img_w / img_h, SENSOR_W_MM

Bbox = tuple[float, float, float, float]  # pixels, y-down
Point = tuple[float, float, float]


@dataclass
class FigureCamera:
    """One figure's measured camera solve: the parameters or a LOUD refusal.

    ``ok=False`` carries a verbatim ``reason`` (the refusal ledger); a
    solved figure carries the camera params + the honesty numbers. The
    stage gate needs BOTH ``ok`` and ``confidence >= CAMERA_CONF_FLOOR``.
    """

    ok: bool
    reason: str = ""
    yaw_deg: float = 0.0
    pitch_deg: float = 0.0
    distance: float = 0.0
    height: float = 0.0
    confidence: float = 0.0
    residual: float = 0.0
    ruler_offset: float = 0.0
    d_stand: float = 0.0
    ledgers: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        out: dict[str, object] = {
            "ok": self.ok,
            "reason": self.reason,
            "yaw_deg": round(self.yaw_deg, 2),
            "pitch_deg": round(self.pitch_deg, 2),
            "distance": round(self.distance, 4),
            "height": round(self.height, 4),
            "confidence": round(self.confidence, 4),
            "ledgers": dict(sorted(self.ledgers.items())),
        }
        return out


def _band(value: float, lo: float, hi: float) -> float:
    if value <= lo:
        return 1.0
    if value >= hi:
        return 0.0
    return (hi - value) / (hi - lo)


def _vertical_pitch(
    z_span: float, kappa: float, sin_yaw: float, g: float, pitch_prev: float
) -> float:
    """The vertical-regime pitch (A6/A7): invert
    z_span/(kappa*R_STAND) = cos(t) + a(Δ)·sin(t) per sign branch."""
    a_mix = DEPTH_MIX_A0 * math.cos(math.asin(max(min(sin_yaw, 1.0), -1.0))) ** 2
    target = z_span / (kappa * R_STAND)
    phi = math.atan(a_mix)
    norm = math.sqrt(1.0 + a_mix * a_mix)
    base = math.acos(max(min(target / norm, 1.0), 0.0))
    if abs(g) > SIGN_GRADIENT_DEADBAND:
        sign = 1.0 if g > 0.0 else -1.0
    elif pitch_prev < 0.0:
        sign = -1.0
    else:
        sign = 1.0
    return phi + base if sign > 0.0 else phi - base


def solve_camera_figure(
    positions: dict[str, Point],
    joint_conf: dict[str, float],
    scale: float,
    bbox_px: Bbox,
    img_w: int,
    img_h: int,
) -> FigureCamera:
    """The measured per-figure solve (docs/CAMERA.md § The solve).

    ``positions``: the solved CanonicalPose.positions (canonical units, the
    anchor joint at the origin, z = image-up). Never raises for weak input:
    it refuses LOUD (ok=False + the reason) so the stage gate can show what
    happened. DETERM-pinned: twin calls return identical results.
    """
    ledgers: dict[str, str] = {}
    sensor_w, sensor_h = sensor_fit(img_w, img_h)
    need = ("hips", "neck", "upper_arm.L", "upper_arm.R", "head")
    missing = [r for r in need if r not in positions]
    if missing:
        return FigureCamera(ok=False, reason="roles unobserved: " + ", ".join(sorted(missing)))
    low = [
        f"{r}={joint_conf.get(r, 0.0):.2f}"
        for r in need
        if joint_conf.get(r, 0.0) < CAMERA_CONF_FLOOR
    ]
    if low:
        return FigureCamera(
            ok=False,
            reason=f"kp-starved: {', '.join(low)} below floor {CAMERA_CONF_FLOOR}",
        )
    if scale <= 1e-9 or img_w <= 0 or img_h <= 0:
        return FigureCamera(
            ok=False, reason=f"degenerate scale {scale:.4f} for frame {img_w}x{img_h}"
        )

    def d2(a: str, b: str) -> float:
        return math.hypot(positions[a][0] - positions[b][0], positions[a][2] - positions[b][2])

    hip_conf = min(
        joint_conf.get("upper_leg.L", 0.0), joint_conf.get("upper_leg.R", 0.0)
    )
    has_hip_pair = (
        "upper_leg.L" in positions
        and "upper_leg.R" in positions
        and hip_conf >= CAMERA_CONF_FLOOR
    )
    if not has_hip_pair:
        ledgers["lateral_agreement"] = (
            f"hip girdle unusable (conf {hip_conf:.2f} < {CAMERA_CONF_FLOOR}); "
            "gradient-free fallback, sign deferred"
        )

    tn = d2("hips", "neck")
    if tn < FORESHORTEN_MIN * R_TORSO:
        return FigureCamera(
            ok=False,
            reason=(
                f"torso-degenerate: in-plane torso {tn:.3f} < "
                f"{FORESHORTEN_MIN}x canonical {R_TORSO:.2f} (the sitting/"
                "slumped class is outside the standing-prior solve)"
            ),
        )
    sh = d2("upper_arm.L", "upper_arm.R")
    hp = d2("upper_leg.L", "upper_leg.R") if has_hip_pair else None

    head_dx = positions["head"][0] - positions["neck"][0]
    head_dz = positions["head"][2] - positions["neck"][2]
    if head_dz <= 1e-9:
        return FigureCamera(
            ok=False,
            reason=f"head placement degenerate (head_dz {head_dz:+.4f} <= 0)",
        )
    rho = head_dx / head_dz
    if abs(rho) >= 0.49:
        return FigureCamera(
            ok=False,
            reason=(
                f"head placement degenerate (rho {rho:+.3f} at the model "
                "boundary) — the facing direction is outside the solved class"
            ),
        )
    # closed form: rho = s/(1+sqrt(1+s^2)) with s = (NOSE_FWD/0.11)*sin(Delta)
    # -> s = 2 rho/(1-rho^2) -> sin(Delta) = 2.2 rho/(1-rho^2), sign carried
    # (A10 final: with right = fw x up_w the nose offset reads POSITIVE rho
    # at Delta > 0 — sign(Delta) = sign(head_dx), the page's original rule)
    sin_yaw = 2.2 * rho / (1.0 - rho * rho)
    yaw = math.asin(max(-1.0, min(1.0, sin_yaw)))
    yaw_deg = math.degrees(yaw)
    if abs(yaw_deg) > ENVELOPE_YAW:
        return FigureCamera(
            ok=False,
            reason=(
                f"envelope breach: yaw {yaw_deg:.1f} deg outside the declared "
                f"envelope (+-{ENVELOPE_YAW:.0f}) — near-profile views are "
                "outside the solved class"
            ),
        )
    sh_ratio = sh / R_SHOULDER

    z_span = 0.0
    if "head" in positions and "foot.L" in positions and "foot.R" in positions:
        z_span = positions["head"][2] - min(positions["foot.L"][2], positions["foot.R"][2])
    if z_span < 0.75 * R_STAND:
        return FigureCamera(
            ok=False,
            reason=(
                f"pose-class breach: nose-to-ankle span {z_span:.2f} < "
                f"0.75x standing {R_STAND:.2f} — the sitting/crouch class is "
                "outside the standing-prior solve"
            ),
        )

    if has_hip_pair and hp is not None and hp > 1e-9:
        lat = 1.0
        g = 0.0
        kappa = 0.0
        pitch_rad = 0.0
        distance = 0.0
        theta_g = 0.0
        theta_v = 0.0
        two_gd = 0.0
        for _round in range(3):  # fixed rounds — determinism
            lat = math.sqrt(max(1.0 - math.cos(pitch_rad) ** 2 * sin_yaw * sin_yaw, 1e-9))
            kappa = (hp / R_HIP) / lat
            g = (hp / R_HIP - sh_ratio) / (0.45 * hp / R_HIP)
            distance = LENS_MM * img_w * math.cos(pitch_rad) / (sensor_w * scale * kappa)
            two_gd = 2.0 * g * distance
            theta_g = 0.5 * math.asin(max(min(two_gd, 0.99), -0.99))
            theta_v = _vertical_pitch(z_span, kappa, sin_yaw, g, pitch_rad)
            bound = VERTICAL_BOUND_RAD
            if abs(two_gd) >= GRADIENT_SWITCH:
                pitch_rad = theta_g
                if abs(two_gd) < 0.4 and abs(theta_g - theta_v) > CROSSCHECK_DEG:
                    pitch_rad = max(min(theta_v, bound), -bound)
            else:
                pitch_rad = max(min(theta_v, bound), -bound)
        pitch_mag = abs(math.degrees(pitch_rad))
        pitch_deg = math.degrees(pitch_rad)
        cos_p = math.cos(pitch_rad)
        distance = LENS_MM * img_w * cos_p / (sensor_w * scale * kappa)
        d_gradient = math.sin(pitch_rad) * cos_p / g if abs(g) > 1e-9 else distance
        gradient_offset = abs(d_gradient / distance - 1.0)
        ledgers["gradient"] = (
            f"g={g:+.4f} -> pitch {pitch_deg:+.1f} deg "
            f"({'gradient' if abs(two_gd) >= GRADIENT_SWITCH else 'vertical'} "
            f"regime), D cross-check {gradient_offset * 100:.1f}%"
        )
    else:
        g_sign = 0.0
        lat = 1.0
        kappa = 0.0
        pitch_rad = 0.0
        for _round in range(3):
            lat = math.sqrt(max(1.0 - math.cos(pitch_rad) ** 2 * sin_yaw * sin_yaw, 1e-9))
            kappa = sh_ratio / lat
            pitch_rad = _vertical_pitch(z_span, kappa, sin_yaw, 0.0, pitch_rad)
        pitch_mag = abs(math.degrees(pitch_rad))
        pitch_deg = pitch_mag  # sign deferred (band prior below)
        cos_p = math.cos(pitch_rad)
        distance = LENS_MM * img_w * cos_p / (sensor_w * scale * kappa)
        gradient_offset = 1.0
        ledgers["gradient"] = "hip girdle unusable — gradient-free fallback, sign deferred"
    if pitch_mag > ENVELOPE_PITCH:
        return FigureCamera(
            ok=False,
            reason=(
                f"envelope breach: |pitch| {pitch_mag:.1f} deg outside the "
                f"declared envelope (+-{ENVELOPE_PITCH:.0f}) — outside the "
                "solved class"
            ),
        )

    v_extent = max((bbox_px[3] - bbox_px[1]) / img_h, 1e-9)
    d_stand = LENS_MM * cos_p * R_STAND / (v_extent * sensor_h)
    ruler_off = abs(d_stand / distance - 1.0)
    if ruler_off > RULER_BAND_HI:
        return FigureCamera(
            ok=False,
            reason=(
                f"pose-class breach: standing-ruler distance {d_stand:.3f} vs "
                f"in-pose {distance:.3f} (off by {ruler_off:.2f} > "
                f"{RULER_BAND_HI}); the subject class is outside the "
                "standing-prior solve"
            ),
        )
    residual = math.sqrt(min(ruler_off, 1.0) ** 2 + min(gradient_offset, 1.0) ** 2)
    agreement = _band(ruler_off, RULER_BAND_LO, RULER_BAND_HI) if has_hip_pair else 0.5
    crosscheck = _band(gradient_offset, RULER_BAND_LO, RULER_BAND_HI) if has_hip_pair else 0.5
    obs_strength = min(joint_conf.get(r, 0.0) for r in need)
    confidence = 0.35 * agreement + 0.35 * crosscheck + 0.3 * obs_strength

    z_mid = (max(p[2] for p in positions.values()) + min(p[2] for p in positions.values())) / 2.0
    anchor_v_up = 1.0 - ((bbox_px[1] + bbox_px[3]) / 2.0 + z_mid * scale) / img_h
    beta = (anchor_v_up - 0.5) * sensor_h / LENS_MM
    if abs(beta * math.tan(math.radians(pitch_deg))) >= 0.99:
        return FigureCamera(
            ok=False,
            reason="height inversion degenerate (beta*tan(theta) -> 1)",
        )

    def cam_above_anchor(pitch_signed: float) -> float:
        t = math.tan(pitch_signed)
        return -distance * (beta + t) / (1.0 - beta * t)

    z_min = min(p[2] for p in positions.values())
    z_max = max(p[2] for p in positions.values())
    cand_plus = cam_above_anchor(math.radians(pitch_mag))  # camera below
    cand_minus = cam_above_anchor(math.radians(-pitch_mag))  # camera above
    g_sign = 0.0
    if has_hip_pair and hp is not None:
        g_live = (hp / R_HIP - sh_ratio) / (0.45 * hp / R_HIP)
        g_sign = 1.0 if g_live > SIGN_GRADIENT_DEADBAND else (
            -1.0 if g_live < -SIGN_GRADIENT_DEADBAND else 0.0
        )
    if g_sign != 0.0:
        cam_z = cam_above_anchor(math.radians(pitch_deg))
        ledgers["pitch_sign"] = f"sign from the depth gradient (g {g_live:+.4f})"
    else:
        band_lo, band_hi = z_min - CAMERA_BAND_MARGIN, z_max + CAMERA_BAND_MARGIN
        in_plus = band_lo <= cand_plus <= band_hi
        in_minus = band_lo <= cand_minus <= band_hi
        if in_plus and not in_minus:
            cam_z, sign_note, pitch_deg = cand_plus, "sign from camera-band prior (+)", pitch_mag
        elif in_minus and not in_plus:
            cam_z, sign_note, pitch_deg = cand_minus, "sign from camera-band prior (-)", -pitch_mag
        elif in_plus and in_minus:
            z_center = (z_min + z_max) / 2.0
            if abs(cand_plus - z_center) <= abs(cand_minus - z_center):
                cam_z, sign_note, pitch_deg = cand_plus, "sign from center-framing prior (+)", pitch_mag
            else:
                cam_z, sign_note, pitch_deg = cand_minus, "sign from center-framing prior (-)", -pitch_mag
        else:
            d_plus = max(band_lo - cand_plus, cand_plus - band_hi, 0.0)
            d_minus = max(band_lo - cand_minus, cand_minus - band_hi, 0.0)
            if d_plus <= d_minus:
                cam_z, sign_note, pitch_deg = cand_plus, "sign by band proximity (+)", pitch_mag
            else:
                cam_z, sign_note, pitch_deg = cand_minus, "sign by band proximity (-)", -pitch_mag
        ledgers["pitch_sign"] = sign_note
    height = cam_z - z_min

    if abs(pitch_deg) > ENVELOPE_PITCH:
        return FigureCamera(
            ok=False,
            reason=(
                f"envelope breach: pitch {pitch_deg:.1f} deg outside the "
                f"declared solve envelope (+-{ENVELOPE_PITCH})"
            ),
        )

    return FigureCamera(
        ok=True,
        yaw_deg=yaw_deg,
        pitch_deg=pitch_deg,
        distance=distance,
        height=height,
        confidence=confidence,
        residual=residual,
        ruler_offset=ruler_off,
        d_stand=d_stand,
        ledgers=ledgers,
    )


def consensus_camera(
    solves: list[tuple[str, FigureCamera]],
) -> dict[str, object]:
    """The multi-figure consensus (docs/CAMERA.md § Multi-figure scenes).

    Confidence-weighted means; yaw a weighted CIRCULAR mean (+175 and
    −175 never average to 0). Per-figure residuals are LOUD report fields.
    Zero usable figures -> a loud refusal.
    """
    usable = [(label, s) for label, s in solves if s.ok]
    if not usable:
        reasons = "; ".join(f"{label}: {s.reason}" for label, s in solves) or "no figures"
        return {"ok": False, "reason": f"no usable figure solves ({reasons})"}
    weights = [max(s.confidence, 1e-6) for _l, s in usable]
    w_sum = sum(weights)
    distance = sum(w * s.distance for w, (_l, s) in zip(weights, usable, strict=True)) / w_sum
    pitch = sum(w * s.pitch_deg for w, (_l, s) in zip(weights, usable, strict=True)) / w_sum
    height = sum(w * s.height for w, (_l, s) in zip(weights, usable, strict=True)) / w_sum
    sin_sum = sum(w * math.sin(math.radians(s.yaw_deg)) for w, (_l, s) in zip(weights, usable, strict=True))
    cos_sum = sum(w * math.cos(math.radians(s.yaw_deg)) for w, (_l, s) in zip(weights, usable, strict=True))
    yaw = math.degrees(math.atan2(sin_sum, cos_sum))
    residuals = {
        label: {
            "yaw_deg": round(s.yaw_deg - yaw, 2),
            "distance": round(s.distance - distance, 4),
        }
        for label, s in usable
    }
    disagreement = max(
        (abs(math.sin(math.radians(r["yaw_deg"]))) + abs(r["distance"]) / max(distance, 1e-9))
        for r in residuals.values()
    )
    agreement = _band(disagreement, 0.10, 0.30)
    confidence = min(s.confidence for _l, s in usable) * (0.7 + 0.3 * agreement)
    return {
        "ok": True,
        "yaw_deg": round(yaw, 2),
        "pitch_deg": round(pitch, 2),
        "distance": round(distance, 4),
        "height": round(height, 4),
        "confidence": round(confidence, 4),
        "figures": [label for label, _s in usable],
        "residuals": residuals,
        "refused": [label for label, s in solves if not s.ok],
    }
