"""riggermortis-core: local, rig-agnostic posing & animation engine.

Blender-independent by design: the Blender add-on and the MCP server are thin
frontends over this package. Phase 0 shipped the canonical skeleton, the
bone-role mapper, per-rig presets, and the content-policy module; Phase 1 adds
the pose solve (canonical_pose), FK apply (fk_apply), and pose payloads
(D-009) that the add-on consumes in-process.
"""
from __future__ import annotations

from .canonical import ALL_ROLES, CORE_ROLES, side_of
from .canonical_pose import CanonicalPose
from .errors import (
    BridgeError,
    MappingError,
    PolicyError,
    PresetError,
    RiggermortisError,
    RigLoadError,
)
from .fk_apply import (
    BoneRotation,
    PoseApplication,
    apply_canonical_pose,
    bone_target_direction,
    verify_application,
)
from .mapper import RigMapping, RoleAssignment, map_rig
from .policy import ContentCategory, PolicyEngine, Refusal
from .review import ReviewItem, review_items, skeleton_segments
from .types import BoneData, RigData

__version__ = "0.0.1"

__all__ = [
    "__version__",
    "ALL_ROLES",
    "CORE_ROLES",
    "BoneData",
    "BoneRotation",
    "CanonicalPose",
    "PoseApplication",
    "RigData",
    "RigMapping",
    "RoleAssignment",
    "apply_canonical_pose",
    "bone_target_direction",
    "verify_application",
    "map_rig",
    "side_of",
    "PolicyEngine",
    "Refusal",
    "ContentCategory",
    "RiggermortisError",
    "RigLoadError",
    "MappingError",
    "PresetError",
    "PolicyError",
    "BridgeError",
    "ReviewItem",
    "review_items",
    "skeleton_segments",
]
