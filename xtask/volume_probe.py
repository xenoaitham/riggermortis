"""P9-2 volume probe — the Blender half (stages A and B; RM_VOL_STAGE env).

Design of record: docs/VOLUME.md (written BEFORE this probe; the A.1 bar
IoU >= 0.85 visible-view scoped is LAW; D-025 adopted `u2net.onnx` as the
segmentation pass). This script is DISPATCHED by the bash block:

  RM_VOL_STAGE=A blender -b --python xtask/volume_probe.py
      -> builds both rig-class fixtures (person meshes), renders base +
         the 4 reference-class meshes with alpha, prints the anchors as
         ONE `RM_VOL META_JSON {...}` line (bash greps it into the
         scratch meta file — python opens nothing for write).
  RM_VOL_STAGE=B blender -b --python xtask/volume_probe.py
      -> reads the bash-written solve file, rebuilds the fixtures
         deterministically, applies the three candidate delivery drafts
         per reference class, verifies JOINT invariance byte-wise,
         renders the sculpted results, runs the editable-exit /
         no-target / twin checks, prints the apply report as ONE
         `RM_VOL REPORT_JSON {...}` line.

The candidate drafts live HERE (the probe-first rule); the winner is
lifted into the add-on and re-run through the REAL apply by the gate
(xtask/volume_gate.py). The mask/solve/IoU half runs OUTSIDE Blender
(xtask/volume_measure.py + volume_rows.py — Blender's python has no
onnxruntime and never gains it).

Rows: the stages print `RM_VOL STAGE-A: OK` / `RM_VOL STAGE-B: OK` (the
bash grep contract — Blender masks crashed scripts with exit 0, so the
OK rows are grepped, never trusted to exit codes).
Env: RM_CORE_SRC (required — the core import), RM_VOL_STAGE (A|B).
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

_core_src = os.environ.get("RM_CORE_SRC")
if not _core_src:
    raise SystemExit("RM_CORE_SRC is required (the core import)")
if _core_src not in sys.path:
    sys.path.insert(0, _core_src)
sys.path.insert(0, str(Path(__file__).resolve().parent))

import volume_common as vc  # noqa: E402
from volume_common import SCRATCH  # noqa: E402

STAGE = os.environ.get("RM_VOL_STAGE", "")

import auto_sculpt_probe as probe9  # noqa: E402
import bpy  # noqa: E402
import mathutils  # noqa: E402

# ---------------------------------------------------------------------------
# The declared fixture deviation (docs/VOLUME.md, repair A1): arms hang in
# a slight A-pose BESIDE the torso (x +-0.38, no arm-torso bridging) and
# the leg chain sits UNDER the leg mesh (x +-0.095, the inflate centers =
# the mesh centers). Patched BEFORE any builder runs so bones, tails, and
# weights stay one table.
# ---------------------------------------------------------------------------
for _side in ("L", "R"):
    _x = 0.38 if _side == "L" else -0.38
    probe9.BASE_JOINTS["upper_arm." + _side] = (_x, 0.0, 1.38)
    probe9.BASE_JOINTS["forearm." + _side] = (_x, 0.0, 1.12)
    probe9.BASE_JOINTS["hand." + _side] = (_x, 0.0, 0.88)
    probe9.RIGID_TAILS["hand." + _side] = (_x, 0.0, 0.71)
    _lx = 0.095 if _side == "L" else -0.095
    probe9.BASE_JOINTS["upper_leg." + _side] = (_lx, 0.0, 0.94)
    probe9.BASE_JOINTS["lower_leg." + _side] = (_lx, 0.0, 0.52)
    probe9.BASE_JOINTS["foot." + _side] = (_lx, 0.0, 0.12)
    probe9.RIGID_TAILS["foot." + _side] = (_lx, -0.16, 0.02)


def build_person_mesh(name: str, mults: dict[str, float], space_scale: float):
    """Engine-built person mesh (deterministic box-person grid)."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int, int]] = []

    def add_box(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float) -> None:
        base = len(verts)
        nx, ny, nz = 6, 3, 6
        for k in range(nz + 1):
            for j in range(ny + 1):
                for i in range(nx + 1):
                    verts.append(
                        (
                            (x0 + (x1 - x0) * i / nx) * space_scale,
                            (y0 + (y1 - y0) * j / ny) * space_scale,
                            (z0 + (z1 - z0) * k / nz) * space_scale,
                        )
                    )

        def vid(i: int, j: int, k: int) -> int:
            return base + k * (ny + 1) * (nx + 1) + j * (nx + 1) + i

        for k in range(nz):
            for j in range(ny):
                for i in range(nx):
                    a = vid(i, j, k)
                    b = vid(i + 1, j, k)
                    c = vid(i + 1, j + 1, k)
                    d = vid(i, j + 1, k)
                    e = vid(i, j, k + 1)
                    f = vid(i + 1, j, k + 1)
                    g = vid(i + 1, j + 1, k + 1)
                    h = vid(i, j + 1, k + 1)
                    faces.extend(
                        [(a, b, c, d), (e, f, g, h), (a, b, f, e), (d, c, g, h), (a, d, h, e), (b, c, g, f)]
                    )

    for _bname, x0, x1, y0, y1, z0, z1, band in vc.BOXES:
        m = mults.get(band, 1.0) if band else 1.0
        if band in vc.LEG_CENTERS:  # legs scale about their own centers
            c = vc.LEG_CENTERS[band]
            x0, x1 = c + (x0 - c) * m, c + (x1 - c) * m
        else:
            x0, x1 = x0 * m, x1 * m
        add_box(x0, x1, y0, y1, z0, z1)
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    return obj


