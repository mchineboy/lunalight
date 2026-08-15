#!/usr/bin/env python3
"""Decode C64 text out of a VICE screenshot by matching the character ROM.

VICE -exitscreenshot writes a 384x272 PNG whose display window starts at
(32,35). Each 8x8 cell is matched against the uppercase charset, normal and
reversed, so gameplay HUD values can be read exactly instead of eyeballed.
"""
import struct
import sys
import zlib
from pathlib import Path

CHARGEN = Path('/opt/homebrew/Cellar/vice/3.10/share/vice/C64/chargen-901225-01.bin')
X0, Y0 = 32, 35
PETSCII = ('@abcdefghijklmnopqrstuvwxyz[\\]^_ !"#$%&\'()*+,-./0123456789:;<=>?')


def read_png(path):
    data = Path(path).read_bytes()
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise SystemExit(f'{path}: not a PNG')
    pos = 8
    idat = b''
    plte = None
    while pos < len(data):
        (length,) = struct.unpack('>I', data[pos:pos + 4])
        ctype = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        if ctype == b'IHDR':
            width, height, depth, color = struct.unpack('>IIBB', chunk[:10])
        elif ctype == b'PLTE':
            plte = chunk
        elif ctype == b'IDAT':
            idat += chunk
        pos += 12 + length
    raw = zlib.decompress(idat)
    if depth != 8 or color not in (3, 6):
        raise SystemExit(f'{path}: expected 8-bit palette/RGBA PNG, got depth={depth} color={color}')
    bpp = 1 if color == 3 else 4
    stride = width * bpp
    rows = []
    prev = bytearray(stride)
    pos = 0
    for _ in range(height):
        ftype = raw[pos]
        line = bytearray(raw[pos + 1:pos + 1 + stride])
        pos += 1 + stride
        if ftype == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif ftype == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ftype == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 0xFF
        elif ftype != 0:
            raise SystemExit(f'unsupported PNG filter {ftype}')
        if bpp == 1:
            rows.append(list(line))
        else:
            rows.append([int.from_bytes(line[i:i + 3], 'big') for i in range(0, stride, bpp)])
        prev = line
    return width, height, rows, plte


def glyphs():
    rom = CHARGEN.read_bytes()
    table = {}
    for code in range(256):
        table[code] = tuple(rom[code * 8 + i] for i in range(8))
    return table


def decode(path):
    width, height, rows, _ = read_png(path)
    table = glyphs()
    out = []
    for r in range(25):
        line = []
        for c in range(40):
            colors = {}
            for y in range(8):
                py = Y0 + r * 8 + y
                for x in range(8):
                    px = X0 + c * 8 + x
                    v = rows[py][px] if py < height and px < width else 0
                    colors[v] = colors.get(v, 0) + 1
            bg = max(colors, key=lambda k: colors[k])
            mask = []
            for y in range(8):
                b = 0
                for x in range(8):
                    py, px = Y0 + r * 8 + y, X0 + c * 8 + x
                    v = rows[py][px] if py < height and px < width else bg
                    b = b << 1 | (0 if v == bg else 1)
                mask.append(b)
            mask = tuple(mask)
            best, code, rev = 9, 32, False
            for cand, pat in table.items():
                d = sum(bin(pat[i] ^ mask[i]).count('1') for i in range(8))
                if d < best:
                    best, code, rev = d, cand, False
                inv = tuple(~p & 0xFF for p in pat)
                d = sum(bin(inv[i] ^ mask[i]).count('1') for i in range(8))
                if d < best:
                    best, code, rev = d, cand, True
            ch = PETSCII[code] if code < len(PETSCII) else '?'
            if best > 6:
                ch = '~'
            line.append(ch.upper() if rev else ch)
        out.append(''.join(line))
    return out


def main():
    for path in sys.argv[1:]:
        print(f'== {path}')
        for r, line in enumerate(decode(path)):
            if line.strip():
                print(f'{r:2d}|{line}')


if __name__ == '__main__':
    main()
