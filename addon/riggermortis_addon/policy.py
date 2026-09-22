"""Add-on side of the content policy (docs/POLICY.md).

The engine lives in core (``riggermortis.policy``); this module is the thin
binding that keeps the add-on honest about it:

* the add-on's ``PolicyEngine`` is ALWAYS built through the default (SFW)
  path — the core itself forbids constructing one with the module enabled;
* the two preferences toggles ("Enable 18+ module" + "I understand the
  policy") are the only user-facing path, and syncing routes through
  ``enable_adult_module(confirm=True)`` / ``disable_adult_module()`` — the
  documented calls — never through any shortcut;
* nothing agent-facing can reach either toggle: this module only ever reads
  the add-on preferences, so the MCP server (a separate process) has no
  enable path at all and runs a fresh SFW engine per call.

bpy-free at import: unit tests exercise the binding headlessly (the tests
mount this package without executing the bpy-importing ``__init__``); the
REAL preferences flow runs in the Blender gate (``xtask/blender_verify.sh``,
``RM_POLICY`` lines).
"""
from __future__ import annotations

from typing import Any

#: The documented check subjects (mirrors ``PolicyEngine.check_explicit_request``).
SUBJECTS = ("minor", "real_person", "fictional_adult", "other")

_ENABLE_HINT = (
    "hint: enable the 18+ module in Preferences > Add-ons > Riggermortis "
    "(two toggles, explicit confirmation required) — docs/POLICY.md"
)

_engine: Any = None


def _reset_engine() -> None:
    """Drop the module-level engine (add-on reload / unit-test isolation).

    The next :func:`engine` call rebuilds through the default (SFW) path.
    """
    global _engine
    _engine = None


def engine() -> Any:
    """The add-on's shared ``PolicyEngine`` — built through the default path.

    Raises ``ImportError`` with the actionable install hint when
    ``riggermortis-core`` is not installed in Blender's Python.
    """
    global _engine
    if _engine is None:
        from .bpy_bridge import import_core

        _engine = import_core().PolicyEngine()
    return _engine


def sync(adult_module_enabled: bool, adult_module_confirm: bool) -> bool:
    """Derive the engine state from the two preference toggles.

    Enabled requires BOTH toggles; the enable always goes through the
    documented ``enable_adult_module(confirm=True)`` and the disable through
    ``disable_adult_module()`` — both idempotent, both core-validated.
    Returns the resulting engine state.
    """
    eng = engine()
    if bool(adult_module_enabled) and bool(adult_module_confirm):
        eng.enable_adult_module(confirm=True)
    else:
        eng.disable_adult_module()
    return eng.adult_module_enabled


def sync_from_preferences() -> bool:
    """Read the two toggles from the add-on preferences and :func:`sync`.

    Falls back to the fresh-install defaults (both off) when bpy is absent
    (unit tests) or the add-on has no preferences entry yet. Core-import
    errors propagate — callers decide how to surface them (``register()``
    ignores them; the check operator reports the install hint).
    """
    enabled = confirm = False
    try:
        import bpy

        prefs = bpy.context.preferences.addons[__package__].preferences
        enabled = bool(prefs.adult_module_enabled)
        confirm = bool(prefs.adult_module_confirm)
    except Exception:  # noqa: BLE001 — no bpy / no prefs entry: fresh defaults
        pass
    return sync(enabled, confirm)


def check(subject: str) -> Any:
    """Evaluate a content subject; returns the core ``Refusal`` or ``None``."""
    return engine().check_explicit_request(subject)


def format_refusal(refusal: Any) -> str:
    """The add-on report line: the refusal code VERBATIM, then the message.

    Only the retryable refusal (``adult_module_disabled``) carries the
    preferences hint — the hard lines are never presented as fixable.
    """
    line = f"refused [{refusal.code}] {refusal.message}"
    if refusal.retryable:
        line += f" ({_ENABLE_HINT})"
    return line


def status_lines() -> list[str]:
    """Short panel readout: module state + the untoggleable hard lines."""
    eng = engine()
    state = "ENABLED (18+ module, confirmed)" if eng.adult_module_enabled else "SFW (default)"
    return [f"module: {state}"] + [f"hard line: {text}" for text in eng.status()["hard_lines"]]
