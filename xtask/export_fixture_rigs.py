#!/usr/bin/env python
"""Write the five synthetic gate rigs as JSON for manual CLI poking.

    python xtask/export_fixture_rigs.py [out-dir]

Default output: out/fixture_rigs/
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "core/tests"))
sys.path.insert(0, str(REPO / "core/src"))

from rigs import all_five


def main() -> int:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "out" / "fixture_rigs"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, rig in sorted(all_five().items()):
        path = rig.to_json(out_dir / f"{name}.rig.json")
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
