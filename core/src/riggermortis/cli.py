"""``rigpose`` command-line interface.

Subcommands:
    inspect <rig.json>      bone inventory + skeleton stats
    map <rig.json>          propose role mapping, print report (--set applies
                            manual reassignments, review-UI equivalent)
    preset save|load|set-secondary  persist / apply reviewed mappings
                    (+ P6-1a chain bindings)
    policy status           content-policy status (adult module off by default)
    detect <image>          DWPose person detection + 133 keypoints
    pose <image> <rig>      one-command posing: detect -> figure select ->
                            solve -> FK; writes the pose payload JSON that
                            the add-on / MCP / headless consumers apply
                            (D-009: frontends consume payloads, they never
                            spawn processes)

Errors print ``error: message (hint: ...)`` and exit 2 — never tracebacks.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from . import payload as payload_mod
from .canonical_pose import observations_from_keypoints, solve_pose
from .errors import MappingError, RiggermortisError
from .face import solve_face
from .fingers import solve_hands
from .fk_apply import apply_canonical_pose
from .inference.figures import FigureBoard
from .io import load_rig
from .mapper import map_rig, propose_reassignment
from .policy import PolicyEngine
from .presets import (
    PRESET_FORMAT,
    Preset,
    apply_preset,
    load_preset,
    load_secondary_bindings,
    preset_from_mapping,
    save_preset,
)

EXIT_OK = 0
EXIT_HANDLED_ERROR = 2
EXIT_UNMET = 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rigpose",
        description="riggermortis core: rig-agnostic posing engine (local, no cloud)",
    )
    parser.add_argument("--version", action="version", version=f"rigpose {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_inspect = sub.add_parser("inspect", help="bone inventory + skeleton stats")
    p_inspect.add_argument("rig", help="rig JSON file")
    p_inspect.add_argument("--json", action="store_true", help="machine-readable output")

    p_map = sub.add_parser("map", help="propose a canonical role mapping")
    p_map.add_argument("rig", help="rig JSON file")
    p_map.add_argument("--json", action="store_true", help="machine-readable output")
    p_map.add_argument(
        "--strict", action="store_true",
        help="exit 1 if any core role could not be mapped confidently",
    )
    p_map.add_argument("--preset", help="apply a saved preset on top", default=None)
    p_map.add_argument(
        "--set", metavar="ROLE=BONE[,ROLE=BONE...]",
        help="apply manual reassignments after mapping (review UI equivalent)",
        default=None,
    )
    p_map.add_argument(
        "--save-preset", metavar="PATH",
        help="save the resulting mapping as a per-rig preset",
    )

    p_save = sub.add_parser("preset", help="preset operations")
    preset_sub = p_save.add_subparsers(dest="preset_command", required=True)
    p_ps = preset_sub.add_parser("save", help="map a rig and save the mapping as a preset")
    p_ps.add_argument("rig", help="rig JSON file")
    p_ps.add_argument("out", help="preset output path (.rigpreset.json)")
    p_ps.add_argument(
        "--secondary", metavar="BINDINGS_JSON", default=None,
        help="attach chain bindings (P6-1a) from a bindings file: "
        '{"format": 1, "secondary": [{"chain": {...}, "bones": [...]}]}',
    )
    p_pl = preset_sub.add_parser("load", help="load a preset and re-apply it to its rig")
    p_pl.add_argument("rig", help="rig JSON file")
    p_pl.add_argument("preset", help="preset path")
    p_pl.add_argument("--force", action="store_true", help="apply even if the rig fingerprint changed")
    p_pss = preset_sub.add_parser(
        "set-secondary",
        help="attach/replace chain bindings (P6-1a) on an existing preset "
        "without re-mapping",
    )
    p_pss.add_argument("preset", help="preset path (updated in place)")
    p_pss.add_argument("bindings", help="bindings file: {\"format\": 1, \"secondary\": [...]}")

    p_policy = sub.add_parser("policy", help="content policy operations")
    policy_sub = p_policy.add_subparsers(dest="policy_command", required=True)
    policy_sub.add_parser("status", help="show policy status (adult module off by default)")

    p_models = sub.add_parser(
        "models", help="managed ONNX models (downloaded only on explicit command)"
    )
    models_sub = p_models.add_subparsers(dest="models_command", required=True)
    m_list = models_sub.add_parser("list", help="list managed models and local status")
    m_list.add_argument("--json", action="store_true", help="machine-readable output")
    m_dl = models_sub.add_parser(
        "download", help="download a model and verify its pinned checksum"
    )
    m_dl.add_argument("name", help="model name from the manifest, or 'all'")
    m_ver = models_sub.add_parser("verify", help="verify stored model checksums")
    m_ver.add_argument("name", nargs="?", default="all", help="model name, or 'all' (default)")
    m_path = models_sub.add_parser("path", help="print the model storage location")
    m_path.add_argument("name", nargs="?", default=None, help="model name (default: the store dir)")

    p_detect = sub.add_parser(
        "detect", help="DWPose person detection + 133 keypoints (models must be downloaded)"
    )
    p_detect.add_argument("image", help="path to an image file")
    p_detect.add_argument("--json", action="store_true", help="machine-readable output")
    p_detect.add_argument(
        "--figure", type=int, default=None, metavar="N",
        help="only report figure N (deterministic order: score desc, then leftmost)",
    )
    p_detect.add_argument(
        "--gpu", action="store_true",
        help="opt in to the CUDA onnxruntime provider (CPU is the default)",
    )

    p_pose = sub.add_parser(
        "pose",
        help="one-command posing: detect -> solve -> FK -> pose payload JSON "
             "(the add-on / MCP consume this payload; D-009)",
    )
    p_pose.add_argument("image", help="path to a reference image (photo or anime art)")
    p_pose.add_argument("rig", help="rig JSON file to apply the pose to")
    p_pose.add_argument("--preset", default=None, help="apply a saved mapping preset on top")
    p_pose.add_argument(
        "--figure", default="largest",
        help="figure selector: board index (0-based), 'largest' (default), or 'primary'",
    )
    p_pose.add_argument(
        "--all-figures", action="store_true",
        help="embed every detected figure's solved pose in the payload so the "
             "add-on's dropdown switches figures without re-running the CLI",
    )
    p_pose.add_argument(
        "--out", metavar="PATH", default=None,
        help="write the pose payload JSON here (use with the add-on's Apply Pose)",
    )
    p_pose.add_argument("--json", action="store_true", help="print the payload to stdout instead")
    p_pose.add_argument(
        "--gpu", action="store_true",
        help="opt in to the CUDA onnxruntime provider (CPU is the default)",
    )

    p_pdf = sub.add_parser(
        "export-pdf",
        help="assemble page PNGs (the P4-4/P4-5 page renders) into a "
             "deterministic PDF (pure-stdlib writer, P4-6)",
    )
    p_pdf.add_argument("pages", nargs="+", metavar="PAGE_PNG",
                       help="page PNG files, in reading order")
    p_pdf.add_argument("--out", required=True, metavar="PATH",
                       help="output PDF path")
    p_pdf.add_argument("--title", default=None, metavar="TEXT",
                       help="optional document title (PDF /Title)")

    p_epub = sub.add_parser(
        "export-epub",
        help="package page PNGs (the P4-4/P4-5 page renders) into a "
             "deterministic EPUB 3 (pure-stdlib writer, P4-6)",
    )
    p_epub.add_argument("pages", nargs="+", metavar="PAGE_PNG",
                        help="page PNG files, in reading order")
    p_epub.add_argument("--out", required=True, metavar="PATH",
                        help="output EPUB path")
    p_epub.add_argument("--title", default="riggermortis pages", metavar="TEXT",
                        help="document title (default: 'riggermortis pages')")

    p_video = sub.add_parser(
        "pose-video",
        help="per-frame posing over an extracted-frames dir: detect -> solve -> "
             "FK -> one payload per frame + resumable job.json (P2-1; decode "
             "lives in xtask/extract_frames.sh per D-009)",
    )
    p_video.add_argument("frames_dir", help="directory of extracted still frames")
    p_video.add_argument("rig", help="rig JSON file to apply poses to")
    p_video.add_argument("--out", required=True, metavar="JOB_DIR",
                         help="job directory (payloads/ + job.json)")
    p_video.add_argument("--stride", type=int, default=1, metavar="N",
                         help="solve every Nth frame (default 1 = all)")
    p_video.add_argument("--max-frames", type=int, default=None, metavar="N",
                         help="cap the plan length (smoke tests)")
    p_video.add_argument("--fresh", action="store_true",
                         help="ignore any existing job.json and restart the plan")
    p_video.add_argument(
        "--gpu", action="store_true",
        help="opt in to the CUDA onnxruntime provider (CPU is the default)",
    )

    p_live = sub.add_parser(
        "live",
        help="P5-1 live side-process: watch a frames dir, emit one D-009 "
             "payload-v2 JSON line per frame (spawn this from a shell or "
             "xtask/live_capture.sh — never from a .py, per D-009)",
    )
    p_live.add_argument("frames_dir",
                        help="directory of frame PNGs (shell-glue writer: "
                             "xtask/extract_frames.sh or xtask/live_capture.sh)")
    p_live.add_argument("rig", help="rig JSON file to apply poses to")
    p_live.add_argument("--out", default="live.jsonl", metavar="PATH",
                        help="stream file, one JSON line per frame "
                             "(default: live.jsonl)")
    p_live.add_argument("--detect-every", type=int, default=1, metavar="N",
                        help="detector every Nth frame; 1 = full regime, >1 = "
                             "tracked regime with pose-only crops between "
                             "(default 1)")
    p_live.add_argument("--margin", type=float, default=None, metavar="F",
                        help="tracked-regime crop expansion as a fraction of "
                             "the box per side (default 0.15)")
    p_live.add_argument("--conf-floor", type=float, default=None, metavar="F",
                        help="mean body confidence under this marks the frame "
                             "a miss (default 0.3)")
    p_live.add_argument("--max-frames", type=int, default=None, metavar="N",
                        help="stop after N frames (probes/tests)")
    p_live.add_argument("--idle-timeout", type=float, default=None, metavar="S",
                        help="stop after S seconds without a new frame "
                             "(default 10; 0 = wait forever)")
    p_live.add_argument(
        "--gpu", action="store_true",
        help="opt in to the CUDA onnxruntime provider (CPU is the default)",
    )

    return parser


def cmd_inspect(args: argparse.Namespace) -> int:
    rig = load_rig(args.rig)
    payload: dict[str, object] = {
        "name": rig.name,
        "source": rig.source,
        "bone_count": len(rig.bones),
        "height_m": round(rig.height(), 3),
        "fingerprint": rig.fingerprint(),
        "roots": rig.roots(),
        "bones": [
            {
                "name": n,
                "parent": rig.bones[n].parent,
                "length": round(_length(rig, n), 4),
                "children": rig.children(n),
            }
            for n in rig.sorted_bone_names()
        ],
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"rig: {rig.name} ({rig.source})")
        print(f"bones: {len(rig.bones)}  height: {rig.height():.3f} m  fingerprint: {rig.fingerprint()}")
        for b in payload["bones"]:  # type: ignore[index]
            name = b["name"]  # type: ignore[index]
            parent = b["parent"] or "-"  # type: ignore[index]
            print(f"  {name:<24} parent={parent:<24} len={b['length']:.3f}")  # type: ignore[index]
    return EXIT_OK


def _length(rig, name: str) -> float:
    from .linalg import v_dist

    b = rig.bones[name]
    return v_dist(b.head, b.tail)


def _parse_set(spec: str) -> list[tuple[str, str]]:
    """Parse ``role=bone[,role=bone...]`` into ordered pairs."""
    pairs: list[tuple[str, str]] = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "=" not in chunk:
            raise MappingError(
                f"invalid --set item {chunk!r}",
                hint="expected role=bone pairs, e.g. --set hips=pelvis,spine=spine.001",
            )
        role, bone = (part.strip() for part in chunk.split("=", 1))
        if not role or not bone:
            raise MappingError(
                f"invalid --set item {chunk!r}",
                hint="both the role and the bone are required: role=bone",
            )
        pairs.append((role, bone))
    if not pairs:
        raise MappingError(
            "empty --set value",
            hint="expected role=bone pairs, e.g. --set hips=pelvis",
        )
    return pairs


def cmd_map(args: argparse.Namespace) -> int:
    rig = load_rig(args.rig)
    preset_mapping = None
    if args.preset:
        preset_mapping = load_preset(args.preset).mapping
    mapping = map_rig(rig, preset_mapping=preset_mapping)
    if args.set:
        for role, bone in _parse_set(args.set):
            mapping = propose_reassignment(mapping, role, bone)
    if args.save_preset:
        save_preset(preset_from_mapping(rig, mapping), args.save_preset)
    if args.json:
        print(json.dumps(mapping.to_dict(), indent=2, sort_keys=True))
    else:
        print(mapping.table())
        print()
        print(mapping.summary())
        if args.save_preset:
            print(f"preset saved: {args.save_preset}")
    if args.strict and mapping.core_missing():
        return EXIT_UNMET
    return EXIT_OK


def cmd_preset_save(args: argparse.Namespace) -> int:
    rig = load_rig(args.rig)
    mapping = map_rig(rig)
    secondary = load_secondary_bindings(args.secondary) if args.secondary else None
    path = save_preset(preset_from_mapping(rig, mapping, secondary=secondary), args.out)
    print(f"preset saved: {path}")
    _print_chains(preset_from_mapping(rig, mapping, secondary=secondary))
    return EXIT_OK


def cmd_preset_set_secondary(args: argparse.Namespace) -> int:
    preset = load_preset(args.preset)
    preset.secondary = load_secondary_bindings(args.bindings)
    preset.format = PRESET_FORMAT
    save_preset(preset, args.preset)
    print(f"preset updated: {args.preset}")
    _print_chains(preset)
    return EXIT_OK


def _print_chains(preset: Preset) -> None:
    """The preset's chain payload, visible — never hidden (P6-1a)."""
    if not preset.secondary:
        print("secondary chains: none")
        return
    for b in preset.secondary:
        print(
            f"secondary chain {b.chain.name}: {b.chain.links} link(s) off "
            f"{b.chain.anchor_role} -> bones: {', '.join(b.bones)}"
        )


