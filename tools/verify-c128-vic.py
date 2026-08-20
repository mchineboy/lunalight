#!/usr/bin/env python3
"""Verify the native-C128 VIC-IIe build under x128. Phase 0 scope.

Every check prints the observed value so a failure names the offending register
or address rather than only the expectation. This driver deliberately makes no
C64 address assumptions: it does not import verify-bank2's layout.
"""

from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vice_monitor import ViceMonitor

RESULTS = 0x1B00            # probe findings, written by the BASIC program
GATEWAY_RESULTS = 0x1340    # probe findings, written by the $1300 machine code
GATEWAY = 0x1300
SIGNATURE = b"L128"
STAGES = 9                  # RESULTS+22 counts up to this as the probe advances
DONE = 0xFF                 # RESULTS+23
WRITE_THROUGH = 111         # byte POKEd to $4200 in BANK 15
MOVSPR_X = 300              # deliberately above 255 to exercise the $D010 MSB
FREE_RAM = (0x1300, 0x1BFF)
RELOCATED_TXTTAB = 0x4001


class Failure(RuntimeError):
    pass


class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def check(self, ok: bool, label: str, observed: object, expected: object) -> bool:
        mark = "ok  " if ok else "FAIL"
        print(f"  [{mark}] {label}: observed {observed}, expected {expected}")
        if not ok:
            self.failures.append(label)
        return ok

    def note(self, label: str, observed: object) -> None:
        print(f"  [note] {label}: {observed}")


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Session:
    """A native-mode x128 with the binary monitor attached."""

    def __init__(self, prg: Path, vice: str, log: Path) -> None:
        self.port = free_port()
        log.parent.mkdir(parents=True, exist_ok=True)
        command = [
            vice,
            "-default",
            "+go64",              # native C128 mode; never the C64 path
            "-sounddev",
            "dummy",
            "+autostart-delay-random",
            "-binarymonitor",
            "-binarymonitoraddress",
            f"ip4://127.0.0.1:{self.port}",
            "-autostart",
            str(prg.resolve()),
        ]
        self.log = log.open("ab")
        self.vice = subprocess.Popen(command, stdout=self.log, stderr=subprocess.STDOUT)
        self.monitor = ViceMonitor("127.0.0.1", self.port, timeout=20.0)
        self.banks = self.monitor.banks()
        self.ram = self.banks.get("ram", ViceMonitor.BANK_RAM)

    def close(self) -> None:
        try:
            self.monitor.quit()
        except (ConnectionError, OSError, RuntimeError):
            pass
        self.monitor.close()
        if self.vice.poll() is None:
            try:
                self.vice.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.vice.kill()
                self.vice.wait()
        self.log.close()

    def read(self, start: int, end: int) -> bytes:
        data = self.monitor.memory_paused(start, end, self.ram)
        self.monitor.resume()
        return data

    def wait_for_done(self, timeout: float) -> bytes:
        deadline = time.monotonic() + timeout
        last = b""
        while time.monotonic() < deadline:
            last = self.read(RESULTS, RESULTS + 0x1F)
            if last[:4] == SIGNATURE and last[23] == DONE:
                return last
            time.sleep(0.05)
        stage = last[22] if len(last) > 22 else -1
        raise Failure(
            f"probe never finished: signature {last[:4]!r}, stage {stage} of {STAGES}"
        )


