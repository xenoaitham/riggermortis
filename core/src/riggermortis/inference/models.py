"""Checksum-pinned model manager: local-first, downloads only when told to.

Rules (mission: LOCAL OR NOTHING):
- Nothing is ever downloaded at import time or during default use — a
  transfer happens ONLY inside :func:`download_model`, which the CLI invokes
  from the explicit ``rigpose models download`` command.
- Every artifact is pinned in the shipped ``manifest.json`` (exact URL,
  sha256, byte size, license). Downloads are verified against the pin BEFORE
  being placed; a mismatch means the file never reaches the store.
- Models live under the platform user-data dir (XDG data / ``%APPDATA%`` /
  ``~/Library/Application Support``), overridable per-call via ``root`` for
  tests and the add-on.
- SSRF guard (defense in depth against a tampered manifest): https-only,
  internal hostnames refused, the hostname RESOLVED and every resulting
  address checked (loopback / private / link-local / reserved / multicast
  refused), and every redirect hop re-validated the same way. https also
  keeps any hop from silently changing hosts via TLS. The known residual:
  the validated resolution and the actual connect are two lookups (stdlib
  limit) — accepted for release-pinned manifest URLs, and flagged here
  rather than hidden.

This module is stdlib-only: the ``[inference]`` extra (``onnxruntime``,
``numpy``) is consumed lazily by the P1-2 wrapper, never here.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import shutil
import socket
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from importlib import resources
from pathlib import Path

from ..errors import InferenceError

MANIFEST_VERSION = 1
_CHUNK = 1 << 20


# -- manifest ---------------------------------------------------------------

def load_manifest() -> dict:
    """Load the shipped, checksum-pinned model manifest (package data)."""
    text = (resources.files("riggermortis.inference") / "manifest.json").read_text(encoding="utf-8")
    data = json.loads(text)
    if int(data.get("manifest_version", 0)) != MANIFEST_VERSION:
        raise InferenceError(
            f"unsupported model manifest version {data.get('manifest_version')}",
            hint=f"this build reads manifest version {MANIFEST_VERSION}",
        )
    if not data.get("models"):
        raise InferenceError("model manifest lists no models", hint="reinstall riggermortis-core")
    return data


def model_names(manifest: dict | None = None) -> list[str]:
    manifest = manifest or load_manifest()
    return sorted(manifest["models"])


def model_entry(name: str, manifest: dict | None = None) -> dict:
    manifest = manifest or load_manifest()
    entry = manifest["models"].get(name)
    if entry is None:
        raise InferenceError(
            f"unknown model {name!r}",
            hint=f"managed models: {', '.join(sorted(manifest['models']))}",
        )
    return entry


# -- storage ----------------------------------------------------------------

def default_root() -> Path:
    """Platform user-data dir for downloaded models (no install-dir writes)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
        return base / "riggermortis" / "models"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "riggermortis" / "models"
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "riggermortis" / "models"


def model_path(name: str, root: Path | None = None, manifest: dict | None = None) -> Path:
    entry = model_entry(name, manifest)
    return (root or default_root()) / entry["filename"]


# -- URL safety (runs before any request, and on every redirect hop) ---------

def _reject_internal_address(host: str, ip: ipaddress._BaseAddress) -> None:
    if (
        ip.is_private or ip.is_loopback or ip.is_link_local
        or ip.is_reserved or ip.is_unspecified or ip.is_multicast
    ):
        raise InferenceError(
            f"model host {host!r} resolves to non-public address {ip}",
            hint="downloads must target public hosts; report a tampered manifest",
        )


