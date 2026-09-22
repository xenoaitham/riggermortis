"""P6-2 capability probe: the Blender-side unknowns for motion-library retarget.

The design page (docs/MOTION_LIBRARY.md) commits to a build only after these
are answered by DOING them in THIS Blender, headless:

1. BVH-ROUNDTRIP — build a small BVH-named humanoid armature + stepped
   action, export BVH, wipe, re-import; verify the action survives (keys,
   frame range), measure the import scale, and compare evaluated bone world
   DIRECTIONS at keyed frames against the source (scale-free; source
   directions are captured BEFORE the wipe).
2. FBX-ROUNDTRIP — the same through the FBX exporter/importer.
3. GLB-CLIPS — if the local Xbot.glb exists (out/real_rigs/Xbot.glb, the
   already-gated real Mixamo export), import it and LIST the actions it
   carries (MEASURED, not assumed). SKIPPED honestly if the file is absent.
4. EXTRACT-ROUNDTRIP — the conversion math on the imported BVH rig: per
   keyed frame, sample evaluated role-bone head positions (armature space),
   convert to canonical positions (hips-anchored, rest-torso-span scale),
   then FK-apply back onto the same rig through the proven pose-basis
   relation (pb = C @ rest @ basis, docs/SECONDARY_MOTION.md) and compare
   against the sampled pose. A nontrivial pose-basis re-assert runs first
   (posed parent + rolled child, candidates must discriminate).
5. ROOT-DROP — the canonical conversion is invariant to source root
   translation (walk-in-place contract, D-008).
6. DETERM — two independent sample passes are byte-identical.

Prints RM_MOTION lines; exit 0 only if every answer is yes (SKIPPED counts
as answered for the asset-dependent GLB section only).
Usage: blender -b --python xtask/motion_probe.py
"""
from __future__ import annotations

import math
import os
import shutil
import sys
import tempfile
from pathlib import Path

import bpy  # noqa: F401 — probe runs inside Blender
from mathutils import Matrix, Quaternion, Vector

FPS = 24
N_FRAMES = 24
STEP_FRAME = 10  # the action STEPS here (arms drop); comparisons at keyed frames
KEYED_FRAMES = (1, STEP_FRAME, N_FRAMES)
SCALE_BAR_UNITS = 0.005  # canonical units (~2.3 cm on the probe rig) — round-trip
EXTRACT_BAR_DEG = 0.5
# FP epsilon for the root-drop identity, chosen ABOVE measured noise (a hips
# offset survives as ~1e-07 canonical units of float dust; any real motion is
# >=1e-3) — the S19 constant-channel epsilon lesson, not a fitted bar.
ROOTDROP_BAR = 1e-6

# BVH-conventional names -> canonical roles (what a mapper must produce; the
# core-side lexicon check runs OUTSIDE Blender — this map only drives the
# probe's own conversion math on the synthetic rig)
ROLES = (
    "Hips:hips",
    "Spine:spine",
    "Spine1:chest",
    "Neck:neck",
    "Head:head",
    "LeftArm:upper_arm.L",
    "LeftForeArm:forearm.L",
    "RightArm:upper_arm.R",
    "RightForeArm:forearm.R",
    "LeftUpLeg:upper_leg.L",
    "LeftLeg:lower_leg.L",
    "RightUpLeg:upper_leg.R",
    "RightLeg:lower_leg.R",
    "LeftFoot:foot.L",
    "RightFoot:foot.R",
)
ORDER = [s.split(":")[0] for s in ROLES]

# parent chain for the mini humanoid (parent-first ORDER for composition)
PARENTS = {
    "Hips": None,
    "Spine": "Hips",
    "Spine1": "Spine",
    "Neck": "Spine1",
    "Head": "Neck",
    "LeftArm": "Spine1",
    "LeftForeArm": "LeftArm",
    "RightArm": "Spine1",
    "RightForeArm": "RightArm",
    "LeftUpLeg": "Hips",
    "LeftLeg": "LeftUpLeg",
    "RightUpLeg": "Hips",
    "RightLeg": "RightUpLeg",
    "LeftFoot": "LeftLeg",
    "RightFoot": "RightLeg",
}

