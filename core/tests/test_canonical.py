"""Canonical skeleton invariants."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from riggermortis import canonical  # noqa: E402
from riggermortis.canonical import ALL_ROLES, CANONICAL, CORE_ROLES, rest_skeleton  # noqa: E402
from riggermortis.linalg import v_len, v_sub  # noqa: E402


def test_all_parents_exist_and_acyclic():
    for role in ALL_ROLES:
        parent = CANONICAL[role].parent
        if parent is not None:
            assert parent in CANONICAL, f"{role} has unknown parent {parent}"
    # Walking up must terminate for every role (no cycles).
    for role in ALL_ROLES:
        seen: set[str] = set()
        cur = role
        while CANONICAL[cur].parent is not None:
            assert cur not in seen, f"cycle at {cur}"
            seen.add(cur)
            cur = CANONICAL[cur].parent


def test_paired_roles_are_symmetric():
    for role in ALL_ROLES:
        if "." not in role:
            continue
        mirror = canonical.mirror_role(role)
        assert mirror in CANONICAL
        a, b = CANONICAL[role], CANONICAL[mirror]
        if a.parent is None:
            assert b.parent is None
        elif "." in a.parent:
            assert a.parent == canonical.mirror_role(b.parent)
        else:
            assert a.parent == b.parent
        assert a.length_ratio == b.length_ratio
        assert a.height_band == b.height_band


def test_core_roles_are_roles():
    assert CORE_ROLES <= set(ALL_ROLES)


def test_rest_skeleton_is_connected_and_sized():
    rest = rest_skeleton(height=1.7)
    assert set(rest) == set(ALL_ROLES)
    for role, (head, tail) in rest.items():
        assert v_len(v_sub(tail, head)) > 1e-4, f"{role} has zero length"
    # spine chain continuity: each bone starts where its parent ends
    for child, parent in (("spine", "hips"), ("chest", "spine"), ("neck", "chest"), ("head", "neck")):
        assert rest[child][0] == rest[parent][1], f"{child} does not start at {parent} tail"
    # character-left arm extends toward +X
    ua = rest["upper_arm.L"]
    assert ua[1][0] > ua[0][0]
    # legs descend from the hips
    assert rest["upper_leg.L"][1][2] < rest["upper_leg.L"][0][2]