def cmd_preset_load(args: argparse.Namespace) -> int:
    rig = load_rig(args.rig)
    preset = load_preset(args.preset)
    mapping = apply_preset(rig, preset, force=args.force)
    print(mapping.table())
    print()
    print(mapping.summary())
    _print_chains(preset)
    return EXIT_OK


def cmd_policy_status(_args: argparse.Namespace) -> int:
    engine = PolicyEngine()
    print(json.dumps(engine.status(), indent=2, sort_keys=True))
    return EXIT_OK


def _models_target(name: str) -> list[str]:
    from .inference.models import model_names

    if name == "all":
        return model_names()
    return [name]


def cmd_models_list(args: argparse.Namespace) -> int:
    from .inference.models import list_models

    rows = list_models()
    if args.json:
        print(json.dumps(rows, indent=2, sort_keys=True))
        return EXIT_OK
    print("managed models (downloaded only via `rigpose models download`):")
    for row in rows:
        state = "downloaded" if row["downloaded"] else "not downloaded"
        size_mb = int(row["bytes"]) / (1024 * 1024)
        print(f"  {row['name']:<24} {row['role']:<9} {size_mb:7.1f} MB  {state}")
        print(f"    license: {row['license']}")
    return EXIT_OK


def cmd_models_download(args: argparse.Namespace) -> int:
    from .inference.models import download_model

    for name in _models_target(args.name):
        path = download_model(name)
        print(f"downloaded {name} -> {path} (checksum verified)")
    return EXIT_OK


