"""``rigpose`` command-line interface.

Subcommands:
    inspect <rig.json>      bone inventory + skeleton stats
    map <rig.json>          propose role mapping, print report (--set applies
                            manual reassignments, review-UI equivalent)
    preset save|load        persist / apply reviewed mappings
    policy status           content-policy status (adult module off by default)

Errors print ``error: message (hint: ...)`` and exit 2 — never tracebacks.
"""
from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .errors import MappingError, RiggermortisError
from .io import load_rig
from .mapper import map_rig, propose_reassignment
from .policy import PolicyEngine
from .presets import apply_preset, load_preset, preset_from_mapping, save_preset

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
    p_pl = preset_sub.add_parser("load", help="load a preset and re-apply it to its rig")
    p_pl.add_argument("rig", help="rig JSON file")
    p_pl.add_argument("preset", help="preset path")
    p_pl.add_argument("--force", action="store_true", help="apply even if the rig fingerprint changed")

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
    path = save_preset(preset_from_mapping(rig, mapping), args.out)
    print(f"preset saved: {path}")
    return EXIT_OK


def cmd_preset_load(args: argparse.Namespace) -> int:
    rig = load_rig(args.rig)
    preset = load_preset(args.preset)
    mapping = apply_preset(rig, preset, force=args.force)
    print(mapping.table())
    print()
    print(mapping.summary())
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
        parser.error(f"unknown command {args.command!r}")
        return EXIT_HANDLED_ERROR
    except RiggermortisError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_HANDLED_ERROR
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