# rest heads (T-pose-ish, meters, Z-up, facing -Y); leaf tails at the end
REST_HEADS = {
    "Hips": (0.0, 0.0, 1.0),
    "Spine": (0.0, 0.0, 1.12),
    "Spine1": (0.0, 0.0, 1.30),
    "Neck": (0.0, 0.0, 1.48),
    "Head": (0.0, 0.0, 1.56),
    "LeftArm": (0.05, 0.0, 1.42),
    "LeftForeArm": (0.25, 0.0, 1.42),
    "RightArm": (-0.05, 0.0, 1.42),
    "RightForeArm": (-0.25, 0.0, 1.42),
    "LeftUpLeg": (0.09, 0.0, 0.92),
    "LeftLeg": (0.09, 0.0, 0.50),
    "RightUpLeg": (-0.09, 0.0, 0.92),
    "RightLeg": (-0.09, 0.0, 0.50),
    "LeftFoot": (0.09, 0.0, 0.08),
    "RightFoot": (-0.09, 0.0, 0.08),
}
REST_TAILS = {
    "Head": (0.0, 0.0, 1.72),
    "LeftForeArm": (0.45, 0.0, 1.42),
    "RightForeArm": (-0.45, 0.0, 1.42),
    "LeftFoot": (0.09, -0.12, 0.02),
    "RightFoot": (-0.09, -0.12, 0.02),
}


def build_humanoid(name):
    """Fresh armature with BVH-conventional names, QUATERNION pose bones."""
    arm = bpy.data.armatures.new(name)
    obj = bpy.data.objects.new(name, arm)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    made = {}
    for bname in ORDER:
        e = arm.edit_bones.new(bname)
        e.head = REST_HEADS[bname]
        child = next((c for c in ORDER if PARENTS[c] == bname), None)
        e.tail = REST_HEADS[child] if child else REST_TAILS[bname]
        made[bname] = e
    for bname in ORDER:
        if PARENTS[bname] is not None:
            made[bname].parent = made[PARENTS[bname]]
            made[bname].use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in obj.pose.bones:
        pb.rotation_mode = "QUATERNION"
    return obj


def key_step_action(obj):
    """Rest pose f1, arms drop ~50 deg about X + knees bend + hips bob
    (root motion) at f10, hold to f24. Keyed ONLY at KEYED_FRAMES so the
    evaluation there is exact regardless of interpolation mode."""
    scene = bpy.context.scene
    scene.render.fps = FPS
    scene.frame_start, scene.frame_end = 1, N_FRAMES
    ad = obj.animation_data_create()
    ad.action = bpy.data.actions.new("rm_motion_src")
    drop = Quaternion((math.cos(math.radians(-25.0)), math.sin(math.radians(-25.0)), 0.0, 0.0))
    knee = Quaternion((math.cos(math.radians(15.0)), math.sin(math.radians(15.0)), 0.0, 0.0))
    for pb in obj.pose.bones:
        pb.rotation_quaternion = Quaternion((1.0, 0.0, 0.0, 0.0))
        pb.keyframe_insert("rotation_quaternion", frame=1)
    for side in ("Left", "Right"):
        obj.pose.bones[f"{side}Arm"].rotation_quaternion = drop
        obj.pose.bones[f"{side}ForeArm"].rotation_quaternion = drop
        obj.pose.bones[f"{side}Leg"].rotation_quaternion = knee
        for bname in (f"{side}Arm", f"{side}ForeArm", f"{side}Leg"):
            obj.pose.bones[bname].keyframe_insert("rotation_quaternion", frame=STEP_FRAME)
    hips = obj.pose.bones["Hips"]
    hips.location = (0.0, 0.0, 0.0)
    hips.keyframe_insert("location", frame=1)
    hips.location = (0.0, 0.05, 0.03)
    hips.keyframe_insert("location", frame=STEP_FRAME)


