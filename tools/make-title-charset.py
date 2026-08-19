#!/usr/bin/env python3
"""Build the title-only RAM character set at VIC-bank-2 $8800.

The normal C64 character ROM is copied first, so ordinary PETSCII text keeps
working.  Eight otherwise-unused character codes then become the chunky
LUNALIGHT logo, and two more are the alternating star glyphs.  The game swaps
back to the ROM image at $9000 before flight, so no gameplay glyphs or the
sprite/background collision configuration change.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path


LOAD_ADDRESS = 0x8800
CHARSET_BYTES = 256 * 8

# The title writes these codes directly into the screen matrix; PETSCII text
# continues to use the copied ROM glyphs.  Keep them out of the $80-$8f range:
# BASIC's printed function-key keycaps use screen codes there.
LOGO_CODES = {
    "l": 240,
    "u": 241,
    "n": 242,
    "a": 243,
    "i": 244,
    "g": 245,
    "h": 246,
    "t": 247,
}
STAR_DIM = 248
STAR_BRIGHT = 249


def glyph(rows: list[str]) -> bytes:
    if len(rows) != 8 or any(len(row) != 8 for row in rows):
        raise ValueError("glyphs must be eight rows of eight pixels")
    return bytes(sum((pixel == "#") << (7 - x) for x, pixel in enumerate(row))
                 for row in rows)


GLYPHS = {
    LOGO_CODES["l"]: glyph([
        "##......", "##......", "##......", "##......",
        "##......", "##......", "#######.", "........",
    ]),
    LOGO_CODES["u"]: glyph([
        "##....##", "##....##", "##....##", "##....##",
        "##....##", "###..###", ".######.", "........",
    ]),
    LOGO_CODES["n"]: glyph([
        "##....##", "###...##", "####..##", "##.##.##",
        "##..####", "##...###", "##....##", "........",
    ]),
    LOGO_CODES["a"]: glyph([
        ".######.", "##....##", "##....##", "########",
        "##....##", "##....##", "##....##", "........",
    ]),
    LOGO_CODES["i"]: glyph([
        ".######.", "...##...", "...##...", "...##...",
        "...##...", "...##...", ".######.", "........",
    ]),
    LOGO_CODES["g"]: glyph([
        ".######.", "##....##", "##......", "##..####",
        "##....##", "##....##", ".######.", "........",
    ]),
    LOGO_CODES["h"]: glyph([
        "##....##", "##....##", "##....##", "########",
        "##....##", "##....##", "##....##", "........",
    ]),
    LOGO_CODES["t"]: glyph([
        "########", "...##...", "...##...", "...##...",
        "...##...", "...##...", "...##...", "........",
    ]),
    STAR_DIM: glyph([
        "........", "........", "........", "........",
        "....#...", "........", "........", "........",
    ]),
    STAR_BRIGHT: glyph([
        "........", "....#...", "...###..", ".#######",
        "...###..", "....#...", "........", "........",
    ]),
}


def chargen_path() -> Path:
    candidates = []
    if configured := os.environ.get("C64_CHARGEN"):
        candidates.append(Path(configured))
    candidates.extend([
        Path("/opt/homebrew/share/vice/C64/chargen-901225-01.bin"),
        Path("/opt/homebrew/Cellar/vice/3.10/share/vice/C64/chargen-901225-01.bin"),
        Path("/usr/share/vice/C64/chargen-901225-01.bin"),
        Path("/usr/share/games/vice/C64/chargen-901225-01.bin"),
    ])
    for candidate in candidates:
        if candidate.is_file() and candidate.stat().st_size >= CHARSET_BYTES:
            return candidate
    raise SystemExit(
        "could not find VICE chargen ROM; set C64_CHARGEN to "
        "chargen-901225-01.bin"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    charset = bytearray(chargen_path().read_bytes()[:CHARSET_BYTES])
    for code, bitmap in GLYPHS.items():
        charset[code * 8:(code + 1) * 8] = bitmap
    args.output.write_bytes(bytes((LOAD_ADDRESS & 0xFF, LOAD_ADDRESS >> 8)) + charset)
    print(f"{args.output}: ${LOAD_ADDRESS:04X}-${LOAD_ADDRESS + CHARSET_BYTES - 1:04X}")


if __name__ == "__main__":
    main()
