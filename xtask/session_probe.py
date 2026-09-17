"""In-Blender probe for the session gate (run INSIDE Blender, headless).

Builds the gate rig, writes a contract-valid v2 payload for the apply action
and a contract-valid walk fixture job for the bake action (P3-7, via
``xtask/walk_job.py`` — the SYNTHETIC generator through the payload
contract), registers the add-on, connects to the MCP server's loopback
bridge, and pumps the main-thread executor until every enqueued action has a
staged result. The AGENT-side half of the verification (collecting the
structured results via ``action_result`` over the server's stdio) lives in
``xtask/session_verify.sh`` — this probe asserts the ADD-ON half: the client
connects, claims, executes through the real add-on machinery (payload apply
= the D-009 path; bake = the P2-3/P2-5 path under the certified
composition), and reports.

Usage: blender -b --python xtask/session_probe.py -- PORT TOKEN PAYLOAD_OUT JOB_DIR
Exits 0 only if all expected actions were executed and staged.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "addon"))
sys.path.insert(0, str(REPO / "core" / "src"))

EXPECTED_ACTIONS = 5
TIMEOUT_S = 120.0


def build_gate_rig() -> str:
    """The blender_verify gate rig (role-nameable bones), object name returned."""
    import bpy

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.object.armature_add(location=(0, 0, 0))
    obj = bpy.context.object
    obj.name = "RM_SessionRig"
    bpy.ops.object.mode_set(mode="EDIT")
    bones = obj.data.edit_bones
    bones.remove(bones[0])  # drop the default 'Bone' created by armature_add

    def add(name, parent, head, tail):
        b = bones.new(name)
        b.head, b.tail = head, tail
        b.parent = bones[parent] if parent else None

    add("pelvis", None, (0, 0, 0.98), (0, 0, 1.06))
    add("spine", "pelvis", (0, 0, 1.06), (0, 0, 1.22))
    add("spine.001", "spine", (0, 0, 1.22), (0, 0, 1.40))
    add("neck", "spine.001", (0, 0, 1.40), (0, 0, 1.50))
    add("head", "neck", (0, 0, 1.50), (0, 0, 1.70))
    add("shoulder.L", "spine.001", (0.03, 0, 1.44), (0.14, 0, 1.46))
    add("upper_arm.L", "shoulder.L", (0.16, 0, 1.45), (0.46, 0, 1.45))
    add("forearm.L", "upper_arm.L", (0.46, 0, 1.45), (0.72, 0, 1.45))
    add("hand.L", "forearm.L", (0.72, 0, 1.45), (0.82, 0, 1.45))
    add("shoulder.R", "spine.001", (-0.03, 0, 1.44), (-0.14, 0, 1.46))
    add("upper_arm.R", "shoulder.R", (-0.16, 0, 1.45), (-0.46, 0, 1.45))
    add("forearm.R", "upper_arm.R", (-0.46, 0, 1.45), (-0.72, 0, 1.45))
    add("hand.R", "forearm.R", (-0.72, 0, 1.45), (-0.82, 0, 1.45))
    add("thigh.L", "pelvis", (0.10, 0, 0.98), (0.11, 0, 0.52))
    add("shin.L", "thigh.L", (0.11, 0, 0.52), (0.11, 0, 0.09))
    add("foot.L", "shin.L", (0.11, 0.01, 0.09), (0.11, -0.13, 0.05))
    add("thigh.R", "pelvis", (-0.10, 0, 0.98), (-0.11, 0, 0.52))
    add("shin.R", "thigh.R", (-0.11, 0, 0.52), (-0.11, 0, 0.09))
    add("foot.R", "shin.R", (-0.11, 0.01, 0.09), (-0.11, -0.13, 0.05))
    bpy.ops.object.mode_set(mode="OBJECT")
    return obj.name


def write_stand_payload(out_path: str) -> None:
    """A contract-valid format-2 payload with one standing figure (the same
    shape the CI fixtures use). Fidelity vs the gate rig is NOT gated here —
    the FK-fidelity bar stays in verify_pose_apply.sh with real payloads."""
    z = 0.0
    positions = {
        "hips": (0.0, 0.0, z), "spine": (0.0, 0.02, z + 0.17),
        "chest": (0.0, 0.04, z + 0.34), "neck": (0.0, 0.06, z + 0.45),
        "head": (0.0, 0.08, z + 0.62),
        "upper_arm.L": (-0.18, 0.06, z + 0.42),
        "upper_arm.R": (0.18, 0.06, z + 0.42),
        "forearm.L": (-0.22, 0.04, z + 0.24),
        "forearm.R": (0.22, 0.04, z + 0.24),
        "upper_leg.L": (-0.09, 0.0, z), "upper_leg.R": (0.09, 0.0, z),
        "lower_leg.L": (-0.10, -0.02, z - 0.42),
        "lower_leg.R": (0.10, -0.02, z - 0.42),
        "foot.L": (-0.11, -0.04, z - 0.90),
        "foot.R": (0.11, -0.04, z - 0.90),
    }
    pose = {
        "positions": {r: list(p) for r, p in sorted(positions.items())},
        "flips": {}, "confidence": 0.8, "reliable": True,
        "scale": 1.0, "anchor": "hips", "notes": ["session-gate stand pose"],
        "joint_confidence": {},
    }
    entry = {
        "label": "session figure 0", "index": 0, "score": 0.9,
        "bbox": [0.0, 0.0, 10.0, 10.0], "pose": pose,
        "rotations": [], "skipped": [], "notes": [],
    }
    payload = {
        "format": 2, "frame": 0, "file": "session_probe.png",
        "figure": {k: entry[k] for k in ("label", "index", "score", "bbox")},
        "pose": pose, "rotations": [], "skipped": [],
        "notes": [], "figures": [entry],
        "rig": {"name": "RM_SessionRig", "fingerprint": "session-gate"},
    }
    Path(out_path).write_text(json.dumps(payload), encoding="utf-8")


def main() -> int:
    argv = sys.argv
    if "--" not in argv:
        print("RM_SESSION_PROBE FAIL: expected -- PORT TOKEN PAYLOAD_OUT JOB_DIR")
        return 2
    args = argv[argv.index("--") + 1:]
    if len(args) < 4:
        print("RM_SESSION_PROBE FAIL: expected -- PORT TOKEN PAYLOAD_OUT JOB_DIR")
        return 2
    port_s, token, payload_out, job_dir = args[:4]

    sys.path.insert(0, str(REPO / "xtask"))
    import walk_job

    stats = walk_job.build_walk_job(Path(job_dir))
    print(
        f"RM_SESSION_PROBE JOB: frames={stats['frames']} "
        f"failed={stats['failed']} (SYNTHETIC generator-cited fixture)"
    )

    rig_name = build_gate_rig()
    write_stand_payload(payload_out)

    import riggermortis_addon
    from riggermortis_addon import session

    riggermortis_addon.register()
    error = session.start_session(int(port_s), token)
    if error:
        print(f"RM_SESSION_PROBE FAIL: {error}")
        return 1

    deadline = time.monotonic() + TIMEOUT_S
    client = session._STATE["client"]
    while time.monotonic() < deadline:
        snap = client.snapshot()
        if snap.get("results_sent", 0) >= EXPECTED_ACTIONS:
            break
        session.pump_once()  # headless: drive the main-thread pump directly
        time.sleep(0.05)
    final = client.snapshot()
    session.stop_session()
    riggermortis_addon.unregister()

    if final.get("results_sent", 0) < EXPECTED_ACTIONS:
        print(f"RM_SESSION_PROBE FAIL: only {final} (wanted {EXPECTED_ACTIONS} results)")
        return 1
    if final.get("state") not in ("connected", "stopped"):
        print(f"RM_SESSION_PROBE FAIL: bad final state {final}")
        return 1
    print(f"RM_SESSION_PROBE OK rig={rig_name} results_sent={final['results_sent']} "
          f"connects={final['connects']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