def cmd_models_verify(args: argparse.Namespace) -> int:
    from .inference.models import verify_model

    for name in _models_target(args.name):
        report = verify_model(name)
        print(f"{name}: OK ({report['path']})")
    return EXIT_OK


def cmd_models_path(args: argparse.Namespace) -> int:
    from .inference.models import default_root, model_path

    if args.name:
        print(model_path(args.name))
    else:
        print(default_root())
    return EXIT_OK


def cmd_detect(args: argparse.Namespace) -> int:
    # Lazy import: importing the CLI must never require numpy/onnxruntime.
    from .inference.dwpose import detect_keypoints

    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"] if args.gpu else None
    detection = detect_keypoints(args.image, providers=providers)
    figures = detection.sorted_figures()
    if args.figure is not None:
        if args.figure < 0 or args.figure >= len(figures):
            print(
                f"error: figure {args.figure} does not exist "
                f"(hint: {len(figures)} figure(s) detected)",
                file=sys.stderr,
            )
            return EXIT_HANDLED_ERROR
        figures = [figures[args.figure]]
    if args.json:
        payload = {"width": detection.width, "height": detection.height,
                   "figures": [f.to_dict() for f in figures]}
        print(json.dumps(payload, indent=2, sort_keys=True))
        return EXIT_OK
    print(f"image: {args.image} ({detection.width}x{detection.height})")
    print(f"figures: {len(figures)}")
    for f in figures:
        mean_conf = sum(f.confidences) / len(f.confidences)
        print(
            f"  figure {f.index}: score={f.score:.2f} "
            f"bbox=({f.bbox[0]:.0f},{f.bbox[1]:.0f},{f.bbox[2]:.0f},{f.bbox[3]:.0f}) "
            f"mean_conf={mean_conf:.2f}"
        )
    return EXIT_OK


