#!/usr/bin/env python
"""P6-2 bridge sampler — THIN CALLER (S25 refactor).

The import/sample loop lives in ``riggermortis_addon/clip_sample.py`` (ONE
copy; the D-016 lockstep lesson — this script used to BE the loop, and the
retarget_clip session action would have needed a second copy). Shell glue
still spawns Blender (D-009):

    blender -b --python xtask/sample_clip.py -- <model> <out.json> \
        [--action NAME] [--rig NAME] [--stride N] [--fps F] [--tag LABEL]

Output contract unchanged: the format-1 clip-sample JSON plus the exact
``RM_MOTION SAMPLE/DETERM/WRITE`` lines the gates grep. Exit 0 = the twin
sample passes agreed byte-for-byte; 1 = DETERM FAIL; 3 = a refused sample
(actionable hint on stderr).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _parse_args(argv):
    if not argv:
        print(
            "usage: sample_clip.py <model> <out.json> "
            "[--action NAME] [--rig NAME] [--stride N] [--fps F] [--tag LABEL]",
            file=sys.stderr,
        )
        raise SystemExit(64)
    model, out = argv[0], argv[1]
    opts = {"action": None, "rig": None, "stride": 1, "fps": None, "tag": None}
    i = 2
    while i < len(argv):
        arg = argv[i]
        if arg in ("--action", "--rig", "--tag") and i + 1 < len(argv):
            opts[arg[2:]] = argv[i + 1]
            i += 2
        elif arg in ("--stride", "--fps") and i + 1 < len(argv):
            opts[arg[2:]] = float(argv[i + 1])
            i += 2
        else:
            print(f"error: unknown argument {arg!r}", file=sys.stderr)
            raise SystemExit(64)
    if opts["stride"] < 1 or opts["stride"] != int(opts["stride"]):
        print("error: --stride must be a positive integer", file=sys.stderr)
        raise SystemExit(64)
    if not out:
        print("error: missing <out.json> argument", file=sys.stderr)
        raise SystemExit(64)
    return model, out, opts


def main():
    model, out, opts = _parse_args(
        sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    )
    core_src = os.environ.get(
        "RM_CORE_SRC",
        str(Path(__file__).resolve().parent.parent / "core" / "src"),
    )
    addon_dir = os.environ.get(
        "RM_ADDON_DIR", str(Path(__file__).resolve().parent.parent / "addon")
    )
    sys.path.insert(0, core_src)
    sys.path.insert(0, addon_dir)
    import riggermortis as core  # noqa: E402
    from riggermortis_addon import bpy_bridge, clip_sample  # noqa: E402

    try:
        report = clip_sample.sample_clip(
            model, out, core, bpy_bridge,
            action=opts["action"], rig=opts["rig"],
            stride=int(opts["stride"]), fps=opts["fps"], tag=opts["tag"],
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    for line in report["lines"]:
        print(line)
    return 0 if report["determ"] else 1


if __name__ == "__main__":
    sys.exit(main())
