"""P5-2 live stream consumer — the Blender side of the puppeteer loop.

Tails the ``rigpose live`` stream file (the side process spawned by the
user's shell or ``xtask/live_capture.sh`` — never by this add-on, D-009) on
a ``bpy.app.timers`` pump and applies the newest applicable pose line
through the REAL P1-6 apply path (``pose_apply.apply_payload`` — the stream
line IS payload-v2 shaped, so ``rm_role_*`` mapping and mirror semantics
are the apply operator's own). Policy (latest-wins, miss-keeps-pose,
staleness, duplicate replays, the P5-3 failsafe) lives in
``riggermortis.live.LiveConsumer`` — pure stdlib, CI-tested with fakes; the
P5-3 smoothing (:class:`riggermortis.live.LivePoseSmoother`) filters the
canonical pose BEFORE the apply, core-side, CI-tested with jitter streams.
This module is the thin bpy adapter: the ONLY bpy touches are the apply,
the failsafe clear, and the status readout, on the main thread.

The pump never raises out of the timer (the session.py rule): an apply
failure lands in the status line, actionable with a hint, and the loop
continues. Stream settings live on the WindowManager — session-only state,
never saved into .blend files. The end-to-end budget instrumentation keeps
per-applied-line ``{age_ms, poll_lag_ms, apply_ms, e2e_ms}`` plus the
applied canonical positions (the P5-3 gate's variance instrument) —
REPLAY-measured on this box; the live number stays unclaimed until a
camera streams.
"""
from __future__ import annotations

import time
from typing import Any

from . import bpy_bridge, pose_apply

#: bpy.app.timers interval, seconds — an order-of-magnitude default (D-008):
#: the producer's fastest useful line rate is ~10-11 fps (pose-only regime),
#: so polling at 10 Hz keeps up with a fresh line nearly every tick.
PUMP_INTERVAL = 0.1

#: Budget rows kept for the readout/gate (bounded; the newest wins).
BUDGET_HISTORY = 64

_STATE: dict[str, Any] = {}


