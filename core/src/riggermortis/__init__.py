"""riggermortis-core: local, rig-agnostic posing & animation engine.

Blender-independent by design: the Blender add-on and the MCP server are thin
frontends over this package. Phase 0 ships the canonical skeleton, the
bone-role mapper, per-rig presets, and the content-policy module.
"""
from __future__ import annotations

from .errors import (
    BridgeError,
    MappingError,
    PolicyError,
    PresetError,
    RiggermortisError,
    RigLoadError,
)
from .mapper import RigMapping, RoleAssignment, map_rig
from .policy import ContentCategory, PolicyEngine, Refusal
from .types import BoneData, RigData

__version__ = "0.0.1"

__all__ = [
    "__version__",
    "BoneData",
    "RigData",
    "RigMapping",
    "RoleAssignment",
    "map_rig",
    "PolicyEngine",
    "Refusal",
    "ContentCategory",
    "RiggermortisError",
    "RigLoadError",
    "MappingError",
    "PresetError",
    "PolicyError",
    "BridgeError",
]
