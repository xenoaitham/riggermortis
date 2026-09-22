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


def addon_policy_module():
    """Import ``addon/riggermortis_addon/policy.py`` headlessly.

    The add-on package ``__init__`` imports ``bpy`` at module scope, which a
    test interpreter does not have — so the package is mounted as a bare
    module with ``__path__`` (submodule imports resolve, ``__init__`` never
    executes). The policy module itself is bpy-free at import by design
    (P6-4); the REAL bpy preferences flow is gated in
    ``xtask/blender_verify.sh`` (``RM_POLICY`` lines).
    """
    name = "riggermortis_addon"
    pkg = sys.modules.get(name)
    if pkg is None:
        pkg = types.ModuleType(name)
        pkg.__path__ = [str(ADDON_PKG_DIR)]
        sys.modules[name] = pkg
    return importlib.import_module("riggermortis_addon.policy")
