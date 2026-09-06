#!/usr/bin/env python
"""Headless demo-media pipeline (placeholder).

RULE 5 of the mission: the repo films itself — every GIF/render in the README
is produced headlessly from scripted demo scenes by this module, and CI
regenerates media on release. The Phase 1 BOOM GIF is the first consumer.

    blender -b -P xtask/render_demos.py -- --demo boom --out media/

Deliberately exits non-zero until Phase 1 lands: no stale, faked, or
hand-made media is allowed to ship.
"""
from __future__ import annotations

import sys

DEMOS: dict[str, str] = {
    # name -> script status; populated in Phase 1+ by the demo scene builders
}


def main(argv: list[str]) -> int:
    requested = "boom"
    if "--demo" in argv:
        requested = argv[argv.index("--demo") + 1]
    print(
        f"render_demos: no scripted demo {requested!r} exists yet.\n"
        "The headless media pipeline lands with Phase 1 (the BOOM GIF); \n"
        "until then no demo media may be generated or shipped.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
