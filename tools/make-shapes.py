#!/usr/bin/env python3
"""Patch the game's added sprite shapes into spare slots of lsprite.prg.

Both shapes are displayed unexpanded, so each art row is one screen pixel.

Slot 243 is the refuel-pad flag: the pennant carries the Earth wire-globe
emblem in the top twelve rows, the mast fills the rest, and the base on row 20
rests on the pad line.

Slot 244 is the orbiting command module, drawn side-on: docking probe and
conical capsule at the left, service module body, flared engine bell at the
right. It is purely cosmetic and centred on art row 10.
"""
import sys
from pathlib import Path

FLAG = [
    ".#######################",
    ".##......#######....#..#",
    ".##.#..##.......##.....#",
    ".##...#...........#..#.#",
    ".##..#.............#...#",
    ".##..###.........###...#",
    ".##..#..#########..#...#",
    ".##...#...........#....#",
    ".##....##.......##.....#",
    ".##......#######.......#",
    ".##....................#",
    ".#######################",
    ".##.....................",
    ".##.....................",
    ".##.....................",
    ".##.....................",
    ".##.....................",
    ".##.....................",
    ".##.....................",
    ".##.....................",
    "#####...................",
]

MODULE = [
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
    "......#.##########......",
    "....###.##.#######..##..",
    "..##.##.##.##..#######..",
    ".##..##.##############..",
    "..#####.#####...######..",
    "....###.##.##...##..##..",
    "......#.##########......",
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
]

SHAPES = {243: FLAG, 244: MODULE}


def patch(body: bytearray, base: int, slot: int, art: list[str]) -> None:
    off = slot * 64 - base
    if off < 0 or off + 64 > len(body):
        raise SystemExit(
            f'slot {slot} (${slot * 64:04x}) is outside '
            f'${base:04x}-${base + len(body) - 1:04x}')
    # A C64 sprite is 63 bytes; the 64th is padding, so a slot counts as spare
    # when its first 63 bytes are empty.
    if any(body[off:off + 63]):
        raise SystemExit(f'slot {slot} (${slot * 64:04x}) already holds sprite data')
    for r, row in enumerate(art):
        for b in range(3):
            bits = 0
            for i in range(8):
                bits = bits << 1 | (row[b * 8 + i] != '.')
            body[off + r * 3 + b] = bits


def main():
    if len(sys.argv) != 3:
        raise SystemExit('usage: make-shapes.py <in.prg> <out.prg>')
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    for slot, art in SHAPES.items():
        if len(art) != 21 or any(len(row) != 24 for row in art):
            raise SystemExit(f'slot {slot} art must be 21 rows of 24 columns')

    raw = src.read_bytes()
    base = raw[0] | raw[1] << 8
    body = bytearray(raw[2:])
    for slot, art in SHAPES.items():
        patch(body, base, slot, art)

    dst.write_bytes(raw[:2] + bytes(body))
    written = ', '.join(f'{slot} (${slot * 64:04x})' for slot in SHAPES)
    print(f'{dst}: shapes written to slots {written}')


if __name__ == '__main__':
    main()
