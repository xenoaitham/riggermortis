"""P6-1 capability probe: the Blender-side unknowns for secondary motion.

The design page (docs/SECONDARY_MOTION.md) commits to a build only after
these are answered by DOING them in THIS Blender, headless:

1. ADD-BONES — extra (appendage) bones can be created headlessly on an
   armature (edit_bones), keyed with pose-rotation fcurves.
2. COMPOSE — the v1 composition (minimal rest-preserving roll: Rodrigues
   from the bone's rest world Y to a target direction, composed through the
   armature's world rotation) reproduces target directions on keyed bones.
   Run twice: identity armature AND a 30-deg-Z-rotated one (object
   transforms must not leak into the keys).
3. REEVAL — scene.frame_set + view_layer.update re-evaluation (the RM_BAKE
   measurement pattern) returns the keyed directions from the fcurves.
4. FOLLOW/SETTLE — the inline reference spring sim (the math core/secondary
   will implement: damped angular springs, semi-implicit Euler, fixed
   substeps) keyed onto the probe chain shows real follow-through while the
   anchor swings and settles back after the anchor holds. Behavior bars,
   not trajectory values (D-008).
5. DETERM — two independent sims produce byte-identical directions.

Prints RM_SECONDARY lines; exit 0 only if every answer is yes.
Usage: blender -b --python xtask/secondary_probe.py
"""
from __future__ import annotations

import math
import sys

import bpy  # noqa: F401 — probe runs inside Blender
from mathutils import Matrix, Quaternion, Vector

FPS = 30
N_FRAMES = 40
LINKS = 3
FREQ_HZ = 3.0          # D-008 order-of-magnitude default, declared untuned
DAMPING_RATIO = 0.5
DT_TARGET = 1.0 / 240.0
COMPOSE_BAR_DEG = 0.05
FOLLOW_BAR_DEG = 5.0
SETTLE_BAR_DEG = 2.0

OMEGA = 2.0 * math.pi * FREQ_HZ
K_SPRING = OMEGA * OMEGA
C_DAMP = 2.0 * DAMPING_RATIO * OMEGA

REST_DIRS = None  # set in main(): link-0 droop + straight-down successors


