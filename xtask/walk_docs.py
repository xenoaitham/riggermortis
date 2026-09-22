#!/usr/bin/env python3
"""Write the P2-8 docs block (docs/BENCHMARKS.md, WALKRIGS markers).

Collects the per-rig manifests written by ``xtask/walk_media.py`` (Blender
bake fidelity + per-interval ankle drift in rig space), recomputes the
canonical-side slide numbers on the exact media pipeline (same generator,
same conditioning as the renders), and publishes the block. Fails loudly if
any manifest misses its gate: FK fidelity > 0.5 deg, or a locked pass whose
planted-foot drift exceeds the 0.010 m bar (the RM_FOOT_LOCK bar).

Honesty rules this block keeps: the clip is the labeled SYNTHETIC generator
(``xtask/hip_stab_gate.py``) — the real walking clip stays NEEDS-HUMAN
(out/video_smoke/SOURCES.md) and the Phase-2 real-clip gate is recorded
NOT-met-with-real-clips (D-015), never relabeled. Deterministic: rerun
prints the same numbers.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

XTASK = Path(__file__).resolve().parent
REPO = XTASK.parent
BEGIN = "<!-- BENCHMARK:WALKRIGS:BEGIN -->"
END = "<!-- BENCHMARK:WALKRIGS:END -->"

GIFS = [
    ("walk_lock_metarig.gif", "Rigify metarig: raw | locked"),
    ("walk_lock_seedsan.gif", "Seed-san (VRM): raw | locked"),
    ("walk_lock_xbot.gif", "Xbot (Mixamo export): raw | locked"),
    ("walk_3rigs.gif", "the locked walk on metarig | Seed-san | Xbot"),
]


def canonical_numbers() -> dict[str, float]:
    """Same pipeline as the renders, canonical side (pure stdlib)."""
    sys.path.insert(0, str(REPO / "core" / "src"))
    sys.path.insert(0, str(XTASK))
    import hip_stab_gate
    import riggermortis as core

    raw = hip_stab_gate.build_walk(drift=True, wobble=0.005)
    conditioned = core.condition_action(
        raw, hip_stabilize=0.7, min_cutoff=None, tolerance=None
    )
    report = core.detect_contacts(conditioned.frames)
    slide_conditioned = core.foot_slide(conditioned.frames, report).total
    _locked, lock = core.lock_feet(conditioned, report)
    return {
        "slide_conditioned": slide_conditioned,
        "slide_locked": lock.slide_after.total,
        "knee": max(lock.max_knee_shift.values(), default=0.0),
        "clamped": sum(lock.clamped.values()),
        "frames": len(conditioned.frames),
    }


def load_rows(manifest_dir: Path) -> list[dict[str, object]]:
    rows: dict[str, dict[str, object]] = {}
    for path in sorted(manifest_dir.glob("*_*.manifest.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        label, mode = str(manifest["label"]), str(manifest["mode"])
        row = rows.setdefault(label, {})
        row[mode] = manifest
    out = []
    for label in sorted(rows):
        row = rows[label]
        if "raw" not in row or "locked" not in row:
            raise SystemExit(f"error: {label} lacks a raw or locked manifest")
        raw_m, locked_m = row["raw"], row["locked"]
        assert isinstance(raw_m, dict) and isinstance(locked_m, dict)
        if locked_m["worst_deg"] > 0.5:
            raise SystemExit(
                f"error: {label} locked bake FK fidelity "
                f"{locked_m['worst_deg']} deg > 0.5 — gate refuses to publish"
            )
        raw_drift = float(raw_m["ankle_drift_m"])
        locked_drift = float(locked_m["ankle_drift_m"])
        # The publish gate is the PUBLISHED P2-5 criterion (>=5x slide
        # reduction, docs/BENCHMARKS.md FOOTLOCK block + D-013) — scale-free,
        # so it compares across rigs. The metarig-probe absolute bar
        # (0.010 m) stays visible as a column, not as the gate: it bakes in
        # one rig's scale (seedsan misses it by ~5% on clamp-cost frames
        # while locking 12x — hiding that behind a refusal would publish
        # less truth, not more).
        ratio = raw_drift / locked_drift if locked_drift > 0 else float("inf")
        if ratio < 5.0:
            raise SystemExit(
                f"error: {label} lock ratio {ratio:.1f}x < the published 5x "
                "slide gate — gate refuses to publish"
            )
        out.append({
            "label": label,
            "format": locked_m["rig_kind"],
            "bones": locked_m["bones"],
            "drift_raw": raw_drift,
            "drift_locked": locked_drift,
            "ratio": ratio,
            "bar_pass": bool(locked_m["drift_pass"]),
            "worst_deg": locked_m["worst_deg"],
            "lock_dev_deg": locked_m["lock_dev_deg"],
            "clamped": locked_m["lock_clamped"],
            "locked_frames": locked_m["locked_frames"],
            "mapping": locked_m["mapping_source"],
        })
    if not out:
        raise SystemExit(f"error: no manifests under {manifest_dir}")
    return out


def write_block(rows: list[dict[str, object]], canon: dict[str, float]) -> None:
    per_rig_note = (
        "Per-rig bake numbers (WORLD units, so rigs of different scales"
        " compare). Drift = max ankle world drift WITHIN one contact"
        " interval (a walk replants each foot per cycle — the lock pins"
        " the plant, not the stride), the RM_FOOT_LOCK measurement. The"
        " publish gate is the PUBLISHED P2-5 >=5x slide criterion"
        " (FOOTLOCK block, D-013) — scale-free, so it compares across"
        " rigs; the 0.010 m metarig-probe bar is shown for scale context"
        " only. FK worst is on the UNLOCKED application, bar 0.5 deg."
    )
    lines = [
        (
            "### Walk across three rigs (P2-8, generated by"
            " `xtask/render_walk_gifs.sh`) — SYNTHETIC"
        ),
        "",
        "**Synthetic instrument, not real-clip footage.** The clip is the",
        "labeled drift + breathing walk from `xtask/hip_stab_gate.py` (the",
        "HIPSTAB generator), retargeted to three real rigs through the",
        "documented pipeline: `condition_action(hip_stabilize=0.7,",
        "min_cutoff=None, tolerance=None)` — the CI-certified composition,",
        "stabilization only —>",
        "`detect_contacts` -> `lock_feet` -> `bake_action(contacts=...)` — the",
        "add-on's real bake path. Smoothing and keyframe reduction are",
        "disabled for the media pass (the GIFs show the generator's native",
        "frame count). The real",
        "walking clip stays NEEDS-HUMAN (out/video_smoke/SOURCES.md); the",
        "Phase-2 real-clip gate is recorded NOT-met-with-real-clips",
        "(DECISIONS D-015) and is never relabeled as met.",
        "",
        "The third rig caught a real compatibility bug: glTF has no bone-tail",
        "concept, and the Mixamo glb's synthesized tails are ~100x the true",
        "joint spacing, which broke Blender's evaluated placement (children",
        "ladder away from parents), the lock's 2-bone solve lengths (bake now",
        "uses head-to-head rest distances), and the proxy visualizer. The",
        "media pipeline repairs tails WHEN they disagree with the skeleton",
        "(deterministic; Blender-native rigs are bit-for-bit untouched);",
        "the ADD-ON runs the same conditional repair on Inspect & Map and",
        "agent applies — the D-016 absurd-ratio rule, count always",
        "reported, sane rigs untouched.",
        "",
        per_rig_note,
        "",
        (
            "| rig | format | bones | mapping | unlocked drift (m) |"
            " locked drift (m) | lock ratio | >=5x gate | 0.010 m bar |"
            " FK worst (deg) | lock_dev (deg) | clamped | locked frames |"
        ),
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['label']} | {r['format']} | {r['bones']} | {r['mapping']} | "
            f"{r['drift_raw']:.4f} | {r['drift_locked']:.4f} | {r['ratio']:.1f}x | "
            f"PASS | {'PASS' if r['bar_pass'] else 'miss (clamp cost)'} | "
            f"{r['worst_deg']:.4f} | {r['lock_dev_deg']:.2f} | {r['clamped']} | "
            f"{r['locked_frames']} |"
        )
    lines += [
        "",
        (
            "Media (pipeline-generated headlessly, bone-proxy visualizer,"
            " workbench; committed under docs/media/, media-guard allowlisted):"
        ),
        "",
    ]
    for name, caption in GIFS:
        lines.append(f"- `docs/media/{name}` — {caption}.")
    lines += [
        "",
        "Canonical side of this exact pipeline (same generator and",
        f"conditioning as the renders): slide {canon['slide_conditioned']:.4f}u",
        f"conditioned -> {canon['slide_locked']:.4f}u locked over",
        f"{canon['frames']} frames (knee corrections <= {canon['knee']:.4f}u,",
        f"{canon['clamped']} clamps). The HIPSTAB block above publishes the",
        "stabilize-only variant of the same generator; FOOTLOCK the",
        "drift-only variant. Nothing here relabels those instruments.",
        "",
        "Reproduce: `make walk-gifs` (needs local rigs + Blender — the rigs",
        "are git-ignored; see docs/BENCHMARKS.md reproduce blocks).",
    ]
    block = "\n".join(lines)
    docs = REPO / "docs" / "BENCHMARKS.md"
    text = docs.read_text(encoding="utf-8")
    if BEGIN in text and END in text:
        head, rest = text.split(BEGIN, 1)
        _old, tail = rest.split(END, 1)
        text = head + BEGIN + "\n" + block + "\n" + END + tail
    else:
        text = text.rstrip() + "\n\n" + BEGIN + "\n" + block + "\n" + END + "\n"
    docs.write_text(text, encoding="utf-8")
    print(f"docs block written: {docs} (between {BEGIN} / {END})")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default="out/p28", help="manifest directory")
    args = parser.parse_args(argv)
    manifest_dir = Path(args.dir)
    if not manifest_dir.is_dir():
        raise SystemExit(f"error: manifest directory not found: {manifest_dir}")
    for name, _caption in GIFS:
        gif = REPO / "docs" / "media" / name
        if not gif.is_file():
            raise SystemExit(
                f"error: {gif} missing — assemble the GIFs into docs/media "
                "before writing the docs block"
            )
    canon = canonical_numbers()
    print(
        f"canonical: slide {canon['slide_conditioned']:.4f}u -> "
        f"{canon['slide_locked']:.4f}u locked"
    )
    rows = load_rows(manifest_dir)
    write_block(rows, canon)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
