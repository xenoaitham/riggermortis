"""P4-6 export tests — stdlib PDF/EPUB writers + PNG decode, no bpy.

The writers are pure stdlib (D-003): the tests build SYNTHETIC PNGs
(zlib + hand-written chunks, all four row filters), assemble documents,
parse them back with the reader-side (pdfinfo-free), and assert
byte-determinism. The CLI is exercised IN-PROCESS (no spawn — D-003/D-009).
The Blender page-render half of the gate is the style probe's EXPORT
section (``RM_STYLE EXPORT`` lines).
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

import pytest

from riggermortis.cli import EXIT_OK
from riggermortis.cli import main as cli_main
from riggermortis.errors import PayloadError
from riggermortis.pagedoc import (
    build_pdf,
    decode_png_rgb,
    read_epub_structure,
    read_pdf_pages,
    write_epub,
    write_pdf,
)


def _png_chunk(ctype: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + ctype
        + data
        + struct.pack(">I", zlib.crc32(ctype + data) & 0xFFFFFFFF)
    )


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _write_png(
    path: Path,
    pixels: list[list[tuple[int, int, int]]],
    color_type: int = 2,
    filter_type: int = 0,
) -> None:
    """Write a minimal 8-bit PNG with a FIXED row filter (test control).

    The forward filter is genuinely applied (filter byte alone would be a
    lie the decoder rightly rejects) — this is what exercises the
    decoder's inverse for every filter type.
    """
    h = len(pixels)
    w = len(pixels[0])
    channels = 3 if color_type == 2 else 4
    ihdr = struct.pack(">IIBBBBB", w, h, 8, color_type, 0, 0, 0)
    rows = bytearray()
    prev = bytes(w * channels)
    for row in pixels:
        raw = bytearray()
        for r, g, b in row:
            for v in ((r, g, b) if channels == 3 else (r, g, b, 255)):
                raw.append(v)
        filtered = bytearray(w * channels)
        for i in range(w * channels):
            left = raw[i - channels] if i >= channels else 0
            up = prev[i]
            ul = prev[i - channels] if i >= channels else 0
            if filter_type == 0:
                filtered[i] = raw[i]
            elif filter_type == 1:
                filtered[i] = (raw[i] - left) & 0xFF
            elif filter_type == 2:
                filtered[i] = (raw[i] - up) & 0xFF
            elif filter_type == 3:
                filtered[i] = (raw[i] - (left + up) // 2) & 0xFF
            else:
                filtered[i] = (raw[i] - _paeth(left, up, ul)) & 0xFF
        rows.append(filter_type)
        rows += filtered
        prev = bytes(raw)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(bytes(rows)))
        + _png_chunk(b"IEND", b"")
    )


def _gradient(w: int, h: int) -> list[list[tuple[int, int, int]]]:
    return [
        [((x * 7) % 256, (y * 5) % 256, (x * y) % 256) for x in range(w)]
        for y in range(h)
    ]


def test_png_decode_all_row_filters(tmp_path: Path) -> None:
    """Pixels must decode identically no matter which row filter was used."""
    pixels = _gradient(23, 9)  # non-round sizes exercise stride math
    for ftype in (0, 1, 2, 3, 4):
        p = tmp_path / f"f{ftype}.png"
        _write_png(p, pixels, filter_type=ftype)
        w, h, rgb = decode_png_rgb(p)
        assert (w, h) == (23, 9)
        assert len(rgb) == 23 * 9 * 3
        got = [
            tuple(rgb[(y * 23 + x) * 3:(y * 23 + x) * 3 + 3])
            for y in range(h)
            for x in range(w)
        ]
        want = [px for row in pixels for px in row]
        assert got == want


def test_png_decode_rgba_drops_alpha(tmp_path: Path) -> None:
    p = tmp_path / "rgba.png"
    _write_png(p, _gradient(4, 4), color_type=6)
    w, h, rgb = decode_png_rgb(p)
    assert (w, h) == (4, 4)
    assert len(rgb) == 4 * 4 * 3


def test_png_decode_rejects_unsupported_shapes(tmp_path: Path) -> None:
    p = tmp_path / "gray.png"
    p.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 0, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00\x00\x00"))
        + _png_chunk(b"IEND", b"")
    )
    with pytest.raises(PayloadError, match="color type 0 unsupported"):
        decode_png_rgb(p)

    p16 = tmp_path / "sixteen.png"
    p16.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 16, 2, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(b"\x00" * 24))
        + _png_chunk(b"IEND", b"")
    )
    with pytest.raises(PayloadError, match="bit depth 16 unsupported"):
        decode_png_rgb(p16)

    notpng = tmp_path / "nope.png"
    notpng.write_bytes(b"not a png at all")
    with pytest.raises(PayloadError, match="is not a PNG"):
        decode_png_rgb(notpng)


def test_pdf_round_trip_and_determinism(tmp_path: Path) -> None:
    pages = []
    for i, (w, h) in enumerate([(24, 16), (20, 30)]):
        p = tmp_path / f"page_{i}.png"
        _write_png(p, _gradient(w, h))
        pages.append(p)
    out1 = tmp_path / "a.pdf"
    out2 = tmp_path / "b.pdf"
    write_pdf(pages, out1, title="test (doc)")
    write_pdf(pages, out2, title="test (doc)")
    raw1 = out1.read_bytes()
    assert raw1 == out2.read_bytes(), "same inputs must give identical bytes"
    assert b"/CreationDate" not in raw1, "no timestamps — determinism"
    assert b"%%EOF" in raw1[-32:]

    parsed = read_pdf_pages(out1)
    assert len(parsed) == 2
    assert parsed[0]["width_pt"] == 24 and parsed[0]["height_pt"] == 16
    assert parsed[1]["width_pt"] == 20 and parsed[1]["height_pt"] == 30
    for entry in parsed:
        assert entry["image_bytes"] == entry["image_width"] * entry["image_height"] * 3


def test_pdf_embedded_pixels_match_the_source(tmp_path: Path) -> None:
    pixels = _gradient(12, 8)
    p = tmp_path / "page.png"
    _write_png(p, pixels)
    pdf = build_pdf([p], title=None)
    # inflate the first image stream straight out of the assembled bytes
    chunk = pdf.split(b"/Subtype /Image", 1)[1]
    stream = chunk.split(b"stream\n", 1)[1].split(b"\nendstream", 1)[0]
    rgb = zlib.decompress(stream)
    want = [v for row in pixels for px in row for v in px]
    assert list(rgb) == want


def test_epub_structure_and_determinism(tmp_path: Path) -> None:
    pages = []
    for i in range(2):
        p = tmp_path / f"page_{i}.png"
        _write_png(p, _gradient(16, 24))
        pages.append(p)
    out1 = tmp_path / "a.epub"
    out2 = tmp_path / "b.epub"
    write_epub(pages, out1, title="manga")
    write_epub(pages, out2, title="manga")
    assert out1.read_bytes() == out2.read_bytes(), "deterministic zip bytes"

    structure = read_epub_structure(out1)
    assert structure["title"] == "manga"
    assert structure["identifier"].startswith("urn:riggermortis:")
    assert structure["manifest_items"] == 2 * 2 + 1  # pages + images + nav
    assert structure["spine_items"] == 2
    assert structure["page_documents"] == 2
    assert structure["images"] == 2
    # images copied VERBATIM
    import zipfile

    with zipfile.ZipFile(out1) as zf:
        assert zf.read("OEBPS/images/page_000.png") == pages[0].read_bytes()


def test_epub_reader_refuses_entity_declarations(tmp_path: Path) -> None:
    pages = []
    p = tmp_path / "page.png"
    _write_png(p, _gradient(4, 4))
    pages.append(p)
    out = tmp_path / "evil.epub"
    write_epub(pages, out)
    import zipfile

    with zipfile.ZipFile(out) as zf:
        infos = [(i, zf.read(i.filename)) for i in zf.infolist()]
    evil_opf = (
        b"<?xml version='1.0'?><!DOCTYPE foo [<!ENTITY a 'aaa'>]>"
        b"<package xmlns='http://www.idpf.org/2007/opf'/>"
    )
    with zipfile.ZipFile(out, "w") as zf:
        for info, data in infos:
            if info.filename == "OEBPS/content.opf":
                data = evil_opf
            zf.writestr(info, data)
    with pytest.raises(PayloadError, match="DOCTYPE/ENTITY"):
        read_epub_structure(out)


def test_writers_reject_empty_inputs(tmp_path: Path) -> None:
    with pytest.raises(PayloadError, match="no page PNGs"):
        build_pdf([])
    with pytest.raises(PayloadError, match="no page PNGs"):
        write_epub([], tmp_path / "x.epub")


def test_export_cli_commands_in_process(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The CLI surface exercises the same writers + parse-back self-check."""
    pages = []
    for i in range(2):
        p = tmp_path / f"page_{i}.png"
        _write_png(p, _gradient(10, 14))
        pages.append(p)
    pdf = tmp_path / "doc.pdf"
    rc = cli_main(
        ["export-pdf", *[str(p) for p in pages], "--out", str(pdf), "--title", "demo"]
    )
    assert rc == EXIT_OK
    assert "parse-back verified" in capsys.readouterr().out
    assert pdf.is_file()

    epub = tmp_path / "doc.epub"
    rc = cli_main(
        ["export-epub", *[str(p) for p in pages], "--out", str(epub), "--title", "demo"]
    )
    assert rc == EXIT_OK
    assert "structure verified" in capsys.readouterr().out
    assert epub.is_file()