def _select_figure(board: FigureBoard, selector: str):
    """Resolve a --figure selector ('largest' | 'primary' | board index)."""
    if selector == "largest":
        figure = board.largest()
    elif selector == "primary":
        figure = board.primary()
    else:
        try:
            index = int(selector)
        except ValueError:
            raise RiggermortisError(
                f"unknown figure selector {selector!r}",
                hint="use a board index (0-based), 'largest', or 'primary'",
            ) from None
        figure = board.select(index)
    if figure is None:
        raise RiggermortisError(
            f"figure {selector} does not exist",
            hint=f"{len(board.figures)} figure(s) detected; "
                 "use --figure largest (default), primary, or an index in "
                 f"0..{max(len(board.figures) - 1, 0)}",
        )
    return figure


def _select_figure(board: FigureBoard, selector: str):
    """Resolve a --figure selector ('largest' | 'primary' | board index)."""
    if selector == "largest":
        figure = board.largest()
    elif selector == "primary":
        figure = board.primary()
    else:
        try:
            index = int(selector)
        except ValueError:
            raise RiggermortisError(
                f"unknown figure selector {selector!r}",
                hint="use a board index (0-based), 'largest', or 'primary'",
            ) from None
        figure = board.select(index)
    if figure is None:
        raise RiggermortisError(
            f"figure {selector} does not exist",
            hint=f"{len(board.figures)} figure(s) detected; "
                 "use --figure largest (default), primary, or an index in "
                 f"0..{max(len(board.figures) - 1, 0)}",
        )
    return figure


