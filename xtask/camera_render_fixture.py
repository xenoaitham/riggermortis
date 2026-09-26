"""P8-5 render-fixture helper (run INSIDE Blender, headless).

Builds the two canonical-exact proxy fixtures (the scene_gate build_rig
family: bones in canonical layout + box-proxy meshes so the workbench
render is detectable), places the declared GT-camera subset, renders each
frame deterministically, and writes out_dir/manifest.json with the GT
camera parameters (yaw/pitch/distance/elevation + image dims) next to the
PNGs. Pure geometry: NO solve here — the probe detects + solves.

Usage: blender -b --python xtask/camera_render_fixture.py -- OUT_DIR
Prints RM_CAM RENDER lines; exit 0 iff every render wrote.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

OUT_DIR = Path(sys.argv[sys.argv.index("--") + 1]).resolve()

# The declared tier-2 subset of the GT grid (docs/CAMERA.md § GT-set
# protocol): 3 yaws x 2 distances x 3 elevations x 2 poses = 36 renders.
GRID_YAW = (-40.0, 0.0, 40.0)
GRID_DIST = (2.6, 6.0)
GRID_ELEV = (-1.0, 0.0, 1.0)
IMG_W, IMG_H = 640, 960
LENS_MM = 50.0
SENSOR_W_MM = 36.0

BONES: tuple[tuple[str, str | None, tuple[float, float, float], tuple[float, float, float]], ...] = (
    ("pelvis", None, (0, 0, 0.98), (0, 0, 1.06)),
    ("spine", "pelvis", (0, 0, 1.06), (0, 0, 1.22)),
    ("spine.001", "spine", (0, 0, 1.22), (0, 0, 1.40)),
    ("neck", "spine.001", (0, 0, 1.40), (0, 0, 1.50)),
    ("head", "neck", (0, 0, 1.50), (0, 0, 1.70)),
    ("shoulder.L", "spine.001", (0.03, 0, 1.44), (0.14, 0, 1.46)),
    ("upper_arm.L", "shoulder.L", (0.16, 0, 1.45), (0.46, 0, 1.45)),
    ("forearm.L", "upper_arm.L", (0.46, 0, 1.45), (0.72, 0, 1.45)),
    ("hand.L", "forearm.L", (0.72, 0, 1.45), (0.82, 0, 1.45)),
    ("shoulder.R", "spine.001", (-0.03, 0, 1.44), (-0.14, 0, 1.46)),
    ("upper_arm.R", "shoulder.R", (-0.16, 0, 1.45), (-0.46, 0, 1.45)),
    ("forearm.R", "upper_arm.R", (-0.46, 0, 1.45), (-0.72, 0, 1.45)),
    ("hand.R", "forearm.R", (-0.72, 0, 1.45), (-0.82, 0, 1.45)),
    ("thigh.L", "pelvis", (0.09, 0, 0.98), (0.09, 0, 0.52)),
    ("shin.L", "thigh.L", (0.09, 0, 0.52), (0.09, 0, 0.10)),
    ("foot.L", "shin.L", (0.09, 0, 0.10), (0.09, -0.14, 0.02)),
    ("thigh.R", "pelvis", (-0.09, 0, 0.98), (-0.09, 0, 0.52)),
    ("shin.R", "thigh.R", (-0.09, 0, 0.52), (-0.09, 0, 0.10)),
    ("foot.R", "shin.R", (-0.09, 0, 0.10), (-0.09, -0.14, 0.02)),
)

ROLE_OF = {
    "pelvis": "hips", "spine": "spine", "spine.001": "chest", "neck": "neck",
    "head": "head",
    "shoulder.L": "shoulder.L", "upper_arm.L": "upper_arm.L",
    "forearm.L": "forearm.L", "hand.L": "hand.L",
    "shoulder.R": "shoulder.R", "upper_arm.R": "upper_arm.R",
    "forearm.R": "forearm.R", "hand.R": "hand.R",
    "thigh.L": "upper_leg.L", "shin.L": "lower_leg.L", "foot.L": "foot.L",
    "thigh.R": "upper_leg.R", "shin.R": "lower_leg.R", "foot.R": "foot.R",
}


def _rot_about(
    p: tuple[float, float, float],
    pivot: tuple[float, float, float],
    axis: str,
    ang: float,
) -> tuple[float, float, float]:
    x, y, z = p[0] - pivot[0], p[1] - pivot[1], p[2] - pivot[2]
    c, s = math.cos(ang), math.sin(ang)
    if axis == "y":  # frontal-plane swing (x, z)
        return (pivot[0] + x * c + z * s, p[1], pivot[2] - x * s + z * c)
    # horizontal swing about world Z (x, y)
    return (pivot[0] + x * c - y * s, pivot[1] + x * s + y * c, p[2])


def posed_layout(
    pose_name: str,
) -> dict[str, tuple[tuple[float, float, float], tuple[float, float, float]]]:
    """The fixture layouts: 'rest' as declared, 'posed' with the SAME
    authored swings the probe's fixture class uses (right arm raised,
    left arm back, right leg stanced)."""
    layout = {name: (head, tail) for name, _par, head, tail in BONES}
    if pose_name == "rest":
        return layout
    # FIXTURE LAW (matches the probe): swing about the SHOULDER/HIP kps —
    # a girdle kp that leaves the torso plane reads as a fake depth
    # gradient in the measured solve.
    pivot_ur = layout["upper_arm.R"][0]
    for role in ("forearm.R", "hand.R"):
        layout[role] = (
            _rot_about(layout[role][0], pivot_ur, "y", math.radians(-60)),
            _rot_about(layout[role][1], pivot_ur, "y", math.radians(-60)),
        )
    pivot_ul = layout["upper_arm.L"][0]
    for role in ("forearm.L", "hand.L"):
        layout[role] = (
            _rot_about(layout[role][0], pivot_ul, "z", math.radians(-40)),
            _rot_about(layout[role][1], pivot_ul, "z", math.radians(-40)),
        )
    pivot_tr = layout["thigh.R"][0]
    for role in ("shin.R", "foot.R"):
        layout[role] = (
            _rot_about(layout[role][0], pivot_tr, "y", math.radians(12)),
            _rot_about(layout[role][1], pivot_tr, "y", math.radians(12)),
        )
    return layout



def _aim_quat(location: Vector, target: Vector):
    """The model-basis camera rotation (matches the probe's projector)."""
    fw = (target - location).normalized()
    right = fw.cross(Vector((0.0, 0.0, 1.0))).normalized()
    up = right.cross(fw).normalized()
    m = Matrix((right, up, -fw)).transposed()
    return m.to_quaternion()


def build_fixture(name: str, pose_name: str) -> None:
    """Canonical-exact armature + box-proxy meshes (TWO-PASS: create every
    bone, then wire parents — the S27 fixture law)."""
    bpy.ops.object.armature_add(location=(0, 0, 0))
    obj = bpy.context.object
    obj.name = name
    bpy.ops.object.mode_set(mode="EDIT")
    bones = obj.data.edit_bones
    bones.remove(bones[0])
    created: dict[str, bpy.types.EditBone] = {}
    for bname, _par, head, tail in BONES:
        b = bones.new(bname)
        b.head, b.tail = head, tail
        created[bname] = b
    for bname, par, _head, _tail in BONES:
        if par:
            created[bname].parent = created[par]
    bpy.ops.object.mode_set(mode="OBJECT")
    for bone, role in sorted(ROLE_OF.items()):
        obj[f"rm_role_{role}"] = bone

    # body proxies with VOLUME — the stick-figure class renders fine but
    # the pinned detector never fires on it (measured, first sweep);
    # a torso box + thick limb boxes + head sphere is the detectable class
    layout = posed_layout(pose_name)
    mat = bpy.data.materials.new(f"{name}_mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs[0].default_value = (0.65, 0.45, 0.35, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.85
    for i, (bname, _par, _head, _tail) in enumerate(BONES):
        head, tail = layout[bname]
        bpy.ops.mesh.primitive_cube_add(
            location=(
                (head[0] + tail[0]) / 2, (head[1] + tail[1]) / 2,
                (head[2] + tail[2]) / 2,
            )
        )
        box = bpy.context.object
        box.name = f"{name}_box_{i}"
        length = max(math.dist(head, tail), 1e-3)
        thickness = 0.075 if bname in ("spine", "spine.001", "pelvis") else 0.05
        box.scale = (thickness, thickness, length / 2 + 0.02)
        box.rotation_mode = "QUATERNION"
        direction = Vector(
            (tail[0] - head[0], tail[1] - head[1], tail[2] - head[2])
        )
        box.rotation_quaternion = direction.to_track_quat("Z", "Y")
        box.data.materials.append(mat)
    head_top = layout["head"][1]
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.12, location=head_top)
    sphere = bpy.context.object
    sphere.name = f"{name}_head"
    sphere.data.materials.append(mat)


def main() -> int:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    # EEVEE + a sun + contrast: the flat workbench gray class is detector-
    # blind (two fixture generations measured 0 detections); the style
    # gates prove EEVEE renders headless on this box
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [
        e.identifier for e in bpy.types.RenderSettings.bl_rna.properties[
            "engine"
        ].enum_items
    ] else "BLENDER_EEVEE"
    scene.render.resolution_x = IMG_W
    scene.render.resolution_y = IMG_H
    scene.render.image_settings.file_format = "PNG"
    world = bpy.data.worlds.new("rm_cam_world")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.85, 0.85, 0.85, 1.0)
        bg.inputs[1].default_value = 1.0
    scene.world = world
    sun_data = bpy.data.lights.new("rm_sun", type="SUN")
    sun_data.energy = 3.0
    sun = bpy.data.objects.new("rm_sun", sun_data)
    scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(50), 0.0, math.radians(30))

    for pose_name in ("rest", "posed"):
        build_fixture(f"fixture_{pose_name}", pose_name)

    entries: list[dict[str, object]] = []
    for pose_name in ("rest", "posed"):
        for ob in bpy.data.objects:
            ob.hide_render = not ob.name.startswith(f"fixture_{pose_name}")
        zs = [p[2] for _n, (p, _t) in posed_layout(pose_name).items()]
        z_mid = (max(zs) + min(zs)) / 2.0
        for yaw in GRID_YAW:
            for dist in GRID_DIST:
                for elev in GRID_ELEV:
                    y = math.radians(yaw)
                    cam_loc = (-dist * math.sin(y), -dist * math.cos(y),
                               z_mid + elev)
                    cam_data = bpy.data.cameras.new("rm_gt_cam")
                    cam_data.lens = LENS_MM
                    cam_data.sensor_width = SENSOR_W_MM
                    cam = bpy.data.objects.new("rm_gt_cam", cam_data)
                    scene.collection.objects.link(cam)
                    cam.location = cam_loc
                    cam.hide_render = False
                    cam.rotation_mode = "QUATERNION"
                    cam.rotation_quaternion = _aim_quat(
                        Vector(cam_loc), Vector((0.0, 0.0, z_mid))
                    )
                    scene.camera = cam
                    pitch_gt = math.degrees(math.atan2(-elev, dist))
                    fname = (
                        f"gt_{pose_name}_y{int(yaw)}_d{int(dist * 10)}"
                        f"_e{int(elev * 100)}.png"
                    )
                    scene.render.filepath = str(OUT_DIR / fname)
                    bpy.ops.render.render(write_still=True)
                    entries.append({
                        "file": fname,
                        "pose": pose_name,
                        "yaw_gt": yaw,
                        "dist_gt": dist,
                        "elev": elev,
                        "pitch_gt": pitch_gt,
                        "img_w": IMG_W,
                        "img_h": IMG_H,
                    })
                    bpy.data.objects.remove(cam)
                    bpy.data.cameras.remove(cam_data)
                    print(f"RM_CAM RENDER wrote {fname} (yaw {yaw} dist {dist} "
                          f"elev {elev} pitch {pitch_gt:.2f})")
    (OUT_DIR / "manifest.json").write_text(json.dumps(entries, indent=1))
    print(f"RM_CAM RENDER MANIFEST: {len(entries)} frames -> {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
