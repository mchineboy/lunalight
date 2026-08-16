#!/usr/bin/env python3
"""Change a PRG load address without modifying its payload."""

from __future__ import annotations

import argparse
from pathlib import Path


def address(value: str) -> int:
    parsed = int(value, 0)
    if not 0 <= parsed <= 0xFFFF:
        raise argparse.ArgumentTypeError("address must be between 0 and 0xffff")
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--from-address", type=address, required=True)
    parser.add_argument("--to-address", type=address, required=True)
    args = parser.parse_args()

    original = args.input.read_bytes()
    if len(original) < 3:
        raise SystemExit(f"{args.input}: too short to be a PRG")

    actual = int.from_bytes(original[:2], "little")
    if actual != args.from_address:
        raise SystemExit(
            f"{args.input}: expected load address ${args.from_address:04X}, "
            f"found ${actual:04X}"
        )

    rebased = args.to_address.to_bytes(2, "little") + original[2:]
    args.output.write_bytes(rebased)
    print(
        f"{args.output}: load ${actual:04X} -> ${args.to_address:04X}, "
        f"{len(original) - 2} payload bytes unchanged"
    )


if __name__ == "__main__":
    main()