def posed_heads(obj):
    """Per-bone posed head positions in ARMATURE space at the current frame.

    pb.matrix's TRANSLATION is the posed head (the bone-local origin);
    multiplying the armature-space head_local by pb.matrix would
    double-apply the rest rotation — the first draft's bug, caught here.
    """
    return {bname: tuple(obj.pose.bones[bname].matrix.to_translation()) for bname in ORDER}


def sample_keyed(obj):
    """{(frame, bone): posed head} at the keyed frames (armature space)."""
    scene = bpy.context.scene
    out = {}
    for f in KEYED_FRAMES:
        scene.frame_set(f)
        bpy.context.view_layer.update()
        for bname, head in posed_heads(obj).items():
            out[(f, bname)] = head
    return out


def wipe_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def find_armature():
    for obj in bpy.data.objects:
        if obj.type == "ARMATURE":
            return obj
    return None


def angle_between(a, b):
    dot = max(-1.0, min(1.0, a[0] * b[0] + a[1] * b[1] + a[2] * b[2]))
    cross = (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )
    return math.degrees(math.atan2(math.sqrt(sum(c * c for c in cross)), dot))


def torso_span(heads):
    """Hips -> mid-shoulders span (the canonical 0.45-unit reference)."""
    mid = tuple((heads["LeftArm"][i] + heads["RightArm"][i]) / 2.0 for i in range(3))
    d = tuple(mid[i] - heads["Hips"][i] for i in range(3))
    return math.sqrt(sum(c * c for c in d))


def quat_from_to(a, b):
    return Vector(a).normalized().rotation_difference(Vector(b).normalized())


def try_op(label, fn):
    try:
        res = fn()
    except Exception as exc:  # noqa: BLE001 — the probe reports, not raises
        print(f"RM_MOTION {label}: FAIL exception={exc!r}")
        return None
    if "FINISHED" not in res:
        print(f"RM_MOTION {label}: FAIL result={res}")
        return None
    return res


def iter_fcurves(act):
    """Action fcurves across Blender APIs (4.x legacy / 5.x slotted)."""
    try:
        return list(act.fcurves)  # Blender <= 4.x
    except AttributeError:
        out = []
        for layer in act.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    out.extend(bag.fcurves)
        return out


def action_facts(obj):
    ad = obj.animation_data
    if ad is None or ad.action is None:
        return None
    act = ad.action
    fcs = iter_fcurves(act)
    return {"name": act.name, "fcurves": len(fcs), "keys": sum(len(fc.keyframe_points) for fc in fcs)}


def roundtrip(tag, do_export, suffix, tmp):
    """Build + key a source humanoid, export, wipe, import, compare.

    The metric is HIPS-RELATIVE NORMALIZED JOINT POSITIONS (the converter's
    actual diet, docs/MOTION_LIBRARY.md rule 1) — bone-axis directions are
    NOT convention-free across importers (the reconstructed rolls differ;
    BVH carries no roll channel), positions are. The source sample is
    captured BEFORE the wipe (the wipe kills the source).

    Returns (ok, path) — the exported file path is kept for re-import.
    """
    src = build_humanoid(f"rm_motion_src_{tag}")
    key_step_action(src)
    src_samples = sample_keyed(src)
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    src_span = torso_span(posed_heads(src))
    src_canon = convert_canonical(src_samples, src_span)
    path = tmp / f"rm_motion_{tag.lower()}{suffix}"
    if try_op(f"{tag}-EXPORT", lambda: do_export(src, path)) is None:
        return False, None
    wipe_scene()
    if try_op(f"{tag}-IMPORT", lambda: import_path(str(path))) is None:
        return False, None
    imp = find_armature()
    if imp is None:
        print(f"RM_MOTION {tag}-IMPORT: FAIL no armature after import")
        return False, None
    facts = action_facts(imp)
    if facts is None:
        print(f"RM_MOTION {tag}-IMPORT: FAIL no action on imported armature {imp.name}")
        return False, None
    print(
        f"RM_MOTION {tag}-IMPORT: ok=True bones={len(imp.data.bones)} "
        f"action={facts['name']} fcurves={facts['fcurves']} keys={facts['keys']}"
    )
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    imp_span = torso_span(posed_heads(imp))
    factor = imp_span / src_span if src_span > 1e-9 else 0.0
    print(
        f"RM_MOTION {tag}-SCALE: source_span={src_span:.4f} imported_span={imp_span:.4f} "
        f"factor={factor:.4f}"
    )
    missing = [b for b in ORDER if b not in imp.data.bones]
    if missing:
        print(f"RM_MOTION {tag}-ROUNDTRIP: FAIL missing bones after import: {missing}")
        return False, path
    imp_canon = convert_canonical(sample_keyed(imp), imp_span)
    worst = max(
        abs(imp_canon[f][b][i] - src_canon[f][b][i])
        for f in KEYED_FRAMES
        for b in ORDER
        for i in range(3)
    )
    ok = worst <= SCALE_BAR_UNITS
    print(
        f"RM_MOTION {tag}-ROUNDTRIP: {'PASS' if ok else 'FAIL'} "
        f"worst={worst:.6f} canonical-units bar<={SCALE_BAR_UNITS:g} "
        f"(hips-relative positions, keyed frames {KEYED_FRAMES})"
    )
    return ok, path