# Per-box skin ownership (amendment A4): the volume fixture's groups MUST
# match the region semantics — nearest-bone weighting gives the pelvis's
# outer columns to the leg bones (the hips bone is a short center-line
# segment), starving the hip band of its extent carriers. Each box's vert
# range is owned by ONE role's bone, declared here by box name.
BOX_OWNERS: dict[str, str] = {
    "pelvis": "hips",
    "waist": "spine",
    "chest": "chest",
    "neck": "neck",
    "head": "head",
    "arm.L": "upper_arm.L",
    "arm.R": "upper_arm.R",
    "leg.L": "upper_leg.L",
    "leg.R": "upper_leg.R",
}


def build_volume_fixture(name: str, mixamo: bool = False, with_mesh: bool = True) -> dict:
    arm_data = bpy.data.armatures.new(name + "_arm")
    arm_obj = bpy.data.objects.new(name + "_armature", arm_data)
    bpy.context.collection.objects.link(arm_obj)
    space_scale = probe9.MIXAMO_SPACE_SCALE if mixamo else 1.0
    role_to_bone = probe9._build_bones(arm_obj, space_scale)
    mesh_obj = None
    n_weighted = 0
    if with_mesh:
        mesh_obj = build_person_mesh(name + "_mesh", {}, space_scale)
        mesh_obj.parent = arm_obj
        # amendment A4: per-box skin ownership (declared, deterministic —
        # the vert ranges follow the build order of build_person_mesh)
        per_box = (6 + 1) * (3 + 1) * (6 + 1)
        for bi, (_bname, _x0, _x1, _y0, _y1, _z0, _z1, _band) in enumerate(vc.BOXES):
            role = BOX_OWNERS[_bname]
            gname = role_to_bone[role]
            g = mesh_obj.vertex_groups.get(gname) or mesh_obj.vertex_groups.new(name=gname)
            g.add(list(range(bi * per_box, (bi + 1) * per_box)), 1.0, "REPLACE")
            n_weighted += per_box
        mod = mesh_obj.modifiers.new("Armature", "ARMATURE")
        mod.object = arm_obj
    if mixamo:
        arm_obj.scale = (1.0 / space_scale,) * 3
        bpy.context.view_layer.update()
    return {
        "name": name,
        "arm": arm_obj,
        "mesh": mesh_obj,
        "role_to_bone": role_to_bone,
        "mixamo": mixamo,
        "space_scale": space_scale,
        "n_weighted": n_weighted,
    }


