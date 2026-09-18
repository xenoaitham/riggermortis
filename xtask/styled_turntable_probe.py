"""In-Blender styled turntable probe (P4-2/P4-3 honest-scope follow-up, S13).

The style system's line art (P4-2) and tones (P4-3) were verified
SINGLE-FRAME only. This probe re-checks them PER FRAME under an ORBITING
camera — the claim class the P4-8 hero material depends on:

- full styled stack (manga: toon material + LineArt ink + screentone
  compositor) on the gate sphere;
- N frames over a full 360-degree orbit, EEVEE headless;
- per frame: the rm_lineart overlay must still evaluate strokes > 0 on
  the depsgraph (the modifier re-traces for the moved view — the actual
  per-frame question), the tone machinery (view layer + compositor group)
  must still exist, and the rendered frame must carry ink (a dark-pixel
  count > 0) without going black (dark < 90% of the frame);
- one material-only baseline frame quantifies the ink+darkening the
  style stack adds.

A GIF is assembled into OUT_DIR when pillow is importable (inspection
artifact — not committed media; regenerable by re-running this probe).
Every claim cites the printed RM_TT numbers.

Usage: blender -b --python xtask/styled_turntable_probe.py -- OUT_DIR [N_FRAMES]
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "addon"))


def _evaluated_strokes() -> int:
    """Strokes on the canonical rm_lineart overlay after a depsgraph
    evaluation (the engine-independent per-frame proof)."""
    import bpy

    overlay = bpy.data.objects.get("rm_lineart")
    if overlay is None:
        return 0
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    total = 0
    for layer in overlay.evaluated_get(dg).data.layers:
        for frame in layer.frames:
            drawing = getattr(frame, "drawing", None)
            if drawing is not None and hasattr(drawing, "strokes"):
                total += len(drawing.strokes)
    return total


def main() -> int:
    argv = sys.argv
    if "--" not in argv:
        print("RM_TT FAIL: expected -- OUT_DIR [N_FRAMES]")
        return 2
    rest = argv[argv.index("--") + 1 :]
    out_dir = Path(rest[0])
    out_dir.mkdir(parents=True, exist_ok=True)
    n_frames = int(rest[1]) if len(rest) > 1 else 12

    import bpy
    from mathutils import Vector
    from riggermortis_addon import style

    print(f"RM_TT BLENDER: {bpy.app.version_string}")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, location=(0, 0, 1))
    obj = bpy.context.object
    world = bpy.data.worlds.new("rm_tt_world")
    world.use_nodes = False
    world.color = (0.08, 0.08, 0.09)
    bpy.context.scene.world = world
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT" if any(
        e.identifier == "BLENDER_EEVEE_NEXT"
        for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items
    ) else "BLENDER_EEVEE"
    scene.render.image_settings.file_format = "PNG"
    scene.render.resolution_x, scene.render.resolution_y = 480, 360
    scene.render.resolution_percentage = 100
    # Standard view transform for the WHOLE probe (probe-recorded: with a
    # scene compositor node group active, 5.1's save path bypasses the
    # AgX transform — compositor frames carry the plain sRGB encode of
    # linear while compositor-free frames got AgX. One transform for both
    # paths keeps the dark-count comparison apples-to-apples; Standard is
    # also the byte-identity transform the page assembly uses.)
    scene.view_settings.view_transform = "Standard"

    # The full styled stack: manga bands + tones first; the LINEART ink is
    # added after the baseline so the ink contribution is measured within
    # the SAME (compositor-active) pipeline. (A compositor-free baseline
    # is NOT apples-to-apples: probe-recorded, compositor-active frames
    # differ from compositor-free ones at the anti-aliased silhouette —
    # the material's black rim ring evaluates 2-3px wider there — which
    # poisoned the first baseline comparison.)
    preset = style.load_preset("manga")
    style.build_toon_material(obj, preset)
    style.build_screentones(scene, preset)

    def orbit_camera(angle: float) -> None:
        cam = bpy.data.objects.get("rm_tt_cam")
        if cam is None:
            data = bpy.data.cameras.new("rm_tt_cam")
            cam = bpy.data.objects.new("rm_tt_cam", data)
            bpy.context.collection.objects.link(cam)
            scene.camera = cam
        cam.location = (
            3.4 * __import__("math").sin(angle),
            -3.4 * __import__("math").cos(angle),
            1.4,
        )
        aim = Vector((0.0, 0.0, 1.0)) - cam.location
        cam.rotation_euler = aim.to_track_quat("-Z", "Y").to_euler()

    # Baseline: banded material + tones, NO lineart, at the frame-0 angle.
    orbit_camera(0.0)
    scene.render.filepath = str(out_dir / "tt_base.png")
    bpy.ops.render.render(write_still=True)
    base_img = bpy.data.images.load(str(out_dir / "tt_base.png"))
    base_px = list(base_img.pixels)
    bpy.data.images.remove(base_img)
    base_dark = sum(1 for i in range(0, len(base_px), 4) if max(base_px[i : i + 3]) < 0.2)
    print(f"RM_TT BASELINE: dark={base_dark} (bands+tones, no ink)")

    # Now add the ink overlay — the styled stack is complete.
    style.build_lineart(obj, preset)

    rows = []
    ok = True
    for i in range(n_frames):
        orbit_camera(2.0 * 3.141592653589793 * i / n_frames)
        scene.frame_set(1)  # re-evaluate the depsgraph for the moved view
        strokes = _evaluated_strokes()
        vl_ok = any(
            layer.name == "rm_tones_uv" for layer in scene.view_layers
        )
        group_ok = (
            getattr(scene, "compositing_node_group", None) is not None
            and scene.compositing_node_group.name == "rm_tones"
        )
        scene.render.filepath = str(out_dir / f"tt_{i:03d}.png")
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(str(out_dir / f"tt_{i:03d}.png"))
        px = list(img.pixels)
        bpy.data.images.remove(img)
        dark = sum(1 for k in range(0, len(px), 4) if max(px[k : k + 3]) < 0.2)
        total = len(px) // 4
        frac = dark / total
        frame_ok = strokes > 0 and vl_ok and group_ok and 0.0 < frac < 0.9
        ok &= frame_ok
        rows.append((i, strokes, dark, round(frac, 4), frame_ok))
        print(
            f"RM_TT FRAME {i:3d}: strokes={strokes} dark={dark} "
            f"({frac:.4f}) vl={vl_ok} group={group_ok} "
            f"{'PASS' if frame_ok else 'FAIL'}"
        )

    added = sum(d for _, _, d, _, _ in rows) / len(rows) - base_dark
    print(f"RM_TT INK ADDED (mean styled dark - baseline): {added:.0f}")
    if ok and added > 0:
        print("RM_TT STABLE: PASS")
    else:
        print("RM_TT STABLE: FAIL")
        return 1

    try:
        from PIL import Image

        frames = [
            Image.open(str(out_dir / f"tt_{i:03d}.png")).convert("P")
            for i in range(n_frames)
        ]
        frames[0].save(
            str(out_dir / "styled_turntable.gif"),
            save_all=True,
            append_images=frames[1:],
            duration=120,
            loop=0,
        )
        print(f"RM_TT GIF: {out_dir / 'styled_turntable.gif'} (inspection artifact)")
    except ImportError:
        print("RM_TT GIF: SKIPPED (no pillow — numbers stand)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
