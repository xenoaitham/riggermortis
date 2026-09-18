"""P4-4 page-preset contract tests — validation + pixel math, no bpy.

``pages.py`` is import-safe WITHOUT Blender (engine calls lazy-import bpy
like ``style.py``), so the preset contract ships CI-tested: the validator
fails loudly on unknown fields / bad geometry / unknown styles, loads are
deterministic, and ``panel_px`` lands the exact probe-verified pixels.
The render/graph half is gated by the Blender style probe
(``RM_STYLE PAGES`` in ``xtask/style_probe.py``).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_ADDON_DIR = Path(__file__).resolve().parents[2] / "addon" / "riggermortis_addon"
_spec = importlib.util.spec_from_file_location("rm_pages", _ADDON_DIR / "pages.py")
assert _spec is not None and _spec.loader is not None
pages = importlib.util.module_from_spec(_spec)
sys.modules["rm_pages"] = pages
_spec.loader.exec_module(pages)


def test_known_pages_are_the_two_shipped_layouts() -> None:
    assert pages.known_pages() == ["manga_koma3", "western_cross3"]


def test_shipped_pages_load_and_carry_the_schema() -> None:
    manga = pages.load_page("manga_koma3")
    assert manga["format"] == 1
    assert manga["reading_direction"] == "rtl"
    assert manga["style"] == "manga"
    assert manga["page"]["width_px"] == 1200
    assert manga["page"]["height_px"] == 1800
    assert len(manga["panels"]) == 3
    western = pages.load_page("western_cross3")
    assert western["reading_direction"] == "ltr"
    assert western["style"] == "western"
    assert western["page"]["width_px"] == 1400
    assert western["page"]["height_px"] == 2100
    assert len(western["panels"]) == 3


def test_load_is_deterministic() -> None:
    assert pages.load_page("manga_koma3") == pages.load_page("manga_koma3")
    assert pages.load_page("western_cross3") == pages.load_page("western_cross3")


def test_panel_px_matches_the_probe_numbers() -> None:
    """The gate sphere probe verified assembly against exactly these px
    rects — the pure math must reproduce them (edge-based rounding)."""
    manga = pages.load_page("manga_koma3")
    assert pages.panel_px(manga, 0) == (0, 1116, 1200, 684)
    assert pages.panel_px(manga, 1) == (612, 558, 588, 522)
    assert pages.panel_px(manga, 2) == (0, 0, 1200, 522)
    western = pages.load_page("western_cross3")
    assert pages.panel_px(western, 0) == (0, 1260, 770, 840)
    assert pages.panel_px(western, 1) == (798, 1260, 602, 840)
    assert pages.panel_px(western, 2) == (0, 0, 1400, 1218)


def test_unknown_page_name_is_actionable() -> None:
    with pytest.raises(ValueError, match="known pages: manga_koma3"):
        pages.load_page("nope")


def _mutated(tmp_path: Path, mutate) -> str:
    raw = json.loads(
        (_ADDON_DIR / "presets" / "pages" / "manga_koma3.json").read_text(
            encoding="utf-8"
        )
    )
    mutate(raw)
    path = tmp_path / "mutated.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return str(path)


def test_unknown_field_fails_loudly(tmp_path: Path) -> None:
    path = _mutated(tmp_path, lambda p: p.update({"oops": 1}))
    with pytest.raises(ValueError, match="unknown page fields: \\['oops'\\]"):
        pages.load_page(path)


def test_overlapping_panels_fail(tmp_path: Path) -> None:
    def overlap(p: dict) -> None:
        p["panels"][1]["rect"] = [0.0, 0.5, 0.6, 0.2]  # into panels 0 and 2

    with pytest.raises(ValueError, match="panels 0 and 1 overlap"):
        pages.load_page(_mutated(tmp_path, overlap))


def test_gutter_violation_fails(tmp_path: Path) -> None:
    def squeeze(p: dict) -> None:
        # 0.015 of page height = 27px < gutter 0.02 * 1800 = 36px
        p["panels"][0]["rect"] = [0.0, 0.615, 1.0, 0.385]

    with pytest.raises(ValueError, match="vertical gap 27.0px < gutter 36.0px"):
        pages.load_page(_mutated(tmp_path, squeeze))


def test_unknown_style_fails_listing_known_styles(tmp_path: Path) -> None:
    def style(p: dict) -> None:
        p["panels"][1]["style"] = "nope"

    with pytest.raises(ValueError, match="known styles: anime, manga, western"):
        pages.load_page(_mutated(tmp_path, style))


def test_unknown_page_level_style_fails(tmp_path: Path) -> None:
    path = _mutated(tmp_path, lambda p: p.update({"style": "nope"}))
    with pytest.raises(ValueError, match="page style 'nope' is not a shipped"):
        pages.load_page(path)


def test_bad_reading_direction_fails(tmp_path: Path) -> None:
    path = _mutated(tmp_path, lambda p: p.update({"reading_direction": "ttb"}))
    with pytest.raises(ValueError, match="reading_direction must be"):
        pages.load_page(path)


def test_rect_leaving_the_page_fails(tmp_path: Path) -> None:
    path = _mutated(tmp_path, lambda p: p["panels"][0].update({"rect": [0.0, 0.9, 1.0, 0.38]}))
    with pytest.raises(ValueError, match="leaves the page"):
        pages.load_page(path)


def test_borderless_page_is_valid(tmp_path: Path) -> None:
    def borderless(p: dict) -> None:
        p["page"]["border"] = {"width_px": 0, "color": "#101010"}

    page = pages.load_page(_mutated(tmp_path, borderless))
    assert page["page"]["border"]["width_px"] == 0
