#!/usr/bin/env python3
"""Drive the original Blitz! compiler in VICE through its binary monitor."""

from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time
from pathlib import Path

from vice_monitor import ViceMonitor


def screen_text(data: bytes) -> str:
    def decode(value: int) -> str:
        value &= 0x7F
        if value in (0, 32):
            return " "
        if 1 <= value <= 26:
            return chr(value + 96)
        if 65 <= value <= 90:
            return chr(value + 32)
        if 32 <= value <= 63:
            return chr(value)
        return " "

    return "\n".join(
        "".join(decode(value) for value in data[row : row + 40]).rstrip()
        for row in range(0, 1000, 40)
    ).rstrip()


def wait_for_screen(
    monitor: ViceMonitor, needles: tuple[str, ...], timeout: float
) -> str:
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        current = screen_text(monitor.memory(0x0400, 0x07E7))
        last = current
        lowered = current.lower()
        if any(needle in lowered for needle in needles):
            return current
        time.sleep(0.05)
    expected = " or ".join(repr(needle) for needle in needles)
    raise TimeoutError(f"timed out waiting for {expected}; screen was:\n{last}")


def stable_screen(monitor: ViceMonitor, timeout: float, stable_for: float = 15.0) -> str:
    deadline = time.monotonic() + timeout
    candidate = ""
    stable_since = time.monotonic()
    while time.monotonic() < deadline:
        current = screen_text(monitor.memory(0x0400, 0x07E7))
        if current != candidate:
            candidate = current
            stable_since = time.monotonic()
        elif time.monotonic() - stable_since >= stable_for:
            return candidate
        time.sleep(0.05)
    raise TimeoutError(f"screen did not stabilize; screen was:\n{candidate}")


def run(args: argparse.Namespace) -> int:
    build = args.build.resolve()
    build.mkdir(parents=True, exist_ok=True)
    output_path = args.output.resolve()
    compiler = build / "blitz-compiler.prg"
    work_disk = build / "blitz-work.d64"
    log = build / "blitz-vice.log"
    port = args.port
    if port == 0:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]

    subprocess.run(
        [args.c1541, str(args.compiler_disk), "-read", "blitz compiler", str(compiler)],
        check=True,
    )
    work_disk.unlink(missing_ok=True)
    subprocess.run(
        [
            args.c1541,
            "-format",
            "blitzwork,42",
            "d64",
            str(work_disk),
            "-write",
            str(compiler),
            "blitz compiler",
            "-write",
            str(args.source),
            "l",
        ],
        check=True,
    )

    vice_command = [
        args.vice,
        "-default",
        "-warp",
        "-sounddev",
        "dummy",
        "-binarymonitor",
        "-binarymonitoraddress",
        f"ip4://127.0.0.1:{port}",
        "-autostart",
        str(work_disk),
    ]
    with log.open("wb") as output:
        vice = subprocess.Popen(vice_command, stdout=output, stderr=subprocess.STDOUT)

    monitor: ViceMonitor | None = None
    try:
        monitor = ViceMonitor("127.0.0.1", port, timeout=10.0)
        menu_screen = wait_for_screen(monitor, ("single floppy", "dual drive"), 20.0)
        print("BLITZ prompt: disk mode")
        print(menu_screen)
        monitor.inject(b"1")

        filename_screen = wait_for_screen(monitor, ("filename",), 20.0)
        print("BLITZ prompt: source filename")
        print(filename_screen)
        monitor.inject(b"L\r")

        next_screen = stable_screen(monitor, 300.0)
        print("BLITZ result:")
        print(next_screen)
        if "errors: 0" not in next_screen.lower() or "ready." not in next_screen.lower():
            raise RuntimeError("Blitz! did not report a successful two-pass compile")
    finally:
        if monitor is not None:
            monitor.close()
        vice.terminate()
        try:
            vice.wait(timeout=3)
        except subprocess.TimeoutExpired:
            vice.kill()
            vice.wait()

    output_path.unlink(missing_ok=True)
    subprocess.run(
        [args.c1541, str(work_disk), "-read", "c/l", str(output_path)],
        check=True,
    )
    if not output_path.is_file() or output_path.stat().st_size <= 2:
        raise RuntimeError(f"Blitz! output was not extracted to {output_path}")
    print(f"blitz-compile: extracted {output_path} ({output_path.stat().st_size} bytes)")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compiler-disk", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--vice", default="x64sc")
    parser.add_argument("--c1541", default="c1541")
    parser.add_argument("--port", type=int, default=0)
    return parser.parse_args()


if __name__ == "__main__":
    try:
        raise SystemExit(run(parse_args()))
    except (ConnectionError, OSError, RuntimeError, TimeoutError) as error:
        print(f"blitz-compile: {error}", file=sys.stderr)
        raise SystemExit(1)
