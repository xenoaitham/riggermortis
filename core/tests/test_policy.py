"""Content policy: SFW by default, opt-in adult module, unconditional hard lines."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from riggermortis.errors import PolicyError  # noqa: E402
from riggermortis.policy import PolicyEngine  # noqa: E402


def test_default_is_sfw():
    engine = PolicyEngine()
    status = engine.status()
    assert status["adult_module_enabled"] is False
    assert status["defaults"]["adult_module_enabled"] is False


def test_cannot_construct_pre_enabled():
    with pytest.raises(PolicyError):
        PolicyEngine(adult_module_enabled=True)


def test_enable_requires_explicit_confirmation():
    engine = PolicyEngine()
    with pytest.raises(PolicyError):
        engine.enable_adult_module(False)
    assert engine.adult_module_enabled is False
    engine.enable_adult_module(True)
    assert engine.adult_module_enabled is True
    engine.disable_adult_module()
    assert engine.adult_module_enabled is False


def test_minor_content_refuses_always():
    engine = PolicyEngine()
    refusal = engine.check_explicit_request("minor")
    assert refusal is not None
    assert refusal.code == "minor_content_prohibited"
    assert refusal.retryable is False
    engine.enable_adult_module(True)  # even then
    assert engine.check_explicit_request("minor") is not None


def test_real_person_explicit_refuses_always():
    engine = PolicyEngine()
    assert engine.check_explicit_request("real_person") is not None
    engine.enable_adult_module(True)
    assert engine.check_explicit_request("real_person") is not None


def test_fictional_adult_gated_by_module():
    engine = PolicyEngine()
    refusal = engine.check_explicit_request("fictional_adult")
    assert refusal is not None
    assert refusal.code == "adult_module_disabled"
    assert refusal.retryable is True
    engine.enable_adult_module(True)
    assert engine.check_explicit_request("fictional_adult") is None


def test_unknown_subject_is_invalid_not_crash():
    refusal = PolicyEngine().check_explicit_request("???")
    assert refusal is not None
    assert refusal.code == "invalid_request"


def test_refusal_dict_shape():
    d = PolicyEngine().check_explicit_request("minor").to_dict()
    assert set(d) == {"code", "message", "category", "retryable"}