def relation_reassert(rel_rig):
    """Nontrivial re-assert of pb = C @ rest @ basis: pose the parent (40 deg
    Z roll on LeftArm) AND key a 90-deg Z basis on LeftForeArm — the two
    candidate compositions must discriminate (Z rolls do not commute with an
    X-pointing arm rest). Runs on a FRESHLY BUILT rig: the discriminator
    depends on the known rest rolls, and importer-reconstructed rolls can
    make the two candidates coincide (measured on the BVH re-import)."""
    scene = bpy.context.scene
    scene.frame_set(1)
    larm, forearm = rel_rig.pose.bones["LeftArm"], rel_rig.pose.bones["LeftForeArm"]
    rest_a = rel_rig.data.bones["LeftArm"].matrix_local.to_3x3()
    rest_f = rel_rig.data.bones["LeftForeArm"].matrix_local.to_3x3()
    saved_a, saved_f = larm.rotation_quaternion.copy(), forearm.rotation_quaternion.copy()
    r45 = Matrix.Rotation(math.radians(40.0), 3, "Z")
    r90 = Matrix.Rotation(math.pi / 2.0, 3, "Z")
    larm.rotation_quaternion = r45.to_quaternion()
    forearm.rotation_quaternion = r90.to_quaternion()
    bpy.context.view_layer.update()
    c_true = larm.matrix.to_3x3() @ rest_a.inverted()
    got = forearm.matrix.to_3x3()
    da = max(abs(x) for row in (got - c_true @ rest_f @ r90) for x in row)
    db = max(abs(x) for row in (got - c_true @ r90 @ rest_f) for x in row)
    larm.rotation_quaternion = saved_a
    forearm.rotation_quaternion = saved_f
    bpy.context.view_layer.update()
    ok = da < 1e-4 and da < db
    print(
        f"RM_MOTION EXTRACT-RELATION: {'PASS' if ok else 'FAIL'} rest@basis_delta={da:.6f} "
        f"basis@rest_delta={db:.6f} (pb = C @ rest @ basis re-asserted, posed parent)"
    )
    return ok


def convert_canonical(samples, rest_span):
    """{frame: {bone: canonical position}} — hips-anchored, rest-span scale."""
    scale = 0.45 / rest_span  # canonical units per source meter
    out = {}
    for f in KEYED_FRAMES:
        hips = samples[(f, "Hips")]
        out[f] = {
            b: tuple((samples[(f, b)][i] - hips[i]) * scale for i in range(3))
            for b in ORDER
        }
    return out