def setup_scene_and_render(filepath: str):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.film_transparent = True
    scene.render.resolution_x = vc.RES_X
    scene.render.resolution_y = vc.RES_Y
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = vc.CAM_LENS
    cam = bpy.data.objects.new("cam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = (0.0, -vc.CAM_DIST, vc.HIPS_Z)
    cam.rotation_euler = mathutils.Euler((math.pi / 2.0, 0.0, 0.0), "XYZ")
    scene.camera = cam
    sun_data = bpy.data.lights.new("sun", "SUN")
    sun_data.energy = 3.0
    sun = bpy.data.objects.new("sun", sun_data)
    scene.collection.objects.link(sun)
    sun.rotation_euler = mathutils.Euler((0.6, 0.2, 0.4), "XYZ")
    scene.render.filepath = filepath
    return scene, cam


def project_px(scene, cam, p_world) -> tuple[float, float]:
    from bpy_extras.object_utils import world_to_camera_view

    v = world_to_camera_view(scene, cam, mathutils.Vector(p_world))
    return (v.x * vc.RES_X, (1.0 - v.y) * vc.RES_Y)


def rest_heads(fx: dict) -> dict[str, tuple[float, float, float]]:
    out: dict[str, tuple[float, float, float]] = {}
    for role, bone_name in fx["role_to_bone"].items():
        h = fx["arm"].data.bones[bone_name].matrix_local.to_translation()
        out[role] = (h.x, h.y, h.z)
    return out


def world_heads(fx: dict) -> dict[str, tuple[float, float, float]]:
    bpy.context.view_layer.update()
    m = fx["arm"].matrix_world
    return {r: tuple(m @ mathutils.Vector(h)) for r, h in rest_heads(fx).items()}


def joint_bytes(arm_obj) -> dict[str, tuple]:
    return {
        pb.name: (tuple(pb.location), tuple(pb.rotation_axis_angle), pb.rotation_mode)
        for pb in sorted(arm_obj.pose.bones, key=lambda b: b.name)
    }


def anchors_world(fx: dict) -> dict[str, tuple[float, float, float]]:
    wh = world_heads(fx)
    hips, neck = wh["hips"], wh["neck"]
    span = math.dist(hips, neck)
    out = {"hips": hips, "neck": neck}
    for param, frac in vc.ANCHOR_FRACS.items():
        out[param] = (hips[0], hips[1], hips[2] + frac * span)
    thigh_z = hips[2] + vc.THIGH_ANCHOR_FRAC * span
    out["vol.thigh_w"] = (hips[0], hips[1], thigh_z)
    out["vol.thigh.L"] = (wh["upper_leg.L"][0], hips[1], thigh_z)
    out["vol.thigh.R"] = (wh["upper_leg.R"][0], hips[1], thigh_z)
    return out


# ---------------------------------------------------------------------------
# Candidate drafts (probe-first; the winner is lifted into the add-on)
# ---------------------------------------------------------------------------
def skin_map(fx: dict) -> dict[tuple[str, ...], list[bool]]:
    mesh = fx["mesh"]
    gi: dict[str, int] = {}
    for role in ("hips", "spine", "chest", "upper_leg.L", "upper_leg.R"):
        gname = fx["role_to_bone"].get(role)
        gi[role] = mesh.vertex_groups[gname].index if (gname and gname in mesh.vertex_groups) else -1
    out: dict[tuple[str, ...], list[bool]] = {}
    for _param, _b0, _b1, roles in vc.BANDS:
        idxs = {gi[r] for r in roles if gi[r] >= 0}
        out[roles] = [any(g.group in idxs and g.weight > 0.0 for g in v.groups) for v in mesh.data.vertices]
    return out


def band_total_weights(fx: dict, skin: dict[tuple[str, ...], list[bool]]) -> list[float]:
    heads = rest_heads(fx)
    hips, neck = heads["hips"], heads["neck"]
    span = math.dist(hips, neck)
    weights: list[float] = []
    for v in fx["mesh"].data.vertices:
        # mesh-local == armature-data units for these fixtures (the mesh is
        # an untransformed child): NO space_scale division here — mixing
        # data units with world meters makes every zt land outside the
        # tents on the Mixamo class (the S37 mixamo-zero lesson)
        zt = (v.co.z - hips[2]) / span
        total = 0.0
        for _param, b0, b1, roles in vc.BANDS:
            wz = vc.tent(zt, b0, b1)
            if wz > 0.0 and skin[roles][v.index]:
                total += wz
        weights.append(min(total, 1.0))
    return weights


def _ensure_basis(fx: dict) -> None:
    mesh_obj = fx["mesh"]
    if mesh_obj.data.shape_keys is None:
        mesh_obj.shape_key_add(name="Basis", from_mix=False)


NO_MESH_LINE = "volume: rig has no armature-deformed mesh — volume not applied"


def apply_inflate(fx: dict, factors: dict[str, float]) -> dict:
    """Candidate (a) `shape_key_inflate`: engine-authored convention keys;
    key DATA = the unit band warp (radial in the horizontal plane,
    skin-gated; the thigh band warps each leg about its OWN center —
    nearest leg axis), key VALUE = the solved delta (the artist dial IS
    the volume param — the P8-4 pattern)."""
    if fx["mesh"] is None:
        return {"applied": False, "values": {}, "capability_lines": [NO_MESH_LINE]}
    _ensure_basis(fx)
    mesh_obj = fx["mesh"]
    heads = rest_heads(fx)
    hips = heads["hips"]
    legx = {"upper_leg.L": heads["upper_leg.L"][0], "upper_leg.R": heads["upper_leg.R"][0]}
    skin = skin_map(fx)
    bw = band_total_weights(fx, skin)
    values: dict[str, float] = {}
    for param, _b0, _b1, roles in vc.BANDS:
        v = max(vc.CLAMP_LO - 1.0, min(vc.CLAMP_HI - 1.0, factors[param] - 1.0))
        kb = mesh_obj.shape_key_add(name=param, from_mix=False)
        kb.slider_min = -1.0  # the S37 slender-zero lesson: negative values
        kb.slider_max = 1.0  # are dead at Blender's default slider_min 0.0
        sflag = skin[roles]
        for i, vert in enumerate(mesh_obj.data.vertices):
            w = bw[i]
            if w <= 0.0 or not sflag[i]:
                continue
            p = vert.co
            if len(roles) == 2:  # the thigh band: nearest leg axis is the center
                cx = legx[roles[0]] if abs(p.x - legx[roles[0]]) <= abs(p.x - legx[roles[1]]) else legx[roles[1]]
            else:
                cx = hips[0]
            kb.data[i].co = (p.x + (p.x - cx) * w, p.y + (p.y - hips[1]) * w, p.z)
        kb.value = v
        values[param] = v
    bpy.context.view_layer.update()
    return {"applied": True, "values": values}


def apply_lattice_bands(fx: dict, factors: dict[str, float]) -> dict:
    """Candidate (b) `region_lattice`: one mesh-bound lattice; control
    points displaced radially by the tent-weighted band factor. The S36
    capability lesson says the mesh follows (the mesh-only class); what
    this draft MEASURES is the class's region blindness (a cage cannot
    see skin — arms ride the torso bands)."""
    if fx["mesh"] is None:
        return {"applied": False, "values": {}, "capability_lines": [NO_MESH_LINE]}
    heads_w = world_heads(fx)
    hips_w, neck_w = heads_w["hips"], heads_w["neck"]
    span_w = math.dist(hips_w, neck_w)
    vof = {param: max(vc.CLAMP_LO - 1.0, min(vc.CLAMP_HI - 1.0, factors[param] - 1.0)) for param, _b, _c, _r in vc.BANDS}

    def feff(z: float) -> float:
        zt = (z - hips_w[2]) / span_w
        num = 0.0
        den = 0.0
        for param, b0, b1, _roles in vc.BANDS:
            wz = vc.tent(zt, b0, b1)
            if wz > 0.0:
                num += wz * vof[param]
                den += wz
        return num / den if den > 1e-12 else 0.0

    zs = [p[2] for p in heads_w.values()]
    xs = [p[0] for p in heads_w.values()]
    margin = 0.6 * span_w
    center = ((min(xs) + max(xs)) / 2.0, hips_w[1], (min(zs) + max(zs)) / 2.0)
    dims = (0.8 + margin, 0.4 + margin, max(max(zs) - min(zs), 0.1) + margin)
    grid = (3, 3, 12)
    lat = bpy.data.lattices.new(fx["name"] + "_vlat")
    lat.points_u, lat.points_v, lat.points_w = grid
    lat_obj = bpy.data.objects.new(fx["name"] + "_vlattice", lat)
    bpy.context.collection.objects.link(lat_obj)
    lat_obj.location = center
    half = (dims[0] / 2.0, dims[1] / 2.0, dims[2] / 2.0)
    lat_obj.scale = half
    probe9._set_active(lat_obj)
    fx["mesh"].select_set(True)
    try:
        bpy.ops.object.parent_set(type="LATTICE")
    except Exception as exc:  # narrow: the bind refusal IS the answer
        fx["mesh"].select_set(False)
        return {"applied": False, "values": {}, "capability_lines": ["lattice bind refused: " + str(exc)]}
    fx["mesh"].select_set(False)
    bpy.context.view_layer.update()
    nu, nv, nw = grid
    for idx, p in enumerate(lat.points):
        iu = idx % nu
        iv = (idx // nu) % nv
        iw = idx // (nu * nv)
        base_co = (-1.0 + 2.0 * iu / (nu - 1), -1.0 + 2.0 * iv / (nv - 1), -1.0 + 2.0 * iw / (nw - 1))
        wx = center[0] + base_co[0] * half[0]
        wy = center[1] + base_co[1] * half[1]
        wz = center[2] + base_co[2] * half[2]
        f = feff(wz)
        p.co_deform = (
            base_co[0] + (wx - hips_w[0]) * f / half[0],
            base_co[1] + (wy - hips_w[1]) * f / half[1],
            base_co[2],
        )
    bpy.context.view_layer.update()
    return {"applied": True, "values": dict(vof)}


def apply_girdle_widen(fx: dict, factors: dict[str, float]) -> dict:
    """Candidate (c) `armature_scale` record case: the P9-1 class driven
    at a volume target — the girdle + leg chains translate outward.
    DECLARED structurally suspect (it moves joints); measured for the
    record on ONE case."""
    v = max(vc.CLAMP_LO - 1.0, min(vc.CLAMP_HI - 1.0, factors["vol.hip_w"] - 1.0))
    moved: list[str] = []
    for role in ("upper_leg.L", "lower_leg.L", "foot.L"):
        pb = fx["arm"].pose.bones[fx["role_to_bone"][role]]
        pb.location.x += v * 0.14
        moved.append(role)
    for role in ("upper_leg.R", "lower_leg.R", "foot.R"):
        pb = fx["arm"].pose.bones[fx["role_to_bone"][role]]
        pb.location.x -= v * 0.14
        moved.append(role)
    bpy.context.view_layer.update()
    return {"applied": True, "values": {"vol.hip_w": v}, "moved": moved}


APPLY = {"a": apply_inflate, "b": apply_lattice_bands, "c": apply_girdle_widen}


# ---------------------------------------------------------------------------
# Stage A / Stage B
# ---------------------------------------------------------------------------
def stage_a() -> None:
    meta: dict = {"anchors": {}, "renders": []}
    for tag in ("metarig", "mixamo"):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        fx = build_volume_fixture("probe_" + tag + "_base", mixamo=(tag == "mixamo"))
        scene, cam = setup_scene_and_render(vc.P_BASE[tag])
        bpy.ops.render.render(write_still=True)
        meta["renders"].append(tag)
        meta["anchors"][tag] = {name: list(project_px(scene, cam, p)) for name, p in anchors_world(fx).items()}
    for cls in sorted(vc.REF_CLASSES):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        build_person_mesh("probe_ref_" + cls, vc.REF_CLASSES[cls], 1.0)
        setup_scene_and_render(vc.P_REF[cls])
        bpy.ops.render.render(write_still=True)
        meta["renders"].append(cls)
    print("RM_VOL META_JSON " + json.dumps(meta, sort_keys=True))
    print("RM_VOL STAGE-A: OK (" + str(len(meta["renders"])) + " renders)")


def capture_case(cand: str, tag: str, cls: str, factors: dict[str, float]) -> dict:
    # a CLEAN scene per case: accumulated fixtures from earlier cases
    # superimpose in the render (the S37 scene-accumulation lesson — the
    # slender case rendered pixel-identical to base because it hid INSIDE
    # the accumulated basis meshes)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mixamo = tag == "mixamo"
    fx = build_volume_fixture("probe_" + cand + "_" + tag + "_" + cls, mixamo=mixamo)
    before = joint_bytes(fx["arm"])
    rep = APPLY[cand](fx, factors)
    bpy.context.view_layer.update()
    after = joint_bytes(fx["arm"])
    setup_scene_and_render(vc.P_SCULPTED[cand + "/" + tag + "/" + cls])
    bpy.ops.render.render(write_still=True)
    entry: dict = {
        "applied": rep["applied"],
        "joints_identical": before == after,
        "values": rep.get("values", {}),
        "capability_lines": rep.get("capability_lines", []),
    }
    if cand == "a" and entry["applied"]:
        # the artist exit: zero every key -> evaluated verts == basis
        mesh_obj = fx["mesh"]
        for k in mesh_obj.data.shape_keys.key_blocks:
            if k.name != "Basis":
                k.value = 0.0
        bpy.context.view_layer.update()
        deps = bpy.context.evaluated_depsgraph_get()
        ev_mesh = mesh_obj.evaluated_get(deps).data
        basis = mesh_obj.data.shape_keys.key_blocks[0].data
        max_drift = 0.0
        for bv, evv in zip(basis, ev_mesh.vertices, strict=False):
            d = (bv.co - evv.co).length
            if d > max_drift:
                max_drift = d
        entry["zero_restore_drift"] = max_drift
    return entry


def stage_b() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)  # the default cube is NOT a fixture
    with open(str(SCRATCH / "solve.json"), encoding="utf-8") as fh:
        solve = json.load(fh)
    report: dict = {"candidates": {}}
    for cls in sorted(vc.REF_CLASSES):
        for tag in ("metarig", "mixamo"):
            report["candidates"].setdefault("a", {})[tag + "/" + cls] = capture_case("a", tag, cls, solve[cls])
    for cls in sorted(vc.REF_CLASSES):
        for tag in ("metarig", "mixamo"):
            report["candidates"].setdefault("b", {})[tag + "/" + cls] = capture_case("b", tag, cls, solve[cls])
    report["candidates"]["c"] = {"metarig/wide_hip": capture_case("c", "metarig", "wide_hip", solve["wide_hip"])}

    # twins (candidate a): two fresh builds, byte-identical keys
    twin_payloads = []
    for name in ("twin1", "twin2"):
        fx = build_volume_fixture("probe_twin_" + name, mixamo=False)
        apply_inflate(fx, solve["wide_hip"])
        kb = fx["mesh"].data.shape_keys.key_blocks
        twin_payloads.append({k.name: (k.value, [tuple(v.co) for v in k.data]) for k in kb if k.name != "Basis"})
    report["twins_identical"] = twin_payloads[0].keys() == twin_payloads[1].keys() and all(
        twin_payloads[0][k][0] == twin_payloads[1][k][0]
        and list(twin_payloads[0][k][1]) == list(twin_payloads[1][k][1])
        for k in twin_payloads[0]
    )
    report["twins_n_keys"] = len(twin_payloads[0])

    # no-target: an armature WITHOUT a mesh -> the loud line, nothing created
    fxn = build_volume_fixture("probe_notarget", with_mesh=False)
    repn = apply_inflate(fxn, solve["wide_hip"])
    report["notarget_refused"] = not repn["applied"]
    report["notarget_line"] = (repn.get("capability_lines") or [""])[0]

    print("RM_VOL REPORT_JSON " + json.dumps(report, sort_keys=True))
    print("RM_VOL STAGE-B: OK (" + str(len(report["candidates"])) + " candidates)")


def main() -> int:
    if STAGE == "A":
        stage_a()
    elif STAGE == "B":
        stage_b()
    else:
        raise SystemExit("RM_VOL_STAGE must be A or B")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
