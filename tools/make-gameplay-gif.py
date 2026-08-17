#!/usr/bin/env python3
"""Capture a title-then-attract gameplay GIF from the canonical Blitz package.

Drives VICE through the binary monitor: wait for the title, sample a short
idle stretch, force the attract-mode idle deadline, then sample the autopilot
descent at a fixed jiffy cadence so the GIF reads at real game timing even
when VICE is warping.
"""

from __future__ import annotations

import argparse
import re
import shutil
import socket
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path

from vice_monitor import ViceMonitor

TITLE_NEEDLES = ("l u n a l i g h t", "press f7 to start")
FLIGHT_NEEDLES = ("vel", "fuel", "horz")
ATTRACT_NEEDLE = "attract"


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def decode_screen(data: bytes) -> list[str]:
    def decode(value: int) -> str:
        value &= 0x7F
        if value <= 31:
            return chr(value + 64)
        if 32 <= value <= 63:
            return chr(value)
        return " "

    return [
        "".join(decode(value) for value in data[row : row + 40]).rstrip()
        for row in range(0, 1000, 40)
    ]


def write_png(path: Path, width: int, height: int, pixels: bytes, palette: bytes) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    raw = bytearray()
    for row in range(height):
        raw.append(0)
        raw.extend(pixels[row * width : (row + 1) * width])
    table = bytearray(palette[: 256 * 3])
    table.extend(b"\0" * (256 * 3 - len(table)))
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 3, 0, 0, 0))
        + chunk(b"PLTE", bytes(table))
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def jiffy_value(raw: bytes) -> int:
    return (raw[0] << 16) | (raw[1] << 8) | raw[2]


def advance_jiffies(monitor: ViceMonitor, count: int) -> None:
    """Advance the C64 jiffy clock by ``count`` ticks (1/60 s each)."""
    if count <= 0:
        return
    current = jiffy_value(monitor.memory_paused(0x00A0, 0x00A2))
    target = (current + count) % 5184000
    # Large steps: wait for $A2 stores. Fine steps: instruction-step to land
    # exactly, matching the motion-oracle helper.
    while True:
        current = jiffy_value(monitor.memory_paused(0x00A0, 0x00A2))
        remaining = (target - current) % 5184000
        if remaining == 0:
            return
        if remaining > 2:
            monitor.stop_on_store(0x00A2)
            continue
        monitor.advance_instructions(50)


def crop_inner(
    width: int, height: int, pixels: bytes, geometry: dict[str, int]
) -> tuple[int, int, bytes]:
    x0 = geometry["x_offset"]
    y0 = geometry["y_offset"]
    inner_w = geometry["width"]
    inner_h = geometry["height"]
    if x0 + inner_w > width or y0 + inner_h > height:
        return width, height, pixels
    cropped = bytearray(inner_w * inner_h)
    for row in range(inner_h):
        src = (y0 + row) * width + x0
        dst = row * inner_w
        cropped[dst : dst + inner_w] = pixels[src : src + inner_w]
    return inner_w, inner_h, bytes(cropped)


def screen_text(monitor: ViceMonitor, screen_base: int) -> str:
    return "\n".join(
        decode_screen(monitor.memory_paused(screen_base, screen_base + 0x03E7))
    ).lower()


def wait_for_screen(
    monitor: ViceMonitor,
    screen_base: int,
    needles: tuple[str, ...],
    timeout: float,
) -> str:
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        last = screen_text(monitor, screen_base)
        monitor.resume()
        if all(needle in last for needle in needles):
            return last
        time.sleep(0.01)
    raise TimeoutError(
        f"timed out waiting for {', '.join(needles)}; screen was:\n{last}"
    )


def trigger_attract(monitor: ViceMonitor, screen_base: int) -> str:
    """Force the title's 20-second idle deadline, then wait for attract flight."""
    monitor.advance_instructions(10000)
    raw = monitor.memory_paused(0x00A0, 0x00A2)
    current = jiffy_value(raw)
    target = (current + 1201) % 5184000
    monitor.set_memory(
        0x00A0,
        bytes(((target >> 16) & 0xFF, (target >> 8) & 0xFF, target & 0xFF)),
    )
    monitor.resume()
    return wait_for_screen(
        monitor, screen_base, (*FLIGHT_NEEDLES, ATTRACT_NEEDLE), 30.0
    )


def capture_frame(
    monitor: ViceMonitor, path: Path, crop: bool
) -> tuple[int, int]:
    width, height, pixels, geometry = monitor.display()
    palette = monitor.palette()
    if crop:
        width, height, pixels = crop_inner(width, height, pixels, geometry)
    write_png(path, width, height, pixels, palette)
    return width, height


