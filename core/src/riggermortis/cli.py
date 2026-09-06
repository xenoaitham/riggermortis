"""``rigpose`` command-line interface.

Subcommands:
    inspect <rig.json>      bone inventory + skeleton stats
    map <rig.json>          propose role mapping, print report
    preset save|load        persist / apply reviewed mappings
    policy status           content-policy status (adult module off by default)

Errors print ``error: message (hint: ...)`` and exit 2 — never tracebacks.
"""
from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .errors import RiggermortisError
from .io import load_rig
from .mapper import map_rig
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


def cmd_map(args: argparse.Namespace) -> int:
    rig = load_rig(args.rig)
    preset_mapping = None
    if args.preset:
        preset_mapping = load_preset(args.preset).mapping
    mapping = map_rig(rig, preset_mapping=preset_mapping)
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
        parser.error(f"unknown command {args.command!r}")
        return EXIT_HANDLED_ERROR
    except RiggermortisError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_HANDLED_ERROR
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