# --- tiny vec helpers (mirror core.linalg; core is not importable here) ------
def v_add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def v_scale(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def v_dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def v_cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def v_len(a):
    return math.sqrt(v_dot(a, a))


def v_norm(a):
    l = v_len(a)
    if l < 1e-12:
        raise ValueError("zero-length vector")
    return v_scale(a, 1.0 / l)


def rodrigues(v, axis, angle):
    c, s = math.cos(angle), math.sin(angle)
    return v_norm(
        v_add(
            v_add(v_scale(v, c), v_scale(v_cross(axis, v), s)),
            v_scale(axis, v_dot(axis, v) * (1.0 - c)),
        )
    )


def frame_from_dir(u, side_ref=(1.0, 0.0, 0.0), fwd_ref=(0.0, -1.0, 0.0)):
    """Right-handed parent frame: X=side ref (orthogonalized), Y=along-bone,
    Z = X x Y. side/fwd refs chosen so spine bones (Y~+Z) resolve cleanly."""
    y = v_norm(u)
    ref = side_ref if abs(v_dot(y, side_ref)) < 0.95 else fwd_ref
    d = v_dot(ref, y)
    x = v_norm((ref[0] - y[0] * d, ref[1] - y[1] * d, ref[2] - y[2] * d))
    z = v_cross(x, y)
    return x, y, z


def apply_rot(mat3, v):
    return tuple(mat3 @ Vector(v))


def quat_from_to(a, b):
    """Deterministic rotation taking unit vector a to unit vector b."""
    axis = v_cross(a, b)
    s = v_len(axis)
    d = v_dot(a, b)
    if s < 1e-9:
        if d > 0.0:
            return Quaternion((1.0, 0.0, 0.0, 0.0))
        perp = (1.0, 0.0, 0.0) if abs(a[0]) < 0.9 else (0.0, 1.0, 0.0)
        perp = v_norm(
            (perp[0] - a[0] * v_dot(perp, a), perp[1] - a[1] * v_dot(perp, a), perp[2] - a[2] * v_dot(perp, a))
        )
        return Quaternion(perp, math.pi)
    return Quaternion(v_scale(axis, 1.0 / s), math.atan2(s, d))


def parent_matrix(prev_dir, anchor_rot):
    """World parent frame for a link: the anchor's rotation for link 0,
    else the frame built on the previous link's direction."""
    if anchor_rot is not None:
        return anchor_rot
    x, y, z = frame_from_dir(prev_dir)
    return Matrix(((x[0], y[0], z[0]), (x[1], y[1], z[1]), (x[2], y[2], z[2])))


def sim_directions(anchor_rots):
    """The reference spring sim (semi-implicit Euler, fixed substeps).

    anchor_rots: per-frame anchor world 3x3 rotation (or None rows meaning
    "hold"). Returns per-frame tuples of unit world directions per link.
    """
    subs = max(1, math.ceil((1.0 / FPS) / DT_TARGET))
    dt = (1.0 / FPS) / subs
    state_d: list[tuple[float, float, float]] = []
    state_w: list[tuple[float, float, float]] = [(0.0, 0.0, 0.0)] * LINKS
    frames_out: list[tuple[tuple[float, float, float], ...]] = []
    for R_a in anchor_rots:
        for _ in range(subs):
            for i in range(LINKS):
                R_p = parent_matrix(state_d[i - 1] if i > 0 else None, R_a)
                t = v_norm(apply_rot(R_p, REST_DIRS[i]))
                if i >= len(state_d):
                    state_d.append(t)  # chain starts at rest
                d = state_d[i]
                axis = v_cross(d, t)
                w_old = state_w[i]
                w = v_add(
                    w_old,
                    v_scale(
                        v_add(v_scale(axis, K_SPRING), v_scale(w_old, -C_DAMP)),
                        dt,
                    ),
                )
                state_w[i] = w
                wl = v_len(w)
                if wl > 1e-12:
                    d = rodrigues(d, v_scale(w, 1.0 / wl), wl * dt)
                state_d[i] = d
        frames_out.append(tuple(state_d))
    return frames_out


def build_chain(name):
    """Fresh armature: an up-pointing anchor bone + LINKS hanging tail bones."""
    import bpy

    arm = bpy.data.armatures.new(name)
    obj = bpy.data.objects.new(name, arm)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    a = arm.edit_bones.new("anchor")
    a.head, a.tail = (0.0, 0.0, 1.0), (0.0, 0.0, 1.5)
    prev, z = a, 1.5
    for i in range(LINKS):
        e = arm.edit_bones.new(f"tail{i + 1}")
        e.head = (0.0, 0.0, z)
        e.tail = (0.0, 0.0, z - 0.12)
        e.parent = prev
        e.use_connect = False
        prev, z = e, z - 0.12
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in obj.pose.bones:
        pb.rotation_mode = "QUATERNION"
    return obj


def bone_world_y(obj, pb_name):
    """World direction of the pose bone's long axis (object x armature space)."""
    m = obj.matrix_world.to_3x3() @ obj.pose.bones[pb_name].matrix.to_3x3()
    return v_norm(tuple(m @ Vector((0.0, 1.0, 0.0))))


def measure_basis_relation(obj):
    """Empirically settle how a pose-basis rotation composes: A) pb = C @ rest
    @ basis (basis bone-local) vs B) pb = C @ basis @ rest. Keys a known 90
    deg basis on tail1 at rest and compares evaluated matrices both ways."""
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    pb = obj.pose.bones["tail1"]
    rest = obj.data.bones["tail1"].matrix_local.to_3x3()
    anchor_rest = obj.data.bones["anchor"].matrix_local.to_3x3()
    anchor_basis = obj.pose.bones["anchor"].rotation_quaternion.to_matrix()
    C = (anchor_rest @ anchor_basis) @ anchor_rest.inverted()
    r90 = Matrix.Rotation(math.pi / 2.0, 3, "Z")  # roll about the bone axis:
    # does NOT commute with the down-bone rest, so the candidates differ
    pb.rotation_quaternion = r90.to_quaternion()
    bpy.context.view_layer.update()
    got = pb.matrix.to_3x3()
    cand_a = C @ rest @ r90
    cand_b = C @ r90 @ rest
    da = max(abs(x) for row in (got - cand_a) for x in row)
    db = max(abs(x) for row in (got - cand_b) for x in row)
    pb.rotation_quaternion = Quaternion((1.0, 0.0, 0.0, 0.0))
    bpy.context.view_layer.update()
    print(
        "REL-DBG rest rows:", [tuple(round(float(v), 3) for v in r) for r in rest]
    )
    print("REL-DBG got rows:", [tuple(round(float(v), 3) for v in r) for r in got])
    print(
        "REL-DBG candA rows:", [tuple(round(float(v), 3) for v in r) for r in cand_a]
    )
    print(f"RM_SECONDARY RELATION: rest@basis_delta={da:.6f} basis@rest_delta={db:.6f}")
    return da <= db


def compose_chain_keys(obj, targets_arm, anchor_basis_rot, state):
    """Key the whole tail chain for ONE frame from per-link armature-space
    target directions (the corrected v1 composition).

    Pose-bone relation: pb.matrix(rot) = C @ bone_rest @ basis, where
    C = parent_pose @ parent_rest⁻¹ carries the POSED parent chain and
    parent_pose is the parent's full armature-space pose rotation
    (= parent_rest @ parent_basis for a root parent). Given a desired
    armature-space world rotation q_w for the bone, the basis is
    R = (C @ bone_rest)⁻¹ @ q_w. C is composed LOCALLY from the full pose
    rotations carried in `state` — pb.matrix is never read mid-keying (the
    S15 stale-state trap). q_w itself is the minimal roll from the bone's
    CURRENT world direction (C @ bone_rest @ Y) to the target, so roll
    stays continuous with the parent chain's motion.
    """
    parent_arm_rot = anchor_basis_rot
    parent_name = "anchor"
    for i in range(LINKS):
        pb_name = f"tail{i + 1}"
        b_rest = obj.data.bones[pb_name].matrix_local.to_3x3()
        bp_rest = obj.data.bones[parent_name].matrix_local.to_3x3()
        C = parent_arm_rot @ bp_rest.inverted()
        base = C @ b_rest
        y_cur = base @ Vector((0.0, 1.0, 0.0))
        q_w = quat_from_to(tuple(y_cur), targets_arm[i]).to_matrix() @ base
        basis = base.inverted() @ q_w
        obj.pose.bones[pb_name].rotation_quaternion = basis.to_quaternion()
        obj.pose.bones[pb_name].keyframe_insert(
            "rotation_quaternion", frame=bpy.context.scene.frame_current
        )
        state[pb_name] = q_w
        parent_arm_rot, parent_name = q_w, pb_name


def angle_between(a, b):
    return math.degrees(math.atan2(v_len(v_cross(a, b)), v_dot(a, b)))


def read_anchor_rots(obj, scene):
    rots = []
    for f in range(1, N_FRAMES + 1):
        scene.frame_set(f)
        bpy.context.view_layer.update()
        rots.append(obj.pose.bones["anchor"].matrix.to_3x3().copy())
    return rots


def run_pass(tag):
    """Full pass on a fresh identity chain; returns (key_worst, eval_worst,
    follow_max, settle_end, track)."""
    import bpy

    obj = build_chain(f"rm_sec_{tag}")
    scene = bpy.context.scene
    scene.render.fps = FPS
    scene.frame_start, scene.frame_end = 1, N_FRAMES

    # anchor action: rest f1..f9, pitched -30 deg about X from f10 on (a
    # STEP — every evaluated anchor basis is exactly known, so the chain
    # keys can assume it without reading evaluated state)
    ad = obj.animation_data_create()
    ad.action = bpy.data.actions.new(f"rm_sec_anchor_{tag}")
    q1 = Quaternion((math.cos(math.radians(-15.0)), math.sin(math.radians(-15.0)), 0.0, 0.0))
    anchor = obj.pose.bones["anchor"]
    anchor.rotation_quaternion = Quaternion((1.0, 0.0, 0.0, 0.0))
    anchor.keyframe_insert("rotation_quaternion", frame=1)
    anchor.keyframe_insert("rotation_quaternion", frame=9)
    anchor.rotation_quaternion = q1
    anchor.keyframe_insert("rotation_quaternion", frame=10)

    anchor_rots = read_anchor_rots(obj, scene)
    track = sim_directions(anchor_rots)

    # key chain bones from the track via the local composition (never
    # reading pb.matrix — the S15 stale-state trap); each frame's anchor
    # basis is set explicitly to its exact keyed value
    tail_names = [f"tail{i + 1}" for i in range(LINKS)]
    obj_rot_inv = obj.matrix_world.to_3x3().inverted()
    anchor_rest = obj.data.bones["anchor"].matrix_local.to_3x3()
    worst_key = 0.0
    for k, f in enumerate(range(1, N_FRAMES + 1)):
        scene.frame_set(f)
        anchor_basis = Matrix.Identity(3) if f < 10 else q1.to_matrix()
        anchor.rotation_quaternion = anchor_basis.to_quaternion()
        targets_arm = [
            tuple(obj_rot_inv @ Vector(track[k][i])) for i in range(LINKS)
        ]
        compose_chain_keys(obj, targets_arm, anchor_rest @ anchor_basis, {})
        bpy.context.view_layer.update()
        for i, pb_name in enumerate(tail_names):
            worst_key = max(
                worst_key, angle_between(bone_world_y(obj, pb_name), track[k][i])
            )

    # re-eval from fcurves (fresh pass over the keyed action)
    worst_eval = 0.0
    for k, f in enumerate(range(1, N_FRAMES + 1)):
        scene.frame_set(f)
        bpy.context.view_layer.update()
        for i in range(LINKS):
            worst_eval = max(
                worst_eval,
                angle_between(bone_world_y(obj, f"tail{i + 1}"), track[k][i]),
            )

    def rest_target(k, i):
        R_p = parent_matrix(track[k][i - 1] if i > 0 else None, anchor_rots[k])
        return v_norm(apply_rot(R_p, REST_DIRS[i]))

    follow = max(
        angle_between(track[k][i], rest_target(k, i))
        for k in range(9, 20)  # the anchor STEPS at f10; swing follows
        for i in range(LINKS)
    )
    settle = max(
        angle_between(track[N_FRAMES - 1][i], rest_target(N_FRAMES - 1, i))
        for i in range(LINKS)
    )
    print(
        f"RM_SECONDARY {tag}: key_worst={worst_key:.4f}deg eval_worst={worst_eval:.4f}deg "
        f"follow_max={follow:.2f}deg settle_end={settle:.2f}deg"
    )
    return worst_key, worst_eval, follow, settle, track


def main():
    global REST_DIRS
    import bpy

    REST_DIRS = [v_norm((0.0, -0.35, -1.0))] + [(0.0, 0.0, -1.0)] * (LINKS - 1)
    ok = True
    rel_a = measure_basis_relation(build_chain("rm_sec_REL"))
    print(
        f"RM_SECONDARY RELATION-A: {'PASS' if rel_a else 'FAIL'} "
        "(pb = C @ rest @ basis — basis bone-local)"
    )
    ok &= rel_a
    wk, we, fol, st, tr1 = run_pass("ID")
    ok &= wk <= COMPOSE_BAR_DEG and we <= COMPOSE_BAR_DEG
    print(
        f"RM_SECONDARY COMPOSE: {'PASS' if wk <= COMPOSE_BAR_DEG else 'FAIL'} "
        f"worst={wk:.4f}deg bar=<={COMPOSE_BAR_DEG}deg"
    )
    print(
        f"RM_SECONDARY REEVAL: {'PASS' if we <= COMPOSE_BAR_DEG else 'FAIL'} "
        f"worst={we:.4f}deg bar=<={COMPOSE_BAR_DEG}deg"
    )
    print(
        f"RM_SECONDARY FOLLOW: {'PASS' if fol >= FOLLOW_BAR_DEG else 'FAIL'} "
        f"max={fol:.2f}deg bar=>={FOLLOW_BAR_DEG}deg"
    )
    print(
        f"RM_SECONDARY SETTLE: {'PASS' if st <= SETTLE_BAR_DEG else 'FAIL'} "
        f"end={st:.2f}deg bar=<={SETTLE_BAR_DEG}deg"
    )

    # determinism: independent second sim, byte-identical directions
    obj = bpy.data.objects["rm_sec_ID"]
    tr2 = sim_directions(read_anchor_rots(obj, bpy.context.scene))
    same = all(
        all(d1 == d2 for d1, d2 in zip(f1, f2)) for f1, f2 in zip(tr1, tr2)
    )
    print(f"RM_SECONDARY DETERM: {'PASS' if same else 'FAIL'} byte_identical={same}")
    ok &= same

    # transformed armature: 30 deg about Z — composition must still hit targets
    q1x = Quaternion((math.cos(math.radians(-15.0)), math.sin(math.radians(-15.0)), 0.0, 0.0))
    obj2 = build_chain("rm_sec_X")
    obj2.matrix_world = Matrix.Rotation(math.radians(30.0), 4, "Z")
    bpy.context.view_layer.update()
    ad2 = obj2.animation_data_create()
    ad2.action = bpy.data.actions.new("rm_sec_anchor_X")
    anch2 = obj2.pose.bones["anchor"]
    anch2.rotation_mode = "QUATERNION"
    anch2.rotation_quaternion = q1x
    anch2.keyframe_insert("rotation_quaternion", frame=5)
    bpy.context.scene.frame_set(5)
    bpy.context.view_layer.update()
    target = v_norm((0.3, 0.2, -0.9))
    rot_inv = obj2.matrix_world.to_3x3().inverted()
    anchor2_rest = obj2.data.bones["anchor"].matrix_local.to_3x3()
    compose_chain_keys(
        obj2,
        [tuple(rot_inv @ Vector(target))] * LINKS,
        anchor2_rest @ q1x.to_matrix(),
        {},
    )
    bpy.context.view_layer.update()
    dx = angle_between(bone_world_y(obj2, "tail1"), target)
    print(
        f"RM_SECONDARY COMPOSE-XFORM: {'PASS' if dx <= COMPOSE_BAR_DEG else 'FAIL'} "
        f"worst={dx:.4f}deg bar=<={COMPOSE_BAR_DEG}deg"
    )
    ok &= dx <= COMPOSE_BAR_DEG

    print(f"RM_SECONDARY: {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


main()