def _figure_entry(
    figure, pose, rotations: list[dict[str, object]], skipped: list[str], notes: list[str]
) -> dict[str, object]:
    """One per-figure entry for the payload v2 ``figures`` list."""
    return {
        "figure": {
            "label": figure.label,
            "index": figure.index,
            "score": round(figure.score, 4),
            "bbox": [round(v, 2) for v in figure.bbox],
        },
        "pose": pose.to_dict(),
        "rotations": rotations,
        "skipped": skipped,
        "notes": notes,
    }


def _solve_and_apply_figure(figure, rig, mapping, finger_map=None, face_bones=None):
    """One figure's keypoints -> (pose, application); P8-3 attaches the
    solved finger chains and P8-4 the solved expression params (both gated:
    they appear only when their keypoints clear the confidence floor — an
    absent hand/face reads as clean); preset bindings ride when authored."""
    observations = observations_from_keypoints(figure.keypoints, figure.confidences)
    pose = solve_pose(observations)
    pose.hands = solve_hands(figure.keypoints, figure.confidences, pose)
    pose.face = solve_face(figure.keypoints, figure.confidences)
    application = apply_canonical_pose(
        rig, mapping, pose, finger_map=finger_map, face_bones=face_bones
    )
    return pose, application


def cmd_pose(args: argparse.Namespace) -> int:
    image = Path(args.image)
    if not image.exists():
        raise RiggermortisError(
            f"image not found: {image}",
            hint="pass a path to a reference photo or anime art file",
        )
    # Lazy import: importing the CLI must never require numpy/onnxruntime.
    from .inference.dwpose import detect_keypoints

    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"] if args.gpu else None
    detection = detect_keypoints(str(image), providers=providers)
    board = FigureBoard.from_detection(detection)
    if not board.figures:
        raise RiggermortisError(
            "no person detected in the image",
            hint="try a clearer reference; DWPose is trained on photoreal "
                 "poses, anime/sketch accuracy is a known gap "
                 "(docs/BENCHMARKS.md tracks the number)",
        )
    figure = _select_figure(board, args.figure)

    rig = load_rig(args.rig)
    preset = load_preset(args.preset) if args.preset else None
    mapping = map_rig(rig, preset_mapping=preset.mapping if preset else None)
    finger_map = dict(preset.hands) if preset and preset.hands else None
    face_map = dict(preset.face_bones) if preset and preset.face_bones else None

    selected_pose, selected_application = _solve_and_apply_figure(
        figure, rig, mapping, finger_map=finger_map, face_bones=face_map
    )
    entries = [_figure_entry(
        figure,
        selected_pose,
        [r.to_dict() for r in selected_application.rotations],
        list(selected_application.skipped),
        list(selected_application.notes),
    )]

    if args.all_figures and len(board.figures) > 1:
        for other in board.figures:
            if other.label == figure.label:
                continue
            pose, application = _solve_and_apply_figure(
                other, rig, mapping, finger_map=finger_map, face_bones=face_map
            )
            entries.append(_figure_entry(
                other,
                pose,
                [r.to_dict() for r in application.rotations],
                list(application.skipped),
                list(application.notes),
            ))
        entries.sort(key=lambda e: e["figure"]["index"])  # board order, deterministic

    payload = payload_mod.build_pose_payload(
        image,
        detection.width,
        detection.height,
        rig,
        entries,
        selected_label=figure.label,
    )

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return EXIT_OK
    if not args.out:
        raise RiggermortisError(
            "no output destination for the pose payload",
            hint="pass --out payload.json (consumed by the add-on's Apply "
                 "Pose) or --json to print it",
        )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    state = "reliable" if selected_pose.reliable else "BELOW the reliable bar — review before use"
    print(f"image: {image} ({detection.width}x{detection.height})")
    print(f"figure: {figure.label} (score {figure.score:.2f})")
    print(f"pose: confidence {selected_pose.confidence:.2f}, {state}")
    for note in selected_pose.notes:
        print(f"  note: {note}")
    print(
        f"rotations: {len(selected_application.rotations)} bone(s), "
        f"{len(selected_application.skipped)} skipped, "
        f"{len(selected_application.notes)} note(s)"
    )
    if len(entries) > 1:
        print(f"figures embedded: {len(entries)} — the panel dropdown switches "
              "them without re-running the CLI")
    print(f"payload written: {out}")
    print(f"apply it in Blender: Riggermortis panel -> Apply Pose (payload: {out.name})")
    return EXIT_OK


