"""Bone-name heuristics: turn a bone name into role evidence.

Handles Rigify (``spine.001``), Mixamo (``mixamorig:LeftUpLeg``), VRM
(``J_Bip_L_UpperArm``), Unreal-style (``thigh_l``) and arbitrary custom names.
Exact-name overrides exist because a few families lie: Mixamo's ``LeftLeg``
is the *shin*, not the thigh.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .canonical import CENTER, LEFT, RIGHT

_SIDE_TOKENS: dict[str, set[str]] = {
    LEFT: {"l", "left"},
    RIGHT: {"r", "right"},
    CENTER: {"c", "center", "centre"},
}

#: Tokens that mark infrastructure or non-pose bones: never map them.
#: ``mch`` is Rigify mechanism bone prefix (never a pose target); ``parent``
#: marks Rigify IK/FK parenting helpers.
_SKIP_TOKENS: set[str] = {
    "twist", "roll", "ik", "fk", "target", "pole", "prop", "gizmo", "helper",
    "placeholder", "tweak", "eye", "eyelid", "eyes", "jaw", "teeth", "tongue",
    "thumb", "index", "middle", "ring", "pinky", "finger", "fingers", "breast",
    "hair", "skirt", "cloth", "slot", "camera", "light", "wheel", "door",
    "mch", "parent",
}

#: Noise tokens from structured families (VRM's ``J_Bip_`` etc).
_NOISE_TOKENS: set[str] = {"j", "bip", "def", "org", "mch", "ctl", "ctrl", "mixamorig"}

#: Family-specific overrides applied to the joined name (side tokens included,
#: e.g. "leftleg"). Mixamo lies: its "LeftLeg" is the shin.
_EXACT_OVERRIDES: dict[str, tuple[str, float]] = {
    "leftleg": ("lower_leg", 0.95),
    "rightleg": ("lower_leg", 0.95),
    "leftupleg": ("upper_leg", 0.95),
    "rightupleg": ("upper_leg", 0.95),
    "lefttoebase": ("toe", 0.92),
    "righttoebase": ("toe", 0.92),
}

#: (joined token string OR single token) -> (base role, weight). Checked
#: longest-joined first; single-token fallback gets x0.9.
_LEXICON_ITEMS: list[tuple[str, str, float]] = [
    ("upperchest", "chest", 0.92), ("chest", "chest", 0.90),
    ("spine", "spine", 0.85),
    ("pelvis", "hips", 0.92), ("hips", "hips", 0.92), ("hip", "hips", 0.85),
    ("neck", "neck", 0.90), ("head", "head", 0.92),
    ("clavicle", "shoulder", 0.88), ("shoulder", "shoulder", 0.85), ("collar", "shoulder", 0.70),
    ("upperarm", "upper_arm", 0.92), ("uparm", "upper_arm", 0.88),
    ("bicep", "upper_arm", 0.85), ("arm", "upper_arm", 0.62),
    ("forearm", "forearm", 0.92), ("lowerarm", "forearm", 0.88), ("elbow", "forearm", 0.72),
    ("hand", "hand", 0.92), ("wrist", "hand", 0.85), ("palm", "hand", 0.70),
    ("upperleg", "upper_leg", 0.92), ("upleg", "upper_leg", 0.92),
    ("thigh", "upper_leg", 0.90), ("leg", "upper_leg", 0.55),
    ("lowerleg", "lower_leg", 0.92), ("shin", "lower_leg", 0.90),
    ("calf", "lower_leg", 0.85), ("knee", "lower_leg", 0.68),
    ("foot", "foot", 0.92), ("ankle", "foot", 0.70),
    ("toebase", "toe", 0.92), ("toe", "toe", 0.90), ("ball", "toe", 0.60),
    ("root", "root", 0.80), ("origin", "root", 0.75), ("master", "root", 0.70),
]
_LEXICON: dict[str, tuple[str, float]] = {k: (b, w) for k, b, w in _LEXICON_ITEMS}

_CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[0-9]+|[A-Z]+")
_SEPARATORS = re.compile(r"[._\-:\s]+")


@dataclass(frozen=True)
class NameEvidence:
    """What a bone's name says about its role."""

    role: str | None  # full canonical role when side is known, else None
    role_base: str | None  # base role when side is unknown (paired roles)
    score: float  # 0..1 name confidence
    side: str  # CENTER/LEFT/RIGHT as detected
    chain_index: int | None  # trailing numeric index, e.g. spine.001 -> 1
    reason: str
    skip: bool = False  # True = non-pose bone, do not map


