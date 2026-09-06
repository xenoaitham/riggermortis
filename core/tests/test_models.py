"""Model manager (P1-1): manifest integrity, URL safety, offline verification.

No network and no optional dependencies are involved anywhere here: the
downloader's network path is exercised via monkeypatched failure injection
only, and verification works against local files in tmp_path.
"""
from __future__ import annotations

import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from riggermortis.errors import InferenceError  # noqa: E402
from riggermortis.inference import models as models_mod  # noqa: E402
from riggermortis.inference.models import (  # noqa: E402
    download_model,
    load_manifest,
    model_path,
    validate_url,
    verify_model,
)

# -- manifest ---------------------------------------------------------------

def test_manifest_is_well_formed():
    manifest = load_manifest()
    assert manifest["manifest_version"] == 1
    entries = manifest["models"]
    assert len(entries) >= 2  # detector + pose for DWPose
    roles = {e["role"] for e in entries.values()}
    assert "detector" in roles and "pose" in roles
    for name, entry in entries.items():
        assert entry["url"].startswith("https://"), name
        validate_url(entry["url"])  # must pass the SSRF guard itself
        assert len(entry["sha256"]) == 64
        int(entry["sha256"], 16)  # hex
        assert isinstance(entry["bytes"], int) and entry["bytes"] > 0
        assert entry["license"]
        assert entry["source"].startswith("https://")
        # filename is a plain basename: never a path escape
        assert "/" not in entry["filename"] and "\\" not in entry["filename"]
        assert entry["filename"] == Path(entry["filename"]).name


# -- path resolution --------------------------------------------------------