def cmd_pose_video(args: argparse.Namespace) -> int:
    """P2-1: per-frame posing over extracted frames, resumable (D-009-safe)."""
    from .video import run_video_job

    frames_dir = Path(args.frames_dir)
    if not frames_dir.is_dir():
        raise RiggermortisError(
            f"frames directory not found: {frames_dir}",
            hint="extract frames first: bash xtask/extract_frames.sh <video> <dir>",
        )
    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"] if args.gpu else None

    def detect_fn(path: str, _providers=providers):
        from .inference.dwpose import detect_keypoints  # noqa: PLC0415

        return detect_keypoints(path, providers=_providers)

    report = run_video_job(
        frames_dir,
        Path(args.rig),
        Path(args.out),
        stride=args.stride,
        max_frames=args.max_frames,
        resume=not args.fresh,
        detect_fn=detect_fn,
        progress=lambda done, total: print(f"progress: {done}/{total} frames"),
    )
    print(report.summary())
    return EXIT_OK


def cmd_live(args: argparse.Namespace) -> int:
    """P5-1: the live side-process entry (this process IS the side process)."""
    from . import live

    frames_dir = Path(args.frames_dir)
    if not frames_dir.is_dir():
        raise RiggermortisError(
            f"frames directory not found: {frames_dir}",
            hint="feed it from shell glue: bash xtask/extract_frames.sh "
                 "<video> <dir> (recorded) or bash xtask/live_capture.sh "
                 "<dir> (capture device; untested on this box)",
        )
    source = live.DirectoryFrameSource(
        frames_dir,
        idle_timeout=(None if args.idle_timeout in (None, 0) else args.idle_timeout),
    )
    report = live.run_live(
        source,
        Path(args.rig),
        Path(args.out),
        live.default_detector(gpu=args.gpu),
        detect_every=args.detect_every,
        margin=(live.DEFAULT_MARGIN if args.margin is None else args.margin),
        conf_floor=(live.DEFAULT_CONF_FLOOR if args.conf_floor is None else args.conf_floor),
        max_frames=args.max_frames,
        on_line=lambda line: print(
            f"frame {line['frame']}: {line['kind']}",  # type: ignore[index]
            file=sys.stderr,
        ),
    )
    print(report.summary())
    return EXIT_OK


