"""Pose payload contract (D-009): one pure module every reader shares.

Format history:
- **v1** (S4): single figure — top-level ``figure`` / ``pose`` / ``rotations``
  / ``skipped`` / ``notes`` keys.
- **v2** (S5): adds ``figures`` — a list of per-figure entries, each carrying
  the figure meta (label, index, score, bbox), the solved ``pose`` dict, and
  the ordered FK ``rotations`` for headless/CLI/MCP consumers. The selected
  figure is named by the top-level ``figure`` key, whose ``pose`` /
  ``rotations`` / ``skipped`` / ``notes`` mirror that entry, so v1-shaped
  reads keep working on v2 payloads.
- **v3** (S26, P8-1): ADDITIVE only — an optional top-level ``pins`` list
  (scene contact pins, validated by ``scene.ContactPin.from_dict`` — carried
  as DATA, never enforced by the apply path). Format 3 entries read exactly
  like format 2; a pins-free v3 payload differs from v2 output only in the
  ``format`` integer. A v2 payload applied through v3 code is byte-identical
  (pinned by contract test); an old build reading a v3 file refuses loudly
  (the preset-format-2 house pattern).

Every reader (add-on apply path, CLI, future MCP tools) goes through this
module so the contract has exactly one implementation and the back-compat
rules live in one place. Pure stdlib.
"""
from __future__ import annotations

from pathlib import Path

from .errors import PayloadError
from .types import RigData

#: Format written by this build. Readers accept 1 (read-only), 2 and 3.
FORMAT = 3

#: Formats this build reads.
READ_FORMATS = (1, 2, 3)


def figure_entries(payload: dict[str, object]) -> list[dict[str, object]]:
    """Per-figure entries; v1 payloads synthesize a one-item list."""
    if not isinstance(payload, dict):
        raise PayloadError(
            "pose payload is not a JSON object",
            hint="regenerate with: rigpose pose <image> <rig.json> --out payload.json",
        )
    fmt = payload.get("format", 1)
    if fmt in (2, 3):
        figures = payload.get("figures")
        if not isinstance(figures, list) or not figures:
            raise PayloadError(
                f"payload v{fmt} has no 'figures' list",
                hint="regenerate with: rigpose pose <image> <rig.json> --out payload.json",
            )
        return figures
    if fmt == 1:
        if "pose" not in payload:
            raise PayloadError(
                "payload v1 has no 'pose' section",
                hint="regenerate with: rigpose pose <image> <rig.json> --out payload.json",
            )
        figure = payload.get("figure") if isinstance(payload.get("figure"), dict) else {}
        return [{
            "label": figure.get("label", "figure 0"),
            "index": figure.get("index", 0),
            "score": figure.get("score", 0.0),
            "bbox": figure.get("bbox", []),
            "pose": payload["pose"],
            "rotations": payload.get("rotations", []),
            "skipped": payload.get("skipped", []),
            "notes": payload.get("notes", []),
        }]
    raise PayloadError(
        f"unsupported pose payload format {fmt!r}",
        hint="this build reads formats 1, 2 and 3; regenerate with: "
             "rigpose pose <image> <rig.json> --out payload.json",
    )


def figure_labels(payload: dict[str, object]) -> list[str]:
    """Stable figure labels in payload order (deterministic)."""
    labels: list[str] = []
    for i, entry in enumerate(figure_entries(payload)):
        label = entry.get("label") if isinstance(entry, dict) else None
        labels.append(str(label) if label else f"figure {i}")
    return labels


def entry_for_label(
    payload: dict[str, object], label: str | None = None
) -> dict[str, object]:
    """Resolve an entry by label; None = the payload's selected figure."""
    entries = figure_entries(payload)
    if label is None:
        selected = payload.get("figure")
        want = selected.get("label") if isinstance(selected, dict) else None
    else:
        want = label
    for entry in entries:
        if isinstance(entry, dict) and entry.get("label") == want:
            return entry
    if want is None and entries:
        return entries[0]
    raise PayloadError(
        f"payload has no figure {want!r}",
        hint=f"figures in this payload: {', '.join(figure_labels(payload))}",
    )


def pose_for_figure(payload: dict[str, object], label: str | None = None) -> dict[str, object]:
    """The solved ``CanonicalPose.to_dict()`` for ``label`` (None = selected)."""
    entry = entry_for_label(payload, label)
    pose = entry.get("pose")
    if not isinstance(pose, dict):
        name = entry.get("label", "?")
        raise PayloadError(
            f"figure {name!r} carries no pose dict",
            hint="regenerate with: rigpose pose <image> <rig.json> --all-figures",
        )
    return pose


def build_pose_payload(
    image_path: Path,
    width: int,
    height: int,
    rig: RigData,
    entries: list[dict[str, object]],
    selected_label: str,
    pins: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """Assemble a format-3 payload (D-009).

    ``entries``: one per figure — ``{"figure": {...meta...}, "pose": ...,
    "rotations": [...], "skipped": [...], "notes": [...]}`` in board order.
    The selected figure's data is mirrored into the v1 top-level keys.
    ``pins``: optional scene contact pins (``ContactPin.to_dict`` dicts,
    validated by ``scene.ContactPin.from_dict``) — omitted from the file
    when empty/None, so a pins-free payload differs from v2 output only in
    the ``format`` integer.
    """
    if not entries:
        raise PayloadError("no figure entries to embed", hint="detect figures first")
    selected = next(
        (e for e in entries if e["figure"].get("label") == selected_label), entries[0]
    )
    out: dict[str, object] = {
        "format": FORMAT,
        "image": {"path": str(image_path), "width": width, "height": height},
        "figure": dict(selected["figure"]),
        "pose": selected["pose"],
        "rotations": selected["rotations"],
        "skipped": selected["skipped"],
        "notes": selected["notes"],
        "figures": [
            {
                "label": e["figure"]["label"],
                "index": e["figure"]["index"],
                "score": e["figure"]["score"],
                "bbox": e["figure"]["bbox"],
                "pose": e["pose"],
                "rotations": e["rotations"],
                "skipped": e["skipped"],
                "notes": e["notes"],
            }
            for e in entries
        ],
        "rig": {"name": rig.name, "fingerprint": rig.fingerprint()},
    }
    if pins:
        out["pins"] = list(pins)
    return out