def extract_roundtrip(imp):
    """Sample -> canonical conversion -> FK-apply onto a fresh TARGET rig.

    This is the production retarget direction: the SOURCE sample is read
    from the imported rig (positions only, animation stays live — forcing
    rotation modes would orphan the importer's euler fcurves and freeze the
    motion), and the canonical result is applied to a correctly-topologied
    target (build_humanoid) through its own apply path. Re-applying onto
    the SAME imported rig does NOT work by design of the importer: BVH
    reconstruction reverses bone head/tail AXES (joint positions stay
    right — the round-trip check above proves them — so the converter is
    unaffected), but a rotations-based apply-back needs the target's own
    sane rest topology. (MEASURED, first draft's failing case.)
    """
    samples_a = sample_keyed(imp)
    samples_b = sample_keyed(imp)  # determinism twin
    determ = all(samples_a[k] == samples_b[k] for k in samples_a)
    print(f"RM_MOTION DETERM: {'PASS' if determ else 'FAIL'} byte_identical={determ}")
    rest_heads = {b: tuple(imp.data.bones[b].head_local) for b in ORDER}
    rest_span = torso_span(rest_heads)
    canonical = convert_canonical(samples_a, rest_span)

    tgt = build_humanoid("rm_motion_tgt")
    scene = bpy.context.scene
    worst = 0.0
    for f in KEYED_FRAMES:
        scene.frame_set(f)
        bpy.context.view_layer.update()
        carried: dict[str, Matrix] = {}  # composed armature-space pose rotation
        for bname in ORDER:  # parent-first
            pb_ = tgt.pose.bones[bname]
            b_rest = tgt.data.bones[bname].matrix_local.to_3x3()
            pname = PARENTS[bname]
            c_b = (
                Matrix.Identity(3)
                if pname is None
                else carried[pname] @ tgt.data.bones[pname].matrix_local.to_3x3().inverted()
            )
            child = next((c for c in ORDER if PARENTS[c] == bname), None)
            if child is None:
                continue  # leaf: keep the chain as composed
            base = c_b @ b_rest
            u_cur = base @ Vector((0.0, 1.0, 0.0))
            u_tgt = Vector(
                tuple(canonical[f][child][i] - canonical[f][bname][i] for i in range(3))
            ).normalized()
            q_w = quat_from_to(tuple(u_cur), tuple(u_tgt)).to_matrix() @ base
            pb_.rotation_quaternion = (base.inverted() @ q_w).to_quaternion()
            carried[bname] = q_w
        bpy.context.view_layer.update()
        got = posed_heads(tgt)
        for bname in ORDER:
            child = next((c for c in ORDER if PARENTS[c] == bname), None)
            if child is None:
                continue
            u_got = tuple(got[child][i] - got[bname][i] for i in range(3))
            u_want = tuple(
                samples_a[(f, child)][i] - samples_a[(f, bname)][i] for i in range(3)
            )
            worst = max(worst, angle_between(u_got, u_want))
    ok = worst <= EXTRACT_BAR_DEG
    print(
        f"RM_MOTION EXTRACT-ROUNDTRIP: {'PASS' if ok else 'FAIL'} worst={worst:.4f}deg "
        f"bar<={EXTRACT_BAR_DEG}deg (imported sample -> canonical -> fresh target, keyed frames)"
    )
    return bool(determ) and ok


def root_drop(imp):
    """Canonical positions are invariant to source root translation: add a
    hips bone-location offset (a root-motion key), re-sample, and the
    hips-anchored canonical shape must be identical within FP noise."""
    scene = bpy.context.scene
    f = STEP_FRAME
    scene.frame_set(f)
    bpy.context.view_layer.update()
    hips = imp.pose.bones["Hips"]
    saved_loc = hips.location.copy()
    rest_heads = {b: tuple(imp.data.bones[b].head_local) for b in ORDER}
    scale = 0.45 / torso_span(rest_heads)

    def canon(heads):
        h = heads["Hips"]
        return {b: tuple((heads[b][i] - h[i]) * scale for i in range(3)) for b in ORDER}

    base = canon(posed_heads(imp))
    hips.location = saved_loc + Vector((0.3, -0.2, 0.15))
    bpy.context.view_layer.update()
    moved = canon(posed_heads(imp))
    hips.location = saved_loc
    bpy.context.view_layer.update()
    worst = max(
        max(abs(base[b][i] - moved[b][i]) for i in range(3)) for b in ORDER
    )
    ok = worst <= ROOTDROP_BAR
    print(
        f"RM_MOTION ROOT-DROP: {'PASS' if ok else 'FAIL'} max_delta={worst:.3e} "
        f"bar<={ROOTDROP_BAR:g} canonical-units (hips-relative shape invariant to root motion)"
    )
    return ok


