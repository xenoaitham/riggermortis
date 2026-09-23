"""Make the core importable for tests whether or not it is pip-installed."""
from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

ADDON_PKG_DIR = SRC.parents[1] / "addon" / "riggermortis_addon"


def addon_module(name: str):
    """Import an add-on submodule headlessly.

    The add-on package ``__init__`` imports ``bpy`` at module scope, which a
    test interpreter does not have — so the package is mounted as a bare
    module with ``__path__`` (submodule imports resolve, ``__init__`` never
    executes). Only for modules that are bpy-free at import by design (the
    add-on convention: bpy imports live inside functions — bake.py,
    policy.py, clip_sample.py, ...); the REAL bpy flows run in the Blender
    gates (``xtask/blender_verify.sh``, ``xtask/verify_pose_apply.sh``).
    """
    pkg = sys.modules.get("riggermortis_addon")
    if pkg is None:
        pkg = types.ModuleType("riggermortis_addon")
        pkg.__path__ = [str(ADDON_PKG_DIR)]
        sys.modules["riggermortis_addon"] = pkg
    return importlib.import_module(f"riggermortis_addon.{name}")


def addon_policy_module():
    """The P6-4 policy binding (kept for the P6-5 enforcement tests)."""
    return addon_module("policy")
