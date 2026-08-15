#!/usr/bin/env python3
"""Merge a BASIC PRG and address-sorted asset PRGs into one loadable PRG.

The game POKEs sprite pointers 187-194, 253 and 254, whose shape data lives in
lsprite.prg at $2E7C. Padding each gap lets a single ",8,1" load place the
sprites and the machine-code soundtrack helper.
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
            'usage: embed-sprites.py BASIC.prg ASSET.prg [ASSET.prg ...] OUT.prg'
        )
    basic_prg = sys.argv[1]
    asset_prgs = sys.argv[2:-1]
    out = sys.argv[-1]

    basic_addr, basic = load(basic_prg)
    payload = bytearray(basic)
    ranges = [f'basic ${basic_addr:04X}-${basic_addr + len(basic) - 1:04X}']

    for asset_prg in asset_prgs:
        asset_addr, asset = load(asset_prg)
        end_addr = basic_addr + len(payload)
        gap = asset_addr - end_addr
        if gap < 0:
            raise SystemExit(
                f'{asset_prg} starts at ${asset_addr:04X}, '
                f'before prior data ends at ${end_addr - 1:04X}'
            )
        payload.extend(b'\x00' * gap)
        payload.extend(asset)
        ranges.append(
            f'{Path(asset_prg).name} ${asset_addr:04X}-'
            f'${asset_addr + len(asset) - 1:04X}'
        )

    Path(out).write_bytes(bytes([basic_addr & 0xFF, basic_addr >> 8]) + payload)
    print(f'{out}: {", ".join(ranges)}, {len(payload) + 2} bytes')


if __name__ == '__main__':
    main()
