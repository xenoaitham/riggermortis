"""P9-2 volume from silhouette — the pure half (the selected mechanism's
core bits).

Design of record: docs/VOLUME.md (the AUTO_SCULPT.md sibling, with the
probe-earned amendments A1–A3). The third-model decision is D-025
(`u2net.onnx` adopted as the segmentation pass — the manifest pin is the
license/checksum/CPU record). The honest physics, extended one step: the
silhouette mask gives the VISIBLE-VIEW widths; DEPTH is unobservable from
a single view and follows the DECLARED circular-cross-section prior (a
D-008 prior, never fitted, never a depth claim).

The MECHANISM (the probe's pre-declared selection, measured at the A.1
binding bar — amendment A3: the binding form is exact-alpha, sculpt vs
reference silhouettes, model-free; the model-mediated form is published
information): ``shape_key_inflate`` — engine-authored convention shape
keys (key DATA = the unit band warp, key VALUE = the solved delta — the
artist dial IS the volume param). The bpy half lives in the add-on
(``riggermortis_addon.volume``); this module is the PURE half: the band
param set, the clamp law, the solve law, the loud capability line, and
the structured report. Stdlib, deterministic, zero payload-format change
(shape keys are mesh data, not pose fields; D-025 was consumed by the
adoption decision itself).
"""
from __future__ import annotations

from .errors import AutoSculptError

# The region params (declared, docs/VOLUME.md): the roadmap's NSFW-relevant
# set, symmetrized (the single view symmetrizes sides by mean — the P9-1
# law). Names are the shape-key convention names (the artist-exit rule).
BAND_PARAMS: tuple[str, ...] = (
    "vol.thigh_w",
    "vol.hip_w",
    "vol.waist_w",
    "vol.chest_w",
)

# The declared solve clamp (loud when it fires — a clamped factor is a
# report note, never a wild solve silently truncated).
CLAMP_LO = 0.5
CLAMP_HI = 2.0

# The A.1 binding bar (amendment A3): exact-alpha IoU, visible-view scoped.
BAR_IOU = 0.85

CAPABILITY_NO_MESH = "volume: rig has no armature-deformed mesh — volume not applied"


def clamp_factor(f: float) -> float:
    """The declared clamp law: factors live in [CLAMP_LO, CLAMP_HI]."""
    return max(CLAMP_LO, min(CLAMP_HI, f))


def value_of_factor(f: float) -> float:
    """The key VALUE law (absolute-target, the S36 law): value = the
    clamped factor minus one — a re-solve OVERWRITES, never composes."""
    return clamp_factor(f) - 1.0


def validate_factors(factors: dict[str, float]) -> dict[str, float]:
    """Validate + clamp a solve's factors (loud): unknown params refuse,
    degenerate factors clamp with the caller expected to record the note."""
    unknown = sorted(set(factors) - set(BAND_PARAMS))
    if unknown:
        raise AutoSculptError(
            f"unknown volume params: {', '.join(unknown)} "
            f"(hint: the band params are {', '.join(BAND_PARAMS)})"
        )
    return {p: clamp_factor(factors[p]) for p in BAND_PARAMS if p in factors}


def capability_lines(has_mesh: bool) -> list[str]:
    """The loud capability draft (the P8-4 verbatim pattern): a rig whose
    mesh is absent (or not armature-deformed) is REFUSED with the line,
    never silently skipped."""
    if has_mesh:
        return []
    return [CAPABILITY_NO_MESH]


class VolumeReport:
    """The volume REPORT — ships as data regardless of any verdict (the
    camera-solve pattern): the solved factors, the applied key values,
    the capability lines, and the notes (clamps land here, loud)."""

    def __init__(
        self,
        factors: dict[str, float],
        values: dict[str, float],
        capability_lines: list[str],
        notes: list[str],
    ) -> None:
        self.factors = dict(sorted(factors.items()))
        self.values = dict(sorted(values.items()))
        self.capability_lines = list(capability_lines)
        self.notes = list(notes)

    def to_dict(self) -> dict[str, object]:
        return {
            "factors": dict(self.factors),
            "values": dict(self.values),
            "capability_lines": list(self.capability_lines),
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, d: dict[str, object]) -> VolumeReport:
        return cls(
            factors=dict(d["factors"]),  # type: ignore[arg-type]
            values=dict(d["values"]),  # type: ignore[arg-type]
            capability_lines=list(d["capability_lines"]),  # type: ignore[arg-type]
            notes=list(d["notes"]),  # type: ignore[arg-type]
        )
