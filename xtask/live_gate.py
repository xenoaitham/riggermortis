"""In-Blender gate for the P5-2 stream consumer (run INSIDE Blender, headless).

Drives the add-on's REAL live driver (rm.live_start's machinery — the same
LiveTail + LiveConsumer + P1-6 apply path the panel Start button runs) against
stream files written by a REAL ``rigpose live`` side process. The producer is
spawned by ``xtask/live_verify.sh`` (D-009: the spawn lives in shell glue) and
synchronized with this probe over the log via ``RM_LIVE READY`` handshakes, so
the budget rows measure the consumer loop, not Blender's boot time.

What is asserted (the work-order bars):
- apply fidelity: every applied line's FK self-check worst_deg <= 0.5 (the
  0.5-deg bar class of verify_pose_apply.sh);
- miss handling: an all-miss stream applies NOTHING and the rig's pose bones
  are byte-unchanged (the miss-keeps-pose contract, docs/LIVE.md);
- staleness reporting: after the producer exits, the driver flips to STALE
  and says so (the honest readout; the failsafe proper is P5-3);
- per-line budget printed as RM_LIVE BUDGET lines (REPLAY-labeled: frames,
  not a camera — the live number stays unclaimed).

Usage: blender -b --python xtask/live_gate.py -- STREAM_A STREAM_B FRAMES_DIR
Exits 0 only if every assertion passes.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "addon"))
sys.path.insert(0, str(REPO / "core" / "src"))

TIMEOUT_APPLY_S = 120.0  # producer: cold ONNX load (~2 s) + 9 frames at the
# tracked cadence; generous, a timeout FAILs the gate, it is not a skip
TIMEOUT_STALE_S = 20.0
STALE_AFTER = 1.0  # a configured knob (speeds the gate; the DEFAULT stays 2.0)
WORST_DEG_BAR = 0.5


def build_gate_rig() -> str:
    """The role-nameable gate rig (the blender_verify/session_probe rig)."""
    import bpy

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.object.armature_add(location=(0, 0, 0))
    obj = bpy.context.object
    obj.name = "RM_LiveRig"
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


def _pump_until(driver, deadline_s: float, done) -> bool:
    """Pump the driver's own tick until done(snapshot) or the deadline."""
    deadline = time.monotonic() + deadline_s
    while time.monotonic() < deadline:
        driver.pump_once()
        if done(driver):
            return True
        time.sleep(0.02)
    return False


def _fail(msg: str) -> int:
    print(f"RM_LIVE GATE: FAIL {msg}")
    return 1