class LiveDriver:
    """Owns the core LiveTail + LiveConsumer + LivePoseSmoother and the
    main-thread apply / failsafe clear."""

    def __init__(
        self,
        stream_path: str,
        armature_name: str,
        *,
        stale_after: float,
        mirror: bool,
        failsafe_after: float | None = None,
        smoothing: bool = True,
    ) -> None:
        core = bpy_bridge.import_core()
        live = getattr(core, "live", None)
        if live is None or not hasattr(live, "LivePoseSmoother"):
            raise ImportError(
                "the installed riggermortis core has no live.LiveTail/ "
                "LivePoseSmoother — the stream consumer needs the repo's core "
                "(hint: install core/ into Blender's Python, or add core/src "
                "to sys.path)"
            )
        self.core = core
        self.tail = live.LiveTail(stream_path)
        self.consumer = live.LiveConsumer(
            self.tail,
            stale_after=stale_after,
            failsafe_after=(
                live.DEFAULT_FAILSAFE_AFTER if failsafe_after is None
                else float(failsafe_after)
            ),
        )
        self.smoother = live.LivePoseSmoother()
        self.stream_path = str(stream_path)
        self.armature_name = str(armature_name)
        self.mirror = bool(mirror)
        self.smoothing_enabled = bool(smoothing)
        self.applied = 0
        self.skipped_total = 0
        self.duplicates_total = 0
        self.last_error = ""
        self.last_seq: int | None = None
        self.last_conf: float | None = None
        self.last_apply_ms: float | None = None
        self.last_pipeline_ms: float | None = None
        self.last_age_ms: float | None = None
        self.last_stale = False
        self.last_since_last_s = 0.0
        self.last_worst_deg: float | None = None
        self.failsafe_active = False
        self.failsafe_since_s = 0.0
        self.recoveries = 0
        self.budget: list[dict[str, float]] = []

    # -- one main-thread tick -------------------------------------------------

    def pump_once(self) -> str:
        """Poll the stream, apply if the decision says so, fire the failsafe
        on its edge. Returns a short status word for the panel/gate:
        "applied"/"held"/"stale"/"failsafe"/error text. Never raises."""
        self._sync_from_window()
        try:
            decision = self.consumer.poll()
        except Exception as exc:  # noqa: BLE001 — the pump must keep running
            self.last_error = f"stream poll failed: {exc} (hint: check the stream path)"
            return self.last_error
        self.skipped_total += decision.skipped
        self.duplicates_total += decision.duplicates
        self.last_seq = decision.last_seq
        self.last_stale = decision.stale
        self.last_since_last_s = decision.since_last_s
        if decision.failsafe and not self.failsafe_active:
            self._failsafe(decision)
        if decision.apply is None:
            if self.failsafe_active:
                return "failsafe"
            return "stale" if decision.stale else "held"
        try:
            self._apply(decision.apply)
        except Exception as exc:  # noqa: BLE001 — a bad line never kills the pump
            self.last_error = f"apply failed: {exc} (hint: check the rig is mapped)"
            return self.last_error
        self.last_error = ""
        if self.failsafe_active:  # the stream recovered: a fresh pose applied
            self.failsafe_active = False
            self.recoveries += 1
        return "applied"

    def _sync_from_window(self) -> None:
        """The panel's smoothing toggle is read fresh per tick (docs/LIVE.md
        P5-3) — the operator's toggle takes effect on the next line. Callers
        without the add-on property keep the current value (best-effort sync;
        the never-raise rule applies)."""
        import contextlib

        import bpy

        with contextlib.suppress(Exception):
            self.smoothing_enabled = bool(
                bpy.context.window_manager.rm_live.smoothing
            )

    def _failsafe(self, decision: Any) -> None:
        """The P5-3 safe state: sustained stream silence -> clear to rest
        (docs/LIVE.md). Once per edge; the smoother resets so recovery starts
        from the stream, not from pre-failsafe history."""
        import bpy

        self.failsafe_active = True
        self.failsafe_since_s = float(decision.since_last_s)
        self.smoother.reset()
        obj = bpy.data.objects.get(self.armature_name)
        try:
            pose_apply.clear_pose(obj)
        except Exception as exc:  # noqa: BLE001 — actionable, never a traceback
            self.last_error = (
                f"failsafe clear failed: {exc} "
                "(hint: check the rig is still in the scene)"
            )

    def _apply(self, line: dict[str, Any]) -> None:
        """The REAL P1-6 apply path, instrumented (main thread). Smoothing
        OFF is ``apply_payload`` exactly as P5-2 shipped; ON routes the
        payload's canonical pose through the smoother first (docs/LIVE.md)."""
        import bpy

        obj = bpy.data.objects.get(self.armature_name)
        if obj is None or obj.type != "ARMATURE":
            raise ValueError(
                f"armature {self.armature_name!r} not found "
                "(hint: pick the rig in the panel, then Start Live)"
            )
        envelope = line.get("live") or {}
        t_emit = envelope.get("t_emit_wall")
        poll_lag_ms = (
            max(0.0, (time.time() - float(t_emit)) * 1000.0)
            if isinstance(t_emit, (int, float))
            else 0.0
        )
        figure = str((line.get("figure") or {}).get("label") or "") or None
        t0 = time.perf_counter()
        if self.smoothing_enabled:
            report, positions = self._apply_smoothed(obj, line, figure)
            smoothed = True
        else:
            report = pose_apply.apply_payload(
                obj, line, mirror=self.mirror, core=self.core, figure=figure,
            )
            positions = self._payload_positions(line, figure)
            smoothed = False
        apply_ms = (time.perf_counter() - t0) * 1000.0

        self.applied += 1
        self.last_apply_ms = apply_ms
        self.last_conf = float(report.get("confidence") or 0.0)
        age_ms = envelope.get("age_ms")
        age_ms = float(age_ms) if isinstance(age_ms, (int, float)) else None
        self.last_age_ms = age_ms
        # The honest per-line pipeline number is emit -> apply. The envelope's
        # age_ms (capture -> emit) is only capture latency for a real camera;
        # on replayed files it is the file's mtime age — kept informational,
        # never summed into the pipeline number (S18 gate finding).
        pipeline_ms = poll_lag_ms + apply_ms
        self.last_pipeline_ms = pipeline_ms
        self.last_worst_deg = float(report.get("worst_deg") or 0.0)
        row = {
            "seq": float(envelope.get("seq", -1)),
            "age_ms": age_ms if age_ms is not None else -1.0,
            "poll_lag_ms": poll_lag_ms,
            "apply_ms": apply_ms,
            "emit_to_apply_ms": pipeline_ms,
            "worst_deg": self.last_worst_deg,
            "smoothed": 1.0 if smoothed else 0.0,
            "positions": positions,  # the applied pose — the gate's variance instrument
        }
        self.budget.append(row)
        del self.budget[:-BUDGET_HISTORY]

    def _apply_smoothed(
        self, obj: Any, line: dict[str, Any], figure: str | None
    ) -> tuple[dict[str, Any], dict[str, list[float]]]:
        """The P5-3 smoothed apply (docs/LIVE.md): payload -> canonical pose
        -> 1€ filter in the STREAM's space -> mirror -> apply_pose_object —
        the payload path's own core, still the REAL P1-6 apply."""
        payload_mod = pose_apply.payload_module()
        pose_dict = payload_mod.pose_for_figure(line, figure)
        pose = self.core.CanonicalPose.from_dict(pose_dict)
        envelope = line.get("live") or {}
        t_emit = envelope.get("t_emit_wall")
        pose = self.smoother.smooth(
            pose, float(t_emit) if isinstance(t_emit, (int, float)) else None
        )
        if self.mirror:
            pose = pose.mirrored()
        report = pose_apply.apply_pose_object(obj, pose, self.core)
        report["mirrored"] = self.mirror
        report["figure"] = str(
            payload_mod.entry_for_label(line, figure).get("label", "?")
        )
        positions = _positions_dict(pose)
        return report, positions

    def _payload_positions(
        self, line: dict[str, Any], figure: str | None
    ) -> dict[str, list[float]]:
        """The unsmoothed path's applied pose (for the budget rows). The
        payload's own positions, mirrored exactly as ``apply_payload`` does
        when the scene toggle is on."""
        payload_mod = pose_apply.payload_module()
        pose = self.core.CanonicalPose.from_dict(
            payload_mod.pose_for_figure(line, figure)
        )
        if self.mirror:
            pose = pose.mirrored()
        return _positions_dict(pose)

    # -- readouts ---------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Panel/gate readout — plain data, no bpy."""
        return {
            "stream": self.stream_path,
            "armature": self.armature_name,
            "mirror": self.mirror,
            "smoothing": self.smoothing_enabled,
            "min_cutoff": self.smoother.min_cutoff,
            "beta": self.smoother.beta,
            "failsafe": self.failsafe_active,
            "failsafe_since_s": round(self.failsafe_since_s, 1),
            "recoveries": self.recoveries,
            "applied": self.applied,
            "skipped": self.skipped_total,
            "duplicates": self.duplicates_total,
            "poses_total": self.consumer.poses_total,
            "misses_total": self.consumer.misses_total,
            "last_seq": self.last_seq,
            "last_conf": self.last_conf,
            "last_apply_ms": self.last_apply_ms,
            "last_pipeline_ms": self.last_pipeline_ms,
            "last_age_ms": self.last_age_ms,
            "stale": self.last_stale,
            "since_last_s": round(self.last_since_last_s, 1),
            "corrupt": self.tail.corrupt,
            "last_error": self.last_error,
            "budget": list(self.budget),
        }

    def ui_status(self) -> str:
        """Short multi-line status for the panel (read fresh at draw time)."""
        snap = self.snapshot()
        lines = [
            f"stream: {snap['stream']}",
            f"poses {snap['poses_total']} (misses {snap['misses_total']})  "
            f"applied {snap['applied']} (skipped {snap['skipped']}, "
            f"dup {snap['duplicates']})",
        ]
        if snap["stale"]:
            lines.append(
                f"STALE — no new line for {snap['since_last_s']:.1f}s "
                "(keeping the last pose)"
            )
        if snap["failsafe"]:
            lines.append(
                f"FAILSAFE — cleared to rest after {snap['failsafe_since_s']:.1f}s "
                "of stream silence (a recovered stream re-applies)"
            )
        elif snap["recoveries"]:
            lines.append(f"recovered from failsafe x{snap['recoveries']}")
        if snap["last_seq"] is not None:
            lines.append(f"last seq {snap['last_seq']}")
        if snap["last_conf"] is not None:
            lines.append(f"conf {snap['last_conf']:.2f}")
        lines.append(
            f"smoothing {'ON' if snap['smoothing'] else 'OFF'} "
            f"(min_cutoff {snap['min_cutoff']:.1f} Hz, beta {snap['beta']:.2f})"
        )
        if snap["last_apply_ms"] is not None:
            latency = f"latency: apply {snap['last_apply_ms']:.1f} ms"
            if snap["last_pipeline_ms"] is not None:
                latency += f" | emit->apply {snap['last_pipeline_ms']:.0f} ms"
            if snap["last_age_ms"] is not None:
                latency += f" | capture age {snap['last_age_ms']:.0f} ms (info)"
            lines.append(latency)
        if snap["corrupt"]:
            lines.append(f"corrupt lines: {snap['corrupt']}")
        if snap["last_error"]:
            lines.append(snap["last_error"])
        return "\n".join(lines)