def validate_url(url: str) -> None:
    """Refuse anything but https to a public, non-internal host."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https":
        raise InferenceError(
            f"refusing non-https model URL {url!r}",
            hint="manifest URLs must be https; report a tampered manifest",
        )
    host = parts.hostname
    if not host:
        raise InferenceError(
            f"model URL has no host: {url!r}",
            hint="manifest URLs must include a hostname",
        )
    lowered = host.lower()
    if lowered == "localhost" or lowered.endswith((".localhost", ".local", ".internal")):
        raise InferenceError(
            f"refusing internal model host {host!r}",
            hint="downloads must target public hosts; report a tampered manifest",
        )
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return  # a DNS name; its resolved addresses are checked separately
    _reject_internal_address(host, ip)


def resolve_public_host(url: str) -> list[str]:
    """Resolve the URL's host and refuse any non-public address it yields."""
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname
    if not host:
        raise InferenceError(f"URL has no host: {url!r}")
    port = parts.port or 443
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise InferenceError(
            f"cannot resolve model host {host!r}",
            hint="check your connection; DNS failures are reported before anything downloads",
        ) from exc
    ips: list[str] = []
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        _reject_internal_address(host, ip)
        ips.append(str(ip))
    if not ips:
        raise InferenceError(
            f"model host {host!r} resolved to no addresses",
            hint="check your connection and retry",
        )
    return ips


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Redirects must pass the same https/public-host gate as the origin."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        validate_url(newurl)
        resolve_public_host(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


# -- verification -----------------------------------------------------------

def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def verify_model(
    name: str, root: Path | None = None, manifest: dict | None = None
) -> dict[str, object]:
    """Verify one stored model against its manifest pin. Raises if unusable."""
    entry = model_entry(name, manifest)
    path = (root or default_root()) / entry["filename"]
    if not path.is_file():
        raise InferenceError(
            f"model {name!r} is not downloaded ({path})",
            hint=f"run: rigpose models download {name}",
        )
    size = path.stat().st_size
    if size != int(entry["bytes"]):
        raise InferenceError(
            f"model {name!r} has {size} bytes, manifest pins {entry['bytes']} ({path})",
            hint=f"delete {path} and re-run: rigpose models download {name}",
        )
    actual = file_sha256(path)
    if actual != entry["sha256"]:
        raise InferenceError(
            f"model {name!r} failed checksum verification at {path}",
            hint=(
                "delete the file and re-run: rigpose models download "
                f"{name}; if it fails again the pinned release changed — do not use the file"
            ),
        )
    return {"name": name, "path": str(path), "sha256": actual, "bytes": size, "verified": True}


def status_model(
    name: str, root: Path | None = None, manifest: dict | None = None
) -> dict[str, object]:
    """Cheap (hash-free) local status for listings: present and size match?"""
    entry = model_entry(name, manifest)
    path = (root or default_root()) / entry["filename"]
    downloaded = path.is_file() and path.stat().st_size == int(entry["bytes"])
    return {
        "name": name,
        "role": entry.get("role", "?"),
        "filename": entry["filename"],
        "bytes": int(entry["bytes"]),
        "license": entry.get("license", ""),
        "downloaded": downloaded,
        "path": str(path),
    }


def list_models(root: Path | None = None, manifest: dict | None = None) -> list[dict[str, object]]:
    manifest = manifest or load_manifest()
    return [status_model(name, root, manifest) for name in sorted(manifest["models"])]


# -- download (explicit user action ONLY) -----------------------------------

def download_model(
    name: str, root: Path | None = None, manifest: dict | None = None
) -> Path:
    """Download one model into the store, verifying the manifest pin.

    Called only from the explicit ``rigpose models download`` command path —
    never at import, never during default use, never by the add-on silently.
    """
    entry = model_entry(name, manifest)
    url = str(entry["url"])
    validate_url(url)
    resolve_public_host(url)

    target_dir = root or default_root()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / entry["filename"]
    expected_sha = str(entry["sha256"])
    expected_bytes = int(entry["bytes"])

    request = urllib.request.Request(url, headers={"User-Agent": "riggermortis-core"})
    opener = urllib.request.build_opener(_SafeRedirectHandler)
    tmp_name: str | None = None
    received = 0
    digest = hashlib.sha256()
    try:
        with opener.open(request, timeout=60) as resp, tempfile.NamedTemporaryFile(
            dir=target_dir, prefix=f".{entry['filename']}.", suffix=".part", delete=False
        ) as tmp:
            tmp_name = tmp.name
            while chunk := resp.read(_CHUNK):
                digest.update(chunk)
                received += len(chunk)
                tmp.write(chunk)
    except (urllib.error.URLError, OSError) as exc:
        if tmp_name is not None:
            Path(tmp_name).unlink(missing_ok=True)
        reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
        raise InferenceError(
            f"download of {name!r} failed: {reason}",
            hint=(
                "check your connection and retry; riggermortis downloads only on this "
                "explicit command and never contacts the network otherwise"
            ),
        ) from exc

    if received != expected_bytes:
        Path(tmp_name).unlink(missing_ok=True)
        raise InferenceError(
            f"downloaded {received} bytes for {name!r}, manifest pins {expected_bytes}",
            hint="the source changed — the file was discarded; report a manifest update",
        )
    actual = digest.hexdigest()
    if actual != expected_sha:
        Path(tmp_name).unlink(missing_ok=True)
        raise InferenceError(
            f"downloaded {name!r} failed checksum verification "
            f"(got {actual}, pinned {expected_sha})",
            hint="the source changed — the file was discarded; report a manifest update",
        )
    shutil.move(str(tmp_name), str(target))
    return target
