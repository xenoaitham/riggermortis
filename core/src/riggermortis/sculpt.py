"""P9-3 sculpt wiring — the reference-side solve contract (pure half).

Design of record: docs/WIRING.md (the VOLUME.md sibling). The wiring's
reference-side measurements ride a SEPARATE deterministic artifact
(``sculpt.json``, format 1) written by ``rigpose solve-sculpt`` and
consumed by the add-on's apply (the D-009 payload-flow pattern — the
segmentation model never enters Blender). This module is the contract:
the artifact's loud validation, the product anchor math (amendment A1 —
the anchors are the DETECTOR's body keypoints, interpolated on the torso
line at the S37-certified fracs), and the mask measurement + factor
solve lifted VERBATIM from the certified S37 pipeline (xtask/
volume_common.py — one copy now; the volume gate re-run proves the lift
byte-identical). Stdlib; the mask measurement lazy-imports numpy (the
inference-extra pattern — the CLI runs in the inference env).

No payload format change and no new pose field ship with this module
(D-026 stays free). The sculpt carries no content by itself (D-019).
"""
from __future__ import annotations

import math

from .auto_sculpt import RULER_NAMES
from .errors import AutoSculptError
from .volume import BAND_PARAMS

#: The sculpt solve artifact format written by this build.
SCULPT_FORMAT = 1
#: Formats this build reads.
READ_FORMATS = (1,)

# ---------------------------------------------------------------------------
# The S37-certified measurement constants (docs/VOLUME.md amendments A1/A2;
# the values the probe's published numbers rode — lifted verbatim).
# ---------------------------------------------------------------------------
#: Band anchor fractions along the hips→neck line (0.0 = the hips head).
ANCHOR_FRACS: dict[str, float] = {
    "vol.hip_w": 0.0,
    "vol.waist_w": 0.25,
    "vol.chest_w": 0.80,
}
#: The mid-band thigh anchor (A2: at -0.43 a widened pelvis bled into the
#: thigh rows — measured, moved, certified at -0.70).
THIGH_ANCHOR_FRAC = -0.70
#: The declared median band k: rows [-k, +k] around the anchor row.
MEDIAN_HALF_BAND = 3


def anchor_points_px(
    kps: dict[str, tuple[float, float]],
) -> tuple[dict[str, tuple[float, float]], float]:
    """The product anchor set (WIRING.md amendment A1) from the detector's
    body keypoints (image space, y down).

    ``kps``: hips/neck (the girdle means) + upper_leg.L/R (the hip
    keypoints — the leg centers). The torso-band anchors interpolate the
    hips→neck line at the certified fracs; the thigh anchor extends the
    line to THIGH_ANCHOR_FRAC with leg centers at the hip keypoints' x.
    Returns (anchors, projected torso span px). Loud on missing roles and
    on a degenerate torso (the solve would normalize by it).
    """
    missing = sorted(r for r in ("hips", "neck", "upper_leg.L", "upper_leg.R") if r not in kps)
    if missing:
        raise AutoSculptError(
            "volume anchors need the hips/neck/upper_leg keypoints "
            f"(missing: {', '.join(missing)})",
            hint="re-detect with a clearer reference; anchor keypoints must "
                 "solve above the 0.55 confidence floor",
        )
    hx, hy = kps["hips"]
    nx, ny = kps["neck"]
    dx, dy = nx - hx, ny - hy
    span = math.hypot(dx, dy)
    if span <= 1e-6:
        raise AutoSculptError(
            f"projected torso span degenerate ({span:.6f} px) "
            "(hint: the detector's hips/neck collapsed onto one point)",
        )
    out: dict[str, tuple[float, float]] = {"hips": (hx, hy), "neck": (nx, ny)}
    for param, frac in ANCHOR_FRACS.items():
        out[param] = (hx + frac * dx, hy + frac * dy)
    tx, ty = hx + THIGH_ANCHOR_FRAC * dx, hy + THIGH_ANCHOR_FRAC * dy
    out["vol.thigh_w"] = (tx, ty)
    out["vol.thigh.L"] = (kps["upper_leg.L"][0], ty)
    out["vol.thigh.R"] = (kps["upper_leg.R"][0], ty)
    return out, span


