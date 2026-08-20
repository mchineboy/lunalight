#!/usr/bin/env python3
"""Build the native-C128 VIC-IIe artifacts. Never invokes Blitz!.

The Phase 0 package is a pure BASIC 7 program at $1C01: the $1300 machine-code
gateway is assembled with ca65/ld65 and then embedded as DATA, so VICE can
autostart the PRG as an ordinary BASIC program with no custom loader. The
builder rejects overlapping regions and writes a machine-readable layout report
beside the PRG.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

DATA_MARKER = re.compile(r"^\s*9000\s+rem\b", re.IGNORECASE)
# Free bank-0 RAM on the C128: no ROM shadows it and BASIC text starts above it.
FREE_RAM = (0x1300, 0x1BFF)
# Where the probe leaves its findings for tools/verify-c128-vic.py.
RESULTS_BLOCK = (0x1B00, 0x1B1F)


class BuildError(RuntimeError):
    pass


def run(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise BuildError(
            f"{command[0]} failed: {' '.join(command)}\n"
            f"{result.stdout}{result.stderr}"
        )


def assemble(source: Path, config: Path, out_dir: Path, ca65: str, ld65: str) -> Path:
    obj = out_dir / f"{source.stem}.o"
    prg = out_dir / f"{source.stem}.prg"
    run([ca65, "-t", "none", "-o", str(obj), str(source)])
    run([ld65, "-C", str(config), "-o", str(prg), str(obj)])
    return prg


def load_prg(path: Path) -> tuple[int, bytes]:
    raw = path.read_bytes()
    if len(raw) < 3:
        raise BuildError(f"{path} is too short to be a PRG")
    return raw[0] | (raw[1] << 8), raw[2:]


def data_lines(blob: bytes, first_line: int, step: int, per_line: int) -> list[str]:
    """Emit the gateway as BASIC DATA: a length, then the bytes."""
    values = [str(len(blob))] + [str(byte) for byte in blob]
    lines = []
    line = first_line
    for index in range(0, len(values), per_line):
        lines.append(f"{line} data{','.join(values[index:index + per_line])}")
        line += step
    return lines


def assemble_blob(spec: str, out_dir: Path, ca65: str, ld65: str) -> tuple[int, bytes]:
    """Assemble one ADDR:SOURCE:CONFIG[:DEFINE=VALUE...] blob specification."""
    parts = spec.split(":")
    if len(parts) < 3:
        raise BuildError(f"--blob needs ADDR:SOURCE:CONFIG, got {spec!r}")
    address = int(parts[0], 0)
    source, config = Path(parts[1]), Path(parts[2])
    defines: list[str] = []
    for define in parts[3:]:
        if "=" not in define:
            raise BuildError(f"--blob define needs NAME=VALUE, got {define!r}")
        defines += ["-D", define]
    obj = out_dir / f"{source.stem}-{address:04x}.o"
    prg = out_dir / f"{source.stem}-{address:04x}.prg"
    run([ca65, "-t", "none", *defines, "-o", str(obj), str(source)])
    run([ld65, "-C", str(config), "-o", str(prg), str(obj)])
    load, body = load_prg(prg)
    if load != address:
        raise BuildError(
            f"{config} links {source.name} at ${load:04X}, --blob asked for "
            f"${address:04X}"
        )
    return load, body


def compose_payload(
    blobs: list[tuple[int, bytes]], window: tuple[int, int]
) -> tuple[bytes, list[dict[str, object]]]:
    """Lay the blobs into one contiguous image covering the window."""
    size = window[1] - window[0] + 1
    image = bytearray(size)
    occupied = bytearray(size)
    regions: list[dict[str, object]] = []
    for address, body in blobs:
        end = address + len(body) - 1
        if address < window[0] or end > window[1]:
            raise BuildError(
                f"payload blob ${address:04X}-${end:04X} escapes the window "
                f"${window[0]:04X}-${window[1]:04X}"
            )
        offset = address - window[0]
        clash = next(
            (i for i in range(len(body)) if occupied[offset + i]), None
        )
        if clash is not None:
            raise BuildError(
                f"payload blob at ${address:04X} overlaps an earlier blob at "
                f"${window[0] + offset + clash:04X}"
            )
        image[offset : offset + len(body)] = body
        occupied[offset : offset + len(body)] = b"\x01" * len(body)
        regions.append(
            {
                "name": f"payload@{address:04X}",
                "start": address,
                "end": end,
                "space": "destination",
            }
        )
    return bytes(image), regions


def check_layout(regions: list[dict[str, object]], space: str) -> None:
    """Reject overlaps within one address space.

    Destination and load-time regions must be checked separately, and never
    against each other. The payload's destinations sit in $1300-$3FFF while the
    BASIC text loads across $1C01 and up, so the two overlap by design: the
    copy runs after GRAPHIC 1 has lifted the text to $4001 and vacated the
    window. Comparing the two spaces rejects a perfectly good layout.
    """
    ordered = sorted(
        (r for r in regions if r.get("space") == space), key=lambda r: r["start"]
    )
    for lower, upper in zip(ordered, ordered[1:]):
        if lower["end"] >= upper["start"]:
            raise BuildError(
                f"{space} overlap: {lower['name']} "
                f"${lower['start']:04X}-${lower['end']:04X} meets "
                f"{upper['name']} ${upper['start']:04X}-${upper['end']:04X}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--basic", type=Path, required=True)
    parser.add_argument("--gateway", type=Path)
    parser.add_argument("--gateway-config", type=Path)
    parser.add_argument(
        "--blob",
        action="append",
        default=[],
        metavar="ADDR:SOURCE:CONFIG[:DEFINE=VALUE...]",
        help="assemble SOURCE with CONFIG and place it at ADDR in the payload",
    )
    parser.add_argument(
        "--stage",
        type=lambda value: int(value, 0),
        help="pad the PRG to this address and append the payload image there",
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--petcat", default="petcat")
    parser.add_argument("--ca65", default="ca65")
    parser.add_argument("--ld65", default="ld65")
    args = parser.parse_args()

    out_dir = args.out.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    if bool(args.blob) == bool(args.gateway):
        raise BuildError("pass either --gateway (DATA embedding) or --blob (staged)")
    if bool(args.blob) != bool(args.stage):
        raise BuildError("--blob needs --stage and vice versa")

    regions: list[dict[str, object]] = []
    payload = b""

    if args.gateway:
        # Phase 0 packaging: one small helper, embedded as BASIC DATA, so the
        # artifact is an ordinary BASIC 7 program with no loader at all.
        gateway_prg = assemble(
            args.gateway, args.gateway_config, out_dir, args.ca65, args.ld65
        )
        gateway_addr, gateway = load_prg(gateway_prg)
        gateway_end = gateway_addr + len(gateway) - 1
        if not (FREE_RAM[0] <= gateway_addr and gateway_end <= FREE_RAM[1]):
            raise BuildError(
                f"gateway ${gateway_addr:04X}-${gateway_end:04X} escapes the free "
                f"bank-0 window ${FREE_RAM[0]:04X}-${FREE_RAM[1]:04X}"
            )
        source = args.basic.read_text().splitlines()
        body = [line for line in source if not DATA_MARKER.match(line)]
        if len(body) == len(source):
            raise BuildError(f"{args.basic} has no line 9000 DATA marker")
        body += data_lines(gateway, first_line=9000, step=1, per_line=16)
        regions.append(
            {
                "name": "gateway",
                "start": gateway_addr,
                "end": gateway_end,
                "space": "destination",
            }
        )
        regions.append(
            {
                "name": "results",
                "start": RESULTS_BLOCK[0],
                "end": RESULTS_BLOCK[1],
                "space": "destination",
            }
        )
    else:
        # Phase 1 packaging: the helpers are too large for DATA, so the payload
        # image is appended to the PRG at a fixed stage address and the BASIC
        # program copies it down into the gateway window as its first action.
        # It must copy before GRAPHIC 1, which relocates the text over the
        # stage.
        blobs = [
            assemble_blob(spec, out_dir, args.ca65, args.ld65) for spec in args.blob
        ]
        payload, payload_regions = compose_payload(blobs, FREE_RAM)
        regions.extend(payload_regions)
        body = args.basic.read_text().splitlines()

    spliced = out_dir / f"{args.basic.stem}.spliced.bas"
    spliced.write_text("\n".join(body) + "\n")
    run([args.petcat, "-w70", "-o", str(args.out), "--", str(spliced)])

    basic_addr, basic = load_prg(args.out)
    if basic_addr != 0x1C01:
        raise BuildError(f"BASIC 7 text must load at $1C01, got ${basic_addr:04X}")
    basic_end = basic_addr + len(basic) - 1
    regions.append(
        {
            "name": "basic-text-at-load",
            "start": basic_addr,
            "end": basic_end,
            "space": "load",
        }
    )

    if payload:
        if basic_end >= args.stage:
            raise BuildError(
                f"BASIC text ends at ${basic_end:04X}, past the payload stage at "
                f"${args.stage:04X}; raise the stage or shrink the program"
            )
        pad = args.stage - (basic_end + 1)
        args.out.write_bytes(args.out.read_bytes() + bytes(pad) + payload)
        regions.append(
            {
                "name": "payload-stage",
                "start": args.stage,
                "end": args.stage + len(payload) - 1,
                "space": "load",
            }
        )
        print(
            f"{'padding':<20} ${basic_end + 1:04X}-${args.stage - 1:04X} "
            f"{pad:5d} bytes to reach the stage"
        )

    check_layout(regions, "destination")
    check_layout(regions, "load")

    # After GRAPHIC 1 the interpreter reserves $2000-$3FFF and lifts the text to
    # $4001, so the report records both homes: the load-time span above and the
    # relocated span the running program actually occupies.
    relocated_end = 0x4001 + len(basic) - 1
    report = {
        "prg": str(args.out),
        "regions": regions,
        "payload_bytes": len(payload),
        "window": {"start": FREE_RAM[0], "end": FREE_RAM[1]},
        "graphic1": {
            "bitmap_reserve": {"start": 0x2000, "end": 0x3FFF},
            "relocated_text": {"start": 0x4001, "end": relocated_end},
        },
        "free_ram": {"start": FREE_RAM[0], "end": FREE_RAM[1]},
    }
    if args.gateway:
        report["gateway_entries"] = {
            "probe": gateway_addr,
            "irq_on": gateway_addr + 3,
            "irq_off": gateway_addr + 6,
            "results": 0x1340,
        }
    args.report.write_text(json.dumps(report, indent=2) + "\n")

    for space in ("destination", "load"):
        for region in sorted(
            (r for r in regions if r.get("space") == space),
            key=lambda item: item["start"],
        ):
            print(
                f"{region['name']:<20} ${region['start']:04X}-${region['end']:04X} "
                f"{region['end'] - region['start'] + 1:5d} bytes  {space}"
            )
    print(
        f"{'relocated text':<20} $4001-${relocated_end:04X} "
        f"(after graphic 1; $2000-$3FFF reserved)"
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BuildError as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
