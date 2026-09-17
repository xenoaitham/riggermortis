"""In-Blender probe for the P3-7 agent demo (headless, REAL rig).

The Blender half of the launch-asset demo: opens the local metarig .blend,
registers the add-on, connects the REAL session client to the MCP server's
loopback bridge, and pumps the main-thread executor until every action the
agent enqueued (inspect_scene, apply_pose, bake_action, render_turntable)
has a staged result. The AGENT half (stdio JSON-RPC, enqueue, animate_from_video
with progress streaming, action_result polling) lives in
``xtask/agent_demo.sh``.

Usage: blender -b --python xtask/agent_demo_blender.py -- PORT TOKEN RIG_BLEND
Exits 0 only if all four actions were executed and staged.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "addon"))
sys.path.insert(0, str(REPO / "core" / "src"))

EXPECTED_ACTIONS = 4
TIMEOUT_S = 600.0  # the turntable render dominates (36 workbench frames)


def main() -> int:
    argv = sys.argv
    if "--" not in argv:
        print("RM_AGENT_DEMO FAIL: expected -- PORT TOKEN RIG_BLEND")
        return 2
    port_s, token, rig_blend = argv[argv.index("--") + 1: argv.index("--") + 4]

    import bpy

    bpy.ops.wm.open_mainfile(filepath=str(Path(rig_blend).resolve()))
    armatures = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    if not armatures:
        print("RM_AGENT_DEMO FAIL: no armature in the rig scene")
        return 1
    rig_name = armatures[0].name

    import riggermortis_addon
    from riggermortis_addon import session

    riggermortis_addon.register()
    error = session.start_session(int(port_s), token)
    if error:
        print(f"RM_AGENT_DEMO FAIL: {error}")
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
        print(
            f"RM_AGENT_DEMO FAIL: only {final} (wanted {EXPECTED_ACTIONS} results)"
        )
        return 1
    print(
        f"RM_AGENT_DEMO OK rig={rig_name} results_sent={final['results_sent']} "
        f"connects={final['connects']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
