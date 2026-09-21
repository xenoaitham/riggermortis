"""P5-2 live stream consumer — the Blender side of the puppeteer loop.

Tails the ``rigpose live`` stream file (the side process spawned by the
user's shell or ``xtask/live_capture.sh`` — never by this add-on, D-009) on
a ``bpy.app.timers`` pump and applies the newest applicable pose line
through the REAL P1-6 apply path (``pose_apply.apply_payload`` — the stream
line IS payload-v2 shaped, so ``rm_role_*`` mapping and mirror semantics
are the apply operator's own). Policy (latest-wins, miss-keeps-pose,
staleness, duplicate replays) lives in ``riggermortis.live.LiveConsumer``
— pure stdlib, CI-tested with fakes; this module is the thin bpy adapter:
the ONLY bpy touch is the apply and the status readout, on the main thread.

The pump never raises out of the timer (the session.py rule): an apply
failure lands in the status line, actionable with a hint, and the loop
continues. Stream settings live on the WindowManager — session-only state,
never saved into .blend files. The end-to-end budget instrumentation keeps
per-applied-line ``{age_ms, poll_lag_ms, apply_ms, e2e_ms}`` (REPLAY-measured
on this box; the live number stays P5-3+ until a camera streams).
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
    """Owns the core LiveTail + LiveConsumer and the main-thread apply."""

    def __init__(
        self,
        stream_path: str,
        armature_name: str,
        *,
        stale_after: float,
        mirror: bool,
    ) -> None:
        core = bpy_bridge.import_core()
        try:
            live = core.live
        except AttributeError as exc:  # an older pip-installed core
            raise ImportError(
                "the installed riggermortis core has no live.LiveTail — the "
                "stream consumer needs the repo's core (hint: install "
                "core/ into Blender's Python, or add core/src to sys.path)"
            ) from exc
        self.core = core
        self.tail = live.LiveTail(stream_path)
        self.consumer = live.LiveConsumer(self.tail, stale_after=stale_after)
        self.stream_path = str(stream_path)
        self.armature_name = str(armature_name)
        self.mirror = bool(mirror)
        self.applied = 0
        self.skipped_total = 0
        self.duplicates_total = 0
        self.last_error = ""
        self.last_seq: int | None = None
        self.last_conf: float | None = None
        self.last_apply_ms: float | None = None
        self.last_pipeline_ms: float | None = None
        self.last_stale = False
        self.last_since_last_s = 0.0
        self.last_worst_deg: float | None = None
        self.budget: list[dict[str, float]] = []

    # -- one main-thread tick -------------------------------------------------

    def pump_once(self) -> str:
        """Poll the stream, apply if the decision says so. Returns a short
        status word for the panel/gate: "applied"/"held"/"stale"/error text.
        Never raises."""
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
        if decision.apply is None:
            return "stale" if decision.stale else "held"
        try:
            self._apply(decision.apply)
        except Exception as exc:  # noqa: BLE001 — a bad line never kills the pump
            self.last_error = f"apply failed: {exc} (hint: check the rig is mapped)"
            return self.last_error
        self.last_error = ""
        return "applied"

    def _apply(self, line: dict[str, Any]) -> None:
        """The REAL P1-6 apply path, instrumented (main thread)."""
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
        t0 = time.perf_counter()
        report = pose_apply.apply_payload(
            obj, line, mirror=self.mirror, core=self.core,
            figure=str((line.get("figure") or {}).get("label") or "") or None,
        )
        apply_ms = (time.perf_counter() - t0) * 1000.0

        self.applied += 1
        self.last_apply_ms = apply_ms
        self.last_conf = float(report.get("confidence") or 0.0)
        age_ms = envelope.get("age_ms")
        age_ms = float(age_ms) if isinstance(age_ms, (int, float)) else None
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
        }
        self.budget.append(row)
        del self.budget[:-BUDGET_HISTORY]

    # -- readouts ---------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Panel/gate readout — plain data, no bpy."""
        return {
            "stream": self.stream_path,
            "armature": self.armature_name,
            "mirror": self.mirror,
            "applied": self.applied,
            "skipped": self.skipped_total,
            "duplicates": self.duplicates_total,
            "poses_total": self.consumer.poses_total,
            "misses_total": self.consumer.misses_total,
            "last_seq": self.last_seq,
            "last_conf": self.last_conf,
            "last_apply_ms": self.last_apply_ms,
            "last_pipeline_ms": self.last_pipeline_ms,
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
        if snap["last_seq"] is not None:
            lines.append(f"last seq {snap['last_seq']}")
        if snap["last_conf"] is not None:
            lines.append(f"conf {snap['last_conf']:.2f}")
        if snap["last_apply_ms"] is not None:
            apply_txt = f"apply {snap['last_apply_ms']:.1f} ms"
            if snap["last_pipeline_ms"] is not None:
                apply_txt += f"  emit->apply {snap['last_pipeline_ms']:.0f} ms"
            lines.append(apply_txt)
        if snap["corrupt"]:
            lines.append(f"corrupt lines: {snap['corrupt']}")
        if snap["last_error"]:
            lines.append(snap["last_error"])
        return "\n".join(lines)


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
    stream_path: str, armature_name: str, *, stale_after: float, mirror: bool
) -> str:
    """Start the driver + timer. Returns an error message, or "" on success
    (the operator's contract)."""
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
