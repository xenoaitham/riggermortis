"""UI screenshot (P1-11 B4): a REAL Blender window (needs a reachable X display).

Opens the metarig, applies the real pose payload through the add-on's own
path, enables the review overlay, and captures the Blender window with
``bpy.ops.screen.screenshot`` — no faked media.

Lessons from this box (honest caveats, see PROGRESS):
- the N-panel's sidebar TAB is not reachable from Python (and toggling the
  region from Python segfaults 4.0 on a fresh window), so the shot shows the
  posed viewport with the review overlay; the panel layout itself is the
  draw() source of record;
- ``wm.open_mainfile`` unregisters add-ons registered before it, so the job
  opens the file FIRST and registers afterwards;
- the whole job runs inside a ``bpy.app.timers`` job: the windowed event loop
  must tick at least once before the window is screenshot-able.

Run via xtask/ui_screenshot.sh.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value or not Path(value).exists():
        raise SystemExit(f"missing {name} — build local assets first")
    return value


def _job() -> None:
    import bpy

    metarig = _required_env("RM_METARIG_BLEND")
    payload_path = _required_env("RM_PAYLOAD")
    out_path = os.environ.get(
        "RM_SCREENSHOT_OUT", str(REPO / "media" / "ui_screenshot.png")
    )

    sys.path.insert(0, os.environ["RM_CORE_SRC"])
    sys.path.insert(0, os.environ["RM_ADDON_DIR"])
    import riggermortis_addon  # noqa: E402
    from riggermortis_addon import overlay, pose_apply  # noqa: E402

    try:
        bpy.ops.wm.open_mainfile(filepath=metarig)
        riggermortis_addon.register()  # open_mainfile wiped any prior registration

        armature = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
        bpy.context.view_layer.objects.active = armature

        with open(payload_path, encoding="utf-8") as fh:
            payload = json.load(fh)
        report = pose_apply.apply_payload(armature, payload, mirror=False)
        if report["worst_deg"] > 0.5:
            raise SystemExit(f"payload self-check failed: {report['worst_deg']:.3f} deg")
        print(f"RM_UI payload applied, worst {report['worst_deg']:.4f} deg")

        settings = bpy.context.scene.rm_settings
        settings.payload_path = payload_path
        settings.rig_object = armature.name
        settings.overlay_enabled = True
        settings.last_report = (
            f"applied {len(report['applied'])} bone(s) [{report['mapping_source']}] — "
            f"self-check worst {report['worst_deg']:.3f} deg"
        )
        overlay.register()

        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == "VIEW_3D":
                    region = next(
                        (r for r in area.regions if r.type == "WINDOW"), None
                    )
                    if region is not None:
                        try:
                            with bpy.context.temp_override(
                                window=window, area=area, region=region
                            ):
                                bpy.ops.view3d.view_all(center=False)
                        except RuntimeError as exc:
                            print(f"RM_UI view_all skipped ({exc})")

        for _ in range(10):
            bpy.context.view_layer.update()

        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        windows = bpy.context.window_manager.windows
        print(f"RM_UI windows: {len(windows)}")
        if not windows:
            raise SystemExit("no Blender window — a screenshot would be faked; aborting")
        with bpy.context.temp_override(window=windows[0]):
            bpy.ops.screen.screenshot(filepath=out_path)
        print(f"RM_UI SCREENSHOT DONE: {out_path}")
    finally:
        bpy.ops.wm.quit_blender()


def main() -> int:
    import bpy

    # Fire the job from the timer queue so the windowed event loop ticks and
    # the window is real before anything touches GL or screenshots it.
    bpy.app.timers.register(_job, first_interval=1.5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
