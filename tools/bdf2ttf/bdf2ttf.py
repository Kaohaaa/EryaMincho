#!/usr/bin/env python3
"""Convert a BDF bitmap font to a TrueType outline font (TTF).

Requires:
    python -m pip install fonttools

This converter preserves BDF pixel geometry by turning horizontal runs of set
pixels into rectangular TrueType contours. It does not automatically implement
complex-script shaping; see the accompanying metadata example and documentation.
"""
from __future__ import annotations

import argparse
import codecs
import json
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.feaLib.builder import addOpenTypeFeatures


def parse_bdf(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Parse the commonly used BDF properties and glyph records."""
    try:
        lines = path.read_text(encoding="ascii", errors="strict").splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError("BDF must be an ASCII text file.") from exc

    font_box: tuple[int, int, int, int] | None = None
    properties: dict[str, str] = {}
    glyphs: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    in_properties = False
    in_bitmap = False
    expected_bitmap_rows = 0

    for line_no, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("COMMENT"):
            continue

        if current is None:
            if line.startswith("FONTBOUNDINGBOX "):
                parts = line.split()
                if len(parts) >= 5:
                    font_box = tuple(map(int, parts[1:5]))  # type: ignore[assignment]
            elif line == "STARTPROPERTIES" or line.startswith("STARTPROPERTIES "):
                in_properties = True
            elif line == "ENDPROPERTIES":
                in_properties = False
            elif in_properties:
                parts = line.split(maxsplit=1)
                if len(parts) == 2:
                    properties[parts[0]] = parts[1].strip().strip('"')
            elif line == "STARTCHAR" or line.startswith("STARTCHAR "):
                name = line[len("STARTCHAR"):].strip() or f"glyph{len(glyphs)}"
                current = {
                    "source_name": name, "encoding": None, "dwidth": (0, 0),
                    "bbx": (0, 0, 0, 0), "bitmap": [],
                }
            continue

        if in_bitmap:
            if line == "ENDCHAR":
                if len(current["bitmap"]) != expected_bitmap_rows:
                    raise ValueError(
                        f"Line {line_no}: glyph {current['source_name']!r} has "
                        f"{len(current['bitmap'])} bitmap rows; expected {expected_bitmap_rows}."
                    )
                glyphs.append(current)
                current = None
                in_bitmap = False
                continue
            if len(current["bitmap"]) >= expected_bitmap_rows:
                raise ValueError(
                    f"Line {line_no}: unexpected bitmap row in glyph {current['source_name']!r}."
                )
            current["bitmap"].append(line)
            continue

        if line.startswith("ENCODING "):
            nums = line.split()[1:]
            current["encoding"] = int(nums[0]) if nums else None
            # BDF permits "ENCODING -1 <actual-codepoint>" for non-standard encodings.
            if len(nums) > 1 and int(nums[0]) == -1:
                current["encoding"] = int(nums[1])
        elif line.startswith("DWIDTH "):
            nums = line.split()
            current["dwidth"] = (int(nums[1]), int(nums[2]))
        elif line.startswith("BBX "):
            nums = line.split()
            current["bbx"] = tuple(map(int, nums[1:5]))
        elif line == "BITMAP":
            in_bitmap = True
            expected_bitmap_rows = current["bbx"][1]

    if current is not None:
        raise ValueError(f"Unterminated BDF glyph: {current['source_name']!r}.")
    if not glyphs:
        raise ValueError("No glyphs found in the BDF file.")
    if font_box is None:
        raise ValueError("Missing FONTBOUNDINGBOX declaration.")

    return {"font_box": font_box, "properties": properties}, glyphs


def glyph_name(codepoint: int) -> str:
    if codepoint <= 0xFFFF:
        return f"uni{codepoint:04X}"
    return f"u{codepoint:05X}"


def pixel_runs(glyph: dict[str, Any]) -> list[tuple[int, int, int, int]]:
    """Return rectangles (x0, y0, x1, y1) in BDF pixel coordinates.

    Consecutive set pixels in a row are merged into one rectangle. Rows are
    interpreted top-to-bottom in BDF, while coordinates are baseline-oriented.
    """
    width, height, xoff, yoff = glyph["bbx"]
    rows = glyph["bitmap"]
    rectangles: list[tuple[int, int, int, int]] = []

    for row_index, row_hex in enumerate(rows):
        try:
            row_bytes = bytes.fromhex(row_hex)
        except ValueError as exc:
            raise ValueError(
                f"Invalid bitmap hex in glyph {glyph['source_name']!r}: {row_hex!r}"
            ) from exc

        bits = "".join(f"{byte:08b}" for byte in row_bytes)
        if len(bits) < width:
            raise ValueError(
                f"Bitmap row too short in glyph {glyph['source_name']!r}."
            )
        # BDF stores pixels most-significant-bit first; ignore byte padding.
        bits = bits[:width]
        y = yoff + height - row_index - 1
        x = 0
        while x < width:
            if bits[x] == "0":
                x += 1
                continue
            start = x
            while x < width and bits[x] == "1":
                x += 1
            rectangles.append((xoff + start, y, xoff + x, y + 1))

    # Merge identical horizontal runs across adjacent rows. This keeps the
    # outlines compact without changing the bitmap geometry.
    merged: list[list[int]] = []
    active: dict[tuple[int, int], int] = {}
    for x0, y0, x1, y1 in sorted(rectangles, key=lambda r: (r[1], r[0])):
        key = (x0, x1)
        if key in active and merged[active[key]][3] == y0:
            merged[active[key]][3] = y1
        else:
            merged.append([x0, y0, x1, y1])
            active[key] = len(merged) - 1
        # Entries whose top edge is below this row can no longer be extended.
        active = {k: idx for k, idx in active.items() if merged[idx][3] >= y1}
    return [tuple(r) for r in merged]  # type: ignore[return-value]


def add_rect(pen: TTGlyphPen, x0: float, y0: float, x1: float, y1: float) -> None:
    # Consistent clockwise contour in the TrueType coordinate system.
    pen.moveTo((x0, y0))
    pen.lineTo((x0, y1))
    pen.lineTo((x1, y1))
    pen.lineTo((x1, y0))
    pen.closePath()


def localized_name(value: Any, fallback: str | None = None) -> Any:
    if value is None:
        return fallback
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and value:
        return value
    raise ValueError("Metadata name fields must be strings or language-to-string objects.")


def load_metadata(path: Path | None, bdf_properties: dict[str, str]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    if path:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Cannot read metadata JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError("Metadata JSON root must be an object.")

    # JSON takes precedence; selected BDF properties provide sensible defaults.
    family = data.get("familyName") or bdf_properties.get("FAMILY_NAME") or "BDF Converted Font"
    style = data.get("styleName") or "Regular"
    version = str(data.get("version") or "1.0")
    ps_name = data.get("psName") or re.sub(r"[^A-Za-z0-9-]", "", str(family)) + "-" + re.sub(
        r"[^A-Za-z0-9-]", "", str(style)
    )
    full_name = data.get("fullName") or (
        (family.get("en", "Font") if isinstance(family, dict) else family)
        + " "
        + (style.get("en", "Regular") if isinstance(style, dict) else style)
    )
    result = {
        "familyName": localized_name(family),
        "styleName": localized_name(style, "Regular"),
        "fullName": localized_name(full_name),
        "psName": ps_name,
        "sampleText": data.get("sampleText"),
        "vendorID": data.get("vendorID", "NONE"),
        "uniqueFontIdentifier": data.get("uniqueFontIdentifier") or f"{ps_name};{version}",
        "version": version,
        "copyright": data.get("copyright") or bdf_properties.get("COPYRIGHT"),
        "trademark": data.get("trademark"),
        "manufacturer": data.get("manufacturer"),
        "designer": data.get("designer"),
        "description": data.get("description"),
        "vendorURL": data.get("vendorURL"),
        "designerURL": data.get("designerURL"),
        "licenseDescription": data.get("licenseDescription"),
        "licenseInfoURL": data.get("licenseInfoURL"),
        "typographicFamily": data.get("typographicFamily"),
        "typographicSubfamily": data.get("typographicSubfamily"),
        "compatibleFullName": data.get("compatibleFullName"),
        "wwsFamilyName": data.get("wwsFamilyName"),
        "wwsSubfamilyName": data.get("wwsSubfamilyName"),
    }
    return {k: v for k, v in result.items() if v is not None}


# OS/2 Code Page Range bit -> Python codec. Detection uses characters
# representable in each code page, excluding ASCII/control characters shared
# by nearly all encodings; otherwise a font containing only "A" would appear
# to support every code page. Some legacy code-page bits share a codec.
CODE_PAGE_CODECS: dict[int, str] = {
    0: "cp1252", 1: "cp1250", 2: "cp1251", 3: "cp1253",
    4: "cp1254", 5: "cp1255", 6: "cp1256", 7: "cp1257",
    8: "cp1258", 16: "cp874", 17: "cp932", 18: "cp936",
    19: "cp949", 20: "cp950", 21: "cp1361", 29: "mac_roman",
    30: "cp437", 48: "cp737", 49: "cp866", 50: "cp865",
    51: "cp864", 52: "cp863", 53: "cp862", 54: "cp861",
    55: "cp860", 56: "cp857", 57: "cp855", 58: "cp852",
    59: "cp775", 60: "cp869", 62: "cp850",
    63: "cp437",
}


@lru_cache(maxsize=None)
def code_page_repertoire(codec_name: str) -> frozenset[int]:
    """Return non-ASCII Unicode characters representable by a code page."""
    repertoire: set[int] = set()
    codec = codecs.lookup(codec_name)
    # Single-byte encodings and the single-byte portions of multibyte ones.
    for first in range(0x100):
        try:
            decoded = bytes([first]).decode(codec.name, errors="strict")
        except (UnicodeDecodeError, LookupError):
            continue
        repertoire.update(ord(char) for char in decoded if ord(char) >= 0xA0)

    # Windows East Asian and Johab code pages use two-byte sequences. Trying
    # all pairs also catches valid lead/trail combinations without locale APIs.
    if codec_name in {"cp932", "cp936", "cp949", "cp950", "cp1361"}:
        for first in range(0x100):
            for second in range(0x100):
                try:
                    decoded = bytes((first, second)).decode(codec.name, errors="strict")
                except UnicodeDecodeError:
                    continue
                repertoire.update(ord(char) for char in decoded if ord(char) >= 0xA0)
    return frozenset(repertoire)


def detect_code_page_ranges(codepoints: set[int]) -> set[int]:
    """Set a code-page bit when the cmap contains any distinctive character
    representable in that code page. This is a heuristic, not a completeness
    test; code pages with overlapping repertoires can both be flagged.
    """
    bits: set[int] = set()
    for bit, codec_name in CODE_PAGE_CODECS.items():
        if codepoints.intersection(code_page_repertoire(codec_name)):
            bits.add(bit)
    return bits


def build_font(
    header: dict[str, Any],
    source_glyphs: list[dict[str, Any]],
    output_path: Path,
    metadata: dict[str, Any],
    upm: int,
    features_path: Path | None,
) -> tuple[int, int]:
    font_box = header["font_box"]
    _, cell_height, _, _ = font_box
    if cell_height <= 0:
        raise ValueError("FONTBOUNDINGBOX height must be positive.")
    scale = upm / cell_height

    by_codepoint: dict[int, dict[str, Any]] = {}
    for glyph in source_glyphs:
        cp = glyph["encoding"]
        if cp is None or cp < 0:
            continue
        if cp > 0x10FFFF or 0xD800 <= cp <= 0xDFFF:
            raise ValueError(f"Invalid Unicode scalar value in BDF: U+{cp:X}.")
        if cp in by_codepoint:
            # Keep the first occurrence deterministically and warn about duplicates.
            print(f"Warning: duplicate encoding U+{cp:04X}; keeping first glyph.", file=sys.stderr)
            continue
        by_codepoint[cp] = glyph

    if not by_codepoint:
        raise ValueError("No Unicode-encoded glyphs found.")

    # .notdef is always first in glyph order.
    cmap: dict[int, str] = {}
    glyph_order = [".notdef"]
    glyphs: dict[str, Any] = {}
    metrics: dict[str, tuple[int, int]] = {}

    empty_pen = TTGlyphPen(None)
    glyphs[".notdef"] = empty_pen.glyph()
    metrics[".notdef"] = (upm, 0)

    for cp, src in sorted(by_codepoint.items()):
        name = glyph_name(cp)
        # Avoid duplicate glyph names in unusual input.
        if name in glyphs:
            continue
        pen = TTGlyphPen(None)
        for x0, y0, x1, y1 in pixel_runs(src):
            add_rect(
                pen,
                round(x0 * scale), round(y0 * scale),
                round(x1 * scale), round(y1 * scale),
            )
        glyphs[name] = pen.glyph()
        glyph_order.append(name)
        cmap[cp] = name

        advance = round(src["dwidth"][0] * scale)
        xoff = src["bbx"][2]
        lsb = round(xoff * scale)
        metrics[name] = (advance, lsb)

    fb = FontBuilder(upm, isTTF=True)
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(metrics)

    # Derive vertical metrics from the BDF font bounding box, preserving the
    # baseline offsets. The values are scaled from BDF pixels to font units.
    _, box_h, box_x, box_y = font_box
    ascent = max(1, round((box_y + box_h) * scale))
    descent = max(0, round(max(0, -box_y) * scale))
    if ascent + descent > 0x7FFF:
        raise ValueError("Vertical metrics exceed the supported TrueType range.")

    fb.setupHead(unitsPerEm=upm)
    fb.setupHorizontalHeader(ascent=ascent, descent=-descent, lineGap=0)
    name_metadata = {key: value for key, value in metadata.items() if key != "vendorID"}
    fb.setupNameTable(name_metadata)
    vendor_id = metadata.get("vendorID", "NONE")
    if not isinstance(vendor_id, str) or not re.fullmatch(r"[ -~]{4}", vendor_id):
        raise ValueError("vendorID must be exactly four printable ASCII characters.")

    fb.setupOS2(
        sTypoAscender=ascent,
        sTypoDescender=-descent,
        sTypoLineGap=0,
        usWinAscent=min(ascent, 0xFFFF),
        usWinDescent=min(descent, 0xFFFF),
        usWeightClass=400,
        usWidthClass=5,
        fsSelection=0x0040,  # REGULAR
        version=4,
    )
    fb.setupPost()

    # Set the four-character OpenType vendor identifier.
    os2 = fb.font["OS/2"]
    os2.achVendID = vendor_id

    # Recalculate both OS/2 coverage fields from the actual Unicode cmap.
    os2.recalcUnicodeRanges(fb.font)
    os2.setCodePageRanges(detect_code_page_ranges(set(cmap)))

    if features_path:
        try:
            addOpenTypeFeatures(fb.font, str(features_path))
        except Exception as exc:
            raise ValueError(f"Could not compile OpenType feature file: {exc}") from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fb.save(output_path)
    return len(cmap), len(glyph_order)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert a BDF bitmap font to a TrueType outline font (TTF)."
    )
    parser.add_argument("input", type=Path, help="Input .bdf file")
    parser.add_argument("output", type=Path, help="Output .ttf file")
    parser.add_argument(
        "-m", "--metadata", type=Path, help="UTF-8 JSON file containing localized font metadata"
    )
    parser.add_argument(
        "--features", type=Path,
        help="Optional OpenType feature file (.fea) for GSUB/GPOS shaping rules"
    )
    parser.add_argument(
        "--upm", type=int, default=1000,
        help="Units per em (default: 1000; must be between 16 and 16384)"
    )
    args = parser.parse_args()

    if not 16 <= args.upm <= 16384:
        parser.error("--upm must be between 16 and 16384.")
    if not args.input.is_file():
        parser.error(f"Input file does not exist: {args.input}")
    if args.metadata and not args.metadata.is_file():
        parser.error(f"Metadata JSON does not exist: {args.metadata}")
    if args.features and not args.features.is_file():
        parser.error(f"Feature file does not exist: {args.features}")

    try:
        header, source_glyphs = parse_bdf(args.input)
        metadata = load_metadata(
            args.metadata, header["properties"]
        )
        count, total = build_font(
            header, source_glyphs, args.output, metadata, args.upm, args.features
        )
    except (OSError, ValueError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Created: {args.output}")
    print(f"Unicode characters: {count}")
    print(f"Total glyphs (including .notdef): {total}")
    print("OS/2 Unicode ranges and code page ranges were recalculated from glyph coverage.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
