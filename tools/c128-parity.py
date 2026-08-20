#!/usr/bin/env python3
"""Prove the C128 edition's reuse of src/music.s and src/rng.s costs the C64 nothing.

The two editions share one assembly source per helper and differ only by
assembly-time defines: LOAD_ADDR and the tempo/jiffy ratio for the player, plus
WAITJ and C128 for the RNG. That keeps the title theme and the PRNG from
drifting apart, but it also puts C128 conditionals inside files the canonical C64
build depends on.

Two checks, because either alone is too weak:

1. A rebuild with no defines at all must equal the packaged C64 blob. This
   catches a link config or a build rule that quietly picked up a C128 define.
2. Both must equal the hash recorded in tools/fixtures/c64-helper-blobs.json,
   taken before any conditional assembly existed. This is the check that
   actually bites, because check 1 compares the source against itself and would
   pass happily while the C64 output drifted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def link(source: Path, config: Path, out_dir: Path, ca65: str, ld65: str) -> bytes:
    obj = out_dir / f"{source.stem}.o"
    prg = out_dir / f"{source.stem}.prg"
    for command in (
        [ca65, "-t", "none", "-o", str(obj), str(source)],
        [ld65, "-C", str(config), "-o", str(prg), str(obj)],
    ):
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            print(f"{' '.join(command)}\n{result.stdout}{result.stderr}", file=sys.stderr)
            raise SystemExit(1)
    return prg.read_bytes()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--music", type=Path, required=True)
    parser.add_argument("--rng", type=Path, required=True)
    parser.add_argument("--music-source", type=Path, default=Path("src/music.s"))
    parser.add_argument("--rng-source", type=Path, default=Path("src/rng.s"))
    parser.add_argument("--music-config", type=Path, default=Path("tools/music.cfg"))
    parser.add_argument("--rng-config", type=Path, default=Path("tools/rng.cfg"))
    parser.add_argument(
        "--fixture", type=Path, default=Path("tools/fixtures/c64-helper-blobs.json")
    )
    parser.add_argument("--ca65", default="ca65")
    parser.add_argument("--ld65", default="ld65")
    args = parser.parse_args()

    fixture = json.loads(args.fixture.read_text())["blobs"]
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        for source, config, packaged in (
            (args.music_source, args.music_config, args.music),
            (args.rng_source, args.rng_config, args.rng),
        ):
            expected = fixture.get(packaged.name)
            if expected is None:
                print(f"  [FAIL] {packaged.name}: not recorded in {args.fixture}")
                failures += 1
                continue

            rebuilt = link(source, config, out_dir, args.ca65, args.ld65)
            reference = packaged.read_bytes()
            if rebuilt == reference:
                print(
                    f"  [ok  ] {packaged.name}: no-define rebuild matches the "
                    f"packaged blob ({len(rebuilt)} bytes)"
                )
            else:
                failures += 1
                first = next(
                    (
                        i
                        for i in range(min(len(rebuilt), len(reference)))
                        if rebuilt[i] != reference[i]
                    ),
                    min(len(rebuilt), len(reference)),
                )
                print(
                    f"  [FAIL] {packaged.name}: no-define rebuild differs from the "
                    f"packaged blob at offset {first}"
                )

            digest = hashlib.sha256(reference).hexdigest()
            if digest == expected["sha256"] and len(reference) == expected["bytes"]:
                print(
                    f"  [ok  ] {packaged.name}: matches the recorded pre-C128 hash"
                )
            else:
                failures += 1
                print(
                    f"  [FAIL] {packaged.name}: {len(reference)} bytes {digest[:16]}..."
                    f" but {args.fixture.name} records {expected['bytes']} bytes "
                    f"{expected['sha256'][:16]}..."
                )

    print()
    if failures:
        print(f"FAILED {failures} check(s): the canonical C64 helper output changed")
        return 1
    print("c128-parity: C64 helper blobs unaffected by the shared C128 defines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