def split_tokens(name: str) -> list[str]:
    """Lowercase and split a bone name into tokens.

    Handles separators (``. _ - :``), camelCase (``LeftUpLeg``), and numeric
    indices (``spine.001`` -> ``["spine", "001"]``).
    """
    tokens: list[str] = []
    for part in _SEPARATORS.split(name):
        if not part:
            continue
        for m in _CAMEL.finditer(part):
            tok = m.group(0).lower()
            if tok:
                tokens.append(tok)
    return tokens


def evidence(name: str) -> NameEvidence:
    raw = [t for t in split_tokens(name) if t not in _NOISE_TOKENS]
    joined_all = "".join(raw)  # side tokens and digits included, for overrides
    digits = [t for t in raw if t.isdigit()]
    chain_index = int(digits[-1]) if digits else None
    kept = [t for t in raw if not t.isdigit()]

    side, remaining = _extract_side(kept)

    # Skip tokens are checked against the pre-strip tokens too, so prefixed
    # mechanism bones (``MCH-spine``) are caught even though the prefix itself
    # is normally stripped as noise.
    skip_hit = next((t for t in raw if t in _SKIP_TOKENS), None)
    if skip_hit is None:
        skip_hit = next((t for t in remaining if t in _SKIP_TOKENS), None)
    if skip_hit is not None:
        return NameEvidence(None, None, 0.0, side, chain_index, f"non-pose token {skip_hit!r}", skip=True)

    if joined_all in _EXACT_OVERRIDES:
        base, score = _EXACT_OVERRIDES[joined_all]
        role = _attach_side(base, side)
        if role is None:
            return NameEvidence(None, base, score, side, chain_index, "exact override (side unresolved)")
        return NameEvidence(role, None, score, side, chain_index, "exact override")

    joined = "".join(remaining)
    hit = _lookup_lexicon(joined, remaining)
    if hit is None:
        return NameEvidence(None, None, 0.0, side, chain_index, "no lexicon match")
    base, score, why = hit
    if base == "hips" and side != CENTER:
        # e.g. Rigify's pelvis.L/.R flanks: half a pelvis, not the center hips.
        return NameEvidence(None, None, 0.0, side, chain_index, "side-marked pelvis/hips flank is not the center hips")
    role = _attach_side(base, side)
    if role is None:
        return NameEvidence(None, base, score, side, chain_index, why)
    return NameEvidence(role, None, score, side, chain_index, why)


def family_signature(name: str) -> tuple[str, int | None]:
    """Prefix- and side-insensitive family identity: (joined base, chain index).

    ``DEF-spine``, ``ORG-spine`` and ``spine`` share ``("spine", None)``;
    ``spine.001`` is ``("spine", 1)``. Used to keep duplicate-namespace copies
    of a bone from taking a role already claimed by the original.
    """
    raw = [t for t in split_tokens(name) if t not in _NOISE_TOKENS]
    digits = [t for t in raw if t.isdigit()]
    chain_index = int(digits[-1]) if digits else None
    kept = [t for t in raw if not t.isdigit()]
    _, remaining = _extract_side(kept)
    return "".join(remaining), chain_index


def _extract_side(tokens: list[str]) -> tuple[str, list[str]]:
    for i, tok in enumerate(tokens):
        for side, names in _SIDE_TOKENS.items():
            if tok in names:
                rest = tokens[:i] + tokens[i + 1:]
                return side, rest
    return CENTER, list(tokens)


def _attach_side(base: str, side: str) -> str | None:
    """Attach a detected side to a base role; None if side is still unknown."""
    _PAIRED = {"shoulder", "upper_arm", "forearm", "hand", "upper_leg", "lower_leg", "foot", "toe"}
    if base in _PAIRED:
        if side == LEFT:
            return f"{base}.{LEFT}"
        if side == RIGHT:
            return f"{base}.{RIGHT}"
        return None  # paired role, side unresolved: geometry decides
    return base


def _lookup_lexicon(joined: str, tokens: list[str]) -> tuple[str, float, str] | None:
    if joined and joined in _LEXICON:
        base, score = _LEXICON[joined]
        return base, score, f"lexicon:{joined}"
    for tok in sorted(tokens, key=lambda t: (-len(t), t)):
        if tok in _LEXICON:
            base, score = _LEXICON[tok]
            return base, score * 0.9, f"lexicon:{tok}"
    return None
