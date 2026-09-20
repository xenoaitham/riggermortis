"""In-Blender probe for P4-7 animatic mechanics (headless).

Answers the Blender-uncertain questions BEFORE any builder is written,
with ``RM_ANIMATIC`` evidence lines (findings recorded in docs/STYLE.md):

- Q-TIME — does a keyframed action evaluate per ``frame_set`` and reach
  EEVEE renders (motion visible in the pixels, stills re-render
  pixel-identical)? The animatic builder consumes the CERTIFIED bake
  path (``bake_action``, RM_BAKE-gated); this probe hand-keys a swing so
  the TIME machinery is proven bake-output-independent.
- Q-AUTHOR — the 5.1 sequencer strip API shape (``strips``; legacy
  ``sequences`` is GONE), image-strip authoring from preset-shaped data
  (two contiguous shots), timing-report determinism. AUTHORING works;
  the MOVIE-APPEND does not (see the recorded dead end — never exercised
  in-process here because a segfault cannot be caught and would kill
  the gate).
- Q-ANIMRENDER — does ``render(animation=True)`` write a PNG frame
  sequence deterministically, and does a scene compositor node group
  process during it (the tones look must survive render-animation)?
  This is the SURVIVING mechanism the animatic builder renders through.
- VSE MOVIE-APPEND DEAD END (bisected 2026-09-21 S15, NOT re-triggered
  here): strip-stack -> FFMPEG movie segfaults racy (~2/3) with a
  garbage ``imb_alloc_buffer`` calloc, independent of source class,
  paths, world, armature, container. The project fallback is per-frame
  PNGs + shell-glue ffmpeg assembly (D-009).

Usage: blender -b --python xtask/animatic_probe.py -- OUT_DIR
"""
from __future__ import annotations

import sys
from pathlib import Path


def _image_px(path: Path) -> list[float]:
    import bpy

    img = bpy.data.images.load(str(path))
    px = list(img.pixels)
    bpy.data.images.remove(img)
    return px


