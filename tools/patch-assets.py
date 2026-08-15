#!/usr/bin/env python3
"""Overwrite fixed-address holes in a PRG with asset PRGs.

Used after MOSpeed /memhole leaves zeroed ranges for sprites, music, and RNG
so a single LOAD\",8,1\" places the compiled program and its machine-code
helpers without relocating either.
"""
import sys
from pathlib import Path


def load(path):
    data = Path(path).read_bytes()
    if len(data) < 3:
        raise SystemExit(f'{path}: too short to be a PRG')
    return data[0] | data[1] << 8, data[2:]


def main():
    if len(sys.argv) < 4:
        raise SystemExit(
            'usage: patch-assets.py BASE.prg ASSET.prg [ASSET.prg ...] OUT.prg'
        )
    base_prg = sys.argv[1]
    asset_prgs = sys.argv[2:-1]
    out = sys.argv[-1]

    base_addr, payload = load(base_prg)
    payload = bytearray(payload)
    ranges = [f'base ${base_addr:04X}-${base_addr + len(payload) - 1:04X}']

    for asset_prg in asset_prgs:
        addr, data = load(asset_prg)
        off = addr - base_addr
        if off < 0 or off + len(data) > len(payload):
            raise SystemExit(
                f'{asset_prg} ${addr:04X}-${addr + len(data) - 1:04X} '
                f'falls outside base image '
                f'${base_addr:04X}-${base_addr + len(payload) - 1:04X}'
            )
        payload[off : off + len(data)] = data
        ranges.append(
            f'{Path(asset_prg).name} ${addr:04X}-${addr + len(data) - 1:04X}'
        )

    Path(out).write_bytes(bytes([base_addr & 0xFF, base_addr >> 8]) + payload)
    print(f'{out}: {", ".join(ranges)}, {len(payload) + 2} bytes')


if __name__ == '__main__':
    main()
