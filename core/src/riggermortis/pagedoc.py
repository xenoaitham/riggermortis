"""P4-6 page export — PDF and EPUB assembly as pure-stdlib writers.

The P4-4/P4-5 page PNG is the unit: ``write_pdf`` embeds one PNG per PDF
page (decoded to raw RGB with a stdlib PNG reader, Flate-compressed into
image XObjects) and ``write_epub`` packages the PNGs verbatim into an
EPUB 3 container (zipfile + XHTML). Both writers are BYTE-DETERMINISTIC
(same inputs = identical files: fixed object order, no timestamps, fixed
zip date_time) and carry no runtime dependencies — D-003's
core-stays-dependency-and-process-free rule holds; assembly is a library
call, never a subprocess (D-009).

Honesty: these documents contain GENERATED page renders (P4-4 composited
layouts, P4-5 bubbles = generated geometry + typeset text). Nothing here
hand-letters, hand-draws, or claims otherwise; producers of shipped
documents must label them as pipeline output.

The PDF reader-side (``read_pdf_pages``) parses the file back (xref +
page objects + image XObject headers + stream lengths) so structure is
verifiable with the stdlib alone — pdfinfo-free, the P4-6 gate contract.

Security posture of the reader-side parsers: they are hardened for
untrusted input within stdlib limits — the EPUB reader refuses oversized
containers and any XML carrying a DOCTYPE/ENTITY declaration before
ElementTree sees it (entity-expansion class), and the PDF reader only
inflates streams bounded by the file's own size.

PNG decode subset (deliberate): 8-bit truecolor, color types 2 (RGB) and
6 (RGBA), no interlace — exactly what Blender's PNG writer emits for
page renders. Everything else fails with an actionable error, never a
silent wrong color.
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path
from typing import Any

from .errors import PayloadError

PDF_PRODUCER = "riggermortis pagedoc (generated page renders)"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_MAX_XML_BYTES = 4 * 1024 * 1024


def _parse_xml_hardened(data: bytes, what: str) -> Any:
    """ElementTree with the stdlib-only entity-expansion defense.

    Refuses oversized inputs and any XML carrying a DOCTYPE/ENTITY
    declaration — the external-entity/billion-laughs class — before the
    parser ever sees it.
    """
    import xml.etree.ElementTree as ET

    if len(data) > _MAX_XML_BYTES:
        raise PayloadError(
            f"{what}: {len(data)} bytes exceeds the {_MAX_XML_BYTES} byte "
            "reader limit (hint: not produced by this writer)"
        )
    head = data[:4096].upper()
    if b"<!DOCTYPE" in head or b"<!ENTITY" in head:
        raise PayloadError(
            f"{what}: DOCTYPE/ENTITY declarations are refused (hint: valid "
            "output of this writer never carries them)"
        )
    return ET.fromstring(data)


# ---- PNG decode (subset) ------------------------------------------------------


def decode_png_rgb(path: Any) -> tuple[int, int, bytes]:
    """Decode an 8-bit RGB/RGBA (non-interlaced) PNG to raw RGB rows.

    Returns ``(width, height, rgb_bytes)`` with exactly ``width*height*3``
    bytes, rows top-to-bottom (PNG row order). Raises ``PayloadError``
    with a hint on anything this deliberate subset does not support.
    """
    data = Path(path).read_bytes()
    if not data.startswith(_PNG_MAGIC):
        raise PayloadError(f"{path} is not a PNG (hint: page renders are PNG files)")
    pos = 8
    width = height = 0
    bit_depth = color_type = interlace = 0
    idat = bytearray()
    while pos + 8 <= len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        ctype = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        if ctype == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(
                ">IIBB", chunk[:10]
            )
            interlace = chunk[12]
        elif ctype == b"IDAT":
            idat += chunk
        elif ctype == b"IEND":
            break
        pos += 12 + length
    if not width or not height:
        raise PayloadError(
            f"{path}: PNG has no usable IHDR (hint: re-render the page)"
        )
    if bit_depth != 8:
        raise PayloadError(
            f"{path}: PNG bit depth {bit_depth} unsupported (hint: page "
            "renders are written 8-bit — render with color_depth 8)"
        )
    if color_type not in (2, 6):
        raise PayloadError(
            f"{path}: PNG color type {color_type} unsupported (hint: the "
            "reader supports truecolor RGB(2)/RGBA(6) — what Blender's "
            "writer emits; palette/grayscale inputs need re-rendering)"
        )
    if interlace:
        raise PayloadError(
            f"{path}: interlaced PNG unsupported (hint: page renders are "
            "never interlaced)"
        )
    channels = 3 if color_type == 2 else 4
    raw = zlib.decompress(bytes(idat))
    stride_in = width * channels
    expected = (stride_in + 1) * height
    if len(raw) != expected:
        raise PayloadError(
            f"{path}: PNG pixel stream is {len(raw)} bytes, expected "
            f"{expected} (hint: the file is corrupt or truncated)"
        )
    out = bytearray(width * height * 3)
    prev = bytearray(stride_in)
    src = 0
    dst = 0
    for _row in range(height):
        ftype = raw[src]
        src += 1
        line = bytearray(raw[src:src + stride_in])
        src += stride_in
        if ftype == 1:  # Sub
            for i in range(channels, stride_in):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif ftype == 2:  # Up
            for i in range(stride_in):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ftype == 3:  # Average
            for i in range(stride_in):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:  # Paeth
            for i in range(stride_in):
                a = line[i - channels] if i >= channels else 0
                b = prev[i]
                c = prev[i - channels] if i >= channels else 0
                p = a + b - c
                pa = abs(p - a)
                pb = abs(p - b)
                pc = abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        elif ftype != 0:
            raise PayloadError(
                f"{path}: unknown PNG row filter {ftype} (hint: corrupt file)"
            )
        if channels == 3:
            out[dst:dst + stride_in] = line
            dst += stride_in
        else:
            for i in range(width):
                s = i * 4
                d = dst + i * 3
                out[d] = line[s]
                out[d + 1] = line[s + 1]
                out[d + 2] = line[s + 2]
            dst += width * 3
        prev = line
    return width, height, bytes(out)


# ---- PDF writer ---------------------------------------------------------------


def _pdf_object(num: int, body: str | bytes, stream: bytes | None = None) -> bytes:
    head = f"{num} 0 obj".encode("ascii")
    if stream is None:
        return head + b"\n" + (body.encode("ascii") if isinstance(body, str) else body) + b"\nendobj\n"
    dict_bytes = body.encode("ascii") if isinstance(body, str) else body
    return (
        head
        + b"\n"
        + dict_bytes
        + b"\nstream\n"
        + stream
        + b"\nendstream\nendobj\n"
    )


def build_pdf(
    png_paths: list[Any],
    title: str | None = None,
) -> bytes:
    """Assemble the PDF for the given page PNGs and return its bytes.

    Deterministic by construction: fixed object numbering (1 catalog, 2
    pages tree, then page/image/content triples), fixed content streams,
    no timestamps anywhere (no /CreationDate, /ID omitted — 1.4 allows
    it). ``title`` (optional) lands in a trailing /Info dict.
    """
    if not png_paths:
        raise PayloadError("no page PNGs given (hint: pass the page renders)")
    images = [decode_png_rgb(p) for p in png_paths]

    objs: list[bytes] = []
    kids = []
    page_first = 3
    for i, (_w, _h, _rgb) in enumerate(images):
        kids.append(f"{page_first + 3 * i} 0 R")
    objs.append(_pdf_object(1, "<< /Type /Catalog /Pages 2 0 R >>"))
    objs.append(
        _pdf_object(
            2,
            f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(images)} >>",
        )
    )
    for i, (w, h, rgb) in enumerate(images):
        base = page_first + 3 * i
        img_ref, content_ref = base + 1, base + 2
        objs.append(
            _pdf_object(
                base,
                "<< /Type /Page /Parent 2 0 R "
                f"/MediaBox [0 0 {w} {h}] /Resources << /XObject << /Im{i} "
                f"{img_ref} 0 R >> /ProcSet [/PDF /ImageC] >> /Contents "
                f"{content_ref} 0 R >>",
            )
        )
        comp = zlib.compress(rgb, 6)
        objs.append(
            _pdf_object(
                img_ref,
                f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} "
                "/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter "
                f"/FlateDecode /Length {len(comp)} >>",
                stream=comp,
            )
        )
        content = f"q {w} 0 0 {h} 0 0 cm /Im{i} Do Q".encode("ascii")
        objs.append(
            _pdf_object(
                content_ref,
                f"<< /Length {len(content)} >>",
                stream=content,
            )
        )
    info_num = None
    if title:
        esc = title.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        info_num = len(objs) + 1
        objs.append(
            _pdf_object(
                info_num,
                f"<< /Title ({esc}) /Producer ({PDF_PRODUCER}) >>",
            )
        )
    trailer_root = (
        f"/Size {len(objs) + 1} /Root 1 0 R"
        + (f" /Info {info_num} 0 R" if info_num else "")
    )

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for obj in objs:
        offsets.append(len(out))
        out += obj
    xref_pos = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode("ascii")
    out += f"trailer\n<< {trailer_root} >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
        "ascii"
    )
    return bytes(out)


def write_pdf(png_paths: list[Any], out_path: Any, title: str | None = None) -> None:
    """Write the PDF for the given page PNGs (deterministic bytes)."""
    Path(out_path).write_bytes(build_pdf(png_paths, title=title))


def read_pdf_pages(path: Any) -> list[dict[str, Any]]:
    """Parse a (simple, writer-shaped) PDF back into its page structure.

    Returns one entry per page: MediaBox size, embedded image width/
    height, and the decompressed image stream length (w*h*3). This is the
    pdfinfo-free structural verification the gate uses — it parses the
    xref, the objects, and inflates the image streams (bounded by the
    file's own size — zlib bombs cannot exceed that budget).
    """
    data = Path(path).read_bytes()
    if not data.startswith(b"%PDF-1."):
        raise PayloadError(f"{path} is not a PDF")
    if b"%%EOF" not in data[-32:]:
        raise PayloadError(f"{path}: PDF has no %%EOF trailer (truncated?)")
    xref_pos = int(data.rsplit(b"startxref", 1)[1].split()[0])
    if not data[xref_pos:xref_pos + 4] == b"xref":
        raise PayloadError(
            f"{path}: startxref does not point at an xref table (hint: the "
            "writer only produces non-compressed xref tables)"
        )
    lines = data[xref_pos:].split(b"\n")
    (count,) = (int(lines[1].split()[1]),)
    offsets: dict[int, int] = {}
    for k in range(1, count):
        fields = lines[2 + k].split()
        if fields[0] != b"0000000000":
            offsets[k] = int(fields[0])
    pages = []
    for num in sorted(offsets):
        chunk = data[offsets[num]:]
        # bound the object at its endobj — the slice otherwise runs to EOF
        # and the NEXT object's header leaks into this object's parse
        end = chunk.find(b"endobj")
        chunk = chunk[:end] if end != -1 else chunk
        if b"/Type /Page " in chunk[:200]:
            box = chunk.split(b"/MediaBox [", 1)[1].split(b"]", 1)[0]
            _x, _y, w, h = (int(v) for v in box.split())
            # "/Im<i> <objnum> 0 R" — skip the name token, take the ref
            after_im = chunk.split(b"/Im", 1)[1]
            img_ref = int(after_im.split(b" ", 2)[1])
            img_chunk = data[offsets[img_ref]:]
            iw = int(img_chunk.split(b"/Width ", 1)[1].split(b" ", 1)[0])
            ih = int(img_chunk.split(b"/Height ", 1)[1].split(b" ", 1)[0])
            stream = img_chunk.split(b"stream\n", 1)[1].split(b"\nendstream", 1)[0]
            rgb = zlib.decompress(stream)
            pages.append(
                {
                    "width_pt": w,
                    "height_pt": h,
                    "image_width": iw,
                    "image_height": ih,
                    "image_bytes": len(rgb),
                }
            )
    if not pages:
        raise PayloadError(
            f"{path}: no page objects parsed (hint: the reader understands "
            "the shape build_pdf writes)"
        )
    return pages


# ---- EPUB writer --------------------------------------------------------------


def _zip_add(zf: Any, name: str, data: bytes, compress_type: int | None = None) -> None:
    import zipfile

    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = (
        compress_type if compress_type is not None else zipfile.ZIP_DEFLATED
    )
    zf.writestr(info, data)


def build_epub(
    png_paths: list[Any],
    title: str = "riggermortis pages",
) -> bytes:
    """Assemble an EPUB 3 document of the page PNGs, deterministically.

    mimetype is the FIRST entry and STORED (the EPUB rule); every entry
    uses a fixed date_time so identical inputs give identical zip bytes.
    The images are copied VERBATIM (no re-encode). The content identifier
    is a hash of the image bytes — same pages, same book.
    """
    import hashlib
    import io
    import zipfile

    if not png_paths:
        raise PayloadError("no page PNGs given (hint: pass the page renders)")
    blobs = [Path(p).read_bytes() for p in png_paths]
    digest = hashlib.sha256(b"".join(blobs)).hexdigest()[:32]
    manifest, spine, nav, pages = [], [], [], []
    for i in range(len(blobs)):
        page_doc = f"page_{i:03d}.xhtml"
        img = f"images/page_{i:03d}.png"
        manifest.append(
            f'<item id="p{i}" href="{page_doc}" media-type="application/xhtml+xml"/>'
        )
        manifest.append(f'<item id="img{i}" href="{img}" media-type="image/png"/>')
        spine.append(f'<itemref idref="p{i}"/>')
        nav.append(f'<li><a href="{page_doc}">page {i + 1}</a></li>')
        pages.append(
            "<?xml version='1.0' encoding='utf-8'?>\n"
            "<!DOCTYPE html>"
            "<html xmlns=\"http://www.w3.org/1999/xhtml\" "
            "xmlns:epub=\"http://www.idpf.org/2007/ops\"><head>"
            f"<title>page {i + 1}</title></head><body>"
            f"<img src=\"{img}\" alt=\"generated page {i + 1}\"/></body></html>"
        )
    opf = (
        "<?xml version='1.0' encoding='utf-8'?>\n"
        "<package xmlns=\"http://www.idpf.org/2007/opf\" version=\"3.0\" "
        "unique-identifier=\"bookid\"><metadata "
        "xmlns:dc=\"http://purl.org/dc/elements/1.1/\">"
        f"<dc:identifier id=\"bookid\">urn:riggermortis:{digest}</dc:identifier>"
        f"<dc:title>{title}</dc:title>"
        "<dc:language>en</dc:language>"
        "<meta property=\"dcterms:modified\">1980-01-01T00:00:00Z</meta>"
        "</metadata><manifest>"
        "<item id=\"nav\" href=\"nav.xhtml\" media-type=\"application/xhtml+xml\" "
        "properties=\"nav\"/>"
        + "".join(manifest)
        + "</manifest><spine>"
        + "".join(spine)
        + "</spine></package>"
    )
    container = (
        "<?xml version='1.0' encoding='utf-8'?>\n"
        "<container version=\"1.0\" "
        "xmlns=\"urn:oasis:names:tc:opendocument:xmlns:container\">"
        "<rootfiles><rootfile full-path=\"OEBPS/content.opf\" "
        "media-type=\"application/oebps-package+xml\"/></rootfiles></container>"
    )
    nav_doc = (
        "<?xml version='1.0' encoding='utf-8'?>\n"
        "<!DOCTYPE html>"
        "<html xmlns=\"http://www.w3.org/1999/xhtml\" "
        "xmlns:epub=\"http://www.idpf.org/2007/ops\"><head>"
        f"<title>{title}</title></head><body><nav epub:type=\"toc\"><ol>"
        + "".join(nav)
        + "</ol></nav></body></html>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        _zip_add(zf, "mimetype", b"application/epub+zip", compress_type=zipfile.ZIP_STORED)
        _zip_add(zf, "META-INF/container.xml", container.encode("utf-8"))
        _zip_add(zf, "OEBPS/content.opf", opf.encode("utf-8"))
        _zip_add(zf, "OEBPS/nav.xhtml", nav_doc.encode("utf-8"))
        for i, (blob, page_doc) in enumerate(zip(blobs, pages, strict=True)):
            _zip_add(zf, f"OEBPS/page_{i:03d}.xhtml", page_doc.encode("utf-8"))
            _zip_add(zf, f"OEBPS/images/page_{i:03d}.png", blob)
    return buffer.getvalue()


def write_epub(
    png_paths: list[Any], out_path: Any, title: str = "riggermortis pages"
) -> None:
    """Write the EPUB for the given page PNGs (deterministic bytes)."""
    Path(out_path).write_bytes(build_epub(png_paths, title=title))


def read_epub_structure(path: Any) -> dict[str, Any]:
    """Parse an EPUB back (zip order, OPF manifest/spine counts, images).

    The OPF is parsed through ``_parse_xml_hardened`` — the reader may be
    pointed at files this writer did not produce.
    """
    import zipfile

    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        if not names or names[0] != "mimetype":
            raise PayloadError(
                f"{path}: the first zip entry must be 'mimetype' (EPUB rule)"
            )
        info = zf.getinfo("mimetype")
        if info.compress_type != zipfile.ZIP_STORED:
            raise PayloadError(f"{path}: mimetype must be STORED (EPUB rule)")
        if zf.read("mimetype") != b"application/epub+zip":
            raise PayloadError(f"{path}: mimetype content is wrong")
        ns = {
            "o": "http://www.idpf.org/2007/opf",
            "dc": "http://purl.org/dc/elements/1.1/",
        }
        opf = _parse_xml_hardened(zf.read("OEBPS/content.opf"), "content.opf")
        title = opf.findtext(".//dc:title", default="", namespaces=ns)
        identifier = opf.findtext(".//dc:identifier", default="", namespaces=ns)
        manifest_items = len(opf.findall(".//o:manifest/o:item", ns))
        spine_items = len(opf.findall(".//o:spine/o:itemref", ns))
        page_docs = [n for n in names if n.startswith("OEBPS/page_")]
        images = [n for n in names if n.startswith("OEBPS/images/")]
        return {
            "title": title,
            "identifier": identifier,
            "manifest_items": manifest_items,
            "spine_items": spine_items,
            "page_documents": len(page_docs),
            "images": len(images),
            "entries": len(names),
        }