def test_default_root_respects_platform_and_xdg(monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", "/tmp/fake-xdg")
    monkeypatch.setattr(sys, "platform", "linux")
    assert models_mod.default_root() == Path("/tmp/fake-xdg/riggermortis/models")

    monkeypatch.delenv("XDG_DATA_HOME")
    root = models_mod.default_root()
    assert root.parts[-3:] == (".local", "share", "riggermortis") or "riggermortis" in root.parts

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", r"C:\Users\u\AppData\Roaming")
    assert str(models_mod.default_root()).startswith(r"C:\Users\u\AppData\Roaming")
    monkeypatch.setattr(sys, "platform", "darwin")
    assert "Application Support" in str(models_mod.default_root())


def test_model_path_uses_manifest_filename(tmp_path):
    manifest = load_manifest()
    for name, entry in manifest["models"].items():
        assert model_path(name, root=tmp_path) == tmp_path / entry["filename"]


# -- URL safety -------------------------------------------------------------

@pytest.mark.parametrize("bad_url", [
    "http://huggingface.co/x.onnx",
    "https://localhost/x.onnx",
    "https://sub.localhost/x.onnx",
    "https://127.0.0.1/x.onnx",
    "https://[::1]/x.onnx",
    "https://169.254.169.254/latest/meta-data",
    "https://10.0.0.1/x.onnx",
    "https://192.168.1.10/x.onnx",
    "https://model.internal/x.onnx",
    "ftp://huggingface.co/x.onnx",
])
def test_validate_url_rejects_internal_and_non_https(bad_url):
    with pytest.raises(InferenceError):
        validate_url(bad_url)


def test_validate_url_accepts_public_https():
    validate_url("https://huggingface.co/yzd-v/DWPose/resolve/main/yolox_l.onnx")


def test_resolve_public_host_rejects_private_resolution(monkeypatch):
    import socket

    def fake_getaddrinfo(host, port, **_kw):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.1.2.3", port))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(InferenceError):
        models_mod.resolve_public_host("https://rebind.example/x.onnx")


# -- verification (local files only) ----------------------------------------

def _tiny_entry(name: str, content: bytes) -> dict[str, object]:
    """A manifest pin for tiny local content: all verifier gates, no big files."""
    import hashlib

    return {
        "role": "pose",
        "filename": "tiny.onnx",
        "url": "https://example.invalid/tiny.onnx",
        "sha256": hashlib.sha256(content).hexdigest(),
        "bytes": len(content),
        "license": "test",
        "source": "https://example.invalid",
    }


def test_verify_fails_on_missing_and_tampered_file(tmp_path):
    content = b"pretend-onnx" * 8
    manifest = {"manifest_version": 1, "models": {"tiny-model": _tiny_entry("t", content)}}

    with pytest.raises(InferenceError) as exc:
        verify_model("tiny-model", root=tmp_path, manifest=manifest)
    assert "not downloaded" in str(exc.value) and "download" in str(exc.value)

    path = model_path("tiny-model", root=tmp_path, manifest=manifest)
    path.write_bytes(b"junk")
    with pytest.raises(InferenceError) as exc:
        verify_model("tiny-model", root=tmp_path, manifest=manifest)
    assert "bytes" in str(exc.value)  # size gate fires before hashing

    path.write_bytes(content[:-1] + b"X")  # right size, wrong content
    with pytest.raises(InferenceError) as exc:
        verify_model("tiny-model", root=tmp_path, manifest=manifest)
    assert "checksum" in str(exc.value) and "download" in str(exc.value)


def test_verify_passes_on_correct_content(tmp_path):
    content = b"pretend-onnx"
    manifest = {"manifest_version": 1, "models": {"tiny-model": _tiny_entry("t", content)}}
    path = model_path("tiny-model", root=tmp_path, manifest=manifest)
    path.write_bytes(content)
    report = verify_model("tiny-model", root=tmp_path, manifest=manifest)
    assert report["verified"] is True
    assert report["bytes"] == len(content)


# -- download error paths (monkeypatched: no real network) ------------------

def test_download_refuses_bad_url_before_any_request(tmp_path):
    manifest = {
        "manifest_version": 1,
        "models": {
            "bad": {
                "role": "pose",
                "filename": "bad.onnx",
                "url": "http://127.0.0.1/steal.onnx",
                "sha256": "0" * 64,
                "bytes": 1,
                "license": "x",
                "source": "x",
            }
        },
    }

    def boom(*_a, **_k):  # any request attempt would fail the test
        raise AssertionError("network request attempted after URL validation")

    monkey_urlopen = boom
    import urllib.request

    saved = urllib.request.urlopen
    urllib.request.urlopen = monkey_urlopen  # type: ignore[assignment]
    try:
        with pytest.raises(InferenceError):
            download_model("bad", root=tmp_path, manifest=manifest)
    finally:
        urllib.request.urlopen = saved  # type: ignore[assignment]
    assert not list(tmp_path.iterdir())  # nothing was written


def test_download_offline_error_is_actionable(tmp_path, monkeypatch):
    manifest = load_manifest()
    name = sorted(manifest["models"])[0]

    def fake_open(_req, timeout=60):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(
        models_mod.urllib.request, "build_opener",
        lambda *_a, **_k: type("O", (), {"open": staticmethod(fake_open)})(),
    )
    with pytest.raises(InferenceError) as exc:
        download_model(name, root=tmp_path)
    assert "check your connection" in str(exc.value)
    assert not list(tmp_path.iterdir())  # no .part litter


# -- CLI surface ------------------------------------------------------------

def test_cli_models_list_and_status(tmp_path, capsys, monkeypatch):
    from riggermortis.cli import EXIT_OK, main

    monkeypatch.setattr(models_mod, "default_root", lambda: tmp_path)
    assert main(["models", "list", "--json"]) == EXIT_OK
    import json

    rows = json.loads(capsys.readouterr().out)
    assert {r["name"] for r in rows} >= {"dwpose-yolox-l", "dwpose-ll-ucoco-384"}
    assert all(r["downloaded"] is False for r in rows)


def test_cli_models_verify_missing_is_actionable(tmp_path, capsys, monkeypatch):
    from riggermortis.cli import EXIT_HANDLED_ERROR, main

    monkeypatch.setattr(models_mod, "default_root", lambda: tmp_path)
    code = main(["models", "verify", "dwpose-ll-ucoco-384"])
    assert code == EXIT_HANDLED_ERROR
    err = capsys.readouterr().err
    assert err.startswith("error:") and "hint:" in err


def test_cli_models_unknown_name_is_actionable(capsys):
    from riggermortis.cli import EXIT_HANDLED_ERROR, main

    code = main(["models", "verify", "no-such-model"])
    assert code == EXIT_HANDLED_ERROR
    err = capsys.readouterr().err
    assert "no-such-model" in err and "managed models:" in err
