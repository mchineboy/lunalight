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

RESULTS = 0x1B00            # phase 0 findings, written by the BASIC program
PHASE1_RESULTS = 0x17A0     # phase 1 findings, inside the RNG scratch region.
                            # $1B00 is the table by then, and $1740 turned out
                            # to be inside the RNG's own code.
PHASE1_STAGES = 8
PHASE1_TXTTAB = 0x4001
WAIT_JIFFIES = 30           # POKEd to the wait argument at $1780
WAIT_JIFFIES_LONG = 60      # second sample, so a scaling error cannot hide
C128_LOOP_JIFFIES = 1036    # 48 steps * 18 ticks * 6/5, published at $1306
CURSOR_ROW = 8              # HOME plus eight newlines
EDITOR_D018_SHADOW = 0x14   # $0A2C holds a $D018-format value, not a page
JOYSTICK_IDLE = 0x1F
JOYSTICK_UP = 0x1E          # active low: bit 0 clear is up
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

    def __init__(
        self, prg: Path, vice: str, log: Path, control_port: bool = False
    ) -> None:
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
        ]
        if control_port:
            command.extend(("-controlport2device", "37"))
        command.extend(("-autostart", str(prg.resolve())))
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

    def wait_for_done(self, timeout: float, base: int, stages: int) -> bytes:
        deadline = time.monotonic() + timeout
        last = b""
        while time.monotonic() < deadline:
            last = self.read(base, base + 0x1F)
            if last[:4] == SIGNATURE and last[23] == DONE:
                return last
            time.sleep(0.05)
        stage = last[22] if len(last) > 22 else -1
        raise Failure(
            f"probe never finished: signature {last[:4]!r}, stage {stage} of {stages}"
        )


def word(data: bytes, offset: int) -> int:
    return data[offset] | (data[offset + 1] << 8)


