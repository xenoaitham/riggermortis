"""The D-011 dual-estimator interface (P8-9): per-image estimator selection
plus the payload provenance contract.

D-011/D-012 history: the pinned DWPose fails outright on 3/10 anime benchmark
images; the planned fallback estimator (task P1-8a) was evaluated under the
Annex A.2 third-model ritual and REFUSED-with-evidence — no published
anime/sketch whole-body estimator with adoptable weights exists (docs/
REVIEW_UX.md candidate scan; the DECISIONS entry records the verdict). The
INTERFACE ships regardless — it is product surface, not the claim:

- an estimator is anything with a ``name`` and a ``detect_keypoints(image)``
  returning the standard :class:`~riggermortis.inference.dwpose.Detection`
  (nothing below the interface changes — downstream consumes the same 133-kp
  layout);
- ``select_estimator`` runs the default first and falls back through the
  registry in keyed (name-ascending) order exactly when the default finds
  no person; all fail -> the honest no-person result, never a fabricated
  pose;
- ``with_estimator_entry`` stamps a payload figure entry with the additive
  ``estimator`` field, written ONLY for non-default estimators, so every
  payload produced by the default-only registry stays byte-identical (the
  P8-9 byte-identity pin).

Weights enter ONLY through the checksum-pinned manifest (P1-1) after the
full third-model ritual: license verbatim, sha256 + byte size, CPU budget
measured on the mid-laptop baseline, the DECISIONS entry written at the
landing. NO fine-tune in the repo; adopted weights only; no scraped
Danbooru-class data, ever (D-011 verbatim).

Pure stdlib; deterministic (keyed registry order, no set iteration).
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

#: The registry key of the pinned default estimator.
DEFAULT_ESTIMATOR = "dwpose"

#: The payload entry field carrying per-figure provenance (additive, v3).
ESTIMATOR_FIELD = "estimator"


@runtime_checkable
class Estimator(Protocol):
    """Anything that can produce the standard 133-keypoint Detection."""

    name: str

    def detect_keypoints(self, image: Any, **kwargs: Any) -> Any:
        """Detect people in ``image``; return a dwpose.Detection."""
        ...  # pragma: no cover


def select_estimator(
    image: Any,
    estimators: dict[str, Estimator],
    **kwargs: Any,
) -> tuple[str, Any]:
    """Run the default estimator first; fall back keyed-order on no-person.

    Returns ``(name, detection)``. The fallback fires ONLY when the default
    detects no person (the D-011 per-image confidence probe — the anime gap
    is an outright no-person failure, measured 3/10). Every registered
    fallback missing the person too returns the LAST estimator's empty
    detection: the honest no-person answer either way — no figures, nothing
    fabricated — and the caller's no-person failure path takes over.
    """
    default = estimators[DEFAULT_ESTIMATOR]
    first = default.detect_keypoints(image, **kwargs)
    if getattr(first, "figures", None):
        return DEFAULT_ESTIMATOR, first
    for name in sorted(estimators):  # keyed order — determinism law
        if name == DEFAULT_ESTIMATOR:
            continue
        return name, estimators[name].detect_keypoints(image, **kwargs)
    return DEFAULT_ESTIMATOR, first


def with_estimator_entry(entry: dict[str, Any], estimator_name: str) -> dict[str, Any]:
    """A payload figure entry stamped with its estimator's provenance.

    The DEFAULT estimator is never written — a default-only pipeline emits
    byte-identical payloads (the P8-9 pin). Non-default names ride the
    additive ``estimator`` field; v3 readers ignore unknown entry fields
    (the ignore-with-note policy), so older builds keep reading the file.
    """
    if estimator_name == DEFAULT_ESTIMATOR:
        return entry
    out = dict(entry)
    out[ESTIMATOR_FIELD] = str(estimator_name)
    return out
