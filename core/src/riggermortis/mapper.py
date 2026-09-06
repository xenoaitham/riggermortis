"""Bone-role mapping v1: names + geometry -> canonical roles, with honesty.

The mapper produces a :class:`RigMapping` for any humanoid-ish armature:
per-role assignments with confidence, the evidence behind each decision, an
ambiguity list for the 30-second review UI, and no silent failures. A rig that
cannot be mapped confidently is *reported* as such — silence is a bug.

Algorithm (deterministic: every sort is keyed, same input -> same output):
1. Structural pre-pass: a parentless-fork bone at hip height is the hips when
   names are silent (and its prefix duplicates are barred from ``spine``);
   catches Rigify metarigs whose hips bone is lexicon-named ``spine``.
2. Name pass: lexicon/override evidence, role-major greedy assignment with
   prefix preference (unprefixed controls > ``DEF-`` > ``ORG-``).
3. Chain promotion: leftover same-lexicon spine bones fill chest/neck/head by
   height order (handles ``spine.001``-style families and Mixamo Spine1/2).
4. Geometry pass for still-empty roles: spine chain by ordering, limb chains
   by direction/proportion, sides by x-offset. Geometry-only confidence is
   capped so it never looks more certain than it is.
5. Quadruped/ambiguity detection and reporting.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from . import geometry as geo
from . import names as names_mod
from .canonical import ALL_ROLES, CORE_ROLES, LEFT, RIGHT, role_def
from .errors import MappingError
from .types import RigData

GEOMETRY_CONF_CAP = 0.75
AMBIGUOUS_CONF = 0.55
SIDE_CONFLICT_PENALTY = 0.3
SIDE_UNKNOWN_PENALTY = 0.8


@dataclass
class RoleAssignment:
    role: str
    bone: str
    confidence: float
    side: str
    evidence: list[str] = field(default_factory=list)
    ambiguous: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "role": self.role,
            "bone": self.bone,
            "confidence": round(self.confidence, 3),
            "side": self.side,
            "evidence": self.evidence,
            "ambiguous": self.ambiguous,
        }


@dataclass
class RigMapping:
    rig_name: str
    fingerprint: str
    assignments: dict[str, RoleAssignment] = field(default_factory=dict)
    unmapped_bones: list[str] = field(default_factory=list)
    skipped_bones: list[str] = field(default_factory=list)
    ambiguities: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def role_of(self, bone: str) -> str | None:
        for a in self.assignments.values():
            if a.bone == bone:
                return a.role
        return None

    def core_missing(self) -> list[str]:
        return [r for r in ALL_ROLES if r in CORE_ROLES and r not in self.assignments]

    def to_dict(self) -> dict[str, object]:
        return {
            "rig_name": self.rig_name,
            "fingerprint": self.fingerprint,
            "assignments": {r: a.to_dict() for r, a in sorted(self.assignments.items())},
            "unmapped_bones": list(self.unmapped_bones),
            "skipped_bones": list(self.skipped_bones),
            "ambiguities": list(self.ambiguities),
            "notes": list(self.notes),
            "core_missing": self.core_missing(),
        }

    def table(self) -> str:
        rows = ["role            bone                conf  notes"]
        for role in ALL_ROLES:
            a = self.assignments.get(role)
            if a is None:
                marker = "MISSING (core)" if role in CORE_ROLES else "not found"
                rows.append(f"{role:<15} {'-':<19} {'-':<5} {marker}")
                continue
            notes = []
            if a.ambiguous:
                notes.append("review")
            if a.evidence:
                notes.append("; ".join(a.evidence))
            rows.append(f"{role:<15} {a.bone:<19} {a.confidence:.2f}  {' | '.join(notes)}")
        return "\n".join(rows)

    def summary(self) -> str:
        lines = [
            f"rig: {self.rig_name} (fingerprint {self.fingerprint})",
            f"roles assigned: {len(self.assignments)}/{len(ALL_ROLES)}",
        ]
        missing = self.core_missing()
        if missing:
            lines.append(f"core roles missing: {', '.join(missing)}")
        if self.ambiguities:
            lines.append(f"ambiguities to review: {len(self.ambiguities)}")
            lines.extend(f"  - {a}" for a in self.ambiguities)
        for note in self.notes:
            lines.append(f"note: {note}")
        if self.unmapped_bones:
            lines.append(f"unmapped bones ({len(self.unmapped_bones)}): {', '.join(self.unmapped_bones)}")
        if not missing and not self.ambiguities:
            lines.append("mapping looks complete; review recommended before posing")
        return "\n".join(lines)


def map_rig(
    rig: RigData,
    *,
    use_names: bool = True,
    use_geometry: bool = True,
    preset_mapping: dict[str, str] | None = None,
) -> RigMapping:
    """Map a rig to canonical roles. See module docstring for the algorithm."""
    if not rig.bones:
        raise MappingError("rig has no bones", hint="re-export the armature")
    feats = geo.analyze(rig)
    mapping = RigMapping(rig_name=rig.name, fingerprint=rig.fingerprint())
    taken: dict[str, str] = {}  # bone -> role

    evidence = {name: names_mod.evidence(name) for name in rig.sorted_bone_names()}

    blocked_spine: set[str] = set()
    if use_geometry:
        blocked_spine = _structural_hips(rig, feats, evidence, mapping, taken)

    if use_names:
        _name_pass(rig, feats, evidence, mapping, taken, blocked_spine)
        _chain_promotion(rig, feats, evidence, mapping, taken)
    if use_geometry:
        _geometry_pass(rig, feats, evidence, mapping, taken)

    _apply_preset(mapping, taken, preset_mapping)

    assigned_bones = {a.bone for a in mapping.assignments.values()}
    mapping.unmapped_bones = [
        n for n in rig.sorted_bone_names() if n not in assigned_bones and not evidence[n].skip
    ]
    mapping.skipped_bones = sorted(n for n in rig.sorted_bone_names() if evidence[n].skip)
    _detect_quadruped(rig, feats, evidence, mapping, taken)
    _flag_low_confidence(mapping)
    return mapping


# --------------------------------------------------------------------------
# pass 0: structure
# --------------------------------------------------------------------------

def _structural_fork(rig: RigData, feats: geo.RigFeatures) -> str | None:
    """The textbook-hips bone: forks to downward limb chains on BOTH character
    sides at hip height. The both-sides requirement separates a pelvis fork
    (thigh.L + thigh.R) from a lowered hand fanning its fingers down.

    Deterministic: (most down-chain children desc, name asc).
    """
    best_key: tuple[int, str] | None = None
    for name in rig.sorted_bone_names():
        down = [
            c for c in rig.children(name)
            if feats.bones[c].direction[2] < -0.5
        ]
        if len(down) < 2:
            continue
        if not {geo.side_sign(feats.bones[c]) for c in down} >= {"L", "R"}:
            continue
        if not 0.4 < feats.bones[name].head_z_frac < 0.7:
            continue
        key = (-len(down), name)
        if best_key is None or key < best_key:
            best_key = key
    return best_key[1] if best_key is not None else None


def _structural_hips(
    rig: RigData,
    feats: geo.RigFeatures,
    evidence: dict[str, names_mod.NameEvidence],
    mapping: RigMapping,
    taken: dict[str, str],
) -> set[str]:
    """Pin the structural fork to ``hips`` when no name claims that role, and
    bar the fork's prefix-duplicates from ``spine`` (they are the same bone in
    another namespace: ``ORG-spine``/``DEF-spine`` of a pinned ``spine``).

    Returns the set of bones barred from the ``spine`` role.
    """
    fork = _structural_fork(rig, feats)
    if fork is None:
        return set()
    blocked = {
        n for n in rig.sorted_bone_names()
        if names_mod.family_signature(n) == names_mod.family_signature(fork)
    }

    hips_claimed = any(
        e.role == "hips" for e in evidence.values() if not e.skip
    )
    if hips_claimed or fork in taken:
        return blocked

    _assign(
        mapping, taken, "hips", fork,
        geo.geometry_score(feats.bones[fork], role_def("hips")),
        "structural fork: limb fork spanning both sides at hip height (hip-role names were silent)",
    )
    # A single-child parentless bone directly above the fork is the root.
    parent = rig.bones[fork].parent
    if (
        parent is not None and parent in rig.bones
        and parent not in taken
        and rig.bones[parent].parent is None
        and rig.children(parent) == [fork]
    ):
        _assign(mapping, taken, "root", parent, 0.6, "geometry: parent above torso fork")
    return blocked


# --------------------------------------------------------------------------
# pass 1: names
# --------------------------------------------------------------------------

def _prefix_rank(bone: str) -> int:
    """Pose-target preference: unprefixed controls, then DEF-, then ORG-."""
    upper = bone.upper()
    if upper.startswith("DEF-"):
        return 1
    if upper.startswith("ORG-"):
        return 2
    if upper.startswith("MCH-"):
        return 3
    return 0


def _name_pass(
    rig: RigData,
    feats: geo.RigFeatures,
    evidence: dict[str, names_mod.NameEvidence],
    mapping: RigMapping,
    taken: dict[str, str],
    blocked_spine: set[str] | None = None,
) -> None:
    blocked = blocked_spine or set()
    candidates: dict[str, list[tuple[float, str, str]]] = {}  # role -> [(score, bone, why)]
    for bone in rig.sorted_bone_names():
        e = evidence[bone]
        if e.skip:
            continue
        target_roles: list[str] = []
        if e.role is not None:
            target_roles = [e.role]
        elif e.role_base is not None:  # paired role, side unresolved by name
            target_roles = [f"{e.role_base}.{LEFT}", f"{e.role_base}.{RIGHT}"]
        for role in target_roles:
            if role not in ALL_ROLES:
                continue
            if role == "spine" and bone in blocked:
                continue
            score = e.score
            whys = [e.reason]
            rd = role_def(role)
            if rd.side != "C" and e.side != "C":
                if rd.side != e.side:
                    score *= SIDE_CONFLICT_PENALTY
                    whys.append("side mismatch vs name")
            elif rd.side != "C" and e.side == "C":
                score *= SIDE_UNKNOWN_PENALTY
                whys.append("name side unknown")
            candidates.setdefault(role, []).append((score, bone, "; ".join(whys)))

    for role in sorted(candidates):
        entries = sorted(candidates[role], key=lambda t: (-t[0], _prefix_rank(t[1]), t[1]))
        for score, bone, why in entries:
            if bone in taken or role in mapping.assignments:
                continue
            if score <= 0.0:
                continue
            conf = 0.7 * score + 0.3 * geo.geometry_score(feats.bones[bone], role_def(role))
            mapping.assignments[role] = RoleAssignment(
                role=role, bone=bone, confidence=conf,
                side=role_def(role).side, evidence=[why],
            )
            taken[bone] = role


def _chain_promotion(
    rig: RigData,
    feats: geo.RigFeatures,
    evidence: dict[str, names_mod.NameEvidence],
    mapping: RigMapping,
    taken: dict[str, str],
) -> None:
    """Leftover bones sharing a lexicon base with chain roles fill empty slots
    in height order (bottom->top) among [spine, chest, neck, head]."""
    chain_roles = [r for r in ("spine", "chest", "neck", "head") if r not in mapping.assignments]
    if not chain_roles:
        return
    leftovers: list[tuple[float, str]] = []
    for bone in rig.sorted_bone_names():
        if bone in taken or evidence[bone].skip:
            continue
        e = evidence[bone]
        base = e.role.rsplit(".", 1)[0] if e.role else e.role_base
        if base in ("spine", "chest", "neck", "head"):
            leftovers.append((feats.bones[bone].head_z, bone))
    if not leftovers:
        return
    leftovers.sort(key=lambda t: (t[0], t[1]))
    # Intentional truncation: extra leftover bones stay unmapped and reported.
    for (_, bone), role in zip(leftovers, chain_roles, strict=False):
        conf = 0.7 * evidence[bone].score + 0.3 * geo.geometry_score(feats.bones[bone], role_def(role))
        mapping.assignments[role] = RoleAssignment(
            role=role, bone=bone, confidence=conf, side="C",
            evidence=["chain-order promotion"],
        )
        taken[bone] = role


# --------------------------------------------------------------------------
# pass 2: geometry
# --------------------------------------------------------------------------

def _geometry_pass(
    rig: RigData,
    feats: geo.RigFeatures,
    evidence: dict[str, names_mod.NameEvidence],
    mapping: RigMapping,
    taken: dict[str, str],
) -> None:
    mappable = {
        n for n in rig.sorted_bone_names()
        if n not in taken and not evidence[n].skip
    }

    _geometry_root_and_chain(rig, feats, mapping, taken, mappable)
    mappable -= set(taken)
    _geometry_legs(rig, feats, mapping, taken, mappable)
    mappable -= set(taken)
    _geometry_arms(rig, feats, mapping, taken, mappable)
    mappable -= set(taken)
    _geometry_shoulders(rig, feats, mapping, taken, mappable)


def _assign(mapping: RigMapping, taken: dict[str, str], role: str, bone: str,
            conf: float, ev: str) -> None:
    capped = min(conf, GEOMETRY_CONF_CAP)
    mapping.assignments[role] = RoleAssignment(
        role=role, bone=bone, confidence=capped, side=role_def(role).side,
        evidence=[ev], ambiguous=True,
    )
    taken[bone] = role
    # Geometry-decided roles always surface in the review checklist: honest
    # flagging means the reviewer sees every assignment the names did not make.
    mapping.ambiguities.append(
        f"{role}: {bone!r} assigned by geometry ({ev}); verify in review UI"
    )


def _geometry_root_and_chain(
    rig: RigData,
    feats: geo.RigFeatures,
    mapping: RigMapping,
    taken: dict[str, str],
    mappable: set[str],
) -> None:
    """Root + [hips, spine, chest, neck, head] filled in height order.

    A parentless single-child bone whose child is a torso fork is the root;
    a parentless fork near hip height is the hips itself (Mixamo has no root).
    """
    needed = [r for r in ("root", "hips", "spine", "chest", "neck", "head") if r not in mapping.assignments]
    if not needed:
        return
    up = {
        n for n in mappable
        if feats.bones[n].direction[2] > 0.5
        and feats.bones[n].head_z_frac > 0.3
    }
    roots = rig.roots()
    # Root/hips disambiguation for parentless bones.
    if "root" in needed or "hips" in needed:
        for r in roots:
            if r not in mappable:
                continue
            kids = rig.children(r)
            if len(kids) >= 2 and 0.4 < feats.bones[r].head_z_frac < 0.7:
                if "hips" in needed:
                    _assign(mapping, taken, "hips", r,
                            geo.geometry_score(feats.bones[r], role_def("hips")),
                            "geometry: parentless fork at hip height")
                    up.discard(r)
                break
            if len(kids) == 1 and kids[0] in mappable and len(rig.children(kids[0])) >= 2 \
                    and 0.4 < feats.bones[kids[0]].head_z_frac < 0.7:
                if "root" in needed:
                    _assign(mapping, taken, "root", r, 0.6, "geometry: parent above torso fork")
                    up.discard(r)
                if "hips" in needed:
                    _assign(mapping, taken, "hips", kids[0],
                            geo.geometry_score(feats.bones[kids[0]], role_def("hips")),
                            "geometry: torso fork below spine chain")
                    up.discard(kids[0])
                break

    chain_roles = [r for r in ("hips", "spine", "chest", "neck", "head") if r not in mapping.assignments]
    chain_cands = sorted(
        (n for n in up if n not in taken),
        key=lambda n: (feats.bones[n].head_z, n),
    )
    # The chain must be a plausible vertical stack: take candidates in height
    # order and only accept bones whose head is above the previously accepted.
    assigned_any = False
    last_z = -1.0
    for bone in chain_cands:
        if not chain_roles:
            break
        z = feats.bones[bone].head_z
        if z <= last_z + 1e-6:
            continue
        role = chain_roles.pop(0)
        _assign(mapping, taken, role, bone,
                geo.geometry_score(feats.bones[bone], role_def(role)),
                f"geometry: spine-chain order ({role})")
        last_z = z
        assigned_any = True
    if assigned_any:
        missing = [r for r in ("hips", "spine", "chest", "neck", "head") if r not in mapping.assignments]
        if missing:
            mapping.ambiguities.append(
                f"spine chain incomplete: {', '.join(missing)} could not be placed by geometry"
            )


def _is_duplicate_leg_view(rig: RigData, name: str, mapping: RigMapping) -> bool:
    """True if ``name`` is the same limb as an already-mapped upper leg seen
    from another namespace or as a bendy sub-segment of it: either co-located
    with the mapped leg's head (``ORG-thigh.L`` of mapped ``DEF-thigh.L``) or
    descending from the mapped leg bone (Rigify ``DEF-thigh.L.001``). Such
    bones are not genuinely extra limb chains."""
    for role, a in mapping.assignments.items():
        if not role.startswith("upper_leg."):
            continue
        other_head = rig.bones[a.bone].head
        head = rig.bones[name].head
        if all(abs(head[i] - other_head[i]) < 1e-3 for i in range(3)):
            return True
        cur = name
        seen: set[str] = set()
        while cur in rig.bones and cur not in seen:
            if cur == a.bone:
                return True
            seen.add(cur)
            cur = rig.bones[cur].parent or ""
    return False


def _leg_chain_tops(rig: RigData, feats: geo.RigFeatures, mappable: set[str]) -> list[str]:
    tops: list[str] = []
    for n in sorted(mappable):
        bf = feats.bones[n]
        if bf.direction[2] > -0.6:
            continue
        if not (0.2 < bf.length_frac < 0.9 and 0.30 < bf.head_z_frac < 0.85):
            continue
        parent = bf.parent
        if parent is not None and parent in mappable and feats.bones[parent].direction[2] < -0.6:
            continue  # child of another down-bone: not the chain top
        tops.append(n)
    return tops


def _geometry_legs(
    rig: RigData,
    feats: geo.RigFeatures,
    mapping: RigMapping,
    taken: dict[str, str],
    mappable: set[str],
) -> None:
    tops = [
        t for t in _leg_chain_tops(rig, feats, mappable)
        if not _is_duplicate_leg_view(rig, t, mapping)
    ]
    if not tops:
        return
    sides: dict[str, str] = {}
    for t in tops:
        sides[t] = geo.side_sign(feats.bones[t])

    chosen: dict[str, str] = {}  # role -> bone
    leftover: list[str] = []
    for side in (LEFT, RIGHT):
        role = f"upper_leg.{side}"
        if role in mapping.assignments:
            continue  # never clobber a name-pass assignment
        pool = [t for t in tops if sides[t] in (side, "C") and role not in chosen]
        pool.sort(key=lambda t: (-feats.bones[t].length, t))
        if pool:
            chosen[role] = pool[0]
    for t in tops:
        if t not in chosen.values():
            leftover.append(t)

    for side in (LEFT, RIGHT):
        top = chosen.get(f"upper_leg.{side}")
        if top is None:
            continue
        _assign(mapping, taken, f"upper_leg.{side}", top,
                geo.geometry_score(feats.bones[top], role_def(f"upper_leg.{side}")),
                "geometry: downward limb chain")
        if f"lower_leg.{side}" not in mapping.assignments:
            lo = [c for c in rig.children(top) if c in mappable and c not in taken
                  and feats.bones[c].direction[2] < -0.5]
            if lo:
                lower = sorted(lo, key=lambda c: (feats.bones[c].head_z, c))[0]
                _assign(mapping, taken, f"lower_leg.{side}", lower,
                        geo.geometry_score(feats.bones[lower], role_def(f"lower_leg.{side}")),
                        "geometry: leg chain continuation")
                foot_pool = [c for c in rig.children(lower) if c in mappable and c not in taken]
                foot_pool.sort(key=lambda c: (feats.bones[c].head_z, c))
                if foot_pool:
                    foot = foot_pool[0]
                    if f"foot.{side}" not in mapping.assignments:
                        _assign(mapping, taken, f"foot.{side}", foot,
                                geo.geometry_score(feats.bones[foot], role_def(f"foot.{side}")),
                                "geometry: foot at leg end")
                    toe_pool = [c for c in rig.children(foot) if c in mappable and c not in taken]
                    if toe_pool and f"toe.{side}" not in mapping.assignments:
                        toe = sorted(toe_pool, key=lambda c: (feats.bones[c].head_z, c))[0]
                        _assign(mapping, taken, f"toe.{side}", toe,
                                geo.geometry_score(feats.bones[toe], role_def(f"toe.{side}")),
                                "geometry: toe chain")

    for t in leftover:
        mapping.ambiguities.append(
            f"extra downward limb chain at {t!r} was not mapped; "
            f"if this is a quadruped, remap its front pair to arms"
        )


def _geometry_arms(
    rig: RigData,
    feats: geo.RigFeatures,
    mapping: RigMapping,
    taken: dict[str, str],
    mappable: set[str],
) -> None:
    tops: list[str] = []
    for n in sorted(mappable):
        bf = feats.bones[n]
        if abs(bf.direction[0]) < 0.5:
            continue
        if not (0.15 < bf.length_frac < 0.6 and bf.head_z_frac > 0.60):
            continue
        parent = bf.parent
        if parent is not None and parent in mappable and abs(feats.bones[parent].direction[0]) > 0.5:
            continue
        tops.append(n)
    if not tops:
        return
    sides = {t: geo.side_sign(feats.bones[t]) for t in tops}
    for side in (LEFT, RIGHT):
        pool = sorted(
            (t for t in tops if sides[t] in (side, "C") and f"upper_arm.{side}" not in mapping.assignments),
            key=lambda t: (-feats.bones[t].length, t),
        )
        if not pool:
            continue
        top = pool[0]
        _assign(mapping, taken, f"upper_arm.{side}", top,
                geo.geometry_score(feats.bones[top], role_def(f"upper_arm.{side}")),
                "geometry: sideways limb chain")
        fore = [c for c in rig.children(top) if c in mappable and c not in taken
                and abs(feats.bones[c].direction[0]) > 0.4]
        if fore and f"forearm.{side}" not in mapping.assignments:
            f = sorted(fore, key=lambda c: (-feats.bones[c].length, c))[0]
            _assign(mapping, taken, f"forearm.{side}", f,
                    geo.geometry_score(feats.bones[f], role_def(f"forearm.{side}")),
                    "geometry: arm chain continuation")
            hand_pool = [c for c in rig.children(f) if c in mappable and c not in taken]
            hand_pool.sort(key=lambda c: (feats.bones[c].head_z, c))
            if hand_pool and f"hand.{side}" not in mapping.assignments:
                h = hand_pool[0]
                _assign(mapping, taken, f"hand.{side}", h,
                        geo.geometry_score(feats.bones[h], role_def(f"hand.{side}")),
                        "geometry: hand at arm end")


def _geometry_shoulders(
    rig: RigData,
    feats: geo.RigFeatures,
    mapping: RigMapping,
    taken: dict[str, str],
    mappable: set[str],
) -> None:
    chest = mapping.assignments.get("chest")
    for side in (LEFT, RIGHT):
        role = f"shoulder.{side}"
        if role in mapping.assignments or role not in ALL_ROLES:
            continue
        arms = mapping.assignments.get(f"upper_arm.{side}")
        if arms is None:
            continue
        parent = rig.bones[arms.bone].parent
        if parent is None or parent not in mappable or parent in taken:
            continue
        if chest is not None and parent != chest.bone:
            continue
        pf = feats.bones[parent]
        if pf.length_frac > 0.3 or pf.head_z_frac < 0.6:
            continue
        _assign(mapping, taken, role, parent,
                geo.geometry_score(pf, role_def(role)), "geometry: short link above upper arm")


# --------------------------------------------------------------------------
# presets, quadruped, confidence flags
# --------------------------------------------------------------------------

def _apply_preset(
    mapping: RigMapping,
    taken: dict[str, str],
    preset_mapping: dict[str, str] | None,
) -> None:
    if not preset_mapping:
        return
    for role, bone in sorted(preset_mapping.items()):
        # Free the bone from any automatic assignment it currently holds.
        for r in [r for r, a in mapping.assignments.items() if a.bone == bone]:
            del mapping.assignments[r]
        taken.pop(bone, None)
        mapping.assignments[role] = RoleAssignment(
            role=role, bone=bone, confidence=1.0,
            side=role_def(role).side if role in ALL_ROLES else "C",
            evidence=["preset override"], ambiguous=False,
        )
        taken[bone] = role


def _detect_quadruped(
    rig: RigData,
    feats: geo.RigFeatures,
    evidence: dict[str, names_mod.NameEvidence],
    mapping: RigMapping,
    taken: dict[str, str],
) -> None:
    # Same mappable definition as the geometry legs pass: skipped non-pose
    # bones (fingers, ik helpers, ...) must never suggest quadrupedism.
    leg_tops = [
        t for t in _leg_chain_tops(
            rig, feats,
            {
                n for n in rig.sorted_bone_names()
                if n not in taken and not evidence[n].skip
            },
        )
        if not _is_duplicate_leg_view(rig, t, mapping)
    ]
    mapped_legs = sum(1 for r in mapping.assignments if r.startswith("upper_leg."))
    if mapped_legs + len(leg_tops) > 2:
        mapping.notes.append(
            f"possible quadruped rig: {mapped_legs + len(leg_tops)} downward limb chains found, "
            f"humanoid mapping covers two; review the flagged chains"
        )


def _flag_low_confidence(mapping: RigMapping) -> None:
    for role, a in sorted(mapping.assignments.items()):
        if a.confidence < AMBIGUOUS_CONF and not a.ambiguous:
            a.ambiguous = True
            a.evidence.append("low confidence")
            mapping.ambiguities.append(
                f"{role}: {a.bone!r} confidence {a.confidence:.2f} is low; verify in review UI"
            )


# --------------------------------------------------------------------------
# review UI API (30-second review)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ReviewItem:
    """One entry of the review checklist, in the order a human should see it."""

    kind: str  # "missing" | "low-conf" | "side-conflict"
    role: str
    detail: str

    def __str__(self) -> str:
        return f"[{self.kind}] {self.role}: {self.detail}"


def propose_reassignment(mapping: RigMapping, role: str, bone: str) -> RigMapping:
    """Return a copy of ``mapping`` with ``role`` assigned to ``bone``.

    Pure function: the input mapping is never mutated — the review UI shows
    the proposal and only writes it back (e.g. as a preset) when confirmed.

    The bone is freed from any role it currently holds (that role becomes
    unassigned and resurfaces in the checklist), the role's previous bone
    returns to the unmapped list, and the new assignment carries confidence
    1.0 with evidence ``["manual reassignment"]``: a human decision outranks
    the heuristics, and the mapping says so honestly.
    """
    if role not in ALL_ROLES:
        raise MappingError(
            f"unknown canonical role {role!r}",
            hint=f"canonical roles: {', '.join(ALL_ROLES)}",
        )
    known = {a.bone for a in mapping.assignments.values()}
    known |= set(mapping.unmapped_bones) | set(mapping.skipped_bones)
    if bone not in known:
        raise MappingError(
            f"bone {bone!r} is not part of rig {mapping.rig_name!r}",
            hint="run `rigpose inspect` for the exact bone names",
        )

    new = RigMapping(
        rig_name=mapping.rig_name,
        fingerprint=mapping.fingerprint,
        assignments={r: replace(a, evidence=list(a.evidence)) for r, a in mapping.assignments.items()},
        unmapped_bones=list(mapping.unmapped_bones),
        skipped_bones=list(mapping.skipped_bones),
        ambiguities=list(mapping.ambiguities),
        notes=list(mapping.notes),
    )

    freed_role: str | None = None
    for r in [r for r, a in new.assignments.items() if a.bone == bone]:
        if r != role:
            del new.assignments[r]
            freed_role = r
    old = new.assignments.pop(role, None)

    new.assignments[role] = RoleAssignment(
        role=role, bone=bone, confidence=1.0, side=role_def(role).side,
        evidence=["manual reassignment"],
    )
    new.unmapped_bones = sorted(
        {n for n in new.unmapped_bones if n != bone}
        | ({old.bone} if old is not None and old.bone != bone else set())
    )
    stale = {f"{role}:", f"{freed_role}:"} if freed_role else {f"{role}:"}
    new.ambiguities = [a for a in new.ambiguities if not a.startswith(tuple(stale))]
    new.notes.append(f"manual reassignment: {role} -> {bone}" +
                     (f" (freed {freed_role})" if freed_role else ""))
    return new


def ambiguity_rank(mapping: RigMapping) -> list[ReviewItem]:
    """The review UI's checklist order.

    Unresolved core roles first (posing is impossible without them), then
    assignments by ascending confidence (most suspect first), then remaining
    side-conflicts. Each role appears at most once. Deterministic: ties break
    by canonical role order.
    """
    items: list[ReviewItem] = []
    seen: set[str] = set()

    for role in mapping.core_missing():
        items.append(ReviewItem("missing", role, "core role has no bone; posing is blocked"))
        seen.add(role)

    conf_items = [
        (a.confidence, role) for role, a in mapping.assignments.items()
        if a.ambiguous and role not in seen
    ]
    conf_items.sort(key=lambda t: (t[0], ALL_ROLES.index(t[1])))
    for conf, role in conf_items:
        a = mapping.assignments[role]
        items.append(ReviewItem("low-conf", role, f"{a.bone!r} at confidence {conf:.2f}; verify"))
        seen.add(role)

    side_items = [
        role for role, a in mapping.assignments.items()
        if role not in seen and any("side mismatch" in ev for ev in a.evidence)
    ]
    side_items.sort(key=ALL_ROLES.index)
    for role in side_items:
        a = mapping.assignments[role]
        items.append(ReviewItem("side-conflict", role, f"{a.bone!r} name side contradicts the role"))
        seen.add(role)

    return items
