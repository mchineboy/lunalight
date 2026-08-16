#!/usr/bin/env python3
"""Record or compare a deterministic gameplay trace from original Blitz! output."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from vice_monitor import ViceMonitor

TITLE_NEEDLES = ("l u n a l i g h t", "press f7 to start")
FLIGHT_NEEDLES = ("vel", "fuel", "horz")
# Fixture-lineage VIC bank 0 layout; the canonical bank-2 package overrides these.
DEFAULT_SCREEN_BASE = 0x0400
DEFAULT_POINTER_BASE = 0x07F8
SAMPLE_JIFFIES = (10, 20, 30, 40, 50, 70)
ROTATE_JIFFY = 25
F7 = b"\x88"
CURSOR_RIGHT = b"\x1d"

# Comparison policy: timing and continuous coordinates may differ by one unit.
# Register bitfields, sprite pointers, decoded text, and fuel are exact.
TOLERANCES = {
    "sample_jiffy": 0,
    "sprite_x": 1,
    "sprite_y": 1,
    "hud.vel": 1,
    "hud.horz": 1,
    "hud.fuel": 0,
}

def decode_screen(data: bytes) -> list[str]:
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

    return [
        "".join(decode(value) for value in data[row : row + 40]).rstrip()
        for row in range(0, 1000, 40)
    ]


def wait_for_screen(
    monitor: ViceMonitor,
    needles: tuple[str, ...],
    timeout: float,
    screen_base: int = DEFAULT_SCREEN_BASE,
) -> list[str]:
    deadline = time.monotonic() + timeout
    last: list[str] = []
    while time.monotonic() < deadline:
        last = decode_screen(monitor.memory(screen_base, screen_base + 0x03E7))
        joined = "\n".join(last).lower()
        if all(needle in joined for needle in needles):
            return last
        time.sleep(0.01)
    raise TimeoutError(
        f"timed out waiting for {', '.join(needles)}; screen was:\n"
        + "\n".join(last)
    )


def jiffy_value(raw: bytes) -> int:
    return (raw[0] << 16) | (raw[1] << 8) | raw[2]


def advance_to_jiffy(monitor: ViceMonitor, target: int) -> None:
    current = jiffy_value(monitor.memory_paused(0x00A0, 0x00A2))
    while current < target - 2:
        monitor.stop_on_store(0x00A2)
        current = jiffy_value(monitor.memory_paused(0x00A0, 0x00A2))
    while current < target:
        monitor.advance_instructions(50)
        current = jiffy_value(monitor.memory_paused(0x00A0, 0x00A2))
    if current != target:
        raise RuntimeError(f"missed deterministic jiffy {target}; stopped at {current}")


def hud_value(screen: list[str], label: str) -> int | None:
    for row, line in enumerate(screen):
        column = line.find(label)
        if column < 0:
            continue
        for candidate in screen[row + 1 : row + 3]:
            match = re.search(r"-?\d+", candidate[max(0, column - 1) : column + 8])
            if match:
                return int(match.group())
    return None


def capture(
    monitor: ViceMonitor,
    requested_jiffy: int,
    screen_base: int = DEFAULT_SCREEN_BASE,
    pointer_base: int = DEFAULT_POINTER_BASE,
) -> dict[str, Any]:
    # The first read stops VICE. Remaining reads occur while it is paused.
    vic = monitor.memory_paused(0xD000, 0xD02F)
    screen = decode_screen(monitor.memory_paused(screen_base, screen_base + 0x03E7))
    pointers = list(monitor.memory_paused(pointer_base, pointer_base + 7))
    actual_jiffy = jiffy_value(monitor.memory_paused(0x00A0, 0x00A2))

    msb = vic[0x10]
    sprites = [
        {
            "index": index,
            "x": vic[index * 2] + (256 if msb & (1 << index) else 0),
            "y": vic[index * 2 + 1],
        }
        for index in range(8)
    ]
    return {
        "requested_jiffy": requested_jiffy,
        "sample_jiffy": actual_jiffy,
        "sprites": sprites,
        "vic": {
            "x_msb": msb,
            "enabled": vic[0x15],
            "expanded_y": vic[0x17],
            "sprite_sprite_collision": vic[0x1E],
            "sprite_background_collision": vic[0x1F],
        },
        "sprite_pointers": pointers,
        "hud": {
            "vel": hud_value(screen, "vel"),
            "fuel": hud_value(screen, "fuel"),
            "horz": hud_value(screen, "horz"),
        },
        "screen_rows": {
            str(index): line for index, line in enumerate(screen) if line.strip()
        },
    }


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def capture_trace(args: argparse.Namespace) -> dict[str, Any]:
    artifact = args.prg.resolve()
    if not artifact.is_file():
        raise RuntimeError(f"missing Blitz! artifact: {artifact}")
    args.screenshot.parent.mkdir(parents=True, exist_ok=True)
    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.screenshot.unlink(missing_ok=True)
    port = args.port or free_port()
    command = [
        args.vice,
        "-default",
        "-seed",
        str(args.seed),
        "+autostart-delay-random",
        "-sounddev",
        "dummy",
        "-binarymonitor",
        "-binarymonitoraddress",
        f"ip4://127.0.0.1:{port}",
        "-exitscreenshot",
        str(args.screenshot),
        "-autostart",
        str(artifact),
    ]
    with args.log.open("wb") as output:
        vice = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT)

    monitor: ViceMonitor | None = None
    samples: list[dict[str, Any]] = []
    try:
        monitor = ViceMonitor("127.0.0.1", port, timeout=10.0)
        wait_for_screen(monitor, TITLE_NEEDLES, args.startup_timeout, args.screen_base)
        monitor.inject_paused(F7)

        # The first player-X write after F7 is the exact flight-start event.
        monitor.stop_on_store(0xD000)
        monitor.set_memory(0x00A0, b"\0\0\0")
        rotation_injected = False
        for target in SAMPLE_JIFFIES:
            if target > ROTATE_JIFFY and not rotation_injected:
                advance_to_jiffy(monitor, ROTATE_JIFFY)
                monitor.inject_paused(CURSOR_RIGHT)
                rotation_injected = True
            advance_to_jiffy(monitor, target)
            samples.append(
                capture(monitor, target, args.screen_base, args.pointer_base)
            )
        monitor.quit()
        monitor.close()
        monitor = None
        vice.wait(timeout=5)
    finally:
        if monitor is not None:
            monitor.close()
        if vice.poll() is None:
            vice.terminate()
            try:
                vice.wait(timeout=5)
            except subprocess.TimeoutExpired:
                vice.kill()
                vice.wait()

    initial_pointer = samples[0]["sprite_pointers"][0]
    if not any(sample["sprite_pointers"][0] != initial_pointer for sample in samples[3:]):
        raise RuntimeError("controlled cursor-right rotation was not observed")
    first_screen = "\n".join(samples[0]["screen_rows"].values()).lower()
    if not all(needle in first_screen for needle in FLIGHT_NEEDLES):
        raise RuntimeError("flight HUD was not established by the first sample")
    trace = {
        "schema": 1,
        "profile": {
            "machine": "C64SC",
            "vice_seed": args.seed,
            "sound_device": "dummy",
            "artifact": str(args.prg),
            "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
            "sprite_embed_address": f"0x{args.sprite_embed_address:04x}",
            "screen_base": f"0x{args.screen_base:04x}",
            "sprite_pointer_base": f"0x{args.pointer_base:04x}",
        },
        "synchronization": {
            "title": list(TITLE_NEEDLES),
            "flight": list(FLIGHT_NEEDLES),
            "flight_instruction_anchor": "first-store:$d000-after-f7",
            "jiffy_epoch_reset": True,
        },
        "events": [{"jiffy": ROTATE_JIFFY, "input": "cursor-right", "petscii": 29}],
        "tolerances": TOLERANCES,
        "samples": samples,
    }
    return trace


def compare_number(
    failures: list[str], path: str, actual: int | None, expected: int | None, tolerance: int
) -> None:
    if actual is None or expected is None or abs(actual - expected) > tolerance:
        failures.append(
            f"{path}: expected {expected} +/- {tolerance}, observed {actual}"
        )


def compare_motion(actual: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    """Compare only foreground flight motion and its numeric state."""
    failures: list[str] = []
    if len(actual["samples"]) != len(expected["samples"]):
        return ["samples: count differs from baseline"]
    for index, (seen, golden) in enumerate(
        zip(actual["samples"], expected["samples"], strict=True)
    ):
        prefix = f"samples[{index}]"
        if seen["requested_jiffy"] != golden["requested_jiffy"]:
            failures.append(f"{prefix}.requested_jiffy: changed")
        compare_number(
            failures,
            f"{prefix}.sample_jiffy",
            seen["sample_jiffy"],
            golden["sample_jiffy"],
            TOLERANCES["sample_jiffy"],
        )
        for sprite_index in (0, 1):
            for axis in ("x", "y"):
                compare_number(
                    failures,
                    f"{prefix}.sprites[{sprite_index}].{axis}",
                    seen["sprites"][sprite_index][axis],
                    golden["sprites"][sprite_index][axis],
                    TOLERANCES[f"sprite_{axis}"],
                )
        for key in ("vel", "fuel", "horz"):
            compare_number(
                failures,
                f"{prefix}.hud.{key}",
                seen["hud"][key],
                golden["hud"][key],
                TOLERANCES[f"hud.{key}"],
            )
    return failures


def compare_strict(actual: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if actual["schema"] != expected["schema"]:
        failures.append(
            f"schema: expected {expected['schema']}, observed {actual['schema']}"
        )
    for key in ("synchronization", "events", "tolerances"):
        if actual[key] != expected[key]:
            failures.append(f"{key}: trace configuration differs from baseline")
    if len(actual["samples"]) != len(expected["samples"]):
        failures.append("samples: count differs from baseline")
        return failures

    for index, (seen, golden) in enumerate(
        zip(actual["samples"], expected["samples"], strict=True)
    ):
        prefix = f"samples[{index}]"
        if seen["requested_jiffy"] != golden["requested_jiffy"]:
            failures.append(f"{prefix}.requested_jiffy: changed")
        compare_number(
            failures,
            f"{prefix}.sample_jiffy",
            seen["sample_jiffy"],
            golden["sample_jiffy"],
            TOLERANCES["sample_jiffy"],
        )
        for sprite_index, (seen_sprite, golden_sprite) in enumerate(
            zip(seen["sprites"], golden["sprites"], strict=True)
        ):
            compare_number(
                failures,
                f"{prefix}.sprites[{sprite_index}].x",
                seen_sprite["x"],
                golden_sprite["x"],
                TOLERANCES["sprite_x"],
            )
            compare_number(
                failures,
                f"{prefix}.sprites[{sprite_index}].y",
                seen_sprite["y"],
                golden_sprite["y"],
                TOLERANCES["sprite_y"],
            )
        for key in ("x_msb", "enabled", "expanded_y",
                    "sprite_sprite_collision", "sprite_background_collision"):
            if seen["vic"][key] != golden["vic"][key]:
                failures.append(
                    f"{prefix}.vic.{key}: expected {golden['vic'][key]}, "
                    f"observed {seen['vic'][key]}"
                )
        if seen["sprite_pointers"] != golden["sprite_pointers"]:
            failures.append(f"{prefix}.sprite_pointers: drifted")
        for key in ("vel", "fuel", "horz"):
            compare_number(
                failures,
                f"{prefix}.hud.{key}",
                seen["hud"][key],
                golden["hud"][key],
                TOLERANCES[f"hud.{key}"],
            )
        if seen["screen_rows"] != golden["screen_rows"]:
            failures.append(f"{prefix}.screen_rows: decoded screen drifted")
    return failures


def run(args: argparse.Namespace) -> int:
    trace = capture_trace(args)
    if args.record:
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        args.baseline.write_text(json.dumps(trace, indent=2) + "\n")
        print(f"recorded Blitz! baseline: {args.baseline}")
    else:
        if not args.baseline.is_file():
            raise RuntimeError(
                f"missing baseline {args.baseline}; run record-blitz-baseline explicitly"
            )
        expected = json.loads(args.baseline.read_text())
        failures = (
            compare_strict(trace, expected)
            if args.mode == "strict"
            else compare_motion(trace, expected)
        )
        if failures:
            print("Blitz! gameplay drift:", file=sys.stderr)
            for failure in failures:
                print(f"  - {failure}", file=sys.stderr)
            return 1
        print(
            f"verified {len(trace['samples'])} deterministic gameplay samples "
            f"against {args.baseline} ({args.mode} mode)"
        )
    if args.screenshot.is_file():
        print(f"screenshot: {args.screenshot}")
    return 0


def address(value: str) -> int:
    parsed = int(value, 0)
    if not 0 <= parsed <= 0xFFFF:
        raise argparse.ArgumentTypeError("address must be between 0 and 0xffff")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prg", type=Path, required=True)
    parser.add_argument("--screen-base", type=address, default=DEFAULT_SCREEN_BASE)
    parser.add_argument("--pointer-base", type=address, default=DEFAULT_POINTER_BASE)
    parser.add_argument("--sprite-embed-address", type=address, default=0x2E7C)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--record", action="store_true")
    parser.add_argument(
        "--mode",
        choices=("strict", "motion"),
        default="strict",
        help="motion compares foreground motion and HUD numbers within the "
        "recorded tolerances; strict additionally requires the whole decoded "
        "screen to match, so it only describes the bank-0 fixture lineage",
    )
    parser.add_argument("--vice", default="x64sc")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--startup-timeout", type=float, default=45.0)
    parser.add_argument("--screenshot", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args()
    if args.screen_base % 0x0400 or args.screen_base + 0x03E7 > 0xFFFF:
        parser.error("--screen-base must be 1KB aligned and hold 1000 bytes")
    if args.pointer_base + 7 > 0xFFFF:
        parser.error("--pointer-base must hold 8 bytes")
    return args


if __name__ == "__main__":
    try:
        raise SystemExit(run(parse_args()))
    except (ConnectionError, OSError, RuntimeError, TimeoutError) as error:
        print(f"verify-blitz-gameplay: {error}", file=sys.stderr)
        raise SystemExit(1)
