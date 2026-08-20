#!/usr/bin/env python3
"""Prepare one C128 asset file for BLOAD.

Each region the C128 edition needs is BLOADed straight to its address in RAM
bank 0, so each one ships as a PRG whose header already names that address. This
tool sets the header and, where a payload runs past the end of the VIC's 16 KB
window, truncates it and says by how much rather than dropping bytes silently.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def address(value: str) -> int:
    parsed = int(value, 0)
    if not 0 <= parsed <= 0xFFFF:
        raise argparse.ArgumentTypeError("address must be between 0 and 0xffff")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--address", type=address, required=True, help="load address to stamp"
    )
    parser.add_argument(
        "--max-end",
        type=address,
        help="truncate so the body ends no later than this address",
    )
    args = parser.parse_args()

    raw = args.input.read_bytes()
    if len(raw) < 3:
        print(f"error: {args.input} is too short to be a PRG", file=sys.stderr)
        return 1
    original = raw[0] | (raw[1] << 8)
    body = raw[2:]
    end = args.address + len(body) - 1

    dropped = 0
    if args.max_end is not None and end > args.max_end:
        dropped = end - args.max_end
        body = body[: len(body) - dropped]
        end = args.max_end

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(
        bytes([args.address & 0xFF, args.address >> 8]) + body
    )
    note = f" (truncated {dropped} bytes)" if dropped else ""
    print(
        f"{args.output.name:<28} ${args.address:04X}-${end:04X} "
        f"{len(body):5d} bytes, was ${original:04X}{note}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