def _positions_dict(pose: Any) -> dict[str, list[float]]:
    """Canonical positions of a pose, rounded for the budget rows."""
    return {
        str(role): [round(float(p[0]), 6), round(float(p[1]), 6), round(float(p[2]), 6)]
        for role, p in sorted(pose.positions.items())
    }


# ---------------------------------------------------------------------------
# timer + lifetime (the session.py shape)
# ---------------------------------------------------------------------------

def _pump() -> float | None:
    """bpy.app.timers callback — tick the driver while it lives."""
    driver = _STATE.get("driver")
    if driver is None:
        _teardown_timer()
        return None
    driver.pump_once()
    return PUMP_INTERVAL


def _teardown_timer() -> None:
    import bpy

    if _STATE.get("timer"):
        try:
            bpy.app.timers.unregister(_pump)
        except ValueError:
            pass  # already unregistered
        _STATE["timer"] = False


def start_live(
    stream_path: str,
    armature_name: str,
    *,
    stale_after: float,
    mirror: bool,
    failsafe_after: float | None = None,
    smoothing: bool = True,
) -> str:
    """Start the driver + timer. Returns an error message, or "" on success
    (the operator's contract). ``failsafe_after=None`` resolves to the core's
    documented default (docs/LIVE.md P5-3); ``smoothing`` is the initial
    value — the panel toggle is re-read every tick."""
    import bpy

    if not str(stream_path or "").strip():
        return (
            "no stream path (hint: rigpose live <frames_dir> <rig.json> "
            "--out live.jsonl writes one; paste the .jsonl path here)"
        )
    if _STATE.get("driver") is not None:
        return "live driver already running (hint: stop it first)"
    try:
        driver = LiveDriver(
            str(stream_path).strip(), str(armature_name).strip(),
            stale_after=float(stale_after), mirror=bool(mirror),
            failsafe_after=(None if failsafe_after is None else float(failsafe_after)),
            smoothing=bool(smoothing),
        )
    except ImportError as exc:
        return str(exc)
    except Exception as exc:  # noqa: BLE001 — actionable, never a traceback
        return f"could not start the live driver: {exc}"
    _STATE["driver"] = driver
    try:
        bpy.app.timers.register(_pump, first_interval=PUMP_INTERVAL, persistent=True)
        _STATE["timer"] = True
    except ValueError:
        _STATE["timer"] = True  # already registered from a previous session
    return ""


def stop_live() -> None:
    driver = _STATE.get("driver")
    if driver is not None:
        _STATE["driver"] = None
    try:
        _teardown_timer()
    except Exception:  # noqa: BLE001 — probe-safe teardown
        pass


def running() -> bool:
    return _STATE.get("driver") is not None


def driver() -> LiveDriver | None:
    return _STATE.get("driver")
