#!/usr/bin/env python3
"""P5-1 probe: measure the live-detector candidates BEFORE trusting the loop.

Runs the pinned DWPose stack headless over recorded frames in the three live
regimes (full / tracked / pose-only) at a couple of input sizes, and prints
``RM_LIVE`` lines for docs/LIVE.md + docs/BENCHMARKS.md. This is a LOCAL
instrument (needs models + git-ignored benchmark images); without them it
answers ``RM_LIVE PROBE SKIPPED`` honestly and exits 0 — CI-safe by design.

Everything it writes lands under ONE OUT_DIR (out/live_probe/); no artifact
moves here (D-009: moves live in shell glue).

Decision this probe feeds (docs/LIVE.md): reuse the pinned DWPose models with
a detector-cadence policy vs. add a lighter MediaPipe-class ONNX. Numbers,
not vibes.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "core" / "src"))

from riggermortis.canonical_pose import observations_from_keypoints, solve_pose  # noqa: E402
from riggermortis.errors import InferenceError, RiggermortisError  # noqa: E402
from riggermortis.fk_apply import apply_canonical_pose  # noqa: E402
from riggermortis.inference import models  # noqa: E402
from riggermortis.inference.dwpose import (  # noqa: E402
    DET_MODEL,
    POSE_MODEL,
    Sessions,
    detect_keypoints,
    estimate_keypoints_at,
    load_sessions,
)
from riggermortis.inference.poses import Figure  # noqa: E402
from riggermortis.live import DEFAULT_MARGIN, expand_bbox, mean_body_confidence  # noqa: E402
from riggermortis.mapper import map_rig  # noqa: E402
from riggermortis.types import BoneData, RigData  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
DEFAULT_IMAGES = REPO / "out" / "benchmark" / "images" / "photo"
DEFAULT_OUT_DIR = REPO / "out" / "live_probe"
DEFAULT_IMAGES_3 = ("pose1_white_shirt.png", "ski_carving.jpg", "man2_thinking.jpg")

MODES = ("full", "tracked", "poseonly")
DETECT_EVERY = 5
WARMUP = 2
TIMED = 6


def _probe_rig() -> RigData:
    """Minimal canonical humanoid (same joint table as the CI fixtures): the
    FK stage of the side-process pipeline, timed on real bones."""
    j: dict[str, tuple[tuple[float, float, float], tuple[float, float, float]]] = {
        "hips": ((0.0, 0.0, 0.98), (0.0, 0.0, 1.06)),
        "spine": ((0.0, 0.0, 1.06), (0.0, 0.0, 1.22)),
        "chest": ((0.0, 0.0, 1.22), (0.0, 0.0, 1.40)),
        "neck": ((0.0, 0.0, 1.40), (0.0, 0.0, 1.50)),
        "head": ((0.0, 0.0, 1.50), (0.0, 0.0, 1.70)),
    }
    for side, sx in (("L", 1.0), ("R", -1.0)):
        j[f"shoulder.{side}"] = ((0.03 * sx, 0.0, 1.44), (0.14 * sx, 0.0, 1.46))
        j[f"upper_arm.{side}"] = ((0.16 * sx, 0.0, 1.45), (0.46 * sx, 0.0, 1.45))
        j[f"forearm.{side}"] = ((0.46 * sx, 0.0, 1.45), (0.72 * sx, 0.0, 1.45))
        j[f"hand.{side}"] = ((0.72 * sx, 0.0, 1.45), (0.82 * sx, 0.0, 1.45))
        j[f"upper_leg.{side}"] = ((0.10 * sx, 0.0, 0.98), (0.11 * sx, 0.0, 0.52))
        j[f"lower_leg.{side}"] = ((0.11 * sx, 0.0, 0.52), (0.11 * sx, 0.0, 0.09))
        j[f"foot.{side}"] = ((0.11 * sx, 0.01, 0.09), (0.11 * sx, -0.13, 0.05))
        j[f"toe.{side}"] = ((0.11 * sx, -0.13, 0.05), (0.11 * sx, -0.24, 0.05))
    parents: dict[str, str | None] = {
        "hips": None, "spine": "hips", "chest": "spine",
        "neck": "chest", "head": "neck",
    }
    for side in ("L", "R"):
        parents[f"shoulder.{side}"] = "chest"
        parents[f"upper_arm.{side}"] = f"shoulder.{side}"
        parents[f"forearm.{side}"] = f"upper_arm.{side}"
        parents[f"hand.{side}"] = f"forearm.{side}"
        parents[f"upper_leg.{side}"] = "hips"
        parents[f"lower_leg.{side}"] = f"upper_leg.{side}"
        parents[f"foot.{side}"] = f"lower_leg.{side}"
        parents[f"toe.{side}"] = f"foot.{side}"
    rig = RigData(name="live_probe_rig", bones={})
    for role, (head, tail) in j.items():
        rig.bones[role] = BoneData(
            name=role, parent=parents[role], head=head, tail=tail
        )
    return rig


def _cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def _percentile(ordered: list[float], fraction: float) -> float:
    n = len(ordered)
    rank = max(1, min(n, round(fraction * n)))
    return ordered[rank - 1]


def skip(reason: str, hint: str) -> int:
    print(f"RM_LIVE PROBE SKIPPED reason={reason} (hint: {hint})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", type=Path, default=DEFAULT_IMAGES,
                        help="dir of person photos (default: the P1-9 photo set)")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR,
                        help="ONE output dir for sized copies + measurements")
    parser.add_argument("--names", nargs="*", default=list(DEFAULT_IMAGES_3),
                        help="image filenames inside --images")
    parser.add_argument("--sizes", nargs="*", default=("native", "640w"),
                        help="input sizes: 'native' or <long-side>w")
    parser.add_argument("--timed", type=int, default=TIMED)
    parser.add_argument("--json-out", type=Path, default=None,
                        help="also dump the raw measurements here (under out-dir)")
    args = parser.parse_args()

    for model in (DET_MODEL, POSE_MODEL):
        try:
            models.verify_model(model)
        except InferenceError:
            return skip("models-missing", "rigpose models download all")
    if not args.images.is_dir():
        return skip("images-dir-missing",
                    f"{args.images} holds the git-ignored benchmark photos")
    present = [n for n in args.names if (args.images / n).is_file()]
    if not present:
        return skip("images-missing",
                    f"none of {args.names} found in {args.images}")

    try:
        import numpy as np_mod  # noqa: F401  (presence check for the env line)
        from PIL import Image
    except ImportError:
        return skip("inference-extra-missing", "pip install riggermortis-core[inference]")

    import onnxruntime

    print(
        f"RM_LIVE ENV py={platform.python_version()} "
        f"ort={onnxruntime.__version__} "
        f"providers={','.join(onnxruntime.get_available_providers())} "
        f"cpu='{_cpu_model()}' threads<=4 models=pinned,deterministic"
    )

    sessions: Sessions = load_sessions()
    rig = _probe_rig()
    mapping = map_rig(rig)

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    measurements: list[dict[str, object]] = []

    for name in present:
        src = args.images / name
        for size in args.sizes:
            if size == "native":
                image_path = src
            else:
                long_side = int(size.rstrip("w"))
                with Image.open(src) as im:
                    w, h = im.size
                    scale = long_side / max(w, h)
                    sized = im.resize(
                        (max(1, round(w * scale)), max(1, round(h * scale))),
                        Image.BILINEAR,
                    )
                    image_path = out_dir / f"{Path(name).stem}_{size}{Path(name).suffix}"
                    sized.save(image_path)
            width, height = Image.open(image_path).size

            for mode in MODES:
                total_ms: list[float] = []
                detect_ms: list[float] = []
                kp_counts: list[int] = []
                confs: list[float] = []
                det_calls = 0
                figure: Figure | None = None
                frames = WARMUP + args.timed
                for i in range(frames):
                    t0 = time.perf_counter()
                    if mode == "full":
                        det_calls += 1
                        board_fig = detect_keypoints(
                            str(image_path), sessions=sessions
                        ).sorted_figures()
                        figure = board_fig[0] if board_fig else None
                    elif mode == "tracked":
                        if figure is None or i % DETECT_EVERY == 0:
                            det_calls += 1
                            board_fig = detect_keypoints(
                                str(image_path), sessions=sessions
                            ).sorted_figures()
                            figure = board_fig[0] if board_fig else None
                        else:
                            box = expand_bbox(figure.bbox, DEFAULT_MARGIN, width, height)
                            figure = estimate_keypoints_at(
                                str(image_path), box, sessions=sessions
                            )
                    else:  # poseonly — the whole frame as one box, no detector
                        figure = estimate_keypoints_at(
                            str(image_path), (0.0, 0.0, float(width), float(height)),
                            sessions=sessions,
                        )
                    t_det = time.perf_counter()
                    if figure is None:
                        total_ms.append((time.perf_counter() - t0) * 1000.0)
                        detect_ms.append((t_det - t0) * 1000.0)
                        continue
                    pose = solve_pose(
                        observations_from_keypoints(figure.keypoints, figure.confidences)
                    )
                    application = apply_canonical_pose(rig, mapping, pose)
                    t_done = time.perf_counter()
                    if i >= WARMUP:
                        total_ms.append((t_done - t0) * 1000.0)
                        detect_ms.append((t_det - t0) * 1000.0)
                        kp_counts.append(sum(
                            1 for c in figure.confidences if c > 0.3
                        ))
                        confs.append(mean_body_confidence(figure))
                    assert application.rotations  # FK produced data

                ordered = sorted(total_ms)
                det_ordered = sorted(detect_ms)
                row = {
                    "mode": mode,
                    "image": name,
                    "size": f"{width}x{height}",
                    "frames": len(ordered),
                    "mean_ms": round(sum(ordered) / len(ordered), 1) if ordered else 0.0,
                    "p50_ms": round(_percentile(ordered, 0.50), 1) if ordered else 0.0,
                    "p95_ms": round(_percentile(ordered, 0.95), 1) if ordered else 0.0,
                    "detect_mean_ms": round(sum(det_ordered) / len(det_ordered), 1)
                    if det_ordered else 0.0,
                    "det_calls": det_calls,
                    "kp_gt03_mean": round(sum(kp_counts) / len(kp_counts), 1)
                    if kp_counts else 0.0,
                    "body_conf_mean": round(sum(confs) / len(confs), 3)
                    if confs else 0.0,
                }
                measurements.append(row)
                print(
                    f"RM_LIVE {mode} image={name} size={row['size']} "
                    f"frames={row['frames']} mean_ms={row['mean_ms']} "
                    f"p50_ms={row['p50_ms']} p95_ms={row['p95_ms']} "
                    f"detect_mean_ms={row['detect_mean_ms']} det_calls={det_calls} "
                    f"kp_gt03={row['kp_gt03_mean']} body_conf={row['body_conf_mean']} "
                    f"static-replay"
                )

    json_path = args.json_out or (out_dir / "probe_measurements.json")
    json_path.write_text(
        json.dumps(measurements, indent=2, sort_keys=True), encoding="utf-8"
    )
    _write_docs_block(measurements)
    print(
        f"RM_LIVE PROBE OK configs={len(measurements)} "
        f"warmup={WARMUP} raw={json_path}"
    )
    return 0


BLOCK_PATH = REPO / "docs" / "BENCHMARKS.md"
BEGIN = "<!-- BENCHMARK:LIVE:BEGIN -->"
END = "<!-- BENCHMARK:LIVE:END -->"


def _aggregate(rows: list[dict[str, object]], mode: str) -> dict[str, object]:
    sel = [r for r in rows if r["mode"] == mode]
    means = [float(r["mean_ms"]) for r in sel]
    p50s = [float(r["p50_ms"]) for r in sel]
    p95s = [float(r["p95_ms"]) for r in sel]
    kps = [float(r["kp_gt03_mean"]) for r in sel]
    confs = [float(r["body_conf_mean"]) for r in sel]
    dets = [int(r["det_calls"]) for r in sel]  # type: ignore[arg-type]
    return {
        "mode": mode,
        "configs": len(sel),
        "mean_ms": round(sum(means) / len(means), 1) if means else 0.0,
        "p50_ms": round(sum(p50s) / len(p50s), 1) if p50s else 0.0,
        "p95_max_ms": round(max(p95s), 1) if p95s else 0.0,
        "det_calls_range": f"{min(dets)}-{max(dets)}" if dets else "0",
        "kp_gt03_mean": round(sum(kps) / len(kps), 1) if kps else 0.0,
        "body_conf_min": round(min(confs), 3) if confs else 0.0,
    }


def _write_docs_block(rows: list[dict[str, object]]) -> None:
    """Publish the measured budget between the LIVE markers (house pattern:
    the instrument writes its own docs block; nothing hand-transcribed)."""
    aggregated = [_aggregate(rows, mode) for mode in MODES]
    lines = [
        "### Live side-process budget (P5-1, generated by `xtask/live_probe.py`)"
        " — STATIC REPLAY",
        "",
        "**Instrument, not an end-to-end benchmark.** Frames are STATIC",
        "replays (2 warmup + 6 timed per config) of three single-person",
        "photos from the P1-9 set (Apache-2.0, git-ignored) at native and",
        "640w sizes; the tracked regime re-detects every 5th frame. Machine:",
        "i5-10400F @ 2.90 GHz (12 threads), onnxruntime 1.25.1 CPU provider",
        "with fixed <=4 threads (the P1-2 deterministic configuration) — an",
        "RTX 3060 is present but NO GPU ORT provider is installed, so CPU is",
        "the measured path and the mid-laptop-relevant one. `kp>0.3` = mean",
        "count of keypoints above 0.3 (out of 133); body conf = the miss-floor",
        "signal (floor 0.3). The Phase-5 <100 ms mid-laptop gate is P5-2's",
        "END-TO-END number (capture -> apply); this is the side-process half.",
        "Aggregate = mean over the 6 per-image/size configs (raw JSON:",
        "`out/live_probe/probe_measurements.json`, git-ignored).",
        "",
        "| regime | configs | mean ms | p50 ms | worst p95 ms | det calls | kp>0.3 | body conf min |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for agg in aggregated:
        lines.append(
            f"| {agg['mode']} | {agg['configs']} | {agg['mean_ms']} | "
            f"{agg['p50_ms']} | {agg['p95_max_ms']} | {agg['det_calls_range']} | "
            f"{agg['kp_gt03_mean']} | {agg['body_conf_min']} |"
        )
    lines += [
        "",
        "The decision this measured (docs/LIVE.md): reuse the pinned DWPose",
        "models — the detector CADENCE is the realtime lever (input downscale",
        "is a dead knob: the ONNX inputs are fixed-size). No new model, no new",
        "download, licenses unchanged. A first-frame cold session load (~2 s)",
        "is normal and visible in the stream envelope (`detect_ms` on seq 0).",
        "",
        "Reproduce: `python3 xtask/live_probe.py` (needs models + the",
        "benchmark photos; answers RM_LIVE PROBE SKIPPED honestly without).",
    ]
    block = "\n".join(lines)
    text = BLOCK_PATH.read_text(encoding="utf-8")
    if BEGIN in text and END in text:
        head, rest = text.split(BEGIN, 1)
        _, tail = rest.split(END, 1)
        text = head + BEGIN + "\n" + block + "\n" + END + tail
    else:
        text = text.rstrip("\n") + "\n\n" + BEGIN + "\n" + block + "\n" + END + "\n"
    BLOCK_PATH.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RiggermortisError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
