"""In-Blender gate for the P5-2/P5-3 stream consumer (run INSIDE Blender).

Drives the add-on's REAL live driver (rm.live_start's machinery — the same
LiveTail + LiveConsumer + LivePoseSmoother + P1-6 apply path the panel Start
button runs) against stream files written by a REAL ``rigpose live`` side
process. The producer is spawned by ``xtask/live_verify.sh`` (D-009: the
spawn lives in shell glue) and synchronized with this probe over the log via
``RM_LIVE READY`` handshakes, so the budget rows measure the consumer loop,
not Blender's boot time.

What is asserted (the work-order bars):
- apply fidelity (run A, smoothing OFF — the P5-2 control): every applied
  line's FK self-check worst_deg <= 0.5 (the 0.5-deg bar class);
- miss handling (run B): an all-miss stream applies NOTHING and the rig's
  pose bones are byte-unchanged (the miss-keeps-pose contract);
- staleness reporting: after the producer exits, the driver flips to STALE;
- smoothing sweep (runs J1/J2, docs/LIVE.md P5-3): a synthetic stream built
  from run A's first REAL payload line with deterministic two-tone jitter at
  the P2-2 sampling class — smoothing OFF is the control curve, ON must cut
  the applied-curve variance >= 4x (the published P2-2 bar, reused verbatim)
  while the mean tracks within the jitter amplitude and every applied line
  stays <= 0.5 deg; constant channels must not move in either run;
- failsafe (run F): sustained silence fires the EDGE once, the rig is
  byte-at-REST, the readout says FAILSAFE; a continuation line applies
  automatically, clears the latch, and passes through the reset smoother
  EXACTLY;
- per-line budget printed as RM_LIVE BUDGET lines (REPLAY-labeled: frames,
  not a camera — the live number stays unclaimed).

Usage: blender -b --python xtask/live_gate.py -- STREAM_A STREAM_B FRAMES_DIR
Exits 0 only if every assertion passes.
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "addon"))
sys.path.insert(0, str(REPO / "core" / "src"))

TIMEOUT_APPLY_S = 120.0  # producer: cold ONNX load (~2 s) + 9 frames at the
# tracked cadence; generous, a timeout FAILs the gate, it is not a skip
TIMEOUT_STALE_S = 20.0
TIMEOUT_TICK_S = 30.0  # per-line deadline for the gate-fed sweep/failsafe runs
STALE_AFTER = 1.0  # a configured knob (speeds the gate; the DEFAULT stays 2.0)
FAILSAFE_AFTER = 2.0  # a configured knob (speeds the gate; the DEFAULT stays 10.0)
WORST_DEG_BAR = 0.5
JITTER_LINES = 40  # ~1.33 s of stream at the sweep's emit spacing
JITTER_DT = 1.0 / 30.0  # the P2-2 instrument's sampling class
JITTER_AMP = 0.01  # canonical units — clearly above FK noise, clearly a jitter


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


def _feed_until(driver, stream_path: str, texts: list[str]) -> bool:
    """Play producer for the gate-fed runs: append line i, pump until it
    applied, next. The filter timeline is the ENVELOPE's emit spacing, so the
    wall-clock write speed does not change the smoothing semantics."""
    for i, text in enumerate(texts):
        with open(stream_path, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")
            fh.flush()
        target = i + 1
        if not _pump_until(
            driver, TIMEOUT_TICK_S, lambda d, t=target: d.applied >= t
        ):
            return False
    return True


def _channel_var(rows: list[dict], role: str, axis: int) -> float:
    """The P2-2 variance instrument over one applied-curve channel."""
    vals = [r["positions"][role][axis] for r in rows]
    mean = sum(vals) / len(vals)
    return sum((v - mean) ** 2 for v in vals) / len(vals)


def _channel_mean(rows: list[dict], role: str, axis: int) -> float:
    return sum(r["positions"][role][axis] for r in rows) / len(rows)


def _jitter_texts(base_event: dict, t0: float) -> tuple[list[str], str, str, str, str]:
    """The synthetic sweep stream (docs/LIVE.md P5-3): the REAL run-A payload
    with deterministic two-tone jitter on two role axes. Returns
    (line texts, channel A label, role A, channel B label, role B)."""
    positions = base_event["pose"]["positions"]
    prefs = [
        r for r in ("forearm.L", "lower_leg.R", "hand.L", "upper_arm.L")
        if r in positions
    ]
    if len(prefs) < 2:
        prefs = sorted(positions)[:2]
    role_a, role_b = prefs[0], prefs[1]
    texts: list[str] = []
    for i in range(JITTER_LINES):
        t = i * JITTER_DT
        j = JITTER_AMP * (
            math.sin(2.0 * math.pi * 3.0 * t)
            + 0.5 * math.sin(2.0 * math.pi * 11.0 * t + 1.3)
        )
        pos = {r: [float(v[0]), float(v[1]), float(v[2])] for r, v in positions.items()}
        pos[role_a][0] += j
        pos[role_b][2] += j
        pose_block = {**base_event["pose"], "positions": pos}
        line = {
            "kind": "pose",
            "live": {
                "seq": i, "t_emit_wall": t0 + t, "t_capture_wall": None,
                "age_ms": 0.0, "detect_every": 1, "detector_ran": True,
                "detect_ms": 0.0, "solve_ms": 0.0, "fk_ms": 0.0, "total_ms": 0.0,
            },
            "format": base_event["format"],
            "frame": i,
            "file": f"jitter_{i:03d}",
            "figure": base_event["figure"],
            "pose": pose_block,
            "rotations": base_event["rotations"],
            "skipped": base_event["skipped"],
            "notes": base_event["notes"],
            "figures": [{**base_event["figures"][0], "pose": pose_block}],
            "rig": base_event["rig"],
        }
        texts.append(json.dumps(line, sort_keys=True))
    return texts, f"{role_a}.x", role_a, f"{role_b}.z", role_b


def _retime(event: dict, seq: int, t0: float) -> str:
    """The same payload re-emitted with a fresh seq/emit time (the failsafe
    run's first line and its continuation)."""
    line = dict(event)
    envelope = dict(line["live"])
    envelope["seq"] = seq
    envelope["t_emit_wall"] = t0
    envelope["age_ms"] = 0.0
    line["live"] = envelope
    line["frame"] = seq
    return json.dumps(line, sort_keys=True)


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

    import bpy
    import riggermortis_addon
    from riggermortis import live as rmlive  # noqa: I001 — gate import block
    from riggermortis_addon import live_driver

    rig_name = build_gate_rig()
    rest_capture = {  # run F compares the failsafe landing against THIS
        pb.name: tuple(pb.rotation_axis_angle)
        for pb in bpy.data.objects[rig_name].pose.bones
    }
    riggermortis_addon.register()
    wm = bpy.context.window_manager

    # -- run A: poses, smoothing OFF (the P5-2 control) -----------------------
    wm.rm_live.smoothing = False
    error = live_driver.start_live(
        stream_a, rig_name, stale_after=STALE_AFTER, mirror=False,
    )
    if error:
        return _fail(f"start_live: {error}")
    driver = live_driver.driver()
    assert driver is not None

    print("RM_LIVE READY", flush=True)  # the shell now spawns producer A

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
            f"worst_deg={row['worst_deg']:.4f} smoothed={int(row['smoothed'])}"
        )
        if row["worst_deg"] > WORST_DEG_BAR:
            return _fail(
                f"seq {int(row['seq'])}: FK self-check {row['worst_deg']:.4f} deg "
                f"> the {WORST_DEG_BAR} deg bar"
            )
        if row["apply_ms"] <= 0.0:
            return _fail(f"seq {int(row['seq'])}: apply cost not measured")
        if row["smoothed"] != 0.0:
            return _fail("run A must be the UNsmoothed control (smoothing OFF)")

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
    live_driver.stop_live()

    # -- runs J1/J2: the smoothing sweep (docs/LIVE.md P5-3) --------------------
    pose_events = [e for e in rmlive.read_live_lines(stream_a)[0]
                   if e.get("kind") == "pose"]
    if not pose_events:
        return _fail("no pose lines in stream A for the jitter fixture")
    sweep_rows: dict[str, list[dict]] = {}
    for tag, smoothing_on in (("J1", False), ("J2", True)):
        stream_j = str(Path(stream_a).with_name(f"stream_{tag}.jsonl"))
        Path(stream_j).unlink(missing_ok=True)
        texts, chan_a, role_a, chan_b, role_b = _jitter_texts(
            pose_events[0], time.time()
        )
        wm.rm_live.smoothing = smoothing_on
        error = live_driver.start_live(
            stream_j, rig_name, stale_after=30.0, failsafe_after=60.0,
            mirror=False, smoothing=smoothing_on,
        )
        if error:
            return _fail(f"start_live ({tag}): {error}")
        driver_j = live_driver.driver()
        assert driver_j is not None
        if not _feed_until(driver_j, stream_j, texts):
            return _fail(
                f"run {tag}: stalled at {driver_j.applied}/{len(texts)} "
                f"applied (snapshot: {driver_j.snapshot()})"
            )
        rows = driver_j.snapshot()["budget"]
        if len(rows) != len(texts):
            return _fail(f"run {tag}: {len(rows)}/{len(texts)} budget rows")
        want_flag = 1.0 if smoothing_on else 0.0
        for row in rows:
            if row["smoothed"] != want_flag:
                return _fail(f"run {tag}: wrong smoothing flag on a budget row")
            if row["worst_deg"] > WORST_DEG_BAR:
                return _fail(
                    f"run {tag}: FK self-check {row['worst_deg']:.4f} deg "
                    f"> the {WORST_DEG_BAR} deg bar"
                )
        sweep_rows[tag] = rows
        live_driver.stop_live()

    rows_off, rows_on = sweep_rows["J1"], sweep_rows["J2"]
    min_ratio = float("inf")
    for chan, role, axis in ((chan_a, role_a, 0), (chan_b, role_b, 2)):
        var_off = _channel_var(rows_off, role, axis)
        var_on = _channel_var(rows_on, role, axis)
        track = abs(
            _channel_mean(rows_on, role, axis) - _channel_mean(rows_off, role, axis)
        )
        ratio = var_off / var_on if var_on > 0.0 else float("inf")
        print(
            f"RM_LIVE SMOOTH {chan} amp={JITTER_AMP} var_off={var_off:.3e} "
            f"var_on={var_on:.3e} ratio={ratio:.1f} mean_track={track:.2e}"
        )
        if var_off <= 0.0:
            return _fail(f"jitter fixture carried no variance on {chan}")
        if var_on * 4.0 >= var_off:
            return _fail(
                f"{chan}: variance cut {ratio:.2f}x is below the P2-2 4x bar"
            )
        if track > JITTER_AMP:
            return _fail(f"{chan}: smoothed mean strays {track:.3e} from the raw mean")
        min_ratio = min(min_ratio, ratio)
    for role in rows_off[0]["positions"]:
        if role in (role_a, role_b):
            continue
        for rows, tag in ((rows_off, "J1"), (rows_on, "J2")):
            # epsilon, not ==0: summing identical floats rounds, so a constant
            # channel's variance is FP noise (~1e-30); any real movement of a
            # 1e-6-rounded value sits >= ~1e-14
            if any(_channel_var(rows, role, ax) > 1e-20 for ax in range(3)):
                return _fail(f"constant channel {role} moved in {tag}")
    print(
        f"RM_LIVE SMOOTH-SUMMARY (REPLAY jitter sweep, P2-2 variance instrument) "
        f"lines={len(rows_on)} amp={JITTER_AMP} min_ratio={min_ratio:.1f} "
        f"worst_deg_bar={WORST_DEG_BAR}"
    )
    print(
        "RM_LIVE SMOOTH PASS variance-cut>=4x mean-tracks fidelity<=0.5deg "
        "(REPLAY/synthetic-labeled: jitter on a real payload — no real-motion "
        "stream exists, defaults are untuned D-008 starting points)"
    )

    # -- run F: the failsafe (sustained silence -> rest -> recovery) ------------
    stream_c = str(Path(stream_a).with_name("stream_c.jsonl"))
    Path(stream_c).write_text(
        _retime(pose_events[0], 500, time.time()) + "\n", encoding="utf-8"
    )
    wm.rm_live.smoothing = True
    error = live_driver.start_live(
        stream_c, rig_name, stale_after=STALE_AFTER, failsafe_after=FAILSAFE_AFTER,
        mirror=False,
    )
    if error:
        return _fail(f"start_live (F): {error}")
    driver_f = live_driver.driver()
    assert driver_f is not None
    if not _pump_until(driver_f, TIMEOUT_TICK_S, lambda d: d.applied >= 1):
        return _fail(f"run F: the first line never applied ({driver_f.snapshot()})")
    if not _pump_until(driver_f, 15.0, lambda d: d.failsafe_active):
        return _fail(f"run F: the failsafe never fired ({driver_f.snapshot()})")
    if driver_f.applied != 1:
        return _fail("run F: lines applied during silence")
    at_rest = all(
        tuple(pb.rotation_axis_angle) == rest_capture[pb.name]
        for pb in bpy.data.objects[rig_name].pose.bones
    )
    if not at_rest:
        return _fail("run F: the rig is not byte-at-REST after the failsafe")
    if "FAILSAFE" not in driver_f.ui_status():
        return _fail("run F: the panel readout does not say FAILSAFE")
    print(
        f"RM_LIVE FAILSAFE fired=True after={driver_f.failsafe_since_s:.1f}s "
        f"applied_at_fire={driver_f.applied} bones=rest"
    )
    with open(stream_c, "a", encoding="utf-8") as fh:  # the stream continues
        fh.write(_retime(pose_events[0], 501, time.time()) + "\n")
    if not _pump_until(driver_f, TIMEOUT_TICK_S, lambda d: d.applied >= 2):
        return _fail(f"run F: the recovery line never applied ({driver_f.snapshot()})")
    snap_f = driver_f.snapshot()
    if snap_f["failsafe"] or snap_f["recoveries"] != 1:
        return _fail(f"run F: recovery did not clear the failsafe ({snap_f})")
    payload_pos = {
        r: [round(float(v[0]), 6), round(float(v[1]), 6), round(float(v[2]), 6)]
        for r, v in pose_events[0]["pose"]["positions"].items()
    }
    passthrough = snap_f["budget"][-1]["positions"] == payload_pos
    print(
        f"RM_LIVE FAILSAFE-RECOVERY applied={driver_f.applied} "
        f"failsafe_cleared={not snap_f['failsafe']} "
        f"recoveries={snap_f['recoveries']} passthrough_exact={passthrough}"
    )
    if not passthrough:
        return _fail(
            "run F: the recovery pose did not pass through the reset smoother "
            "exactly (first post-reset observation must be unfiltered)"
        )
    live_driver.stop_live()

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
          "miss-keeps-pose + staleness + smoothing sweep + failsafe/rest/"
          "recovery verified; capture->apply stays REPLAY-labeled — the "
          "<100 ms live gate remains unclaimed)")
    riggermortis_addon.unregister()
    return 0


if __name__ == "__main__":
    sys.exit(main())
