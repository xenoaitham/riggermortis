"""P9-2 volume gate (run INSIDE Blender, headless) — the RM_VOL GATE rows,
the sibling of auto_sculpt_gate (the Mimosa new-file rule). The SELECTED
mechanism (docs/VOLUME.md § As-built: shape_key_inflate — the probe's
pre-declared selection at the A.1 binding bar, amendment A3) through the
REAL addon apply path (riggermortis_addon.volume.apply_volume_sculpt):

1. GATE-FIXTURE  — both rig classes build (the probe's builders, ONE copy
                   — the motion_fixture rule).
2. GATE-APPLY    — the addon apply on BOTH rigs x the 4 reference classes:
                   keys created by convention name, values absolute, and
                   EVERY pose bone byte-identical pre/post (the skeleton-
                   invariance contract).
3. GATE-WIDTH    — the width delivery: mid-band horizontal extents of the
                   evaluated mesh scale by the solved factors (per class x
                   band, bar 10% — the tent-taper + f32 margin).
4. GATE-EDITABLE — the artist exit: zeroed keys restore the basis (the
                   addon's measure_zero_restore, bar 1e-4 m).
5. GATE-NOTARGET — an armature WITHOUT a mesh: the loud capability line
                   verbatim, nothing created.
6. GATE-TWIN     — twin applies byte-identical (key values + unit-warp
                   data).

Rows print as `RM_VOL GATE-...: PASS|FAIL <detail>`; the final `RM_VOL
GATE: PASS` is the crash-proof contract (grep-tested both shapes; no
`: FAIL` row may exist on a green run). Model-free by construction (the
mask/solve evidence lives in the probe pipeline rows; CI runs this gate
without the u2net artifact). Usage:

    blender -b --python xtask/volume_gate.py
Env: RM_CORE_SRC, RM_ADDON_DIR (required).
"""
from __future__ import annotations

import math
import os
import sys

_core_src = os.environ.get("RM_CORE_SRC")
_addon_dir = os.environ.get("RM_ADDON_DIR")
if not _core_src or not _addon_dir:
    raise SystemExit("RM_CORE_SRC and RM_ADDON_DIR are required")
for _p in (_core_src, _addon_dir, os.path.dirname(os.path.abspath(__file__))):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bpy  # noqa: E402
import riggermortis as core  # noqa: E402
import volume_probe as probe  # noqa: E402
from riggermortis_addon import volume as addon_vol  # noqa: E402

OK = True


def check(label: str, ok: bool, detail: str = "") -> bool:
    global OK
    if not ok:
        OK = False
    print(f"RM_VOL {label}: {'PASS' if ok else 'FAIL'}{(' ' + detail) if detail else ''}")
    return ok


def fresh_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def joint_bytes(arm_obj) -> dict[str, tuple]:
    return {
        pb.name: (tuple(pb.location), tuple(pb.rotation_axis_angle), pb.rotation_mode)
        for pb in sorted(arm_obj.pose.bones, key=lambda b: b.name)
    }


def band_extent(fx: dict, param: str) -> float:
    """The mid-band horizontal extent (meters, evaluated mesh), measured
    over the band's OWNED vertex groups (the A4 per-box ownership — an
    x-window alone re-includes the arms and goes arm-dominated/static).
    Torso bands: one group's extent. The thigh band: per-leg extents
    summed (upper_leg.L group / upper_leg.R group)."""
    mesh_obj = fx["mesh"]
    deps = bpy.context.evaluated_depsgraph_get()
    ev_mesh = mesh_obj.evaluated_get(deps).data
    t = probe.vc.BAND_TENT_T
    b0, b1 = addon_vol.BAND_TFRAC[param]
    roles = addon_vol.BAND_ROLES[param]
    heads = probe.rest_heads(fx)
    hips = heads["hips"]
    span = math.dist(hips, heads["neck"])
    ss = fx["space_scale"]

    group_idxs = set()
    for role in roles:
        gname = fx["role_to_bone"][role]
        if gname in mesh_obj.vertex_groups:
            group_idxs.add(mesh_obj.vertex_groups[gname].index)
    member = {
        v.index
        for v in mesh_obj.data.vertices
        if any(g.group in group_idxs and g.weight > 0.0 for g in v.groups)
    }

    def in_band(v) -> bool:
        if v.index not in member:
            return False
        zt = (v.co.z / ss - hips[2]) / span
        return (b0 + t) <= zt <= (b1 - t)

    if len(roles) != 2:
        xs = [v.co.x / ss for v in ev_mesh.vertices if in_band(v)]
        return (max(xs) - min(xs)) if xs else 0.0
    total = 0.0
    for role in roles:  # per leg: the group IS the leg (the ownership)
        gname = fx["role_to_bone"][role]
        gi = mesh_obj.vertex_groups[gname].index
        xs = [
            v.co.x / ss
            for v in ev_mesh.vertices
            if any(g.group == gi and g.weight > 0.0 for g in v.groups)
            and (b0 + t) <= (v.co.z / ss - hips[2]) / span <= (b1 - t)
        ]
        total += (max(xs) - min(xs)) if xs else 0.0
    return total


def extents_before_after(fx: dict, factors: dict[str, float]) -> dict[str, tuple[float, float]]:
    before = {param: band_extent(fx, param) for param in addon_vol.BAND_TFRAC}
    addon_vol.apply_volume_sculpt(fx["arm"], fx["mesh"], factors, fx["role_to_bone"])
    bpy.context.view_layer.update()
    after = {param: band_extent(fx, param) for param in addon_vol.BAND_TFRAC}
    return {p: (before[p], after[p]) for p in before}


