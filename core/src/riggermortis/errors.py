"""Error hierarchy.

Every error surfaced to a user or an agent carries an actionable message and,
where possible, a ``hint`` describing how to fix it. Nothing in this project
ever dumps a raw traceback at a frontend: the add-on reports ``str(exc)`` and
the MCP server maps these to structured error objects.
"""
from __future__ import annotations


class RiggermortisError(Exception):
    """Base class for all engine errors."""

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        if self.hint:
            return f"{self.message} (hint: {self.hint})"
        return self.message


class RigLoadError(RiggermortisError):
    """A rig file could not be read or contains no usable armature."""


class MappingError(RiggermortisError):
    """Bone-role mapping failed or produced an unusable result."""


class PresetError(RiggermortisError):
    """A per-rig preset is missing, malformed, or does not match the rig."""


class PolicyError(RiggermortisError):
    """A content-policy configuration attempt was invalid."""


class SecondaryError(RiggermortisError):
    """A secondary-motion chain spec or simulation input is invalid."""


class BridgeError(RiggermortisError):
    """The Blender headless bridge failed (missing binary, bad script output)."""


class InferenceError(RiggermortisError):
    """A managed model is missing, tampered with, or a download failed."""


class PayloadError(RiggermortisError):
    """A pose/detection payload is malformed, unsupported, or missing a figure."""
