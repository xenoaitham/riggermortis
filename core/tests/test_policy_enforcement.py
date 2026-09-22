"""P6-5 enforcement tests: the 18+ module is OFF by default through BOTH
frontends, refusal codes surface verbatim, and there is no side door.

Layer map (mirrors how every other surface is tested here):

- CORE — the PolicyEngine contract (default SFW, construction guard,
  ``enable_adult_module(confirm=True)`` as the only enable path) is pinned
  in ``test_policy.py`` since P0-10; the strictness additions below pin the
  two-toggle semantics against truthy-but-not-True slips.
- ADD-ON — the bpy-free binding (``addon/riggermortis_addon/policy.py``)
  is exercised headlessly: a fresh install syncs OFF, BOTH toggles are
  required, the enable routes through the documented call, and the report
  line carries the refusal code verbatim. The REAL Blender preferences
  flow (real AddonPreferences defaults, real property writes) runs in the
  Blender gate — ``xtask/blender_verify.sh``, ``RM_POLICY`` lines.
- MCP — the server answers from a fresh default engine per call and its
  tool set contains NO enable path (tested in ``test_mcp_server.py``).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from conftest import addon_policy_module  # noqa: E402
from riggermortis.errors import PolicyError  # noqa: E402
from riggermortis.policy import (  # noqa: E402
    ADULT_MODULE_DISABLED,
    INVALID_REQUEST,
    MINOR_CONTENT,
    REAL_PERSON_EXPLICIT,
    PolicyEngine,
)

# ---------------------------------------------------------------------------
# core: the two-toggle semantics are strict, not truthy
# ---------------------------------------------------------------------------

def test_enable_rejects_truthy_non_true_confirmation():
    """``confirm`` must be exactly True — a truthy slip (1, "yes", a widget
    int) is not the explicit confirmation the policy demands."""
    engine = PolicyEngine()
    for bad in (1, "yes", [True], 0.0):
        with pytest.raises(PolicyError):
            engine.enable_adult_module(bad)  # type: ignore[arg-type]
        assert engine.adult_module_enabled is False


def test_constructed_engine_never_starts_enabled_and_default_is_the_factory():
    """Every engine a frontend can build starts SFW; the documented enable
    path is the only transition — no constructor kwarg shortcut exists."""
    engine = PolicyEngine()
    assert engine.adult_module_enabled is False
    assert PolicyEngine().status()["defaults"] == {"adult_module_enabled": False}
    engine.enable_adult_module(confirm=True)
    fresh = PolicyEngine()
    assert fresh.adult_module_enabled is False  # a new engine never inherits


# ---------------------------------------------------------------------------
# add-on: the bpy-free binding (fresh install, two toggles, verbatim codes)
# ---------------------------------------------------------------------------

@pytest.fixture()
def addon_policy():
    policy = addon_policy_module()
    policy._reset_engine()  # each test starts from a fresh default engine
    yield policy
    policy._reset_engine()  # leave the shared module SFW for later tests


def test_addon_fresh_install_defaults_off(addon_policy):
    """Fresh install: both toggles read False, the engine stays OFF, and the
    fictional-adult subject refuses with the retryable module code."""
    assert addon_policy.sync_from_preferences() is False  # no bpy here -> defaults
    engine = addon_policy.engine()
    assert engine.adult_module_enabled is False
    assert type(engine).__name__ == "PolicyEngine"
    refusal = addon_policy.check("fictional_adult")
    assert refusal is not None
    assert refusal.code == ADULT_MODULE_DISABLED
    assert refusal.retryable is True


def test_addon_enable_requires_both_toggles(addon_policy):
    assert addon_policy.sync(True, False) is False   # enable without confirm
    assert addon_policy.sync(False, True) is False   # confirm without enable
    assert addon_policy.engine().adult_module_enabled is False
    assert addon_policy.sync(True, True) is True     # both -> the documented call
    assert addon_policy.engine().adult_module_enabled is True


def test_addon_any_toggle_off_disables(addon_policy):
    addon_policy.sync(True, True)
    assert addon_policy.engine().adult_module_enabled is True
    assert addon_policy.sync(False, True) is False
    assert addon_policy.sync(True, False) is False
    assert addon_policy.sync(False, False) is False
    assert addon_policy.engine().adult_module_enabled is False
    # and the disabled engine refuses fictional_adult again
    refusal = addon_policy.check("fictional_adult")
    assert refusal is not None and refusal.code == ADULT_MODULE_DISABLED


def test_addon_report_carries_the_verbatim_code(addon_policy):
    """The add-on report line embeds the EXACT public-API code — the codes
    are imported from riggermortis.policy, never re-typed (P3-3 rule)."""
    for subject, code in (
        ("minor", MINOR_CONTENT),
        ("real_person", REAL_PERSON_EXPLICIT),
        ("fictional_adult", ADULT_MODULE_DISABLED),
        ("nope", INVALID_REQUEST),
    ):
        refusal = addon_policy.check(subject)
        assert refusal is not None, subject
        assert refusal.code == code
        line = addon_policy.format_refusal(refusal)
        assert f"[{code}]" in line, line
    # only the retryable refusal advertises the preferences path
    hard_line = addon_policy.format_refusal(addon_policy.check("minor"))
    assert "Preferences" not in hard_line
    gated = addon_policy.format_refusal(addon_policy.check("fictional_adult"))
    assert "Preferences" in gated and "two toggles" in gated


def test_addon_allowed_subject_and_enabled_gate(addon_policy):
    assert addon_policy.check("other") is None
    addon_policy.sync(True, True)
    assert addon_policy.check("fictional_adult") is None  # module ON: allowed
    assert addon_policy.check("minor") is not None        # hard line: still refused


def test_addon_subjects_match_the_core_contract(addon_policy):
    """The binding's subject list is exactly what the core evaluates."""
    engine = PolicyEngine()
    for subject in addon_policy.SUBJECTS:
        # must not raise: every documented subject is core-evaluable
        engine.check_explicit_request(subject)
    assert set(addon_policy.SUBJECTS) == {
        "minor", "real_person", "fictional_adult", "other"
    }
