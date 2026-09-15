#!/usr/bin/env python
"""P1-9: pose benchmark harness (NOT in CI — needs the real ONNX models).

Walks ``out/benchmark/images/{photo,anime}/``, runs the full Phase-1 chain per
image (detect -> FigureBoard(largest) -> solve), and writes a generated
markdown block into ``docs/BENCHMARKS.md`` between markers:

    <!-- BENCHMARK:POSES:BEGIN --> ... <!-- BENCHMARK:POSES:END -->

Metric (defined here, honestly — no hand-waving):
- ``usable-straight-away`` = solver says reliable AND no flip margin below the
  review bar AND no deep-foreshortening flag. It is a *lower bound* on
  "artist can use this pose immediately"; it does not measure anatomical
  correctness of the depth solve.
- ``flip_uncertain`` column = the D-008 review-UI rescue cases (elbow/knee
  bend ambiguity); ``deep_foreshortening`` = proximal segment 2D length well
  below its canonical 3D length (>=0.6 cut) — the documented kick /
  arms-behind miss class, flagged as a heuristic, not a verdict.
- The confidence distribution is always reported alongside the headline rate.

Usage:
    python3 xtask/benchmark_poses.py                # run + write docs block
    python3 xtask/benchmark_poses.py --print-only   # don't touch the docs
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
IMAGES_ROOT = REPO / "out" / "benchmark" / "images"
DOCS = REPO / "docs" / "BENCHMARKS.md"
BEGIN, END = "<!-- BENCHMARK:POSES:BEGIN -->", "<!-- BENCHMARK:POSES:END -->"

#: 2D/canonical-3D length ratio below which a proximal segment is flagged as
#: deeply foreshortened (heuristic proxy for the D-008 kick / arms-back class).
FORESHORTEN_CUT = 0.6

#: Per-segment canonical lengths (mirrors canonical_pose._FLIP_CHAINS).
PROXIMAL = {"upper_arm": 0.32, "upper_leg": 0.50}


@dataclass
class Row:
    path: Path
    figures: int
    label: str
    score: float
    confidence: float
    reliable: bool
    flip_min: float
    flip_uncertain: bool
    foreshortened: list[str] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        return self.reliable and not self.flip_uncertain and not self.foreshortened

    def flags(self) -> str:
        out = []
        if self.flip_uncertain:
            out.append("flip")
        if self.foreshortened:
            out.append("fore-" + ",".join(self.foreshortened))
        return ";".join(out) if out else ""


def _engine():
    """Load the real engine pieces; exits with an actionable message in CI envs."""
    try:
        import riggermortis as core
        from riggermortis.canonical_pose import observations_from_keypoints, solve_pose
        from riggermortis.inference import dwpose
        from riggermortis.inference.figures import FigureBoard
        from riggermortis.review import CONFIDENCE_BAR
    except ImportError as exc:
        raise SystemExit(
            f"benchmark needs the engine + [inference] extra ({exc}); "
            "install with: pip install -e 'core[inference]' and run "
            "`rigpose models download all` first"
        ) from exc
    return core, dwpose, FigureBoard, observations_from_keypoints, solve_pose, CONFIDENCE_BAR


def _foreshortened_segments(observations: dict, scale: float) -> list[str]:
    """Proximal segments whose 2D length is far below their canonical 3D length.

    Uses the solver's own chain table (girdle->mid, canonical length), so the
    flag is consistent with what the solve assumed.
    """
    from riggermortis.canonical_pose import _FLIP_CHAINS  # noqa: PLC2701 — solver's own table

    out = []
    for flip_key, (girdle, mid, _end, l_prox, _l_dist) in sorted(_FLIP_CHAINS.items()):
        if girdle not in observations or mid not in observations:
            continue
        (ux, uy) = observations[girdle][0]
        (mx, my) = observations[mid][0]
        ratio = math.hypot(mx - ux, my - uy) / (scale * l_prox)
        if ratio < FORESHORTEN_CUT:
            out.append(f"{flip_key}:{girdle}")
    return out


def run_image(engine, path: Path) -> Row | None:
    core, dwpose, FigureBoard, observations_from_keypoints, solve_pose, conf_bar = engine
    detection = dwpose.detect_keypoints(str(path))
    board = FigureBoard.from_detection(detection)
    figure = board.largest()
    if figure is None:
        return Row(
            path=path, figures=0, label="-", score=0.0, confidence=0.0,
            reliable=False, flip_min=0.0, flip_uncertain=True,
            foreshortened=["no-person"],
        )
    observations = observations_from_keypoints(figure.keypoints, figure.confidences)
    pose = solve_pose(observations)
    flip_confs = [pose.joint_confidence.get(k, 0.0) for k in
                  ("forearm.L", "forearm.R", "lower_leg.L", "lower_leg.R")]
    flip_min = min(flip_confs) if flip_confs else 0.0
    return Row(
        path=path,
        figures=len(board.figures),
        label=figure.label,
        score=figure.score,
        confidence=pose.confidence,
        reliable=pose.reliable,
        flip_min=flip_min,
        flip_uncertain=flip_min < conf_bar,
        foreshortened=_foreshortened_segments(observations, pose.scale),
    )


def collect() -> dict[str, list[Row]]:
    if not IMAGES_ROOT.is_dir():
        raise SystemExit(f"missing {IMAGES_ROOT} — put licensing-clean images under images/photo and images/anime")
    engine = _engine()
    sets: dict[str, list[Row]] = {}
    for subset in sorted(p for p in IMAGES_ROOT.iterdir() if p.is_dir()):
        rows = []
        for path in sorted(subset.iterdir()):
            if path.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
                continue
            row = run_image(engine, path)
            if row is not None:
                rows.append(row)
                state = "USABLE" if row.usable else f"flagged[{row.flags()}]"
                print(f"  {path.name}: conf {row.confidence:.2f} flip_min {row.flip_min:.2f} -> {state}")
        sets[subset.name] = rows
    return sets


def _fmt_stats(rows: list[Row]) -> str:
    if not rows:
        return "no images"
    confs = sorted(r.confidence for r in rows)
    n = len(confs)
    median = confs[n // 2] if n % 2 else (confs[n // 2 - 1] + confs[n // 2]) / 2
    usable = sum(1 for r in rows if r.usable)
    return (
        f"{usable}/{n} usable ({100.0 * usable / n:.0f}%), "
        f"confidence min {confs[0]:.2f} / median {median:.2f} / max {confs[-1]:.2f}"
    )


def markdown_block(sets: dict[str, list[Row]]) -> str:
    lines = [
        "### Phase 1 pose benchmark (P1-9, generated by xtask/benchmark_poses.py)",
        "",
        "`usable-straight-away` = solver-reliable AND every flip margin >= 0.55 "
        "AND no deep-foreshortening flag (heuristic proxy for the two documented "
        "D-008 miss classes: deep kicks, wrists behind the back). Flags: "
        "`flip` = bend direction for human review; `fore-<segment>` = proximal "
        "segment 2D length < 0.6x canonical (single-view depth limitation).",
        "",
    ]
    for name in sorted(sets):
        rows = sets[name]
        lines.append(f"#### {name} set — {_fmt_stats(rows)}")
        lines.append("")
        lines.append("| image | figures | figure used | det score | pose conf | reliable | min flip margin | flags | usable |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for row in rows:
            lines.append(
                f"| {row.path.name} | {row.figures} | {row.label} | {row.score:.2f} "
                f"| {row.confidence:.2f} | {'yes' if row.reliable else 'NO'} "
                f"| {row.flip_min:.2f} | {row.flags() or '-'} "
                f"| {'YES' if row.usable else 'no'} |"
            )
        lines.append("")
    anime = sets.get("anime", [])
    if 0 < len(anime) < 10:
        lines.append(
            f"**NEEDS-HUMAN (anime sourcing):** only {len(anime)} licensing-clean "
            "anime image(s) available locally; the P1-8 fallback-estimator "
            "decision stays explicitly pending until a 10-image set exists."
        )
        lines.append("")
    if not sets.get("anime"):
        lines.append(
            "**NEEDS-HUMAN (anime sourcing):** no anime images found locally; "
            "P1-8 decision pending."
        )
        lines.append("")
    return "\n".join(lines)


def write_docs(block: str) -> None:
    text = DOCS.read_text(encoding="utf-8") if DOCS.exists() else "# Benchmarks\n"
    if BEGIN in text and END in text:
        head, rest = text.split(BEGIN, 1)
        _old, tail = rest.split(END, 1)
        text = head + BEGIN + "\n" + block + "\n" + END + tail
    else:
        text = text.rstrip() + "\n\n" + BEGIN + "\n" + block + "\n" + END + "\n"
    DOCS.write_text(text, encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print-only", action="store_true", help="don't write docs/BENCHMARKS.md")
    parser.add_argument("--json", action="store_true", help="machine-readable summary to stdout")
    args = parser.parse_args(argv)

    sets = collect()
    block = markdown_block(sets)
    print()
    for name in sorted(sets):
        print(f"{name}: {_fmt_stats(sets[name])}")
    if args.print_only:
        print(block)
    else:
        write_docs(block)
        print(f"docs block written: {DOCS} (between {BEGIN} / {END})")
    if args.json:
        print(json.dumps(
            {name: [_row_dict(r) for r in rows] for name, rows in sorted(sets.items())},
            indent=2, sort_keys=True,
        ))
    return 0


def _row_dict(row: Row) -> dict:
    return {
        "image": row.path.name,
        "figures": row.figures,
        "figure": row.label,
        "score": round(row.score, 3),
        "confidence": round(row.confidence, 3),
        "reliable": row.reliable,
        "flip_min": round(row.flip_min, 3),
        "flags": row.flags(),
        "usable": row.usable,
    }


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
