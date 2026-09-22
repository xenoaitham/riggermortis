"""Network audit: default use performs ZERO outbound connections.

This is a headline property of riggermortis, tested like one. An audit hook
(Python 3.8+ ``sys.addaudithook``) records every socket-flavoured audit event —
``socket.connect``, ``socket.getaddrinfo``, ``socket.create_connection`` —
while the full default-use path runs in-process: all five synthetic fixtures
mapped, a preset saved and re-applied, policy status queried, and the CLI
``map``/``policy`` path exercised end-to-end. The test then asserts that no
socket event fired at all.

Audit hooks cannot be unregistered, so the hook is record-only and stays
installed for the remainder of the pytest session; it only ever appends to a
local list, which keeps it inert for unrelated tests.

CI additionally runs this module under ``unshare -n`` (kernel-level network
isolation, needs root — GitHub runners have passwordless sudo) where available;
the audit hook alone is sufficient and root is NOT required locally.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from conftest import addon_policy_module  # noqa: E402
from riggermortis.cli import EXIT_OK, main  # noqa: E402
from riggermortis.mapper import map_rig  # noqa: E402
from riggermortis.policy import PolicyEngine  # noqa: E402
from riggermortis.presets import (  # noqa: E402
    apply_preset,
    load_preset,
    preset_from_mapping,
    save_preset,
)
from rigs import all_five  # noqa: E402

_SOCKET_EVENTS = frozenset({
    "socket.connect",
    "socket.getaddrinfo",
    "socket.create_connection",
    "socket.bind",
})

_recorded: list[tuple[str, tuple[object, ...]]] = []
_hook_installed = False


def _hook(event: str, args: tuple[object, ...]) -> None:
    if event in _SOCKET_EVENTS:
        _recorded.append((event, args))


@pytest.fixture()
def socket_audit() -> list[tuple[str, tuple[object, ...]]]:
    """Install (once per session) the record-only socket audit hook."""
    global _hook_installed
    if not _hook_installed:
        sys.addaudithook(_hook)
        _hook_installed = True
    return _recorded


def test_default_use_path_makes_no_connections(socket_audit, tmp_path):
    del socket_audit  # fixture installed the hook; the list is shared
    _recorded.clear()

    rigs = all_five()
    assert len(rigs) == 5
    for name, rig in rigs.items():
        mapping = map_rig(rig)
        assert mapping.fingerprint == rig.fingerprint(), name
        preset = preset_from_mapping(rig, mapping)
        path = save_preset(preset, tmp_path / f"{name}.rigpreset.json")
        reapplied = apply_preset(rig, load_preset(path))
        assert reapplied.core_missing() == mapping.core_missing(), name

    assert PolicyEngine().status()["adult_module_enabled"] is False

    # P6-5: the add-on policy binding is part of the default-use surface —
    # the fresh-install sync, both toggle states, and a full check sweep
    # must open zero sockets too (the module is bpy-free at import).
    addon_policy = addon_policy_module()
    addon_policy._reset_engine()
    try:
        assert addon_policy.sync(False, False) is False
        assert addon_policy.sync(True, True) is True
        assert addon_policy.check("fictional_adult") is None
        addon_policy.sync(False, False)
        for subject in ("minor", "real_person", "fictional_adult", "other", "???"):
            refusal = addon_policy.check(subject)
            if refusal is not None:  # "other" is allowed under any state
                addon_policy.format_refusal(refusal)
    finally:
        addon_policy._reset_engine()

    rig_path = tmp_path / "cli_rig.json"
    rigs["rigify"].to_json(rig_path)
    assert main(["map", str(rig_path), "--json"]) == EXIT_OK
    assert main(["policy", "status"]) == EXIT_OK

    assert _recorded == [], (
        "default-use path opened sockets — local-only guarantee violated: "
        f"{_recorded}"
    )


def test_audit_hook_detects_a_real_connection_attempt(socket_audit):
    """Test the test: a real connection attempt must land in the record.

    Uses a loopback address with nothing listening, which fails fast without
    network round-trips; the assertion is about the audit event being
    RECORDED, not about the connection succeeding.
    """
    import socket

    _recorded.clear()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.05)
    try:
        s.connect(("127.0.0.1", 1))  # nothing listens on port 1; fails fast
    except OSError:
        pass
    finally:
        s.close()
    assert any(ev == "socket.connect" for ev, _ in _recorded), (
        "audit hook failed to record a real socket.connect attempt"
    )
    _recorded.clear()