def check_phase1(session: Session, report: Report, timeout: float) -> None:
    """Phase 1: the ported helpers, the runtime model and the C64 assumptions."""
    # Held from before the program starts, so the read at stage 8 is not a race.
    session.monitor.set_joyport(1, JOYSTICK_UP)
    session.monitor.resume()

    results = session.wait_for_done(timeout, PHASE1_RESULTS, PHASE1_STAGES)
    results = session.read(PHASE1_RESULTS, PHASE1_RESULTS + 0x2F)

    print("probe completion")
    report.check(
        results[:4] == SIGNATURE,
        f"probe signature at ${PHASE1_RESULTS:04X}",
        results[:4].decode("latin-1"),
        "L128",
    )
    report.check(
        results[22] == PHASE1_STAGES, "stages completed", results[22], PHASE1_STAGES
    )

    print("payload relocation and BASIC 7 text model")
    txttab = word(results, 6)
    report.check(
        txttab == PHASE1_TXTTAB,
        "TXTTAB after GRAPHIC 1",
        hex(txttab),
        hex(PHASE1_TXTTAB),
    )
    before, after = word(results, 4), word(results, 12)
    report.check(
        before != 0,
        "ported player relocated into $1300 (non-zero checksum)",
        before,
        "non-zero",
    )
    report.check(
        before == after,
        "player checksum unchanged by heavy string churn",
        f"{before} -> {after}",
        "identical: strings live in RAM bank 1",
    )

    print("character-set slots inside the GRAPHIC 1 reserve")
    # Two traps here. Bit 0 of $D018 is unused on the VIC-IIe and reads back as
    # 1, so a POKE of $18 reads as $19. And the C128 editor's interrupt reloads
    # $D018 from its shadow at $0A2C, so POKEing the register alone does not
    # stick: an earlier run read back $15, which is the shadow's default $14
    # with bit 0 set. The probe writes the shadow and waits a second before
    # reading, so this asserts the switch survives an interrupt.
    for reg_offset, shadow_offset, slot, expected_bits, poked in (
        (8, 35, "$2000", 4, 0x18),
        (9, 36, "$2800", 5, 0x1A),
    ):
        value = results[reg_offset]
        report.check(
            (value >> 1) & 0x07 == expected_bits and (value >> 4) & 0x0F == 1,
            f"$D018 still selects the {slot} charset slot an interrupt later",
            f"${value:02X}: charset field {(value >> 1) & 7}, screen field {(value >> 4) & 0xF}",
            f"charset field {expected_bits}, screen field 1",
        )
        report.check(
            results[shadow_offset] == poked,
            f"$0A2C shadow holds the {slot} selection",
            f"${results[shadow_offset]:02X}",
            f"${poked:02X}",
        )
    report.check(results[10] == 170, "pattern at $2000 survived", results[10], 170)
    report.check(results[11] == 85, "pattern at $2800 survived", results[11], 85)

    print("ported RNG")
    report.check(
        results[14] >= 32,
        "table varies across 64 samples after collect",
        f"{results[14]}/63 differ from the first byte",
        ">= 32",
    )
    report.check(results[15] == 1, "refill rewrote the table", results[15], 1)

    print("ported jiffy wait, argument re-homed from $02A7 to $1780")
    report.check(
        abs(results[16] - WAIT_JIFFIES) <= 2,
        f"TI advanced by the requested {WAIT_JIFFIES} jiffies",
        results[16],
        f"{WAIT_JIFFIES} +/- 2",
    )
    report.check(
        abs(results[17] - WAIT_JIFFIES) <= 2,
        "$A2 is the C128 jiffy clock and agrees with TI",
        results[17],
        f"{WAIT_JIFFIES} +/- 2",
    )
    report.check(
        abs(results[32] - WAIT_JIFFIES_LONG) <= 2,
        f"the same wait is exact at {WAIT_JIFFIES_LONG} too, so no 6/5 scaling",
        results[32],
        f"{WAIT_JIFFIES_LONG} +/- 2",
    )
    loop = results[33] | (results[34] << 8)
    report.check(
        loop == C128_LOOP_JIFFIES,
        "player publishes its loop length in C128 jiffies",
        loop,
        C128_LOOP_JIFFIES,
    )

    print("ported title player: install, coexistence, uninstall")
    report.check(
        results[18] != 0,
        "SID $D418 driven while the player is installed",
        f"${results[18]:02X}",
        "non-zero",
    )
    report.check(
        results[21] == 0,
        "SID silenced on uninstall",
        f"${results[21]:02X}",
        "$00",
    )
    report.check(
        results[19] & 0x01 == 0x01,
        "BUMP(2) still latches with the player chained",
        f"${results[19]:02X}",
        "bit 0 set",
    )
    report.check(
        results[20] == 1,
        "MOVSPR still positions with the player chained",
        results[20],
        1,
    )

    print("joystick port 2 against the C128 keyboard scan")
    report.check(
        results[24] & 0x01 == 0 and results[25] & 0x01 == 0,
        "both $DC00 reads show the held direction",
        f"${results[24]:02X} ${results[25]:02X}",
        "bit 0 clear in both",
    )

    print("C64 editor and keyboard locations under C128 BASIC 7")
    report.check(
        results[27] == CURSOR_ROW,
        "cursor row lives at $EB (235), not $D6 (214)",
        f"$EB={results[27]}, $D6={results[26]}",
        f"$EB={CURSOR_ROW}",
    )
    report.check(
        results[26] != CURSOR_ROW,
        "PEEK(214) is not the cursor row on the C128",
        results[26],
        f"anything but {CURSOR_ROW}",
    )
    report.check(
        results[29] == EDITOR_D018_SHADOW,
        "$0A2C (2604) holds a $D018-format value, not a screen page",
        f"${results[29]:02X}",
        f"${EDITOR_D018_SHADOW:02X}",
    )
    report.check(
        results[30] == 0,
        "PEEK(648) carries nothing on the C128",
        results[30],
        0,
    )
    report.check(
        results[31] != 0,
        "PEEK(653) is not a shift flag: non-zero with no key held",
        results[31],
        "non-zero, so the C64 constant is unusable",
    )
    report.note("PEEK(236)", results[28])
    report.note("joystick reads", f"${results[24]:02X} ${results[25]:02X}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prg", type=Path, required=True)
    parser.add_argument("--phase", type=int, choices=(0, 1), default=0)
    parser.add_argument("--vice", default="x128")
    parser.add_argument("--log", type=Path, default=Path("build/verify-c128-vic.log"))
    parser.add_argument("--timeout", type=float, default=90.0)
    args = parser.parse_args()

    report = Report()
    session = Session(args.prg, args.vice, args.log, control_port=args.phase == 1)
    if args.phase == 1:
        try:
            check_phase1(session, report, args.timeout)
        finally:
            session.close()
        print()
        if report.failures:
            print(f"FAILED {len(report.failures)} check(s): {', '.join(report.failures)}")
            return 1
        print("phase 1: native C128 runtime model verified")
        return 0
    try:
        results = session.wait_for_done(args.timeout, RESULTS, STAGES)
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