def assemble_gif(
    frames: list[Path],
    output: Path,
    fps: float,
    scale: int,
    magick: str,
) -> None:
    if not frames:
        raise RuntimeError("no frames captured")
    delay = max(1, int(round(100.0 / fps)))
    command = [
        magick,
        "-delay",
        str(delay),
        "-loop",
        "0",
    ]
    command.extend(str(path) for path in frames)
    if scale != 100:
        command.extend(
            (
                "-filter",
                "point",
                "-resize",
                f"{scale}%",
            )
        )
    command.extend(("-layers", "Optimize", str(output)))
    subprocess.run(command, check=True)


def status_score(text: str) -> int | None:
    match = re.search(r"\bscore\s*(-?\d+)", text)
    return int(match.group(1)) if match else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prg", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--frame-dir", type=Path, default=Path("build/gif-frames"))
    parser.add_argument("--screen-base", type=lambda s: int(s, 0), default=0x8400)
    parser.add_argument("--vice", default="x64sc")
    parser.add_argument("--magick", default="magick")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--fps", type=float, default=6.0)
    parser.add_argument("--title-seconds", type=float, default=2.0)
    parser.add_argument(
        "--flight-seconds",
        type=float,
        default=45.0,
        help="max attract capture length; stops early after a scored landing",
    )
    parser.add_argument(
        "--scale",
        type=int,
        default=200,
        help="nearest-neighbour scale percent for the GIF (100 = native)",
    )
    parser.add_argument("--startup-timeout", type=float, default=180.0)
    parser.add_argument(
        "--keep-frames",
        action="store_true",
        help="leave PNG frames in --frame-dir after assembly",
    )
    parser.add_argument(
        "--no-crop",
        action="store_true",
        help="keep the full VICE display buffer including borders",
    )
    args = parser.parse_args()

    if args.fps <= 0:
        raise SystemExit("--fps must be positive")
    if shutil.which(args.magick) is None:
        raise SystemExit(f"{args.magick} not found; install ImageMagick")
    if not args.prg.is_file():
        raise SystemExit(f"missing PRG: {args.prg}")

    args.frame_dir.mkdir(parents=True, exist_ok=True)
    for stale in args.frame_dir.glob("frame-*.png"):
        stale.unlink()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    port = free_port()
    log_path = args.frame_dir / "vice.log"
    command = [
        args.vice,
        "-default",
        "-warp",
        "-seed",
        str(args.seed),
        "+autostart-delay-random",
        "-sounddev",
        "dummy",
        "-binarymonitor",
        "-binarymonitoraddress",
        f"ip4://127.0.0.1:{port}",
        "-autostart",
        str(args.prg.resolve()),
    ]
    with log_path.open("wb") as log:
        vice = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        monitor: ViceMonitor | None = None
        frames: list[Path] = []
        try:
            monitor = ViceMonitor("127.0.0.1", port, timeout=30.0)
            wait_for_screen(
                monitor, args.screen_base, TITLE_NEEDLES, args.startup_timeout
            )

            step = max(1, int(round(60.0 / args.fps)))
            title_frames = max(1, int(round(args.title_seconds * args.fps)))
            flight_frames = max(1, int(round(args.flight_seconds * args.fps)))

            for index in range(title_frames):
                path = args.frame_dir / f"frame-{len(frames):04d}.png"
                capture_frame(monitor, path, crop=not args.no_crop)
                frames.append(path)
                if index + 1 < title_frames:
                    advance_jiffies(monitor, step)

            trigger_attract(monitor, args.screen_base)
            baseline = status_score(screen_text(monitor, args.screen_base))

            for index in range(flight_frames):
                path = args.frame_dir / f"frame-{len(frames):04d}.png"
                capture_frame(monitor, path, crop=not args.no_crop)
                frames.append(path)
                text = screen_text(monitor, args.screen_base)
                score = status_score(text)
                landed = (
                    baseline is not None
                    and score is not None
                    and score > baseline
                    and ATTRACT_NEEDLE in text
                )
                if landed or ATTRACT_NEEDLE not in text:
                    break
                if index + 1 < flight_frames:
                    advance_jiffies(monitor, step)

            assemble_gif(frames, args.output, args.fps, args.scale, args.magick)
            size = args.output.stat().st_size
            print(
                f"gif: {args.output} ({len(frames)} frames, "
                f"{size} bytes, {args.fps:g} fps, scale {args.scale}%)"
            )
            return 0
        finally:
            if monitor is not None:
                try:
                    monitor.quit()
                except (ConnectionError, OSError, RuntimeError):
                    pass
                monitor.close()
            if vice.poll() is None:
                try:
                    vice.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    vice.terminate()
                    try:
                        vice.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        vice.kill()
                        vice.wait()
            if not args.keep_frames:
                for path in frames:
                    path.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
