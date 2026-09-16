#!/usr/bin/env python3
"""P2-6 gate instrument: hip stabilization before/after on SYNTHETIC actions.

Two deterministic synthetic scenarios (full leg chain, canonical units):

- "breathing stance": both feet planted, no drift — the per-frame scale track
  breathes +/-0.5% (bob + detector noise modulating the torso-span scale
  estimate). This is EXACTLY the artifact ``stabilize_hips`` targets: the
  ankles inherit the anchor-frame breathing and slide while "planted".
- "drift + breathing walk": the P2-5 stance drift (0.012 u/frame) PLUS the
  same breathing — the composed-pipeline scenario (stabilize -> detect ->
  lock), proving stabilization does not disturb the foot-lock guarantee.

Measures: hip-frame sway (relative scale RMS) before/after, ankle
``contacts.foot_slide`` before stabilization / after stabilization (no lock) /
after the full lock, and the lock's cost columns. Writes the results block
into docs/BENCHMARKS.md between the HIPSTAB markers. Pure stdlib, no models,
deterministic. Honest: labeled SYNTHETIC instrument; real-clip numbers land
with P2-8; no solve priors, contact thresholds, or the published P2-5 gate
numbers are touched (D-008, D-010..013).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from riggermortis.action import action_from_poses, stabilize_hips
from riggermortis.canonical_pose import CanonicalPose
from riggermortis.contacts import detect_contacts, foot_slide, lock_feet

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs" / "BENCHMARKS.md"
BEGIN = "<!-- BENCHMARK:HIPSTAB:BEGIN -->"
END = "<!-- BENCHMARK:HIPSTAB:END -->"

GROUND = -1.0
DRIFT = 0.012      # canonical u/frame — the P2-5 hip-anchoring drift artifact
BREATH = 0.005     # +/- relative scale breathing (period 4 frames)
BASE_SCALE = 30.0

# 70 frames, two steps per foot (same phase pattern as the P2-5 gate).
PHASES_L = [("stance", 0, 9), ("swing", 10, 23), ("stance", 24, 39),
            ("swing", 40, 53), ("stance", 54, 69)]
PHASES_R = [("swing", 0, 13), ("stance", 14, 29), ("swing", 30, 43),
            ("stance", 44, 59), ("swing", 60, 69)]
#: Both feet planted for the whole clip (the pure breathing scenario).
PHASES_STANCE = [("stance", 0, 69)]

TORSO = {
    "hips": (0.0, 0.0, 0.0), "spine": (0.0, 0.0, 0.09), "chest": (0.0, 0.0, 0.26),
    "neck": (0.0, 0.0, 0.45), "head": (0.0, 0.0, 0.56),
    "shoulder.L": (0.13, 0.0, 0.45), "shoulder.R": (-0.13, 0.0, 0.45),
    "upper_arm.L": (0.26, 0.0, 0.45), "upper_arm.R": (-0.26, 0.0, 0.45),
    "forearm.L": (0.58, 0.0, 0.45), "forearm.R": (-0.58, 0.0, 0.45),
    "hand.L": (0.86, 0.0, 0.45), "hand.R": (-0.86, 0.0, 0.45),
}


def _scale_at(i: int) -> float:
    return BASE_SCALE * (1.0 + BREATH * math.sin(2.0 * math.pi * i / 4.0))


def _pose(
    i: int,
    *,
    drift: bool,
    wobble: float,
    phases_l: list,
    phases_r: list,
) -> CanonicalPose:
    """One walk frame; positions are then rescaled by the breathing frame."""
    positions: dict[str, tuple[float, float, float]] = dict(TORSO)
    sway = 0.01 * math.sin(0.5 * i)
    positions["hips"] = (sway, 0.0, 0.0)
    for side, sign in ((".L", -1.0), (".R", 1.0)):
        hip = (sign * 0.08 + sway, 0.0, 0.0)
        positions[f"upper_leg{side}"] = hip
        for kind, start, end in phases_l if side == ".L" else phases_r:
            if not (start <= i <= end):
                continue
            if kind == "stance":
                wob = wobble * math.sin(0.9 * i)
                d = DRIFT * (i - start) if drift else 0.0
                ankle = (sign * 0.11 + d + wob * 0.25, 0.0, GROUND + wob)
            else:
                span = end - start + 2
                t = (i - start + 1) / span
                ankle = (
                    sign * 0.11 + 0.02 * (i - start), 0.0,
                    GROUND + 0.35 * math.sin(math.pi * t),
                )
            knee = ((hip[0] + ankle[0]) / 2.0, (hip[1] + ankle[1]) / 2.0 - 0.08,
                    (hip[2] + ankle[2]) / 2.0)
            positions[f"lower_leg{side}"] = knee
            positions[f"foot{side}"] = ankle
            positions[f"toe{side}"] = (ankle[0], ankle[1] - 0.12, ankle[2])
    s = _scale_at(i)
    k = BASE_SCALE / s
    return CanonicalPose(
        positions={r: (p[0] * k, p[1] * k, p[2] * k) for r, p in positions.items()},
        flips={}, confidence=0.9, reliable=True, scale=s, anchor="hips",
    )


def build_walk(*, drift: bool, stance_only: bool = False,
               wobble: float = 0.0) -> object:
    pl = PHASES_STANCE if stance_only else PHASES_L
    pr = PHASES_STANCE if stance_only else PHASES_R
    return action_from_poses(
        [(i, _pose(i, drift=drift, wobble=wobble, phases_l=pl, phases_r=pr))
         for i in range(70)]
    )


def measure(label: str, action: object) -> dict[str, object]:
    report = detect_contacts(action.frames)  # type: ignore[attr-defined]
    slide_raw = foot_slide(action.frames, report)  # type: ignore[attr-defined]

    stabilized, stab = stabilize_hips(action, strength=0.7)
    slide_stab = foot_slide(stabilized.frames, report)  # type: ignore[attr-defined]

    cond_report = detect_contacts(stabilized.frames)  # type: ignore[attr-defined]
    locked, lock = lock_feet(stabilized, cond_report)
    slide_locked = lock.slide_after
    gate = slide_locked.total <= max(slide_raw.total, slide_stab.total) / 5.0
    print(
        f"{label}: contact raw={sum(report.in_contact.values())}f "
        f"cond={sum(cond_report.in_contact.values())}f "
        f"slide raw={slide_raw.total:.4f}u stab={slide_stab.total:.4f}u "
        f"locked={slide_locked.total:.4f}u (gate {'PASS' if gate else 'FAIL'}) "
        f"scale RMS {stab.scale_sway_before:.5f} -> {stab.scale_sway_after:.5f} "
        f"knee<={max(lock.max_knee_shift.values(), default=0.0):.4f}u "
        f"clamped={sum(lock.clamped.values())}"
    )
    assert locked.frame_indices == stabilized.frame_indices  # type: ignore[attr-defined]
    return {
        "label": label,
        "contact_raw": sum(report.in_contact.values()),
        "contact_cond": sum(cond_report.in_contact.values()),
        "raw": slide_raw.total,
        "stab": slide_stab.total,
        "locked": slide_locked.total,
        "gate": "PASS" if gate else "FAIL",
        "sway_before": stab.scale_sway_before or 0.0,
        "sway_after": stab.scale_sway_after or 0.0,
        "knee": max(lock.max_knee_shift.values(), default=0.0),
        "clamped": sum(lock.clamped.values()),
    }


def write_docs(rows: list[dict[str, object]]) -> None:
    lines = [
        "### Hip stabilization gate (P2-6, generated by `xtask/hip_stab_gate.py`) — SYNTHETIC",
        "",
        "**Synthetic instrument, not a real-clip benchmark.** The scale track",
        f"breathes +/-{BREATH:.1%} (period 4 frames) — the anchor-frame artifact",
        "P2-6 targets — and the walk scenario adds the P2-5 stance drift",
        f"({DRIFT} u/frame). Pipeline: stabilize_hips(0.7) -> detect -> lock.",
        "Slide = ankle path length while in contact. Real-clip numbers land",
        "with P2-8; no thresholds or priors were tuned against this fixture,",
        "and the published P2-5 gate numbers above are untouched (D-008,",
        "D-010..013). Deterministic: rerun prints the same numbers.",
        "",
        (
            "| scenario | contact raw -> cond | slide raw (u) | after stabilize (u) |"
            " after lock (u) | lock gate | scale sway RMS before -> after |"
            " max knee corr (u) | clamped |"
        ),
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['label']} | {r['contact_raw']} -> {r['contact_cond']} | "
            f"{r['raw']:.4f} | {r['stab']:.4f} | {r['locked']:.4f} | {r['gate']} | "
            f"{r['sway_before']:.5f} -> {r['sway_after']:.5f} | "
            f"{r['knee']:.4f} | {r['clamped']} |"
        )
    lines += [
        "",
        "The stabilization column is the honest P2-6 headline: anchor-frame",
        "noise removed BEFORE detection, so the lock absorbs less of it. A",
        "steady per-frame drift is low-frequency to any smoother by",
        "construction — it stays the foot lock's job (scenario 2), which is",
        "why both halves exist. Stance scenario isolates the breathing",
        "artifact (no drift, both feet planted throughout).",
        "",
        "Reproduce: `python3 xtask/hip_stab_gate.py`.",
    ]
    block = "\n".join(lines)
    text = DOCS.read_text(encoding="utf-8") if DOCS.exists() else "# Benchmarks\n"
    if BEGIN in text and END in text:
        head, rest = text.split(BEGIN, 1)
        _old, tail = rest.split(END, 1)
        text = head + BEGIN + "\n" + block + "\n" + END + tail
    else:
        text = text.rstrip() + "\n\n" + BEGIN + "\n" + block + "\n" + END + "\n"
    DOCS.write_text(text, encoding="utf-8")
    print(f"docs block written: {DOCS} (between {BEGIN} / {END})")


def main() -> int:
    rows = [
        measure(
            "breathing stance (no drift)",
            build_walk(drift=False, stance_only=True),
        ),
        measure(
            "drift + breathing walk",
            build_walk(drift=True, wobble=0.005),
        ),
    ]
    if any(r["gate"] != "PASS" for r in rows):
        print("HIP STAB GATE: FAIL", file=sys.stderr)
        return 1
    if rows[0]["stab"] >= rows[0]["raw"]:
        print(
            "HIP STAB GATE: FAIL (stabilization did not cut stance slide)",
            file=sys.stderr,
        )
        return 1
    write_docs(rows)
    print("HIP STAB GATE: PASS (synthetic instrument)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
