#!/usr/bin/env python3
"""Patch the refuel-pad flag shape into a spare sprite slot of lsprite.prg.

The flag is displayed Y-expanded, so each art row covers two screen pixels:
the pennant is the top six rows and the mast fills the rest, with the base on
row 20 resting on the pad line.
"""
import sys
from pathlib import Path

SLOT = 243  # sprite pointer; data lands at SLOT*64 inside VIC bank 0

FLAG = [
    "...#####################",
    "...#.#.#.#.#.#..........",
    "...##.#.#.#.#.##########",
    "...#.#.#.#.#.#..........",
    "...#####################",
    "...###..................",
    "...#####################",
    "...###..................",
    "...###..................",
    "...###..................",
    "...###..................",
    "...###..................",
    "...###..................",
    "...###..................",
    "...###..................",
    "...###..................",
    "...###..................",
    "...###..................",
    "...###..................",
    "...###..................",
    "..#####.................",
]


def main():
    if len(sys.argv) != 3:
        raise SystemExit('usage: make-flag.py <in.prg> <out.prg>')
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    if len(FLAG) != 21 or any(len(row) != 24 for row in FLAG):
        raise SystemExit('flag art must be 21 rows of 24 columns')

    raw = src.read_bytes()
    base = raw[0] | raw[1] << 8
    body = bytearray(raw[2:])
    off = SLOT * 64 - base
    if off < 0 or off + 64 > len(body):
        raise SystemExit(
            f'slot {SLOT} (${SLOT * 64:04x}) is outside {src} '
            f'(${base:04x}-${base + len(body) - 1:04x})')
    if any(body[off:off + 63]):
        raise SystemExit(f'slot {SLOT} (${SLOT * 64:04x}) already holds sprite data')

    for r, row in enumerate(FLAG):
        for b in range(3):
            bits = 0
            for i in range(8):
                bits = bits << 1 | (row[b * 8 + i] != '.')
            body[off + r * 3 + b] = bits

    dst.write_bytes(raw[:2] + bytes(body))
    print(f'{dst}: flag sprite written to slot {SLOT} (${SLOT * 64:04x})')


if __name__ == '__main__':
    main()
