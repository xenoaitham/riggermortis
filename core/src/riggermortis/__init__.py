"""riggermortis-core: local, rig-agnostic posing & animation engine.

Blender-independent by design: the Blender add-on and the MCP server are thin
frontends over this package. Phase 0 shipped the canonical skeleton, the
bone-role mapper, per-rig presets, and the content-policy module; Phase 1 adds
the pose solve (canonical_pose), FK apply (fk_apply), and pose payloads
(D-009) that the add-on consumes in-process.
"""
from __future__ import annotations

from .action import (
    ActionFrame,
    CanonicalAction,
    HipStabReport,
    action_from_poses,
    condition_action,
    load_action,
    stabilize_hips,
)
from .canonical import ALL_ROLES, CORE_ROLES, side_of
from .canonical_pose import CanonicalPose
from .contacts import (
    LOCK_CHAIN_BASES,
    ContactInterval,
    ContactReport,
    LockReport,
    SlideReport,
    attach_contacts,
    detect_contacts,
    foot_slide,
    lock_feet,
)
from .errors import (
    BridgeError,
    MappingError,
    PayloadError,
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
from .policy import (
    ADULT_MODULE_DISABLED,
    INVALID_REQUEST,
    MINOR_CONTENT,
    REAL_PERSON_EXPLICIT,
    ContentCategory,
    PolicyEngine,
    Refusal,
)
from .review import (
    ReviewItem,
    joint_points,
    pick_joint,
    review_items,
    skeleton_segments,
)
from .types import BoneData, RigData

__version__ = "0.0.1"

__all__ = [
    "__version__",
    "ALL_ROLES",
    "CORE_ROLES",
    "ActionFrame",
    "BoneData",
    "BoneRotation",
    "CanonicalAction",
    "CanonicalPose",
    "ContactInterval",
    "ContactReport",
    "HipStabReport",
    "LOCK_CHAIN_BASES",
    "LockReport",
    "PoseApplication",
    "RigData",
    "RigMapping",
    "RoleAssignment",
    "SlideReport",
    "action_from_poses",
    "apply_canonical_pose",
    "attach_contacts",
    "bone_target_direction",
    "condition_action",
    "detect_contacts",
    "foot_slide",
    "lock_feet",
    "verify_application",
    "map_rig",
    "side_of",
    "stabilize_hips",
    "load_action",
    "PolicyEngine",
    "Refusal",
    "ContentCategory",
    "MINOR_CONTENT",
    "REAL_PERSON_EXPLICIT",
    "ADULT_MODULE_DISABLED",
    "INVALID_REQUEST",
    "RiggermortisError",
    "RigLoadError",
    "MappingError",
    "PresetError",
    "PayloadError",
    "PolicyError",
    "BridgeError",
    "ReviewItem",
    "review_items",
    "skeleton_segments",
    "joint_points",
    "pick_joint",
]
