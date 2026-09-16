#!/usr/bin/env python3
"""P2-5 gate instrument: IK foot lock before/after on a SYNTHETIC walking action.

Builds deterministic synthetic walk actions (full leg chain, canonical units,
stance ankles drifting 0.012 u/frame to reproduce the hip-anchoring artifact),
detects contacts, measures ``contacts.foot_slide`` before/after
``contacts.lock_feet``, and writes the results block into docs/BENCHMARKS.md
between the FOOTLOCK markers. Pure stdlib, no models, deterministic.

Honesty: this is an INSTRUMENT gate on synthetic data, labeled as such in the
docs block. It proves the lock removes exactly the artifact it targets and
quantifies its cost (knee corrections, ankle shifts, clamps). Real-clip
numbers land with P2-8 (dance/fight clips); contact thresholds are NOT tuned
against this fixture (D-008).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from riggermortis.action import ActionFrame, action_from_poses
from riggermortis.canonical_pose import CanonicalPose
from riggermortis.contacts import detect_contacts, foot_slide, lock_feet

REPO = Path(__file__).resolve().parent.parent

DOCS = REPO / "docs" / "BENCHMARKS.md"
BEGIN = "<!-- BENCHMARK:FOOTLOCK:BEGIN -->"
END = "<!-- BENCHMARK:FOOTLOCK:END -->"

GROUND = -1.0
DRIFT = 0.012  # canonical u/frame — the hip-anchoring artifact, injected on purpose

# 70 frames, two steps per foot (same phase pattern as the CI fixture).
PHASES_L = [("stance", 0, 9), ("swing", 10, 23), ("stance", 24, 39),
            ("swing", 40, 53), ("stance", 54, 69)]
PHASES_R = [("swing", 0, 13), ("stance", 14, 29), ("swing", 30, 43),
            ("stance", 44, 59), ("swing", 60, 69)]

# Static torso/arms (canonical proportions, hip height = 1.0) so the pose is a
# complete skeleton, not just a leg chain.
TORSO = {
    "hips": (0.0, 0.0, 0.0), "spine": (0.0, 0.0, 0.09), "chest": (0.0, 0.0, 0.26),
    "neck": (0.0, 0.0, 0.45), "head": (0.0, 0.0, 0.56),
    "shoulder.L": (0.13, 0.0, 0.45), "shoulder.R": (-0.13, 0.0, 0.45),
    "upper_arm.L": (0.26, 0.0, 0.45), "upper_arm.R": (-0.26, 0.0, 0.45),
    "forearm.L": (0.58, 0.0, 0.45), "forearm.R": (-0.58, 0.0, 0.45),
    "hand.L": (0.86, 0.0, 0.45), "hand.R": (-0.86, 0.0, 0.45),
}


def _swing(i: int, start: int, end: int, x: float) -> tuple[float, float, float]:
    span = end - start + 2
    t = (i - start + 1) / span
    return (x + 0.02 * (i - start), 0.0, GROUND + 0.35 * math.sin(math.pi * t))


def _pose(i: int, phases_l: list, phases_r: list, *, wobble: float) -> CanonicalPose:
    positions: dict[str, tuple[float, float, float]] = dict(TORSO)
    sway = 0.01 * math.sin(0.5 * i)
    positions["hips"] = (sway, 0.0, 0.0)
    for phases, sign in ((phases_l, -1.0), (phases_r, 1.0)):
        side = ".L" if sign < 0 else ".R"
        hip = (sign * 0.08 + sway, 0.0, 0.0)
        positions[f"upper_leg{side}"] = hip
        for kind, start, end in phases:
            if not (start <= i <= end):
                continue
            if kind == "stance":
                wob = wobble * math.sin(0.9 * i)
                ankle = (sign * 0.11 + DRIFT * (i - start) + wob * 0.25, 0.0,
                         GROUND + wob)
            else:
                ankle = _swing(i, start, end, x=sign * 0.11)
            knee = ((hip[0] + ankle[0]) / 2.0, (hip[1] + ankle[1]) / 2.0 - 0.08,
                    (hip[2] + ankle[2]) / 2.0)
            positions[f"lower_leg{side}"] = knee
            positions[f"foot{side}"] = ankle
            positions[f"toe{side}"] = (ankle[0], ankle[1] - 0.12, ankle[2])
    return CanonicalPose(
        positions=positions, flips={}, confidence=0.9, reliable=True,
        scale=30.0, anchor="hips",
    )


def _walk(phases_l: list, phases_r: list, *, wobble: float) -> list[ActionFrame]:
    return [
        ActionFrame(frame=i, pose=_pose(i, phases_l, phases_r, wobble=wobble))
        for i in range(70)
    ]


def measure(label: str, wobble: float) -> dict[str, object]:
    frames = _walk(PHASES_L, PHASES_R, wobble=wobble)
    action = action_from_poses([(f.frame, f.pose) for f in frames])
    report = detect_contacts(frames)
    before = foot_slide(frames, report)
    locked, lock = lock_feet(action, report)
    after = lock.slide_after
    gate = after.total <= before.total / 5.0
    print(
        f"{label}: contact={sum(report.in_contact.values())}f "
        f"slide {before.total:.4f}u -> {after.total:.4f}u "
        f"(gate {'PASS' if gate else 'FAIL'}) "
        f"knee<={max(lock.max_knee_shift.values(), default=0.0):.4f}u "
        f"shift<={max(lock.max_ankle_shift.values(), default=0.0):.4f}u "
        f"clamped={sum(lock.clamped.values())}"
    )
    assert locked.frame_indices == action.frame_indices
    return {
        "label": label,
        "contact": sum(report.in_contact.values()),
        "before": before.total,
        "after": after.total,
        "gate": "PASS" if gate else "FAIL",
        "knee": max(lock.max_knee_shift.values(), default=0.0),
        "shift": max(lock.max_ankle_shift.values(), default=0.0),
        "clamped": sum(lock.clamped.values()),
    }


def write_docs(rows: list[dict[str, object]]) -> None:
    lines = [
        "### IK foot lock gate (P2-5, generated by `xtask/foot_lock_gate.py`) — SYNTHETIC",
        "",
        "**Synthetic instrument, not a real-clip benchmark.** Walk actions are",
        "constructed (full leg chain, canonical units); stance ankles drift",
        f"{DRIFT} u/frame to reproduce the hip-anchoring artifact the lock",
        "removes. Real-clip numbers land with P2-8. Contact thresholds are NOT",
        "tuned against this fixture (D-008). Deterministic: rerun prints the",
        "same numbers.",
        "",
        (
            "| scenario | contact frames | slide before (u) | slide after (u) |"
            " after <= before/5 | max knee correction (u) | max ankle shift (u) | clamped |"
        ),
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['label']} | {r['contact']} | {r['before']:.4f} | "
            f"{r['after']:.4f} | {r['gate']} | {r['knee']:.4f} | "
            f"{r['shift']:.4f} | {r['clamped']} |"
        )
    lines += [
        "",
        "Slide = ankle path length while in contact (`contacts.foot_slide`).",
        "After = 0.0 by construction (position pinning); the cost columns are",
        "the honest price: how far knees and pinned ankles moved away from the",
        "source observation to get there. A real (near-static) person clip",
        "reads slide 0.0 before the lock — no slide to fix — which is why the",
        "gate number comes from this labeled synthetic walk until P2-8.",
        "",
        "Reproduce: `python3 xtask/foot_lock_gate.py`.",
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
        measure("drift walk", wobble=0.0),
        measure("drift + wobble", wobble=0.005),
    ]
    if any(r["gate"] != "PASS" for r in rows):
        print("FOOT LOCK GATE: FAIL", file=sys.stderr)
        return 1
    write_docs(rows)
    print("FOOT LOCK GATE: PASS (synthetic instrument)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