def _mean_abs_diff(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return float("inf")
    if not a:
        return 0.0
    return sum(abs(x - y) for x, y in zip(a, b, strict=True)) / len(a)


def _diff_channels(a: list[float], b: list[float]) -> int:
    return sum(1 for x, y in zip(a, b, strict=True) if abs(x - y) > 0.02)


def build_scene(out_dir: Path) -> None:
    """A CUBE on a 2-bone armature + two cameras + an 8-frame swing action.

    The cube hangs ENTIRELY on the child bone (vertex group b2 + armature
    modifier), so the keyed swing moves the pixels the subject owns.
    Probe-bisected traps, do not reintroduce: pose bones default to
    QUATERNION (rotation_euler keys silently do nothing unless the mode
    switches to XYZ); a SPHERE is rotationally symmetric (a 0.5-rad swing
    moves ~no pixels); frames 1 and 5 of this sinusoid are both zero
    crossings (compare 1 vs 3, the peak).
    """
    import math

    import bpy
    from mathutils import Vector

    bpy.ops.wm.read_factory_settings(use_empty=True)
    world = bpy.data.worlds.new("rm_world")
    world.use_nodes = False
    world.color = (0.08, 0.08, 0.09)
    bpy.context.scene.world = world

    bpy.ops.object.armature_add(location=(0, 0, 0))
    arm = bpy.context.object
    arm.name = "rm_rig"
    bpy.ops.object.mode_set(mode="EDIT")
    bones = arm.data.edit_bones
    bones.remove(bones[0])
    upper = bones.new("b1")
    upper.head, upper.tail = (0.0, 0.0, 0.5), (0.0, 0.0, 1.5)
    lower = bones.new("b2")
    lower.head, lower.tail = (0.0, 0.0, 1.5), (0.0, 0.0, 2.2)
    lower.parent = upper
    bpy.ops.object.mode_set(mode="OBJECT")

    bpy.ops.mesh.primitive_cube_add(size=0.9, location=(0, 0, 1.9))
    cube = bpy.context.object
    cube.name = "rm_subject"
    group = cube.vertex_groups.new(name="b2")
    group.add(list(range(len(cube.data.vertices))), 1.0, "REPLACE")
    mod = cube.modifiers.new("arm", "ARMATURE")
    mod.object = arm

    for i, loc in enumerate([(0.0, -4.0, 1.6), (2.2, -3.0, 2.0)]):
        data = bpy.data.cameras.new(f"rm_cam_{i + 1}")
        cam = bpy.data.objects.new(f"rm_cam_{i + 1}", data)
        cam.location = loc
        aim = Vector((0.0, 0.0, 1.9)) - cam.location
        cam.rotation_euler = aim.to_track_quat("-Z", "Y").to_euler()
        bpy.context.collection.objects.link(cam)

    scene = bpy.context.scene
    scene.camera = bpy.data.objects["rm_cam_1"]
    scene.render.resolution_x, scene.render.resolution_y = 320, 200
    scene.render.image_settings.file_format = "PNG"

    pb = arm.pose.bones["b2"]
    pb.rotation_mode = "XYZ"
    for frame in range(1, 9):
        scene.frame_set(frame)
        pb.rotation_euler.x = 0.5 * math.sin(2.0 * math.pi * (frame - 1) / 8.0)
        pb.keyframe_insert("rotation_euler", frame=frame)
    scene.frame_set(1)


def probe(out_dir: Path) -> int:
    import bpy

    build_scene(out_dir)
    scene = bpy.context.scene
    r = scene.render
    ok = True

    # ---- Q-TIME: frame_set -> still render carries the motion ----------
    scene.camera = bpy.data.objects["rm_cam_1"]
    scene.frame_set(1)
    r.filepath = str(out_dir / "time_f1.png")
    bpy.ops.render.render(write_still=True)
    px_f1_a = _image_px(out_dir / "time_f1.png")

    scene.frame_set(3)
    r.filepath = str(out_dir / "time_f3.png")
    bpy.ops.render.render(write_still=True)
    px_f3 = _image_px(out_dir / "time_f3.png")

    scene.frame_set(1)
    r.filepath = str(out_dir / "time_f1b.png")
    bpy.ops.render.render(write_still=True)
    px_f1_b = _image_px(out_dir / "time_f1b.png")

    motion = _mean_abs_diff(px_f1_a, px_f3)
    motion_channels = _diff_channels(px_f1_a, px_f3)
    det_diff = _diff_channels(px_f1_a, px_f1_b)
    # Channel-count bar, not mean: the sphere trap moved ~0.0010 mean
    # (anti-aliased lighting shift) — a real swing moves EDGE channels.
    q_time = motion_channels > 100 and det_diff == 0
    print(
        f"RM_ANIMATIC Q-TIME: {'PASS' if q_time else 'FAIL'} "
        f"motion_mean={motion:.4f} motion_channels={motion_channels} "
        f"re-render_diff={det_diff}",
        flush=True,
    )
    ok = ok and q_time

    # ---- Q-AUTHOR: strip authoring from preset-shaped data -------------
    has_create = hasattr(scene, "sequence_editor_create")
    ed = scene.sequence_editor_create() if has_create else None
    strips_api = getattr(ed, "strips", None) if ed is not None else None
    legacy_api = getattr(ed, "sequences", None) if ed is not None else None
    print(
        f"RM_ANIMATIC VSE API: create={has_create} "
        f"strips={strips_api is not None} sequences={legacy_api is not None}",
        flush=True,
    )
    if ed is None or (strips_api is None and legacy_api is None):
        print("RM_ANIMATIC Q-AUTHOR: FAIL (no strip collection)", flush=True)
        return 1
    collection = strips_api if strips_api is not None else legacy_api

    shots = [
        {"name": "rm_anim_s00", "frames": 4},
        {"name": "rm_anim_s01", "frames": 4},
    ]
    sources = [out_dir / "time_f1.png", out_dir / "time_f3.png"]

    def build_strips() -> list[dict[str, object]]:
        for strip in list(collection):
            collection.remove(strip)
        start = 1
        report = []
        for shot in shots:
            strip = collection.new_image(shot["name"], str(sources[0]), 1, start)
            for k in range(1, int(shot["frames"])):
                strip.elements.append(str(sources[k % len(sources)]))
            report.append(
                {
                    "name": strip.name,
                    "start": int(strip.frame_start),
                    "elements": len(strip.elements),
                    "duration": int(getattr(strip, "frame_final_duration", 0)),
                }
            )
            start += int(shot["frames"])
        return report

    try:
        rep1 = build_strips()
        rep2 = build_strips()
        q_author = rep1 == rep2 and all(row["elements"] == 4 for row in rep1)
        print(
            f"RM_ANIMATIC Q-AUTHOR: {'PASS' if q_author else 'FAIL'} "
            f"api={'strips' if strips_api is not None else 'sequences'} "
            f"timing={[(row['start'], row['duration']) for row in rep1]}",
            flush=True,
        )
        ok = ok and q_author
    except Exception as exc:  # noqa: BLE001 — the probe records the dead end
        print(f"RM_ANIMATIC Q-AUTHOR: FAIL ({exc.__class__.__name__}: {exc})", flush=True)
        return 1

    # The recorded dead end: strip stacks are NEVER rendered to a movie
    # in-process (a segfault cannot be caught and would kill this probe).
    print(
        "RM_ANIMATIC VSE MOVIE-APPEND: DEAD END (5.1.0) — racy segfault "
        "(garbage imb_alloc_buffer calloc), ~2/3 across 16 bisect runs, "
        "independent of source class/paths/world/armature/container; the "
        "animatic assembles through shell-glue ffmpeg instead (D-009)",
        flush=True,
    )
    # Leave the scene WITHOUT strips: the surviving mechanism renders
    # frames, and nothing downstream may accidentally exercise the crash.
    for strip in list(collection):
        collection.remove(strip)

    # ---- Q-ANIMRENDER: two render modes compared -----------------------
    # (a) render(animation=True) PNG sequences are pixel-deterministic;
    # (b) BUT the scene compositor node group is INACTIVE during them
    #     (probe finding — the tones look must not ride this path). The
    #     builder therefore renders PER-FRAME STILLS, which honor the
    #     compositor (the P4-3 tones proof) — checked here as a full
    #     still sweep with the group active.
    seq_dir = out_dir / "seq"
    seq_dir.mkdir(exist_ok=True)
    r.filepath = str(seq_dir / "frame_")
    scene.frame_start, scene.frame_end = 1, 8
    scene.use_nodes = True
    scene.compositing_node_group = None
    bpy.ops.render.render(animation=True)
    sweep: dict[int, list[float]] = {}
    for f in range(1, 9):
        sweep[f] = _image_px(seq_dir / f"frame_{f:04d}.png")

    bpy.ops.render.render(animation=True)
    det_bad = 0
    for f in range(1, 9):
        det_bad += _diff_channels(sweep[f], _image_px(seq_dir / f"frame_{f:04d}.png"))
    print(
        f"RM_ANIMATIC ANIMATION DET: {'PASS' if det_bad == 0 else 'FAIL'} "
        f"differing_channels={det_bad}",
        flush=True,
    )
    ok = ok and det_bad == 0

    comp = bpy.data.node_groups.new("rm_probe_comp", "CompositorNodeTree")
    comp.interface.new_socket(
        name="Image", in_out="OUTPUT", socket_type="NodeSocketColor"
    )
    src = comp.nodes.new("CompositorNodeRLayers")
    bc = comp.nodes.new("CompositorNodeBrightContrast")
    # Contrast 5.0, NOT Bright 0.15 — the latter provably changes ZERO
    # channels through this dark scene's pipeline (instrument trap; a
    # weak knob once masqueraded as "the compositor is inactive").
    bc.inputs["Contrast"].default_value = 5.0
    sink = comp.nodes.new("NodeGroupOutput")
    comp.links.new(src.outputs["Image"], bc.inputs["Image"])
    comp.links.new(bc.outputs["Image"], sink.inputs["Image"])
    scene.compositing_node_group = comp
    bpy.ops.render.render(animation=True)
    composed_changed = 0
    for f in range(1, 9):
        composed_changed += _diff_channels(
            sweep[f], _image_px(seq_dir / f"frame_{f:04d}.png")
        )
    scene.compositing_node_group = None
    bpy.data.node_groups.remove(comp)
    print(
        "RM_ANIMATIC ANIMSWEEP COMPOSITOR: "
        + ("INACTIVE (recorded)" if composed_changed == 0
           else f"ACTIVE changed_channels={composed_changed}"),
        flush=True,
    )

    # ---- Q-STILLSWEEP: per-frame stills + compositor, deterministic ----
    still_dir = out_dir / "stills"
    still_dir.mkdir(exist_ok=True)
    comp = bpy.data.node_groups.new("rm_probe_comp", "CompositorNodeTree")
    comp.interface.new_socket(
        name="Image", in_out="OUTPUT", socket_type="NodeSocketColor"
    )
    src = comp.nodes.new("CompositorNodeRLayers")
    bc = comp.nodes.new("CompositorNodeBrightContrast")
    # Contrast 5.0, NOT Bright 0.15 — the latter provably changes ZERO
    # channels through this dark scene's pipeline (instrument trap; a
    # weak knob once masqueraded as "the compositor is inactive").
    bc.inputs["Contrast"].default_value = 5.0
    sink = comp.nodes.new("NodeGroupOutput")
    comp.links.new(src.outputs["Image"], bc.inputs["Image"])
    comp.links.new(bc.outputs["Image"], sink.inputs["Image"])
    scene.compositing_node_group = comp

    def still_sweep() -> dict[int, list[float]]:
        out: dict[int, list[float]] = {}
        for f in range(1, 9):
            scene.frame_set(f)
            r.filepath = str(still_dir / f"frame_{f:04d}.png")
            bpy.ops.render.render(write_still=True)
            out[f] = _image_px(still_dir / f"frame_{f:04d}.png")
        return out

    sweep_a = still_sweep()
    sweep_b = still_sweep()
    scene.compositing_node_group = None
    bpy.data.node_groups.remove(comp)
    still_det_bad = sum(
        _diff_channels(sweep_a[f], sweep_b[f]) for f in range(1, 9)
    )
    still_comp_changed = sum(
        _diff_channels(sweep[f], sweep_a[f]) for f in range(1, 9)
    )
    q_stills = still_det_bad == 0 and still_comp_changed > 0
    print(
        f"RM_ANIMATIC Q-STILLSWEEP: {'PASS' if q_stills else 'FAIL'} "
        f"re-render_diff={still_det_bad} compositor_changed={still_comp_changed}",
        flush=True,
    )
    ok = ok and q_stills

    print(f"RM_ANIMATIC PROBE {'OK' if ok else 'PARTIAL'}", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    argv = sys.argv
    if "--" not in argv:
        print("RM_ANIMATIC FAIL: expected -- OUT_DIR")
        sys.exit(2)
    sys.exit(probe(Path(argv[argv.index("--") + 1])))