def main() -> int:
    argv = sys.argv
    if "--" not in argv:
        print("RM_LIVE GATE: FAIL expected -- STREAM_A STREAM_B FRAMES_DIR")
        return 2
    stream_a, stream_b, frames_dir = argv[argv.index("--") + 1:][:3]
    expected = len(
        [p for p in Path(frames_dir).iterdir()
         if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp")]
    )
    if expected < 1:
        return _fail(f"no frames in {frames_dir}")

    import riggermortis_addon
    from riggermortis_addon import live_driver

    rig_name = build_gate_rig()
    riggermortis_addon.register()
    error = live_driver.start_live(
        stream_a, rig_name, stale_after=STALE_AFTER, mirror=False,
    )
    if error:
        return _fail(f"start_live: {error}")
    driver = live_driver.driver()
    assert driver is not None

    print("RM_LIVE READY", flush=True)  # the shell now spawns producer A

    # -- run A: poses ---------------------------------------------------------
    if not _pump_until(
        driver, TIMEOUT_APPLY_S, lambda d: d.applied >= expected
    ):
        return _fail(
            f"only {driver.applied}/{expected} lines applied "
            f"(snapshot: {driver.snapshot()})"
        )
    snap = driver.snapshot()
    if snap["misses_total"] != 0:
        return _fail(f"run A expected a clean stream, got {snap['misses_total']} miss(es)")
    for row in snap["budget"]:
        print(
            f"RM_LIVE BUDGET seq={int(row['seq'])} age_ms={row['age_ms']:.0f} "
            f"poll_lag_ms={row['poll_lag_ms']:.1f} apply_ms={row['apply_ms']:.2f} "
            f"emit_to_apply_ms={row['emit_to_apply_ms']:.1f} "
            f"worst_deg={row['worst_deg']:.4f}"
        )
        if row["worst_deg"] > WORST_DEG_BAR:
            return _fail(
                f"seq {int(row['seq'])}: FK self-check {row['worst_deg']:.4f} deg "
                f"> the {WORST_DEG_BAR} deg bar"
            )
        if row["apply_ms"] <= 0.0:
            return _fail(f"seq {int(row['seq'])}: apply cost not measured")

    import bpy

    pose_bone = bpy.data.objects[rig_name].pose.bones["upper_arm.L"]
    pose_after_a = tuple(pose_bone.rotation_axis_angle)

    # -- staleness: the producer exits after the frames; the stream goes quiet --
    if not _pump_until(
        driver, TIMEOUT_STALE_S, lambda d: d.last_stale
    ):
        return _fail(f"staleness never reported (snapshot: {driver.snapshot()})")
    since = driver.snapshot()["since_last_s"]
    print(f"RM_LIVE STALE reported=True since_last_s={since:.1f} "
          f"(pose kept: applied={driver.applied})")

    # -- run B: an all-miss stream applies NOTHING ------------------------------
    live_driver.stop_live()
    error = live_driver.start_live(
        stream_b, rig_name, stale_after=STALE_AFTER, mirror=False,
    )
    if error:
        return _fail(f"start_live (B): {error}")
    driver_b = live_driver.driver()
    assert driver_b is not None
    print("RM_LIVE READY-B", flush=True)  # the shell now spawns producer B

    if not _pump_until(
        driver_b, TIMEOUT_APPLY_S, lambda d: d.consumer.misses_total >= expected
    ):
        return _fail(
            f"run B: only {driver_b.consumer.misses_total}/{expected} miss "
            f"lines seen (snapshot: {driver_b.snapshot()})"
        )
    driver_b.pump_once()
    snap_b = driver_b.snapshot()
    if snap_b["applied"] != 0:
        return _fail(f"run B applied {snap_b['applied']} pose line(s) — misses must keep the pose")
    pose_after_b = tuple(pose_bone.rotation_axis_angle)
    if pose_after_b != pose_after_a:
        return _fail("run B MOVED the rig despite zero applies (miss-keeps-pose broken)")
    print(f"RM_LIVE MISS-KEEP PASS applied={snap_b['applied']} "
          f"misses={snap_b['misses_total']} "
          f"corrupt={snap_b['corrupt']}")

    # -- the REPLAY end-to-end summary (per-line rows printed above) ------------
    # The honest replay number is EMIT -> APPLY (poll lag + apply cost): the
    # envelope's age_ms on replayed files is the frame file's mtime age, not
    # capture latency — printed per line for provenance, never summed in.
    pipeline = sorted(r["emit_to_apply_ms"] for r in snap["budget"])
    apply_ms = sorted(r["apply_ms"] for r in snap["budget"])

    def pct(values: list[float], fraction: float) -> float:
        rank = max(1, min(len(values), round(fraction * len(values))))
        return values[rank - 1]

    if not pipeline:
        return _fail("no budget rows (stream carried no lines?)")
    print(
        f"RM_LIVE BUDGET-SUMMARY (REPLAY emit->apply, this box) frames={len(pipeline)} "
        f"p50_ms={pct(pipeline, 0.50):.0f} p95_ms={pct(pipeline, 0.95):.0f} "
        f"apply_p95_ms={pct(apply_ms, 0.95):.2f}"
    )
    print("RM_LIVE GATE: PASS "
          f"(applied={snap['applied']}/{expected} worst_deg<={WORST_DEG_BAR} "
          "miss-keeps-pose + staleness readout verified; capture->apply stays "
          "REPLAY-labeled — the <100 ms live gate remains unclaimed)")
    live_driver.stop_live()
    riggermortis_addon.unregister()
    return 0


if __name__ == "__main__":
    sys.exit(main())