def import_path(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".bvh":
        # the 5.1 BVH EXPORTER has no axis params (writes Blender world axes
        # as-is) but the IMPORTER defaults to a Y-up file convention
        # (axis_forward='-Z', axis_up='Y') — MEASURED on 5.1: importing an
        # already-Blender-convention file needs axis_forward='Y',
        # axis_up='Z' (exact round-trip; the defaults land a 90 deg axis
        # rotation, '-Y' lands a VERTICAL MIRROR — both caught by this probe)
        return bpy.ops.import_anim.bvh(filepath=str(path), axis_forward="Y", axis_up="Z")
    if ext == ".fbx":
        return bpy.ops.import_scene.fbx(filepath=str(path))
    if ext in (".glb", ".gltf"):
        return bpy.ops.import_scene.gltf(filepath=str(path))
    raise ValueError(f"unsupported import: {ext}")


def export_bvh(obj, path):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    return bpy.ops.export_anim.bvh(
        filepath=str(path), frame_start=1, frame_end=N_FRAMES, rotate_mode="XYZ"
    )


def export_fbx(obj, path):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    return bpy.ops.export_scene.fbx(filepath=str(path), add_leaf_bones=False)


def glb_clips():
    """Import the local Xbot.glb if present and LIST its actions (measured)."""
    candidates = [
        os.environ.get("RM_MOTION_XBOT", ""),
        os.path.join(os.getcwd(), "out", "real_rigs", "Xbot.glb"),
    ]
    path = next((p for p in candidates if p and os.path.isfile(p)), None)
    if path is None:
        print("RM_MOTION GLB-CLIPS: SKIPPED (Xbot.glb not found; set RM_MOTION_XBOT)")
        return True
    if try_op("GLB-IMPORT", lambda: import_path(path)) is None:
        return False
    actions = []
    for act in bpy.data.actions:
        fcs = iter_fcurves(act)
        actions.append((act.name, len(fcs), sum(len(fc.keyframe_points) for fc in fcs)))
    arms = sorted(o.name for o in bpy.data.objects if o.type == "ARMATURE")
    print(
        f"RM_MOTION GLB-CLIPS: ok=True armatures={arms} actions={len(actions)} "
        f"list={actions}"
    )
    return True


def main():
    ok = True
    tmp = Path(tempfile.mkdtemp(prefix="rm_motion_probe_"))
    try:
        # pose-basis relation re-assert on a freshly built rig (known rest
        # rolls — the discriminator can coincide on importer-reconstructed
        # rests), then the import/convert stages
        wipe_scene()
        ok &= relation_reassert(build_humanoid("rm_motion_rel"))
        wipe_scene()
        r, bvh_path = roundtrip("BVH", export_bvh, ".bvh", tmp)
        ok &= r
        wipe_scene()
        r, _ = roundtrip("FBX", export_fbx, ".fbx", tmp)
        ok &= r
        wipe_scene()
        ok &= glb_clips()
        if bvh_path is None:
            print("RM_MOTION EXTRACT-ROUNDTRIP: SKIPPED (BVH round-trip failed)")
            ok = False
        else:
            wipe_scene()
            if try_op("BVH-REIMPORT", lambda: import_path(str(bvh_path))) is None:
                ok = False
            else:
                imp = find_armature()
                if imp is None:
                    print("RM_MOTION EXTRACT-ROUNDTRIP: FAIL no armature on re-import")
                    ok = False
                else:
                    ok &= extract_roundtrip(imp)
                    ok &= root_drop(imp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"RM_MOTION: {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
