"""P4-7 animatic presets — timed panel sequences from pose actions.

An animatic is a TIMED ROUGH: N shots in play order, each pointing a
scene camera at the posed subject for a preset number of frames while a
canonical action (the P2/P3 pose-sequence machinery, baked by the caller
through the certified ``bake_action`` path) plays underneath. The output
is one deterministic PNG per output frame; movie ASSEMBLY lives in shell
glue (``xtask/*.sh``, ffmpeg — D-009), never here.

Why no Video Sequence Editor: the 5.1.0 VSE movie-append (strip stack ->
FFMPEG render) SEGFAULTS racy (~2/3 crash rate across a 16-run bisect;
garbage ``imb_alloc_buffer`` calloc) independent of source class, paths,
armature, or container — the dead end is recorded in docs/STYLE.md and
must never be "fixed" backwards. Per-frame stills are the deterministic
artifact; ``render(animation=True)`` is also avoided (camera swaps are
per-frame state anyway).

This module imports WITHOUT bpy (validation + timing math are pure) so
the CI suite exercises the preset contract; everything engine-facing
lazy-imports bpy like ``pages.py``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ANIMATICS_DIR = Path(__file__).resolve().parent / "presets" / "animatics"
PAGE_GROUP = "rm_page"  # the page assembly is REFUSED during animatic renders
FRAME_FILE_TEMPLATE = "rm_animatic_{:04d}.png"
# bake_action's default frame_offset: source frame 0 plays at Blender frame 1
BAKE_FRAME_OFFSET = 1

_ALLOWED = {
    "format",
    "name",
    "resolution",
    "fps",
    "style",
    "shots",
    "notes",
}


def known_animatics() -> list[str]:
    """Shipped animatic presets, sorted (deterministic)."""
    return sorted(p.stem for p in ANIMATICS_DIR.glob("*.json"))


def _known_style_names() -> list[str]:
    """Shipped STYLE preset names (for shot ``style`` validation).

    A local re-glob rather than an import of ``style``: this module must
    stay importable without bpy (see ``pages.py``).
    """
    return sorted(p.stem for p in ANIMATICS_DIR.parent.glob("*.json"))


def _is_num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def load_animatic(name: str) -> dict[str, Any]:
    """Load a shipped animatic preset by name (or an explicit .json path)."""
    if name.endswith(".json"):
        path = Path(name)
    else:
        path = ANIMATICS_DIR / f"{name}.json"
    if not path.is_file():
        raise ValueError(
            f"unknown animatic preset: {name!r} (hint: known animatics: "
            + ", ".join(known_animatics())
            + " — or pass an explicit .json path)"
        )
    animatic = json.loads(path.read_text(encoding="utf-8"))
    _validate_animatic(animatic, path.name)
    return animatic


def _validate_animatic(animatic: dict[str, Any], source: str) -> None:
    unknown = set(animatic) - _ALLOWED
    if unknown:
        raise ValueError(f"{source}: unknown animatic fields: {sorted(unknown)}")
    if animatic.get("format") != 1:
        raise ValueError(f"{source}: animatic format must be 1")
    styles = _known_style_names()
    style_name = animatic.get("style")
    if style_name is not None and style_name not in styles:
        raise ValueError(
            f"{source}: animatic style {style_name!r} is not a shipped style "
            f"preset (hint: known styles: {', '.join(styles)})"
        )
    res = animatic.get("resolution")
    if not isinstance(res, dict):
        raise ValueError(f"{source}: 'resolution' is required")
    res_unknown = set(res) - {"width_px", "height_px"}
    if res_unknown:
        raise ValueError(f"{source}: unknown resolution fields: {sorted(res_unknown)}")
    for key in ("width_px", "height_px"):
        value = res.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"{source}: resolution.{key} must be a positive int")
    fps = animatic.get("fps")
    if not isinstance(fps, int) or isinstance(fps, bool) or fps <= 0:
        raise ValueError(f"{source}: fps must be a positive int")

    shots = animatic.get("shots")
    if not isinstance(shots, list) or not shots:
        raise ValueError(f"{source}: shots must be a non-empty list")
    for index, shot in enumerate(shots):
        if not isinstance(shot, dict):
            raise ValueError(f"{source}: shot {index} must be an object")
        shot_unknown = set(shot) - {"camera", "frames", "style"}
        if shot_unknown:
            raise ValueError(
                f"{source}: unknown shot {index} fields: {sorted(shot_unknown)}"
            )
        camera = shot.get("camera")
        if not isinstance(camera, str) or not camera:
            raise ValueError(
                f"{source}: shot {index}.camera must be a scene object name"
            )
        frames = shot.get("frames")
        if not isinstance(frames, int) or isinstance(frames, bool) or frames <= 0:
            raise ValueError(f"{source}: shot {index}.frames must be a positive int")
        shot_style = shot.get("style")
        if shot_style is not None and shot_style not in styles:
            raise ValueError(
                f"{source}: shot {index}.style {shot_style!r} is not a shipped "
                f"style preset (hint: known styles: {', '.join(styles)})"
            )


def animatic_frames(animatic: dict[str, Any], action_len: int) -> list[dict[str, Any]]:
    """Pure deterministic timing plan: one entry per OUTPUT frame.

    Shot k occupies output frames ``[start_k, start_k + frames_k)`` with
    ``start_k = sum(frames_<k)`` — timing is fully determined by the
    data. The action plays EVENLY and IN ORDER: output frame k of T
    total plays canonical action index ``(k * action_len) // T``
    (integer math; the action loops naturally when the shots outrun it).
    A 1-frame action degenerates to a held panel — same code path.
    """
    _validate_animatic(animatic, f"{animatic.get('name', 'animatic')}.json")
    if not isinstance(action_len, int) or isinstance(action_len, bool) or action_len <= 0:
        raise ValueError(
            f"action_len must be a positive int (got {action_len!r} — hint: "
            "pass the baked canonical action's frame count)"
        )
    total = sum(int(shot["frames"]) for shot in animatic["shots"])
    entries: list[dict[str, Any]] = []
    for shot_index, shot in enumerate(animatic["shots"]):
        for _ in range(int(shot["frames"])):
            k = len(entries)
            entries.append(
                {
                    "frame": k,
                    "shot": shot_index,
                    "camera": shot["camera"],
                    "action_frame": (k * action_len) // total,
                    "style": shot.get("style"),
                }
            )
    return entries


def render_animatic_frames(
    scene: Any,
    animatic: dict[str, Any],
    out_dir: Any,
    action_len: int,
    subject: Any = None,
) -> dict[str, Any]:
    """Render one PNG per OUTPUT frame (``rm_animatic_0000.png``, 0-based).

    The caller bakes the canonical action FIRST (``bake_action`` — the
    certified transport); this builder owns TIMING only: per frame it
    does ``frame_set(action_frame + BAKE_FRAME_OFFSET)`` and swaps the
    shot's camera, so the pose math is never duplicated here.

    Style semantics follow the page rules: the preset-level ``style`` is
    the BASE look (applied to ``subject`` by the caller); a per-shot
    ``style`` restyles ``subject`` through the P4-1/2/3 builders for that
    shot's frames. Application is persistent in the scene, so frames
    render in style groups — base-look frames FIRST (time order), then
    each styled shot's frames (time order within) — while the report is
    in TIME order regardless.

    Staged + RESTORED: camera, resolution, filepath, scene frame. An
    active PAGE assembly (``rm_page``) is refused with an actionable
    error (a static page must not composite over moving frames); tones
    machinery stays as found (it is part of the look and honors
    per-frame renders — the RM_TT precedent).
    """
    import bpy

    from riggermortis_addon import style

    _validate_animatic(animatic, f"{animatic.get('name', 'animatic')}.json")
    group = getattr(scene, "compositing_node_group", None)
    if group is not None and group.name == PAGE_GROUP:
        raise ValueError(
            "the scene's compositor graph is the PAGE assembly (rm_page) — "
            "a static page must not composite over animatic frames (hint: "
            "call pages.remove_page(scene) first)"
        )
    frames = animatic_frames(animatic, action_len)
    cameras = {o.name: o for o in scene.objects if o.type == "CAMERA"}
    render = scene.render
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    staged = (
        scene.camera,
        render.resolution_x,
        render.resolution_y,
        render.resolution_percentage,
        render.filepath,
        scene.frame_current,
    )
    width = int(animatic["resolution"]["width_px"])
    height = int(animatic["resolution"]["height_px"])
    try:
        # Style-group render order (base look first — persistent-style
        # semantics must not leak backwards into earlier frames).
        base_frames = [e for e in frames if e["style"] is None]
        styled_shots: list[int] = []
        for entry in frames:
            if entry["style"] is not None and entry["shot"] not in styled_shots:
                styled_shots.append(entry["shot"])
        ordered = base_frames + [
            e for si in styled_shots for e in frames if e["shot"] == si
        ]
        entries: dict[int, dict[str, Any]] = {}
        for entry in ordered:
            cam = cameras.get(entry["camera"])
            if cam is None:
                available = ", ".join(sorted(cameras)) or "none"
                raise ValueError(
                    f"shot {entry['shot']} camera {entry['camera']!r} is not "
                    f"a camera in this scene (hint: scene cameras: {available})"
                )
            if entry["style"] is not None:
                if subject is None:
                    raise ValueError(
                        f"shot {entry['shot']} has style {entry['style']!r} "
                        "but no subject was given (hint: pass the object the "
                        "style builders should restyle)"
                    )
                preset = style.load_preset(entry["style"])
                style.build_toon_material(subject, preset)
                if preset.get("lineart") is not None:
                    style.build_lineart(subject, preset)
                else:
                    style.remove_lineart()
                if preset.get("tones") is not None:
                    style.build_screentones(scene, preset)
                else:
                    style.remove_screentones(scene)
            path = out / FRAME_FILE_TEMPLATE.format(entry["frame"])
            scene.frame_set(entry["action_frame"] + BAKE_FRAME_OFFSET)
            scene.camera = cam
            render.resolution_x, render.resolution_y = width, height
            render.resolution_percentage = 100
            render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            entries[entry["frame"]] = {
                **entry,
                "file": str(path),
                "width_px": width,
                "height_px": height,
            }
    finally:
        (
            scene.camera,
            render.resolution_x,
            render.resolution_y,
            render.resolution_percentage,
            render.filepath,
            scene.frame_current,
        ) = staged
    return {
        "frames": [entries[i] for i in sorted(entries)],
        "out_dir": str(out),
        "action_len": action_len,
        "fps": int(animatic["fps"]),
        "total": len(frames),
    }