def main() -> int:
    fresh_scene()
    fixtures = {}
    for mixamo in (False, True):
        tag = "mixamo" if mixamo else "metarig"
        fixtures[mixamo] = probe.build_volume_fixture(f"gate_{tag}_base", mixamo=mixamo)
    check(
        "GATE-FIXTURE",
        all(f["n_weighted"] > 0 for f in fixtures.values()),
        "the probe's builders, ONE fixture copy (the motion_fixture rule)",
    )

    # ---- GATE-APPLY (the real addon apply; one scene, object-scoped) --------
    apply_ok = True
    apply_notes: list[str] = []
    for mixamo in (False, True):
        tag = "mixamo" if mixamo else "metarig"
        fx = fixtures[mixamo]
        for cls in sorted(probe.vc.REF_CLASSES):
            factors = factors_of(cls)
            before = joint_bytes(fx["arm"])
            rep = addon_vol.apply_volume_sculpt(fx["arm"], fx["mesh"], factors, fx["role_to_bone"])
            bpy.context.view_layer.update()
            after = joint_bytes(fx["arm"])
            identical = before == after
            keys_ok = sorted(rep["values"]) == sorted(core.BAND_PARAMS)
            apply_ok &= rep["applied"] and identical and keys_ok
            apply_notes.append(f"{tag}/{cls}: joints {'ok' if identical else 'MOVED'}")
    check("GATE-APPLY", apply_ok, "; ".join(apply_notes) + " — keys by convention name, values absolute")

    # ---- GATE-WIDTH (per-case CLEAN scenes; the width loop wipes) -----------
    width_ok = True
    width_notes: list[str] = []
    for mixamo in (False, True):
        tag = "mixamo" if mixamo else "metarig"
        for cls in sorted(probe.vc.REF_CLASSES):
            factors = factors_of(cls)
            fresh_scene()
            fx2 = probe.build_volume_fixture(f"gate_{tag}_{cls}_width", mixamo=mixamo)
            ba = extents_before_after(fx2, factors)
            for param, (b, a) in ba.items():
                if b <= 1e-9:
                    continue
                ratio = a / b
                want = factors[param]
                width_ok &= abs(ratio - want) <= 0.10
                width_notes.append(f"{tag}/{cls}/{param}: {ratio:.4f} vs {want:.2f}")
    check("GATE-WIDTH", width_ok, "mid-band extents vs solved factors (bar 10%): " + "; ".join(width_notes))

    # ---- GATE-EDITABLE (fresh scene; the width loop wiped everything) -------
    fresh_scene()
    fxe = probe.build_volume_fixture("gate_editable", mixamo=False)
    factors = {"vol.hip_w": 1.2, "vol.waist_w": 1.1, "vol.chest_w": 1.15, "vol.thigh_w": 1.2}
    addon_vol.apply_volume_sculpt(fxe["arm"], fxe["mesh"], factors, fxe["role_to_bone"])
    drift = addon_vol.measure_zero_restore(fxe["mesh"])
    check("GATE-EDITABLE", drift <= 1e-4, f"zero-value restore drift {drift:.2e} m (bar 1e-04, the artist exit)")

    # ---- GATE-NOTARGET --------------------------------------------------------
    fxn = probe.build_volume_fixture("gate_notarget", with_mesh=False)
    repn = addon_vol.apply_volume_sculpt(fxn["arm"], None, {"vol.hip_w": 1.2}, fxn["role_to_bone"])
    loud = (not repn["applied"]) and repn["capability_lines"] == [core.CAPABILITY_NO_MESH]
    check("GATE-NOTARGET", bool(loud), repn["capability_lines"][0] if repn["capability_lines"] else "NO LINE")

    # ---- GATE-TWIN ---------------------------------------------------------------
    twins = []
    for name in ("gate_twin1", "gate_twin2"):
        fresh_scene()
        fxd = probe.build_volume_fixture(name, mixamo=False)
        factors = {"vol.hip_w": 1.2, "vol.waist_w": 1.0, "vol.chest_w": 1.1, "vol.thigh_w": 1.15}
        addon_vol.apply_volume_sculpt(fxd["arm"], fxd["mesh"], factors, fxd["role_to_bone"])
        kb = fxd["mesh"].data.shape_keys.key_blocks
        twins.append({k.name: (k.value, [tuple(v.co) for v in k.data]) for k in kb if k.name != "Basis"})
    identical = twins[0].keys() == twins[1].keys() and all(
        twins[0][k][0] == twins[1][k][0] and list(twins[0][k][1]) == list(twins[1][k][1]) for k in twins[0]
    )
    check("GATE-TWIN", identical, f"{len(twins[0])} keys byte-identical (values + unit-warp data)")

    check("GATE", OK, "the gate's rows above are the contract")
    return 0 if OK else 1


def factors_of(cls: str) -> dict[str, float]:
    """The reference class's factors (the declared deltas, verbatim)."""
    d = probe.vc.REF_CLASSES[cls]
    return {
        "vol.hip_w": d["hip"],
        "vol.waist_w": d["waist"],
        "vol.chest_w": d["chest"],
        "vol.thigh_w": d["thigh"],
    }


if __name__ == "__main__":
    sys.exit(main())