def _require_numpy():
    try:
        import numpy  # noqa: PLC0415 — the inference-extra lazy pattern
    except ImportError as exc:  # pragma: no cover - dev envs carry numpy
        raise AutoSculptError(
            "the mask measurement needs numpy (hint: pip install "
            "riggermortis-core[inference])"
        ) from exc
    return numpy


def runs(xs: list[int], min_len: int = 3) -> list[tuple[int, int]]:
    """Contiguous index runs of a sorted index list, length >= min_len."""
    if not xs:
        return []
    out: list[tuple[int, int]] = []
    s = prev = xs[0]
    for x in xs[1:]:
        if x - prev > 1:
            if prev - s + 1 >= min_len:
                out.append((s, prev))
            s = x
        prev = x
    if prev - s + 1 >= min_len:
        out.append((s, prev))
    return out


def region_widths(mask, anchors_px: dict, torso_px: float) -> dict[str, float]:
    """The S37 mask measurement, verbatim: torso regions (hip/waist/chest)
    = the connected horizontal mask run containing the projected torso
    center at the anchor row (median over the declared band); the thigh
    region = the run(s) containing the projected LEG centers (one merged
    run when the legs read closed — counted once), summing two runs when
    the legs read separated. All normalized by the projected torso span.
    """
    np = _require_numpy()

    out: dict[str, float] = {}
    for param in list(ANCHOR_FRACS) + ["vol.thigh_w"]:
        ay = int(round(anchors_px[param][1]))
        centers = [int(round(anchors_px[param][0]))]
        if param == "vol.thigh_w":
            centers = [
                int(round(anchors_px["vol.thigh.L"][0])),
                int(round(anchors_px["vol.thigh.R"][0])),
            ]
        vals = []
        for dy in range(-MEDIAN_HALF_BAND, MEDIAN_HALF_BAND + 1):
            rr = runs(np.flatnonzero(mask[ay + dy]).tolist())
            hit = {}
            for cx in centers:
                for s, e in rr:
                    if s <= cx <= e:
                        hit[cx] = (s, e)
                        break
            if not hit:
                w = 0.0
            elif len(set(hit.values())) == 1:
                s, e = next(iter(hit.values()))
                w = float(e - s + 1)
            else:
                w = float(sum(e - s + 1 for s, e in hit.values()))
            vals.append(w)
        out[param] = sorted(vals)[len(vals) // 2] / torso_px
    return out


def solve_factors(ref_r: dict[str, float], base_r: dict[str, float]) -> dict[str, float]:
    """The declared solve (the clamp law lives in riggermortis.volume):
    per-region factor = ref/base, clamped loud (clamps land in the
    caller's report notes, never a wild solve silently truncated)."""
    from .volume import CLAMP_HI, CLAMP_LO

    out = {}
    for p, b in base_r.items():
        f = ref_r[p] / b if b > 1e-9 else CLAMP_HI
        out[p] = max(CLAMP_LO, min(CLAMP_HI, f))
    return out


def clamp_note_params(factors: dict[str, float]) -> list[str]:
    """The params sitting at a clamp bound (the loud clamp note's input)."""
    from .volume import CLAMP_HI, CLAMP_LO

    return sorted(p for p, f in factors.items() if f in (CLAMP_LO, CLAMP_HI))


# ---------------------------------------------------------------------------
# The artifact contract (loud validation; deterministic bytes)
# ---------------------------------------------------------------------------

def _finite_positive(v: object, where: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise AutoSculptError(f"{where} must be a number (got {v!r})")
    f = float(v)
    if not math.isfinite(f) or f <= 0.0:
        raise AutoSculptError(
            f"{where} must be finite and positive (got {f!r}) "
            f"(hint: the ratios are torso-normalized measurements)"
        )
    return f


class SculptSolve:
    """The reference-side solve (sculpt.json): proportion + volume ratios,
    shipped as data for the add-on apply (the camera-solve report pattern).
    ``from_dict`` refuses loudly on anything it does not understand — a
    misread solve would fabricate a sculpt."""

    def __init__(
        self,
        figure: str,
        reference_image: str,
        image_size: tuple[int, int],
        reference_ratios: dict[str, float],
        volume_ratios: dict[str, float],
        notes: list[str] | None = None,
    ) -> None:
        self.figure = str(figure)
        self.reference_image = str(reference_image)
        self.image_size = (int(image_size[0]), int(image_size[1]))
        self.reference_ratios = {k: float(v) for k, v in sorted(reference_ratios.items())}
        self.volume_ratios = {k: float(v) for k, v in sorted(volume_ratios.items())}
        self.notes = list(notes or [])

    def to_dict(self) -> dict[str, object]:
        return {
            "format": SCULPT_FORMAT,
            "figure": self.figure,
            "reference_image": self.reference_image,
            "image_size": [self.image_size[0], self.image_size[1]],
            "proportions": {"reference_ratios": dict(self.reference_ratios)},
            "volume": {"ref_ratios": dict(self.volume_ratios)},
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, d: object) -> SculptSolve:
        if not isinstance(d, dict):
            raise AutoSculptError(
                "sculpt solve is not a JSON object",
                hint="regenerate with: rigpose solve-sculpt <image> "
                     "<payload.json> --out sculpt.json",
            )
        fmt = d.get("format", 1)
        if fmt not in READ_FORMATS:
            raise AutoSculptError(
                f"unsupported sculpt solve format {fmt!r} "
                f"(hint: this build reads formats "
                f"{', '.join(map(str, READ_FORMATS))}; regenerate with: "
                "rigpose solve-sculpt <image> <payload.json> --out sculpt.json)"
            )
        figure = d.get("figure")
        if not isinstance(figure, str) or not figure:
            raise AutoSculptError("sculpt solve carries no figure label")
        image_size = d.get("image_size")
        if (
            not isinstance(image_size, list)
            or len(image_size) != 2
            or any(isinstance(v, bool) or not isinstance(v, int) for v in image_size)
        ):
            raise AutoSculptError(
                "sculpt solve image_size must be [width, height] integers"
            )
        proportions = d.get("proportions")
        if not isinstance(proportions, dict):
            raise AutoSculptError(
                "sculpt solve has no 'proportions' section "
                "(hint: regenerate with rigpose solve-sculpt)"
            )
        raw_ratios = proportions.get("reference_ratios")
        if not isinstance(raw_ratios, dict):
            raise AutoSculptError(
                "sculpt solve proportions carry no 'reference_ratios' object"
            )
        need = {"torso", *RULER_NAMES}
        missing = sorted(need - set(raw_ratios))
        if missing:
            raise AutoSculptError(
                "sculpt solve reference ratios missing rulers: "
                + ", ".join(missing)
                + " (hint: the payload's solved positions must cover the "
                "torso + 6 rulers — regenerate the payload)"
            )
        ratios = {
            k: _finite_positive(raw_ratios[k], f"reference ratio {k!r}") for k in sorted(need)
        }
        volume = d.get("volume")
        if not isinstance(volume, dict):
            raise AutoSculptError(
                "sculpt solve has no 'volume' section "
                "(hint: regenerate with rigpose solve-sculpt)"
            )
        raw_vol = volume.get("ref_ratios")
        if not isinstance(raw_vol, dict):
            raise AutoSculptError(
                "sculpt solve volume carries no 'ref_ratios' object"
            )
        vol_missing = sorted(set(BAND_PARAMS) - set(raw_vol))
        vol_unknown = sorted(set(raw_vol) - set(BAND_PARAMS))
        if vol_unknown:
            raise AutoSculptError(
                "unknown volume params in the sculpt solve: "
                + ", ".join(vol_unknown)
                + f" (hint: the band params are {', '.join(BAND_PARAMS)})"
            )
        if vol_missing:
            raise AutoSculptError(
                "sculpt solve volume ratios missing bands: "
                + ", ".join(vol_missing)
            )
        vol_ratios = {
            k: _finite_positive(raw_vol[k], f"volume ratio {k!r}") for k in sorted(BAND_PARAMS)
        }
        notes = d.get("notes", [])
        if not isinstance(notes, list):
            raise AutoSculptError("sculpt solve notes must be a list")
        return cls(
            figure=figure,
            reference_image=str(d.get("reference_image", "")),
            image_size=(image_size[0], image_size[1]),
            reference_ratios=ratios,
            volume_ratios=vol_ratios,
            notes=[str(n) for n in notes],
        )