def cmd_export_pdf(args: argparse.Namespace) -> int:
    from .pagedoc import read_pdf_pages, write_pdf

    write_pdf(args.pages, args.out, title=args.title)
    pages = read_pdf_pages(args.out)
    print(f"wrote {args.out}: {len(pages)} page(s), parse-back verified")
    for i, p in enumerate(pages):
        print(
            f"  page {i + 1}: {p['width_pt']}x{p['height_pt']} pt, "
            f"image {p['image_width']}x{p['image_height']}, "
            f"{p['image_bytes']} bytes decoded"
        )
    return EXIT_OK


def cmd_export_epub(args: argparse.Namespace) -> int:
    from .pagedoc import read_epub_structure, write_epub

    write_epub(args.pages, args.out, title=args.title)
    structure = read_epub_structure(args.out)
    print(f"wrote {args.out}: structure verified")
    print(
        f"  title={structure['title']!r} entries={structure['entries']} "
        f"page_docs={structure['page_documents']} images={structure['images']}"
    )
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            return cmd_inspect(args)
        if args.command == "map":
            return cmd_map(args)
        if args.command == "preset":
            if args.preset_command == "save":
                return cmd_preset_save(args)
            if args.preset_command == "set-secondary":
                return cmd_preset_set_secondary(args)
            return cmd_preset_load(args)
        if args.command == "policy":
            if args.policy_command == "status":
                return cmd_policy_status(args)
        if args.command == "models":
            if args.models_command == "list":
                return cmd_models_list(args)
            if args.models_command == "download":
                return cmd_models_download(args)
            if args.models_command == "verify":
                return cmd_models_verify(args)
            return cmd_models_path(args)
        if args.command == "detect":
            return cmd_detect(args)
        if args.command == "pose":
            return cmd_pose(args)
        if args.command == "pose-video":
            return cmd_pose_video(args)
        if args.command == "live":
            return cmd_live(args)
        if args.command == "export-pdf":
            return cmd_export_pdf(args)
        if args.command == "export-epub":
            return cmd_export_epub(args)
        parser.error(f"unknown command {args.command!r}")
        return EXIT_HANDLED_ERROR
    except RiggermortisError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_HANDLED_ERROR
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
