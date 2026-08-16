#!/usr/bin/env python3
"""Measure bank-2 code headroom and emit a capacity artifact for it.

Relocating the sprites out of VIC bank 0 frees the address range the shapes
used to occupy. This tool measures where the compiled code actually ends, how
far it may now grow, and writes a padded copy of the compiled PRG whose payload
extends through the old sprite region with a recognisable filler byte. Loading
that artifact and reading the filler back proves the range is available rather
than merely unclaimed on paper.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def address(value: str) -> int:
    parsed = int(value, 0)
    if not 0 <= parsed <= 0xFFFF:
        raise argparse.ArgumentTypeError("address must be between 0 and 0xffff")
    return parsed


def byte(value: str) -> int:
    parsed = int(value, 0)
    if not 0 <= parsed <= 0xFF:
        raise argparse.ArgumentTypeError("filler must be a single byte")
    return parsed


def load_prg(path: Path) -> tuple[int, bytes]:
    data = path.read_bytes()
    if len(data) < 3:
        raise SystemExit(f"{path}: too short to be a PRG")
    return int.from_bytes(data[:2], "little"), data[2:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--code-prg", type=Path, required=True)
    parser.add_argument("--sprite-prg", type=Path, required=True)
    parser.add_argument("--original-sprite-prg", type=Path, required=True)
    parser.add_argument("--music-prg", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--filler-value", type=byte, default=0xAA)
    parser.add_argument(
        "--reserve-bytes",
        type=int,
        default=0,
        help="leave zero-filled runtime workspace after the compiled payload",
    )
    parser.add_argument(
        "--extend-to",
        type=address,
        help="last address the padded payload occupies (default: music start - 1)",
    )
    args = parser.parse_args()

    code_addr, code = load_prg(args.code_prg)
    sprite_addr, sprites = load_prg(args.sprite_prg)
    original_addr, original = load_prg(args.original_sprite_prg)
    music_addr, music = load_prg(args.music_prg)

    code_end = code_addr + len(code) - 1
    if args.reserve_bytes < 0:
        raise SystemExit("--reserve-bytes must be non-negative")
    reserve_start = code_end + 1
    reserve_end = code_end + args.reserve_bytes
    old_ceiling = original_addr - 1
    new_ceiling = music_addr - 1
    extend_to = args.extend_to if args.extend_to is not None else new_ceiling

    failures: list[str] = []
    if extend_to <= reserve_end:
        failures.append(
            f"--extend-to ${extend_to:04X} is not above the reserved runtime "
            f"workspace ending ${reserve_end:04X}"
        )
    if extend_to < original_addr:
        failures.append(
            f"--extend-to ${extend_to:04X} does not reach the old sprite region "
            f"starting ${original_addr:04X}"
        )
    if extend_to >= sprite_addr:
        failures.append(
            f"--extend-to ${extend_to:04X} overlaps the relocated sprites at "
            f"${sprite_addr:04X}"
        )
    if extend_to >= music_addr:
        failures.append(
            f"--extend-to ${extend_to:04X} overlaps the music player at "
            f"${music_addr:04X}"
        )

    filler_start = reserve_end + 1
    filler_bytes = extend_to - reserve_end
    payload = (
        bytes(code)
        + bytes(args.reserve_bytes)
        + bytes([args.filler_value]) * max(filler_bytes, 0)
    )
    report = {
        "code": {
            "range": f"${code_addr:04X}-${code_end:04X}",
            "bytes": len(code),
        },
        "old_layout": {
            "sprites": f"${original_addr:04X}-${original_addr + len(original) - 1:04X}",
            "code_ceiling": f"${old_ceiling:04X}",
            "headroom_bytes": old_ceiling - code_end,
        },
        "bank2_layout": {
            "relocated_sprites": f"${sprite_addr:04X}-"
            f"${sprite_addr + len(sprites) - 1:04X}",
            "music": f"${music_addr:04X}-${music_addr + len(music) - 1:04X}",
            "code_ceiling": f"${new_ceiling:04X}",
            "headroom_bytes": new_ceiling - code_end,
        },
        "headroom_gain_bytes": (new_ceiling - code_end) - (old_ceiling - code_end),
        "filler": {
            "start": filler_start,
            "end": extend_to,
            "value": args.filler_value,
            "bytes": filler_bytes,
        },
        "runtime_reserve": {
            "start": reserve_start,
            "end": reserve_end,
            "bytes": args.reserve_bytes,
        },
        "artifact": str(args.output),
        "failures": failures,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")

    print(f"code                 {report['code']['range']} ({len(code)} bytes)")
    print(
        f"old sprite start     ${original_addr:04X}  "
        f"headroom {report['old_layout']['headroom_bytes']} bytes"
    )
    print(
        f"bank-2 ceiling       ${new_ceiling:04X} (music start - 1)  "
        f"headroom {report['bank2_layout']['headroom_bytes']} bytes"
    )
    print(f"headroom gain        {report['headroom_gain_bytes']} bytes")
    print(
        f"runtime reserve      ${reserve_start:04X}-${reserve_end:04X} "
        f"({args.reserve_bytes} zero bytes)"
    )
    print(
        f"filler               ${filler_start:04X}-${extend_to:04X} "
        f"({filler_bytes} bytes of 0x{args.filler_value:02x})"
    )
    print(f"relocated sprites    {report['bank2_layout']['relocated_sprites']}")
    if failures:
        for failure in failures:
            print(f"bank2-capacity: {failure}")
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(code_addr.to_bytes(2, "little") + payload)
    print(
        f"{args.output}: ${code_addr:04X}-${extend_to:04X}, "
        f"{len(payload) + 2} bytes, no sprite overlap"
    )
    print(f"report: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
