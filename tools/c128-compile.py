#!/usr/bin/env python3
"""Compile the C128 BASIC source with Basic 128 v1.03, driven headless in VICE.

The C64 edition compiles with the original Blitz! disk through
tools/blitz-compile.py. This is the C128 equivalent, and it differs in three
ways that are forced by the compiler rather than chosen:

Blitz! 128 would have been the closer parallel -- same publisher, same lineage
as tools/BLITZ.d64 -- but it refuses to run without a dongle in the user port,
which VICE cannot provide. Basic 128 emits real machine code where Blitz emits
P-code, so it is the better target anyway.

The compiler disk is copy protected and cannot be copied, so, unlike the C64
driver, this one cannot assemble a work disk carrying the compiler. Instead the
source is written *into* a scratch copy of the protected .g64, which c1541 does
happily and which leaves the protection undisturbed. The compiler's output lands
on that same disk, where c1541 can read it back.

The manual's workflow is a single-drive disk swap: boot the compiler, then swap
in the program disk. That is not reproducible here -- the binary monitor's
autostart command resets the machine and takes the resident compiler with it --
and putting the source on the compiler's own disk avoids needing a swap at all.
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

# Where the compiler may start using bank 0 for variables. Must clear the VIC
# window at $1300-$3FFF, and the manual requires >16383 while GRAPHIC is used.
BANK0_START = 16384


def screen_text(data: bytes) -> str:
    def decode(value: int) -> str:
        value &= 0x7F
        if value in (0, 32):
            return " "
        if 1 <= value <= 26:
            return chr(value + 96)
        if 33 <= value <= 63:
            return chr(value)
        return "."

    return "\n".join(
        "".join(decode(v) for v in data[row : row + 40]).rstrip()
        for row in range(0, 1000, 40)
    )


class Compiler:
    def __init__(self, monitor: ViceMonitor) -> None:
        self.monitor = monitor

    def feed(self, text: str) -> None:
        """Type through VICE itself rather than poking a keyboard buffer.

        The buffer address differs between the C64 ($0277/$00C6) and the C128
        ($034A/$00D0), and vice_monitor.inject() hard-codes the C64 pair. Using
        VICE's own keyboard-feed command sidesteps the question entirely.
        """
        payload = text.replace("\n", "\r").encode("ascii")
        self.monitor.command(0x72, bytes([len(payload)]) + payload)
        self.monitor.resume()

    def screen(self) -> str:
        return screen_text(self.monitor.memory(0x0400, 0x07E7))

    def wait_for(self, needles: tuple[str, ...], timeout: float) -> str:
        deadline = time.monotonic() + timeout
        last = ""
        while time.monotonic() < deadline:
            last = self.screen()
            if any(n in last.lower() for n in needles):
                return last
            time.sleep(0.3)
        raise TimeoutError(
            f"timed out waiting for {' or '.join(needles)}; screen was:\n{last}"
        )

    def wait_until_settled(self, timeout: float, settle: float = 30.0) -> str:
        """Wait for the screen to stop changing; the compiler prints line numbers."""
        deadline = time.monotonic() + timeout
        previous, since = None, time.monotonic()
        while time.monotonic() < deadline:
            current = self.screen()
            if current != previous:
                previous, since = current, time.monotonic()
            elif time.monotonic() - since >= settle:
                return current
            time.sleep(0.5)
        raise TimeoutError(f"compiler never settled; screen was:\n{previous}")


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="tokenized PRG")
    parser.add_argument("--out", type=Path, required=True, help="compiled PRG")
    parser.add_argument(
        "--compiler-disk", type=Path, default=Path("tools/BASIC128.g64")
    )
    parser.add_argument("--work-disk", type=Path, default=Path("build/c128-compile.g64"))
    parser.add_argument("--vice", default="x128")
    parser.add_argument("--c1541", default="c1541")
    parser.add_argument("--log", type=Path, default=Path("build/c128-compile.log"))
    parser.add_argument("--timeout", type=float, default=600.0)
    args = parser.parse_args()

    # The same filename has to be spelled in opposite cases on the two sides of
    # this pipeline, because ASCII-to-PETSCII conversion swaps case:
    #
    #   c1541 gets "l": ASCII $6C -> PETSCII $4C, the letter L. Correct.
    #   c1541 gets "L": ASCII $4C -> PETSCII $CC, shifted L. The compiler will
    #                   not find it, and answers "disk error: 62".
    #   keyboard feed gets "L": types the letter L, matching PETSCII $4C.
    #   keyboard feed gets "l": types a PETSCII graphics character instead.
    #
    # Both mistakes produce the identical "file not found", from opposite
    # causes, so the two spellings are deliberate and not a typo.
    disk_name = "l"
    typed_name = "L"
    # Native code output is prefixed "m-"; P-code output would be "p-".
    out_prefix = "m-"

    args.work_disk.parent.mkdir(parents=True, exist_ok=True)
    args.work_disk.write_bytes(args.compiler_disk.read_bytes())
    subprocess.run(
        [args.c1541, "-attach", str(args.work_disk), "-write", str(args.source),
         disk_name],
        check=True,
        capture_output=True,
    )

    port = free_port()
    command = [
        args.vice, "-default", "+go64", "-warp", "-sounddev", "dummy",
        "-drive8truedrive", "-drive8type", "1541",
        "-binarymonitor", "-binarymonitoraddress", f"ip4://127.0.0.1:{port}",
        "-autostart", f"{args.work_disk.resolve()}:start",
    ]
    args.log.parent.mkdir(parents=True, exist_ok=True)
    with args.log.open("wb") as log:
        vice = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)

    monitor = None
    try:
        monitor = ViceMonitor("127.0.0.1", port, timeout=30.0)
        compiler = Compiler(monitor)

        compiler.wait_for(("compiler/optimizer",), 300.0)
        print("basic 128: menu reached")

        # Two settings have to change before compiling, both in the advanced
        # development package (main menu option 3).
        compiler.feed("3")
        compiler.wait_for(("code-generator",), 60.0)

        # The default code generator emits P-code, which a runtime module then
        # interprets. Option A switches to native 8502 code and renames the
        # output from "p-" to "m-". Compiling without this produces a working
        # program that is still interpreted, just at a different level.
        compiler.feed("A")
        compiler.wait_for(("6502/6510/8502",), 60.0)
        print("basic 128: code generator set to native 8502")

        # "bank 0 start" defaults to 4864 = $1300, which is exactly where this
        # edition's music player and RNG live. That is variable storage, so
        # clearing variables zeroes the helpers, and the first SYS into them
        # breaks -- observed as a BRK at $1502, two bytes into the RNG entry.
        # The charset and sprites survived only because GRAPHIC makes the
        # compiler auto-reserve $1E00-$4000.
        #
        # The manual allows raising this, with one constraint: while a GRAPHIC
        # command is present the value "may not be changed or only changed to a
        # value over 16383". So it goes to $4000, above the whole VIC window,
        # leaving $1300-$3FFF entirely to us.
        #
        # Menu item 1 is "bank 0 start". Item 2 is "bank 0 top" -- a different
        # setting that does not protect anything down here.
        compiler.feed("E")
        compiler.wait_for(("bank 0",), 60.0)
        compiler.feed("1")
        compiler.wait_for(("address",), 60.0)
        compiler.feed(f"{BANK0_START}\n")
        time.sleep(2)
        memory = compiler.screen()
        if str(BANK0_START) not in memory:
            print(f"bank 0 start did not take:\n{memory}", file=sys.stderr)
            return 1
        print(f"basic 128: bank 0 start raised to {BANK0_START} (${BANK0_START:04X})")

        compiler.feed("\n")                       # leave the memory menu
        compiler.wait_for(("code-generator",), 60.0)
        compiler.feed("\n")                       # back to the main menu
        compiler.wait_for(("compiler/optimizer",), 60.0)

        compiler.feed("1")
        compiler.wait_for(("program name",), 90.0)
        compiler.feed(f"{typed_name}\n")
        print(f"basic 128: compiling {typed_name}")

        final = compiler.wait_until_settled(args.timeout)
        print(final)
        lowered = final.lower()
        if "error" in lowered and "disk error" not in lowered:
            print("basic 128: reported errors; not extracting", file=sys.stderr)
            return 1
        if "disk error" in lowered:
            print("basic 128: disk error; not extracting", file=sys.stderr)
            return 1
    finally:
        if monitor is not None:
            try:
                monitor.quit()
            except (ConnectionError, OSError, RuntimeError):
                pass
            monitor.close()
        if vice.poll() is None:
            try:
                vice.wait(timeout=8)
            except subprocess.TimeoutExpired:
                vice.kill()
                vice.wait()

    listing = subprocess.run(
        [args.c1541, "-attach", str(args.work_disk), "-list"],
        check=True, capture_output=True, text=True,
    ).stdout
    if f"{out_prefix}{disk_name}" not in listing.lower():
        print(f"no {out_prefix}{disk_name} on the work disk:\n{listing}",
              file=sys.stderr)
        return 1
    subprocess.run(
        [args.c1541, "-attach", str(args.work_disk),
         "-read", f"{out_prefix}{disk_name}", str(args.out)],
        check=True, capture_output=True,
    )
    raw = args.out.read_bytes()
    load = raw[0] | (raw[1] << 8)
    print(
        f"{args.out}: ${load:04X}-${load + len(raw) - 3:04X}, {len(raw) - 2} bytes"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
