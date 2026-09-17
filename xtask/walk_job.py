#!/usr/bin/env python3
"""Contract-valid walk fixture job (P3-7) — the SYNTHETIC walk as a video job.

Serializes the published HIPSTAB walk generator (``xtask/hip_stab_gate.py``
``build_walk`` — the drift + breathing walk behind every published lock
number) into the ``rigpose pose-video`` job layout (``job.json`` + payload
files) so session actions exercise ``core.load_action`` through the REAL
payload contract (D-009). Shared by the session gate (``session_probe.py``)
and the agent demo (``agent_demo_blender.py``). Runs anywhere (no bpy).

The labeling rule holds: this job is SYNTHETIC (generator-cited); the real
walking clip stays NEEDS-HUMAN (out/video_smoke/SOURCES.md) and nothing
downstream may relabel it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

XTASK = Path(__file__).resolve().parent

STATE_NAME = "job.json"
PAYLOADS_DIR = "payloads"
GENERATOR_NOTE = (
    "SYNTHETIC walk fixture: xtask/hip_stab_gate.py build_walk(drift=True, "
    "wobble=0.005) serialized through the payload contract — real-clip "
    "NEEDS-HUMAN (out/video_smoke/SOURCES.md)"
)


def build_walk_job(job_dir: Path) -> dict[str, object]:
    """Write the fixture job; returns a small stats dict (deterministic)."""
    sys.path.insert(0, str(XTASK))
    sys.path.insert(0, str(XTASK.parent / "core" / "src"))
    import hip_stab_gate

    action = hip_stab_gate.build_walk(drift=True, wobble=0.005)
    job_dir = Path(job_dir)
    (job_dir / PAYLOADS_DIR).mkdir(parents=True, exist_ok=True)

    done: dict[str, str] = {}
    for af in action.frames:
        name = f"frame_{af.frame:06d}.json"
        pose = af.pose.to_dict()
        entry = {
            "label": "walk figure 0", "index": 0, "score": 0.9,
            "bbox": [0.0, 0.0, 10.0, 10.0], "pose": pose,
            "rotations": [], "skipped": [], "notes": [],
        }
        payload = {
            "format": 2, "frame": af.frame, "file": name.replace(".json", ".png"),
            "figure": {k: entry[k] for k in ("label", "index", "score", "bbox")},
            "pose": pose, "rotations": [], "skipped": [],
            "notes": [GENERATOR_NOTE], "figures": [entry],
            "rig": {"name": "walk_fixture", "fingerprint": "synthetic-walk"},
        }
        path = job_dir / PAYLOADS_DIR / name
        path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        done[str(af.frame)] = f"{PAYLOADS_DIR}/{name}"

    state = {
        "format": 1,
        "source": "synthetic-walk-fixture",
        "rig": "(fixture — no rig file; poses are canonical)",
        "stride": 1,
        "frames": [f"frame_{i:06d}.png" for i in range(len(action.frames))],
        "done": done,
        "notes": [GENERATOR_NOTE],
        "updated": "1970-01-01T00:00:00Z",  # fixture: content-deterministic
    }
    (job_dir / STATE_NAME).write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
    return {
        "job_dir": str(job_dir),
        "frames": len(action.frames),
        "failed": len(action.failed),
        "generator": GENERATOR_NOTE,
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: walk_job.py JOB_DIR")
    print(json.dumps(build_walk_job(Path(sys.argv[1])), sort_keys=True))