def word(data: bytes, offset: int) -> int:
    return data[offset] | (data[offset + 1] << 8)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prg", type=Path, required=True)
    parser.add_argument("--vice", default="x128")
    parser.add_argument("--log", type=Path, default=Path("build/verify-c128-vic.log"))
    parser.add_argument("--timeout", type=float, default=90.0)
    args = parser.parse_args()

    report = Report()
    session = Session(args.prg, args.vice, args.log)
    try:
        results = session.wait_for_done(args.timeout)
        gateway = session.read(GATEWAY_RESULTS, GATEWAY_RESULTS + 0x10)

        print("native boot and display")
        report.check(
            results[:4] == SIGNATURE,
            "probe signature at $1B00",
            results[:4].decode("latin-1"),
            "L128",
        )
        report.check(
            results[22] == STAGES, "stages completed", results[22], STAGES
        )
        report.check(results[8] == 0, "$D7 40/80 flag (0 = 40 columns)", results[8], 0)

        print("BASIC 7 text relocation")
        before, after = word(results, 4), word(results, 6)
        report.check(before == 0x1C01, "TXTTAB before GRAPHIC 1", hex(before), "0x1c01")
        report.check(
            after == RELOCATED_TXTTAB,
            "TXTTAB after GRAPHIC 1",
            hex(after),
            hex(RELOCATED_TXTTAB),
        )

        print("RAM under BASIC ROM")
        report.check(
            results[9] != WRITE_THROUGH,
            "BANK 15 PEEK $4200 returns ROM, not the POKEd byte",
            results[9],
            f"anything but {WRITE_THROUGH}",
        )
        report.check(
            results[10] == WRITE_THROUGH,
            "BANK 0 PEEK $4200 returns the POKEd byte",
            results[10],
            WRITE_THROUGH,
        )

        print("machine-code gateway at $1300")
        report.check(gateway[:4] == SIGNATURE, "gateway signature at $1340",
                     gateway[:4].decode("latin-1"), "L128")
        report.check(gateway[16] == 1, "probe returned to BASIC", gateway[16], 1)
        report.check(
            gateway[4] == WRITE_THROUGH,
            "all-RAM read of $4200 sees RAM",
            gateway[4],
            WRITE_THROUGH,
        )
        report.check(
            gateway[7] == results[9],
            "BANK 15 read of $4200 agrees with BASIC",
            gateway[7],
            results[9],
        )
        report.check(
            gateway[8] == gateway[9],
            "$FF00 restored after the all-RAM window",
            f"${gateway[8]:02X} -> ${gateway[9]:02X}",
            "unchanged",
        )
        report.note("$D012 raster read after restore", gateway[10])
        report.note("all-RAM read of $4800 (C64 RNG table home)", gateway[5])
        report.note("all-RAM read of $8400 (C64 bank-2 screen home)", gateway[6])

        print("MMU and VIC bank state")
        report.note("$D505 mode register", f"${results[11]:02X}")
        report.check(
            results[12] & 0xC0 == 0,
            "$D506 VIC RAM bank (bits 6-7) is bank 0",
            f"${results[12]:02X}",
            "bits 6-7 clear",
        )
        report.check(
            results[13] & 0x03 == 0x03,
            "$DD00 VIC 16K window is bank 0 ($0000-$3FFF)",
            f"${results[13]:02X}",
            "bits 0-1 set",
        )
        report.note("$D018 screen/charset pointer", f"${results[14]:02X}")

        print("BASIC 7 sprites and collision")
        report.check(
            results[19] == 56,
            "sprite 0 pointer selects the $0E00 sprite area",
            results[19],
            56,
        )
        movspr_x = word(results, 15)
        report.check(
            movspr_x == MOVSPR_X,
            "RSPPOS reads back the MOVSPR X above 255",
            movspr_x,
            MOVSPR_X,
        )
        report.check(
            results[17] & 0x01 == 0x01,
            "MOVSPR set the $D010 MSB for sprite 0",
            f"${results[17]:02X}",
            "bit 0 set",
        )
        report.check(
            results[18] & 0x01 == 0x01,
            "BUMP(2) reports the forced sprite-background hit",
            f"${results[18]:02X}",
            "bit 0 set",
        )

        print("IRQ chain install and restore")
        report.check(results[20] == 1, "chained handler ticked", results[20], 1)
        report.check(
            results[21] == 1, "counter froze after restore", results[21], 1
        )
    finally:
        session.close()

    print()
    if report.failures:
        print(f"FAILED {len(report.failures)} check(s): {', '.join(report.failures)}")
        return 1
    print("phase 0: native C128 bootstrap verified")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Failure as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
