#!/usr/bin/env python3
"""Verify the canonical VIC-bank-2 package's layout and runtime behaviour.

Static checks read the packaged PRG segments; runtime checks drive VICE through
its binary monitor and record screenshots at the title, flight, pause and
explosion states. Every assertion prints the observed value so a failure names
the offending register or address instead of only the expectation.
"""

from __future__ import annotations

import argparse
import json
import re
import socket
import struct
import subprocess
import sys
import time
import traceback
import zlib
from pathlib import Path
from typing import Any

from vice_monitor import ViceMonitor

TITLE_NEEDLES = ("press f7 to start",)
FLIGHT_NEEDLES = ("vel", "fuel", "horz")
ATTRACT_NEEDLE = "attract"
F7 = b"\x88"
F1 = b"\x85"
CURSOR_RIGHT = b"\x1d"
CURSOR_DOWN = b"\x11"
PAUSE_TILE = 134
PAUSE_COLOR = 7
UNPAUSED_TILE = 160
# Procedural terrain paints reverse-video spaces (screen code 160) across the
# lower rows and pad surfaces as screen code 100 with a green (5) body flanked by
# grey (7) edge cells in colour RAM. Pads are placed by the RNG each game, so the
# harness proves the pads are *rendered* rather than asserting fixed positions.
TERRAIN_TILE = 160
PAD_SURFACE_TILE = 100
PAD_BODY_COLOR = 5
PAD_EDGE_COLOR = 7
# The refuel flag lives on sprite 4, pointer slot 243, coloured white and
# unexpanded. Its shape is patched into the spare sprite slot 243 whose
# VIC-bank-2 address is $BCC0. Sprite 5 carries the pennant field from slot 245
# at the same coordinates one priority step behind it, so the outline, emblem and
# mast read as white over blue: the Earth decoration's two-sprite layover, and
# its palette, applied to the flag. The mast and base sit on the front sprite
# against black sky, so the front sprite has to be the lighter of the pair, and
# neither colour may be 11 or 12 because the terrain is painted in those greys.
# The soundtrack belongs to the title screen alone. SYS 16896 points $0314 at
# the player loaded at $4200; SYS 16899 restores the KERNAL vector, so flight
# and attract mode leave the SID to the engine and explosion effects.
MUSIC_START = 0x4200
MUSIC_END = 0x4400
TITLE_D018 = 0x12
TITLE_CHARSET_ADDRESS = 0x8800
# MEMSIZ must stay at $A000 on the title as well as in flight. Lowering it to
# the title character page put the top of the descending string heap at $87FF,
# straight over the sprite pointers at $87F8-$87FF, so the forced collection in
# line 840 rewrote them the first time a round ended. The heap is kept clear of
# $8800 by that collection instead, not by a MEMSIZ guard.
FLIGHT_MEMSIZ = 0xA000
TITLE_SPRITE_POINTERS = [187, 246, 253, 254, 243, 245, 195, 244]
# The lander graphic fills its 24-pixel sprite, so its centre sits half a sprite
# right of the $D000 value the landing verdict reads.
SPRITE_CENTRE_OFFSET = 12
FLAG_SLOT = 243
FLAG_POINTER_INDEX = 4
FLAG_SPRITE_COLOR = 1
FIELD_SLOT = 245
FIELD_POINTER_INDEX = 5
FIELD_SPRITE_COLOR = 6
LEM_FILL_SLOTS = (246, 247, 248, 249, 250)
LEM_FILL_ATTITUDES = dict(zip(LEM_FILL_SLOTS, (187, 188, 189, 193, 194)))
LEM_FILL_POINTER_INDEX = 1
LEM_FILL_SPRITE_COLOR = 0
EXHAUST_POINTER_INDEX = 6
DUST_SLOT = 251
# Rows of the flag shape the pennant (and therefore the field block) occupies.
PENNANT_ROWS = 12
# The cosmetic orbiting command module lives on sprite 7, pointer slot 244,
# light grey. Sprite 7 is otherwise explosion-only, so the flight loop has to
# re-establish it after every round.
MODULE_SLOT = 244
MODULE_POINTER_INDEX = 7
MODULE_SPRITE_COLOR = 15
MODULE_SPRITE_Y = 55
# Shapes patched into spare slots of the original payload by make-shapes.py.
PATCHED_SLOTS = (FLAG_SLOT, MODULE_SLOT, FIELD_SLOT) + LEM_FILL_SLOTS + (DUST_SLOT,)
FLIGHT_POINTERS = {
    2: 253,
    3: 254,
    FIELD_POINTER_INDEX: FIELD_SLOT,
    MODULE_POINTER_INDEX: MODULE_SLOT,
}
EXPLOSION_POINTER_RANGE = (203, 242)
# $D015 enable masks the flight loop writes: coast keeps the lander, its black
# interior fill, the two decoration sprites, the flag pair and command module
# (all but exhaust sprite 6 = 191); thrust enables all eight sprites.
COAST_ENABLE = 191
THRUST_ENABLE = 255
# Sprite pointers the source POKEs during flight, the added shapes and explosion.
USED_POINTERS = (
    tuple(range(187, 203))
    + tuple(range(203, 243))
    + PATCHED_SLOTS
    + (253, 254)
)
# Landing evaluation and explosion presentation must stay identical to the
# bank-0 fallback source; these are the BASIC line numbers that implement them.
LANDING_LINES = (
    630, 635, 640, 641, 642, 644, 649, 650, 670, 680, 690, 695, 696, 700,
    710, 720, 730, 740, 744, 746, 748, 750, 752, 753, 754, 755, 760, 775,
    778, 780, 785, 790, 795, 840,
)
# The bank-2 crash post-mortem must know a crash happened off-pad, and the only
# place that fact exists is the pad-failure fallthrough. Allow exactly that
# marker as a prefix; the bank-0 statement it precedes still has to match
# byte for byte, so the landing decision itself remains unchanged.
LANDING_LINE_PREFIXES = {700: "xz=1:"}
# Crash post-mortem strings. Each crash prints exactly one line: either a cause
# chosen from the crash state or a consequence read from the DATA table, picked
# by a coin flip off the RNG table, so a single descent can only show one tier.
CRASH_CAUSES = (
    "you rearranged the landscape",
    "boulders are not landing pads",
    "you cartwheeled",
    "lems do not land sideways",
    "new crater",
)
CRASH_CONSEQUENCES = (
    "salvage crews found one boot",
    "houston is billing your estate",
    "taxpayers demand an inquiry",
    "your damage deposit is forfeit",
    "next of kin have been notified",
    "underwriters call it pilot error",
    "you also flattened the flag",
    "the parked rover is now scrap",
    "another 100 megabucks well spent",
    "aux tanks are now lunar confetti",
    "your crater needs its own postcode",
    "mission control muted your channel",
    "your flight recorder just resigned",
)


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


class Report:
    def __init__(self) -> None:
        self.checks: list[dict[str, Any]] = []
        self.facts: dict[str, Any] = {}
        self.notes: list[str] = []
        self.screenshots: list[str] = []

    def check(self, name: str, passed: bool, observed: Any, expected: Any) -> bool:
        self.checks.append(
            {
                "check": name,
                "passed": bool(passed),
                "observed": observed,
                "expected": expected,
            }
        )
        return bool(passed)

    def equal(self, name: str, observed: Any, expected: Any) -> bool:
        return self.check(name, observed == expected, observed, expected)

    def note(self, text: str) -> None:
        self.notes.append(text)

    @property
    def failures(self) -> list[dict[str, Any]]:
        return [entry for entry in self.checks if not entry["passed"]]


def load_prg(path: Path) -> tuple[int, bytes]:
    data = path.read_bytes()
    if len(data) < 3:
        raise RuntimeError(f"{path}: too short to be a PRG")
    return int.from_bytes(data[:2], "little"), data[2:]


def hexrange(start: int, length: int) -> str:
    return f"${start:04X}-${start + length - 1:04X}"


def static_layout(args: argparse.Namespace, report: Report) -> dict[str, Any]:
    full_addr, full = load_prg(args.prg)
    code_addr, code = load_prg(args.code_prg)
    sprite_addr, sprites = load_prg(args.sprite_prg)
    original_addr, original = load_prg(args.original_sprite_prg)

    code_end = code_addr + len(code) - 1
    sprite_end = sprite_addr + len(sprites) - 1
    bank_base = args.vic_bank * 0x4000
    slot_offsets = {slot: slot * 64 - original_addr for slot in PATCHED_SLOTS}
    flag_block_bank2 = bank_base + FLAG_SLOT * 64
    layout = {
        "full_artifact": hexrange(full_addr, len(full)),
        "code": hexrange(code_addr, len(code)),
        "code_end": f"${code_end:04X}",
        "relocated_sprites": hexrange(sprite_addr, len(sprites)),
        "vic_bank": f"${bank_base:04X}-${bank_base + 0x3FFF:04X}",
        "patched_slots": {
            slot: f"${bank_base + slot * 64:04X}" for slot in PATCHED_SLOTS
        },
        "flag_block_bank2_address": f"${flag_block_bank2:04X}",
    }

    if args.title_charset is not None:
        charset_addr, charset = load_prg(args.title_charset)
        charset_offset = charset_addr - full_addr
        resident = full[charset_offset : charset_offset + len(charset)]
        report.equal("static.title_charset_load_address", charset_addr, TITLE_CHARSET_ADDRESS)
        report.equal("static.title_charset_size", len(charset), 2048)
        report.check(
            "static.title_charset_embedded_at_$8800",
            charset_offset >= 0 and resident == charset,
            f"{args.title_charset.name} ${charset_addr:04X}-${charset_addr + len(charset) - 1:04X}",
            "the complete title charset embedded at $8800",
        )

    # The relocated sprite must be the original shapes with the added shapes
    # patched into spare slots, its load address moved into VIC bank 2, and
    # nothing else changed. Comparing against both the raw original and the
    # patched build proves exactly which 64-byte blocks the shapes occupy.
    if args.patched_sprite_prg is not None:
        patched_addr, patched = load_prg(args.patched_sprite_prg)
        report.equal(
            "static.patched_source_load_address",
            f"${patched_addr:04X}",
            f"${original_addr:04X}",
        )
        report.check(
            "static.sprite_payload_matches_patched_source",
            sprites == patched,
            f"{len(sprites)} bytes, "
            f"{sum(1 for a, b in zip(sprites, patched) if a != b)} differ from "
            f"{args.patched_sprite_prg.name}",
            f"rebased payload identical to {args.patched_sprite_prg.name}",
        )
    differ = [i for i, (a, b) in enumerate(zip(sprites, original)) if a != b]
    only_patched = bool(differ) and all(
        any(off <= i < off + 64 for off in slot_offsets.values()) for i in differ
    )
    report.check(
        "static.only_patched_slots_differ_from_original",
        only_patched and len(sprites) == len(original),
        f"{len(differ)} byte(s) differ, "
        f"{'all' if only_patched else 'some'} inside slots "
        + ", ".join(
            f"{slot} (offset {off}-{off + 63})" for slot, off in slot_offsets.items()
        ),
        "only the 64-byte blocks of slots "
        + ", ".join(str(slot) for slot in PATCHED_SLOTS)
        + f" differ from {args.original_sprite_prg.name}",
    )
    # A C64 sprite is 63 bytes; the 64th byte of each slot is unused padding, so
    # make-shapes.py treats a slot as spare when its first 63 bytes are empty.
    spare_before = {
        slot: sum(1 for b in original[off : off + 63] if b)
        for slot, off in slot_offsets.items()
    }
    shaped_after = {
        slot: sum(1 for b in sprites[off : off + 63] if b)
        for slot, off in slot_offsets.items()
    }
    report.check(
        "static.patched_slots_were_spare_now_hold_shapes",
        not any(spare_before.values()) and all(shaped_after.values()),
        {"original_nonzero": spare_before, "patched_nonzero": shaped_after},
        "shape bytes of slots "
        + ", ".join(str(slot) for slot in PATCHED_SLOTS)
        + " empty in the original, non-empty after patching",
    )
    fill_outside: dict[int, list[tuple[int, int]]] = {}
    for slot, attitude in LEM_FILL_ATTITUDES.items():
        fill_off = slot_offsets[slot]
        outline_off = attitude * 64 - original_addr
        outside: list[tuple[int, int]] = []
        for row in range(21):
            outline_x = [
                x
                for x in range(24)
                if original[outline_off + row * 3 + x // 8] & (0x80 >> (x % 8))
            ]
            for x in range(24):
                filled = sprites[fill_off + row * 3 + x // 8] & (0x80 >> (x % 8))
                if filled and (
                    len(outline_x) < 2
                    or x < min(outline_x)
                    or x > max(outline_x)
                ):
                    outside.append((x, row))
        if outside:
            fill_outside[slot] = outside
    report.check(
        "static.lem_fill_pixels_within_outline_envelopes",
        not fill_outside,
        fill_outside,
        "every black fill pixel lies between outline pixels on the matching "
        "lander attitude's scanline",
    )
    report.equal(
        "static.sprite_bank_offset_preserved",
        f"${sprite_addr - bank_base:04X}",
        f"${original_addr:04X}",
    )
    report.check(
        "static.flag_block_maps_to_bank2_address",
        flag_block_bank2 == 0xBCC0
        and sprite_addr <= flag_block_bank2
        and flag_block_bank2 + 63 <= sprite_end,
        f"slot {FLAG_SLOT} -> ${flag_block_bank2:04X}",
        f"$BCC0 inside {layout['relocated_sprites']}",
    )
    report.check(
        "static.sprites_clear_of_code",
        sprite_addr > code_end,
        f"code ends ${code_end:04X}, sprites start ${sprite_addr:04X}",
        "sprite start above code end",
    )
    report.check(
        "static.old_sprite_region_free_of_sprites",
        sprite_addr > original_addr + len(original) - 1,
        f"sprites now {hexrange(sprite_addr, len(sprites))}",
        f"nothing at {hexrange(original_addr, len(original))}",
    )
    report.check(
        "static.full_artifact_covers_relocated_sprites",
        full_addr <= sprite_addr and full_addr + len(full) - 1 >= sprite_end,
        layout["full_artifact"],
        f"covers {layout['relocated_sprites']}",
    )

    pointer_addresses = {
        pointer: bank_base + pointer * 64 for pointer in USED_POINTERS
    }
    lowest = min(pointer_addresses.values())
    highest = max(pointer_addresses.values()) + 63
    layout["used_pointer_span"] = f"${lowest:04X}-${highest:04X}"
    report.check(
        "static.used_pointer_blocks_inside_loaded_sprites",
        sprite_addr <= lowest and highest <= sprite_end,
        layout["used_pointer_span"],
        f"inside {layout['relocated_sprites']}",
    )
    report.check(
        "static.used_pointer_blocks_inside_vic_bank",
        highest <= bank_base + 0x3FFF,
        f"${highest:04X}",
        f"<= ${bank_base + 0x3FFF:04X}",
    )
    if args.rng_prg is not None:
        rng_addr, rng = load_prg(args.rng_prg)
        rng_end = rng_addr + len(rng) - 1
        layout["rng"] = hexrange(rng_addr, len(rng))
        report.equal(
            "static.rng_cpu_side_load_range",
            hexrange(rng_addr, len(rng)),
            "$4400-$4BFF",
        )
        report.check(
            "static.rng_clear_of_code_and_sprites",
            rng_addr > code_end and rng_end < sprite_addr,
            f"code ends ${code_end:04X}, rng {hexrange(rng_addr, len(rng))}, "
            f"sprites start ${sprite_addr:04X}",
            "rng sits above code and below the relocated sprites",
        )
        report.check(
            "static.full_artifact_covers_rng",
            full_addr <= rng_addr and full_addr + len(full) - 1 >= rng_end,
            layout["full_artifact"],
            f"covers {layout['rng']}",
        )
    if args.music_prg is not None:
        music_addr, music = load_prg(args.music_prg)
        layout["music"] = hexrange(music_addr, len(music))
        layout["code_growth_ceiling"] = f"${music_addr - 1:04X}"
        layout["code_headroom_bytes"] = music_addr - 1 - code_end
        layout["headroom_under_old_sprite_layout_bytes"] = original_addr - 1 - code_end
        report.check(
            "static.growth_ceiling_above_old_sprite_start",
            music_addr - 1 > original_addr,
            f"ceiling ${music_addr - 1:04X} (music start - 1), old sprite start "
            f"${original_addr:04X}, code ends ${code_end:04X}",
            "the reachable ceiling lies past the freed sprite region",
        )
        if args.rng_prg is not None:
            rng_addr, rng = load_prg(args.rng_prg)
            report.check(
                "static.assets_in_ascending_order",
                code_end < music_addr
                and music_addr + len(music) - 1 < rng_addr
                and rng_addr + len(rng) - 1 < sprite_addr,
                f"code end ${code_end:04X} < music ${music_addr:04X} < "
                f"rng ${rng_addr:04X} < sprites ${sprite_addr:04X}",
                "code, music $4200, rng $4400, sprites $AE7C in ascending order",
            )
    if args.filler is not None:
        start, end, value = args.filler
        offset = start - full_addr
        span = full[offset : end - full_addr + 1]
        layout["filler"] = {
            "range": f"${start:04X}-${end:04X}",
            "value": f"0x{value:02x}",
            "bytes": len(span),
        }
        report.check(
            "static.filler_present_in_artifact",
            len(span) == end - start + 1 and set(span) == {value},
            f"{len(span)} bytes, distinct values {sorted(set(span))[:4]}",
            f"{end - start + 1} bytes of 0x{value:02x}",
        )
        report.check(
            "static.filler_clear_of_sprites",
            end < sprite_addr,
            f"filler ends ${end:04X}, sprites start ${sprite_addr:04X}",
            "no overlap",
        )
    report.facts["layout"] = layout
    return layout


def source_lines(path: Path) -> dict[int, str]:
    lines: dict[int, str] = {}
    for raw in path.read_text().splitlines():
        match = re.match(r"\s*(\d+)\s(.*)$", raw)
        if match:
            lines[int(match.group(1))] = match.group(2).rstrip()
    return lines


def _normalize(text: str) -> str:
    return text.replace(" ", "")


def landing_logic(args: argparse.Namespace, report: Report) -> None:
    """Prove the generic pad-metadata landing verdict, scoring and refuel.

    The promoted bank-2 source replaces the bank-0 hard-coded landing windows
    with a loop over the RNG-generated pad arrays. This check pins that generic
    logic to the source: the verdict gate must use tilt, upright-shape and the
    float velocity threshold 5, the pad loop must test the px/pw x-window and the
    py altitude window, award pb() points, mark off-pad crashes, and refuel from
    the rf() metadata. Scoring lines that are physics-shared with the bank-0
    fallback source are held byte-identical against it.

    px() is the sprite-X of a pad's left edge, so the verdict has to compare the
    lander's centre rather than its left edge. Line 649 therefore carries the
    half-sprite offset; without it the generated windows sit 12 pixels right of
    the craft and the centre bonus at line 740 is unreachable.
    """
    variant = source_lines(args.bank2_source)

    # (line, substring that must appear once whitespace is removed)
    required = {
        642: "ifp<>187goto1320",
        644: "ifint(m2)>5goto1320",
        649: f"pf=int(pp)+{SPRITE_CENTRE_OFFSET}:ife2thenpf=pf+256",
        650: "fori=1to5",
        660: "ifpf<px(i)orpf>=px(i)+pw(i)*8then690",
        670: "ifabs(po-py(i))>4then690",
        680: "lz=i:tp=tp+pb(i)",
        690: "next",
        700: "iflz=.thenxz=1:goto1320",
        705: "ifrf(lz)<>.andfe<=399thenfe=1000:e7=1",
        706: "gosub1700:goto720",
        1700: f"pokepn+6,{DUST_SLOT}",
    }
    missing = [line for line in required if line not in variant]
    differing = [
        line
        for line in required
        if line in variant
        and _normalize(required[line]) not in _normalize(variant[line])
    ]
    report.check(
        "landing.generic_pad_verdict_logic",
        not missing and not differing,
        {"missing": missing, "differing": differing},
        "verdict/threshold/pad-loop/refuel lines present with generic pad "
        "metadata (px/pw/py/pb/rf) and float velocity threshold 5",
    )

    # Line 720 is held byte-identical to the bank-0 fallback, and it writes
    # $D010=fm, which clears the lander's X-MSB. A craft that touched down past
    # sprite X 255 (e2=1) would therefore jump 256 pixels left off its pad. The
    # bit is restored in the bank-2-only module routine that 720 gosubs.
    msb_restore = "ife2thenpokev+16,fh"
    report.check(
        "landing.lander_x_msb_restored_on_pad",
        1214 in variant and _normalize(msb_restore) in _normalize(variant[1214]),
        {"line_1214": variant.get(1214)},
        "the successful-landing path restores the lander's X-MSB so a craft that "
        "lands past sprite X 255 stays on its pad instead of snapping 256px left",
    )
    # The flag layover is two sprites deep, so its colours land in adjacent VIC
    # registers: $D02B (v+43) for the front sprite and $D02C (v+44) for the field
    # behind it. Sprite 5's power-on colour is already blue, so a field colour
    # POKEd one register too high still renders correctly by accident; only the
    # source text distinguishes the intended write from that coincidence.
    layover = {
        1210: "poke34812,243:pokev+8,fx:pokev+9,fy:pokev+43,"
        f"{FLAG_SPRITE_COLOR}",
        1211: f"poke34813,{FIELD_SLOT}:pokev+10,fx:pokev+11,fy:pokev+44,"
        f"{FIELD_SPRITE_COLOR}",
        1212: "pokev+21,peek(v+21)or162",
    }
    layover_diff = [
        line
        for line, expected in layover.items()
        if line not in variant or _normalize(expected) not in _normalize(variant[line])
    ]
    report.check(
        "flight.flag_layover_register_arithmetic",
        not layover_diff,
        {
            "differing": layover_diff,
            "lines": {line: variant.get(line) for line in layover},
        },
        f"flag colour to $D02B, field slot {FIELD_SLOT} and colour to $D02C at the "
        "flag's coordinates, and $D015 bits 1, 5 and 7 restored after line 720",
    )
    lem_fill = {
        130: "p=187:f=246",
        135: "pokev+40,0:pokev+45,8",
        185: "f=p+59:ifp>189thenf=p+56",
        187: "pokepn,p:pokepn+1,f:pokepn+6,p+8",
        220: "pokev+21,255",
        235: "pokev+21,191",
        430: "pokev,pp:pokev+1,po:pokev+2,pp:pokev+3,po",
        435: "ifqthenpokev+12,pp:pokev+13,po",
        1197: "fx=px(rz)-3:fm=.",
        1198: "fh=67+fm:fy=py(rz)-5:gosub1210",
        1212: "pokev+21,peek(v+21)or162",
    }
    lem_fill_diff = [
        line
        for line, expected in lem_fill.items()
        if line not in variant or _normalize(expected) not in _normalize(variant[line])
    ]
    report.check(
        "flight.lander_fill_register_arithmetic",
        not lem_fill_diff,
        {
            "differing": lem_fill_diff,
            "lines": {line: variant.get(line) for line in lem_fill},
        },
        "sprite 1 black fill tracks the attitude and position, sprite 6 carries "
        "the conditional exhaust, and enable/MSB masks include both",
    )
    report.check(
        "landing.generated_pads_are_four_glyphs_wide",
        1142 in variant and "pw(i)=4" in _normalize(variant[1142]),
        {"line_1142": variant.get(1142)},
        "every generated landing pad is exactly four character cells wide",
    )

    planned_miss = {
        1925: "tx=px(al)+4:af=(af+1)and3:ifaf=.thentx=px(al)-16",
        1926: "ap=.:return",
    }
    planned_miss_diff = [
        line
        for line, expected in planned_miss.items()
        if line not in variant
        or _normalize(expected) not in _normalize(variant[line])
    ]
    report.check(
        "attract.every_fourth_approach_deliberately_misses",
        not planned_miss_diff,
        {
            "differing": planned_miss_diff,
            "lines": {line: variant.get(line) for line in planned_miss},
        },
        "the demo centres three approaches, then aims outside the pad on the fourth",
    )

    # The demo plays one game and hands the screen back to the title for a fresh
    # idle wait. Clearing nf first is load-bearing: the shared message routine
    # ends at 984, which sends a game-over message into the F7 wait at 960, so a
    # demo that kept nf set would stall there instead of restarting.
    attract_exit = "ifnfthenifamthennf=.:gosub982:goto20"
    report.check(
        "attract.game_over_returns_to_title",
        792 in variant and _normalize(attract_exit) in _normalize(variant[792]),
        {"line_792": variant.get(792)},
        "attract game over announces itself and restarts at line 20 rather than "
        "resetting lives and flying on indefinitely",
    )

    # Scoring arithmetic shared with the bank-0 fallback (velocity, tilt and fuel
    # penalties plus the running total) must remain byte-identical.
    canonical = source_lines(args.canonical_source) if args.canonical_source else {}
    shared_scoring = (752, 753, 754, 755, 760)
    scoring_diff = [
        line
        for line in shared_scoring
        if line not in variant
        or (line in canonical and canonical[line] != variant[line])
    ]
    report.check(
        "landing.shared_scoring_identical",
        not scoring_diff,
        {"differing": scoring_diff},
        "velocity/tilt/fuel penalty and running-total lines byte-identical",
    )
    report.facts["landing_source_lines"] = {
        line: variant.get(line) for line in sorted(set(required) | set(shared_scoring))
    }


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class Session:
    def __init__(
        self,
        args: argparse.Namespace,
        prg: Path | None = None,
        screen_base: int | None = None,
        pointer_base: int | None = None,
        shot_prefix: str | None = None,
        control_port_io: bool = False,
    ):
        self.args = args
        self.prg = prg if prg is not None else args.prg
        self.screen_base = args.screen_base if screen_base is None else screen_base
        self.pointer_base = args.pointer_base if pointer_base is None else pointer_base
        self.shot_prefix = args.shot_prefix if shot_prefix is None else shot_prefix
        self.port = free_port()
        args.log.parent.mkdir(parents=True, exist_ok=True)
        args.shot_dir.mkdir(parents=True, exist_ok=True)
        self.exit_shot = args.shot_dir / f"{self.shot_prefix}-exit.png"
        self.exit_shot.unlink(missing_ok=True)
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
            f"ip4://127.0.0.1:{self.port}",
            "-exitscreenshot",
            str(self.exit_shot),
        ]
        if control_port_io:
            command.extend(("-controlport2device", "37"))
        command.extend(("-autostart", str(self.prg.resolve())))
        self.log = args.log.open("ab")
        self.vice = subprocess.Popen(
            command, stdout=self.log, stderr=subprocess.STDOUT
        )
        self.monitor: ViceMonitor | None = ViceMonitor(
            "127.0.0.1", self.port, timeout=15.0
        )
        self.ram = self.monitor.banks().get("ram", ViceMonitor.BANK_RAM)
        self.screenshots: list[str] = []

    def close(self) -> None:
        if self.monitor is not None:
            try:
                self.monitor.quit()
            except (ConnectionError, OSError, RuntimeError):
                pass
            self.monitor.close()
            self.monitor = None
        if self.vice.poll() is None:
            try:
                self.vice.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.vice.terminate()
                try:
                    self.vice.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.vice.kill()
                    self.vice.wait()
        self.log.close()

    def screen_codes(self) -> bytes:
        assert self.monitor is not None
        return self.monitor.memory_paused(self.screen_base, self.screen_base + 0x03E7)

    def screen(self) -> list[str]:
        return decode_screen(self.screen_codes())

    def wait_for_screen(self, needles: tuple[str, ...], timeout: float) -> list[str]:
        assert self.monitor is not None
        deadline = time.monotonic() + timeout
        last: list[str] = []
        while time.monotonic() < deadline:
            last = self.screen()
            self.monitor.resume()
            joined = "\n".join(last).lower()
            if all(needle in joined for needle in needles):
                return last
            time.sleep(0.01)
        raise TimeoutError(
            f"timed out waiting for {', '.join(needles)}; screen was:\n"
            + "\n".join(last)
        )

    def snapshot(self, name: str) -> Path:
        assert self.monitor is not None
        width, height, pixels, _ = self.monitor.display()
        palette = self.monitor.palette()
        path = self.args.shot_dir / f"{self.shot_prefix}-{name}.png"
        write_png(path, width, height, pixels, palette)
        self.screenshots.append(str(path))
        return path


def check_registers(
    session: Session,
    report: Report,
    phase: str,
    expected_d018: int | None = None,
) -> None:
    monitor = session.monitor
    assert monitor is not None
    cia2 = monitor.memory_paused(0xDD00, 0xDD00)[0]
    vic = monitor.memory_paused(0xD000, 0xD02F)
    hibase = monitor.memory_paused(0x0288, 0x0288)[0]
    d018 = vic[0x18]
    expected_d018 = (
        session.args.patch_d018
        if session.args.patch_d018 is not None
        else (expected_d018 if expected_d018 is not None else session.args.expect_d018)
    )
    report.equal(f"{phase}.cia2_dd00_bank_bits", cia2 & 0x03, 0x01)
    # $D018 bit 0 is unused and always reads back as 1. Compare defined bits.
    report.equal(f"{phase}.d018_defined_bits", d018 & 0xFE, expected_d018 & 0xFE)
    report.equal(f"{phase}.hibase", hibase, session.screen_base >> 8)
    addresses = vic_addresses(cia2, d018)
    report.equal(
        f"{phase}.vic_screen_matrix_address",
        addresses["screen_matrix"],
        session.screen_base,
    )
    report.equal(
        f"{phase}.vic_sprite_pointer_address",
        addresses["screen_matrix"] + 0x03F8,
        session.pointer_base,
    )
    report.facts.setdefault("registers", {})[phase] = {
        "cia2_dd00": f"${cia2:02X}",
        "vic_bank": f"${addresses['vic_bank']:04X}",
        "d018": f"${d018:02X}",
        "screen_matrix": f"${addresses['screen_matrix']:04X}",
        "char_base": f"${addresses['char_base']:04X}",
        "char_base_source": (
            "character ROM image" if addresses["char_rom_image"] else "RAM"
        ),
        "hibase": f"${hibase:02X}",
        "d011": f"${vic[0x11]:02X}",
        "d015": f"${vic[0x15]:02X}",
    }


def vic_addresses(cia2: int, d018: int) -> dict[str, Any]:
    """Resolve the VIC bank, screen matrix and character base the VIC sees."""
    vic_bank = (~cia2 & 0x03) * 0x4000
    char_base = vic_bank + ((d018 >> 1) & 0x07) * 0x0800
    return {
        "vic_bank": vic_bank,
        "screen_matrix": vic_bank + ((d018 >> 4) & 0x0F) * 0x0400,
        "char_base": char_base,
        # The character ROM appears to the VIC at $1000-$1FFF of banks 0 and 2.
        "char_rom_image": vic_bank in (0x0000, 0x8000)
        and 0x1000 <= char_base - vic_bank < 0x2000,
    }


def check_character_source(session: Session, report: Report) -> None:
    """A correct display needs glyph data at the selected character base."""
    monitor = session.monitor
    assert monitor is not None
    cia2 = monitor.memory_paused(0xDD00, 0xDD00)[0]
    d018 = monitor.memory_paused(0xD018, 0xD018)[0]
    addresses = vic_addresses(cia2, d018)
    char_base = addresses["char_base"]
    rom_image = addresses["char_rom_image"]
    glyphs = monitor.memory_paused(char_base, char_base + 0x07FF, session.ram)
    nonzero = sum(1 for byte in glyphs if byte)
    report.facts["character_data"] = {
        "char_base": f"${char_base:04X}",
        "is_rom_image": rom_image,
        "nonzero_bytes_in_2k": nonzero,
    }
    report.check(
        "display.character_data_present_at_char_base",
        rom_image or nonzero > 0,
        f"${char_base:04X} is {'the character ROM image' if rom_image else 'RAM'}; "
        f"the RAM there holds {nonzero} non-zero bytes of 2048",
        "character ROM image, or RAM holding a character set",
    )


def check_flag_layover_rendered(session: Session, report: Report) -> None:
    """Sample the pennant on screen and prove both layover colours are painted.

    Register reads alone cannot prove this: sprite 5's power-on colour is blue,
    so a field colour written to the wrong register still reads back as intended
    and renders in the intended hue by coincidence.

    The window is the sprite box grown by a margin rather than the exact box,
    because the offset between $D000 coordinates and VICE's reported display
    origin is not worth pinning here; only pixels of the two layover colours are
    counted, and neither appears elsewhere near the pad. The Earth decoration
    shares this palette but sits high in the sky, far outside the window.
    """
    monitor = session.monitor
    assert monitor is not None
    vic = monitor.memory_paused(0xD000, 0xD017)
    flag_x = vic[FLAG_POINTER_INDEX * 2] + (256 if vic[0x10] & 0x10 else 0)
    flag_y = vic[FLAG_POINTER_INDEX * 2 + 1]
    width, _, pixels, geometry = monitor.display()
    margin = 8
    left = max(geometry["x_offset"], geometry["x_offset"] + flag_x - 24 - margin)
    right = min(
        geometry["x_offset"] + geometry["width"],
        geometry["x_offset"] + flag_x - 24 + 24 + margin,
    )
    top = max(geometry["y_offset"], geometry["y_offset"] + flag_y - 50 - margin)
    bottom = min(
        geometry["y_offset"] + geometry["height"],
        geometry["y_offset"] + flag_y - 50 + PENNANT_ROWS + margin,
    )
    counts: dict[int, int] = {}
    longest_field_run = 0
    for row in range(top, bottom):
        base = row * width
        run = 0
        for col in range(left, right):
            value = pixels[base + col]
            counts[value] = counts.get(value, 0) + 1
            run = run + 1 if value == FIELD_SPRITE_COLOR else 0
            longest_field_run = max(longest_field_run, run)
    field = counts.get(FIELD_SPRITE_COLOR, 0)
    outline = counts.get(FLAG_SPRITE_COLOR, 0)
    report.facts["flag_layover_pixels"] = {
        "flag_x": flag_x,
        "flag_y": flag_y,
        "sampled": sum(counts.values()),
        "longest_field_run": longest_field_run,
        "colour_counts": {str(key): counts[key] for key in sorted(counts)},
    }
    # A solid field leaves runs the width of the pennant; a field that had been
    # drawn as an outline, or lost behind the front sprite, could not.
    report.check(
        "flight.flag_layover_rendered_in_two_colours",
        field >= 120 and outline >= 60 and longest_field_run >= 8,
        {
            "field_pixels": field,
            "outline_pixels": outline,
            "longest_field_run": longest_field_run,
        },
        f"at least 120 pixels of field colour {FIELD_SPRITE_COLOR} in runs of 8 or "
        f"more, and at least 60 pixels of front colour {FLAG_SPRITE_COLOR}",
    )


def check_rendered_pixels(session: Session, report: Report, phase: str) -> None:
    monitor = session.monitor
    assert monitor is not None
    width, _, pixels, geometry = monitor.display()
    # Sample only VICE's inner screen, inset from its edges, so border pixels
    # cannot mask an entirely unrendered character matrix.
    inset = 4
    left = geometry["x_offset"] + inset
    top = geometry["y_offset"] + inset
    span = geometry["width"] - 2 * inset
    inner = bytearray()
    for row in range(top, top + geometry["height"] - 2 * inset):
        base = row * width + left
        inner.extend(pixels[base : base + span])
    distinct = sorted(set(inner))
    report.facts.setdefault("rendered_pixels", {})[phase] = {
        "inner_screen": geometry,
        "distinct_inner_colors": distinct,
        "inner_pixels": len(inner),
    }
    report.check(
        f"{phase}.inner_screen_not_blank",
        len(distinct) > 1,
        f"{len(distinct)} distinct colour(s) {distinct} across "
        f"{len(inner)} pixels of the {geometry['width']}x{geometry['height']} "
        "inner screen",
        "more than one colour inside the 40x25 character area",
    )


def music_irq_installed(session: Session) -> tuple[bool, str]:
    assert session.monitor is not None
    raw = session.monitor.memory_paused(0x0314, 0x0315)
    vector = raw[0] | raw[1] << 8
    return MUSIC_START <= vector < MUSIC_END, f"${vector:04X}"


def check_title(session: Session, report: Report) -> None:
    screen = session.wait_for_screen(TITLE_NEEDLES, session.args.startup_timeout)
    if session.args.patch_d018 is not None:
        # Diagnostic only: prove which behaviour depends on the character base
        # without modifying the tracked source.
        assert session.monitor is not None
        session.monitor.set_memory(0xD018, bytes([session.args.patch_d018]))
        session.monitor.resume()
        time.sleep(0.5)
        report.facts["patched_d018"] = f"${session.args.patch_d018:02X}"
        report.note(
            f"$D018 was patched to ${session.args.patch_d018:02X} at runtime; "
            "results below do not describe the unmodified artifact."
        )
    joined = "\n".join(screen).lower()
    for needle in TITLE_NEEDLES:
        report.check(
            f"title.'{needle}'_in_screen_at_${session.screen_base:04X}",
            needle in joined,
            [line for line in screen if line.strip()],
            needle,
        )
    installed, vector = music_irq_installed(session)
    report.check(
        "title.music_irq_installed",
        installed,
        {"irq_vector": vector},
        f"$0314 inside the music player ${MUSIC_START:04X}-${MUSIC_END - 1:04X}",
    )
    check_registers(session, report, "title", TITLE_D018)
    check_character_source(session, report)
    assert session.monitor is not None
    title_pointers = list(
        session.monitor.memory_paused(session.pointer_base, session.pointer_base + 7)
    )
    title_enable = session.monitor.memory_paused(0xD015, 0xD015)[0]
    title_memsiz_raw = session.monitor.memory_paused(0x37, 0x38)
    title_memsiz = title_memsiz_raw[0] | title_memsiz_raw[1] << 8
    report.equal("title.tableau_sprite_pointers", title_pointers, TITLE_SPRITE_POINTERS)
    report.equal("title.memsiz_clear_of_sprite_pointers", title_memsiz, FLIGHT_MEMSIZ)
    report.check(
        "title.tableau_sprites_enabled",
        title_enable in (COAST_ENABLE, THRUST_ENABLE),
        f"$D015=${title_enable:02X}",
        f"title tableau keeps sprites 0-5 and 7 active, with sprite 6 pulsing ({COAST_ENABLE} or {THRUST_ENABLE})",
    )
    check_rendered_pixels(session, report, "title")
    session.snapshot("title")
    report.facts["title_screen"] = [line for line in screen if line.strip()]


def trigger_attract(session: Session) -> list[str]:
    """Advance the live title jiffy beyond its 20-second idle deadline."""
    monitor = session.monitor
    assert monitor is not None
    # The title text becomes visible just before line 1074 captures t0. Move
    # beyond that one-time assignment before changing the clock.
    monitor.advance_instructions(10000)
    raw = monitor.memory_paused(0x00A0, 0x00A2)
    current = raw[0] << 16 | raw[1] << 8 | raw[2]
    target = (current + 1201) % 5184000
    monitor.set_memory(
        0x00A0,
        bytes(((target >> 16) & 0xFF, (target >> 8) & 0xFF, target & 0xFF)),
    )
    monitor.resume()
    return session.wait_for_screen((*FLIGHT_NEEDLES, ATTRACT_NEEDLE), 30.0)


def sprites_enabled(session: Session) -> int:
    """Read $D015 at this instant, then let the emulator run on."""
    monitor = session.monitor
    assert monitor is not None
    mask = monitor.memory_paused(0xD015, 0xD015)[0]
    monitor.resume()
    return mask


def status_values(screen: list[str]) -> tuple[int | None, int | None, int | None]:
    text = "\n".join(screen).lower()
    high = re.search(r"\bhi\s*(-?\d+)", text)
    score = re.search(r"\bscore\s*(-?\d+)", text)
    lems = re.search(r"(-?\d+)\s+lems\b", text)
    return (
        int(high.group(1)) if high else None,
        int(score.group(1)) if score else None,
        int(lems.group(1)) if lems else None,
    )


def check_attract(args: argparse.Namespace, report: Report) -> None:
    """Trigger demo mode deterministically and observe its real flight outcomes."""
    session = Session(
        args,
        shot_prefix=f"{args.shot_prefix}-attract",
        control_port_io=True,
    )
    monitor = session.monitor
    assert monitor is not None
    starts: list[dict[str, int]] = []
    successes = 0
    explosions = 0
    bonus_seen = False
    highs: set[int] = set()
    title_sprites: dict[str, int] = {}
    title_memsizes: dict[str, int] = {}
    try:
        monitor.set_joyport(1, 0x1F)
        session.wait_for_screen(TITLE_NEEDLES, args.startup_timeout)

        keyboard_demo = trigger_attract(session)
        keyboard_text = "\n".join(keyboard_demo).lower()
        monitor.inject_paused(CURSOR_RIGHT)
        keyboard_exit = session.wait_for_screen(TITLE_NEEDLES, 20.0)
        raw = monitor.memory_paused(0x37, 0x38)
        title_memsizes["keyboard_exit"] = raw[0] | raw[1] << 8
        monitor.resume()
        title_sprites["keyboard_exit"] = sprites_enabled(session)

        joystick_demo = trigger_attract(session)
        joystick_text = "\n".join(joystick_demo).lower()
        monitor.set_joyport(1, 0x17)
        joystick_exit = session.wait_for_screen(TITLE_NEEDLES, 20.0)
        raw = monitor.memory_paused(0x37, 0x38)
        title_memsizes["joystick_exit"] = raw[0] | raw[1] << 8
        monitor.resume()
        title_sprites["joystick_exit"] = sprites_enabled(session)
        monitor.set_joyport(1, 0x1F)

        flight = trigger_attract(session)
        session.snapshot("flight")
        demo_music_installed, demo_vector = music_irq_installed(session)
        high, score, lems = status_values(flight)
        if high is not None:
            highs.add(high)
        previous_score = score if score is not None else 0
        vic = monitor.memory_paused(0xD000, 0xD02F)
        x = vic[0] + (256 if vic[0x10] & 1 else 0)
        starts.append({"x": x, "score": previous_score, "lems": lems or 0})
        previous_y = vic[1]
        attempt_exploded = False

        # The bank-2 screen matrix sits inside the string heap's descent path,
        # and BASIC's own collector cannot rescue it: STREND lies below the
        # music player, so the heap would cross the screen, the RNG buffer and
        # the player before an automatic collection ever triggered. Line 840
        # therefore forces one collection per round. Seed FRETOP next to the
        # screen and require the demo to haul it back.
        heap_seed = session.screen_base + 0x0500
        zp = monitor.memory_paused(0x33, 0x38)
        memsiz = zp[4] | zp[5] << 8
        monitor.set_memory(0x33, bytes((heap_seed & 0xFF, heap_seed >> 8)))
        monitor.resume()
        heap_low = heap_seed
        heap_high = heap_seed

        deadline = time.monotonic() + args.attract_timeout
        # Observe four complete approaches: the demo deliberately centres the
        # first three and aims outside the pad on the fourth. Reaching a fifth
        # spawn proves that fourth approach completed.
        while time.monotonic() < deadline and (successes < 2 or len(starts) < 5):
            screen = session.screen()
            vic = monitor.memory_paused(0xD000, 0xD02F)
            heap = monitor.memory_paused(0x33, 0x34)
            monitor.resume()
            fretop = heap[0] | heap[1] << 8
            heap_low = min(heap_low, fretop)
            heap_high = max(heap_high, fretop)
            high, score, lems = status_values(screen)
            if high is not None:
                highs.add(high)
            bonus_seen = bonus_seen or any("bonus" in line for line in screen)
            if vic[0x15] == 252 and not attempt_exploded:
                attempt_exploded = True
                explosions += 1
            y = vic[1]
            player_pointer = monitor.memory_paused(
                session.pointer_base, session.pointer_base
            )[0]
            if (
                y <= 35
                and previous_y > 40
                and vic[0x15] in (COAST_ENABLE, THRUST_ENABLE)
                and 187 <= player_pointer <= 194
                and ATTRACT_NEEDLE in "\n".join(screen)
            ):
                x = vic[0] + (256 if vic[0x10] & 1 else 0)
                if x == starts[-1]["x"]:
                    previous_y = y
                    time.sleep(0.005)
                    continue
                current_score = score if score is not None else previous_score
                if not attempt_exploded and current_score > previous_score:
                    successes += 1
                starts.append(
                    {"x": x, "score": current_score, "lems": lems or 0}
                )
                previous_score = current_score
                attempt_exploded = False
            previous_y = y
            time.sleep(0.005)

        session.snapshot("outcome")
        monitor.inject_paused(CURSOR_RIGHT)
        final_title = session.wait_for_screen(TITLE_NEEDLES, 20.0)
        raw = monitor.memory_paused(0x37, 0x38)
        title_memsizes["final_exit"] = raw[0] | raw[1] << 8
        monitor.resume()
        title_sprites["final_exit"] = sprites_enabled(session)
        monitor.inject_paused(F7)
        monitor.stop_on_store(0xD000)
        reentry_flight = session.wait_for_screen(FLIGHT_NEEDLES, 20.0)

        keyboard_exit_text = "\n".join(keyboard_exit).lower()
        joystick_exit_text = "\n".join(joystick_exit).lower()
        final_title_text = "\n".join(final_title).lower()
        report.check(
            "attract.jiffy_timeout_starts_demo",
            ATTRACT_NEEDLE in keyboard_text,
            [line for line in keyboard_demo if line.strip()],
            "flight HUD marked 'attract' after a controlled +1201-jiffy advance",
        )
        report.check(
            "attract.keyboard_input_returns_to_title",
            all(needle in keyboard_exit_text for needle in TITLE_NEEDLES),
            [line for line in keyboard_exit if line.strip()],
            list(TITLE_NEEDLES),
        )
        report.check(
            "attract.joystick_input_returns_to_title",
            ATTRACT_NEEDLE in joystick_text
            and all(needle in joystick_exit_text for needle in TITLE_NEEDLES),
            [line for line in joystick_exit if line.strip()],
            list(TITLE_NEEDLES),
        )
        report.check(
            "attract.normal_spawn_sequence_across_attempts",
            len(starts) >= 3 and len({entry["x"] for entry in starts[:3]}) >= 3,
            starts,
            "at least three attempts entering from distinct normal player spawns",
        )
        report.check(
            "attract.repeatable_successful_landings",
            successes >= 2,
            {"successful_landings": successes, "explosions": explosions, "starts": starts},
            "at least two score-advancing flights without an explosion",
        )
        report.check(
            "attract.fourth_approach_demonstrates_failure",
            len(starts) >= 5 and explosions >= 1,
            {"explosions": explosions, "starts": starts},
            "four completed approaches with at least one explosion from the "
            "deliberately off-pad fourth target",
        )
        report.check(
            "attract.lands_on_the_bonus_bullseye",
            bonus_seen,
            {"bonus_message_seen": bonus_seen, "starts": starts},
            "a centre-bonus message during the demo, proving the autopilot "
            "aims at the middle of the pad rather than its edge",
        )
        report.check(
            "attract.music_irq_uninstalled",
            not demo_music_installed,
            {"irq_vector": demo_vector},
            "$0314 restored to the KERNAL handler once the demo flies",
        )
        report.equal("attract.demo_never_updates_high_score", sorted(highs), [0])
        report.check(
            "strings.heap_reclaimed_between_rounds",
            heap_high >= memsiz - 0x0100,
            f"FRETOP seeded ${heap_seed:04X}, recovered to ${heap_high:04X}, "
            f"MEMSIZ ${memsiz:04X}",
            "a round returns the string heap to within 256 bytes of MEMSIZ",
        )
        report.check(
            "strings.heap_clear_of_screen_matrix",
            heap_low > session.screen_base + 0x03FF,
            f"lowest FRETOP ${heap_low:04X}, screen matrix "
            f"${session.screen_base:04X}-${session.screen_base + 0x03FF:04X}",
            "string allocations never descend into the screen matrix",
        )
        report.check(
            "attract.final_input_exit_returns_to_title",
            all(needle in final_title_text for needle in TITLE_NEEDLES),
            [line for line in final_title if line.strip()],
            list(TITLE_NEEDLES),
        )
        report.equal(
            "title.reentry_uses_normal_memsiz",
            title_memsizes,
            {name: FLIGHT_MEMSIZ for name in title_memsizes},
        )
        report.check(
            "title.reentry_f7_starts_flight",
            all(needle in "\n".join(reentry_flight).lower() for needle in FLIGHT_NEEDLES),
            [line for line in reentry_flight if line.strip()],
            "F7 from an attract-returned title reaches the flight HUD",
        )
        # The title deliberately reclaims all eight sprites for its animated
        # tableau.  A title re-entered from flight must establish that mask,
        # rather than inheriting a frozen flight or explosion mask.
        report.check(
            "title.tableau_reestablished_after_flight",
            all(mask in (COAST_ENABLE, THRUST_ENABLE) for mask in title_sprites.values()),
            {name: f"${mask:02X}" for name, mask in title_sprites.items()},
            f"$D015={COAST_ENABLE} or {THRUST_ENABLE} on every title re-entry",
        )
        report.facts["attract"] = {
            "starts": starts,
            "successful_landings": successes,
            "explosions": explosions,
            "centre_bonus_seen": bonus_seen,
            "high_scores_seen": sorted(highs),
            "title_sprite_masks": {
                name: f"${mask:02X}" for name, mask in title_sprites.items()
            },
            "title_reentry_memsizes": {
                name: f"${memsiz:04X}" for name, memsiz in title_memsizes.items()
            },
            "string_heap": {
                "seeded_fretop": f"${heap_seed:04X}",
                "lowest_fretop": f"${heap_low:04X}",
                "highest_fretop": f"${heap_high:04X}",
                "memsiz": f"${memsiz:04X}",
            },
        }
    finally:
        monitor.set_joyport(1, 0x1F)
        session.close()
    report.screenshots.extend(session.screenshots)


def check_flight(session: Session, report: Report) -> None:
    monitor = session.monitor
    assert monitor is not None
    monitor.inject_paused(F7)
    monitor.stop_on_store(0xD000)
    screen = session.wait_for_screen(FLIGHT_NEEDLES, 20.0)
    installed, vector = music_irq_installed(session)
    report.check(
        "flight.music_irq_uninstalled",
        not installed,
        {"irq_vector": vector},
        "$0314 restored to the KERNAL handler, so the title tune is silent",
    )
    check_registers(session, report, "flight")
    pointers = list(monitor.memory_paused(session.pointer_base, session.pointer_base + 7))
    report.facts["flight_pointers"] = pointers
    lander_pointer = pointers[0]
    expected_fill = (
        lander_pointer + 59 if lander_pointer <= 189 else lander_pointer + 56
    )
    report.check(
        f"flight.player_pointers_at_${session.pointer_base:04X}",
        lander_pointer in range(187, 195)
        and pointers[LEM_FILL_POINTER_INDEX] == expected_fill
        and pointers[EXHAUST_POINTER_INDEX] == lander_pointer + 8,
        {
            "lander": lander_pointer,
            "fill": pointers[LEM_FILL_POINTER_INDEX],
            "exhaust": pointers[EXHAUST_POINTER_INDEX],
        },
        "187-194 lander shape, its attitude-matched fill and thrust companion",
    )
    for index, expected in FLIGHT_POINTERS.items():
        report.equal(
            f"flight.pointer[{index}]_at_${session.pointer_base + index:04X}",
            pointers[index],
            expected,
        )
    report.equal(
        f"flight.flag_pointer[{FLAG_POINTER_INDEX}]_at_"
        f"${session.pointer_base + FLAG_POINTER_INDEX:04X}",
        pointers[FLAG_POINTER_INDEX],
        FLAG_SLOT,
    )
    vic = monitor.memory_paused(0xD000, 0xD02F)
    enable = vic[0x15]
    report.check(
        "flight.lander_fill_registered_behind_outline",
        bool(enable & (1 << LEM_FILL_POINTER_INDEX))
        and pointers[LEM_FILL_POINTER_INDEX] in LEM_FILL_SLOTS
        and vic[2] == vic[0]
        and vic[3] == vic[1]
        and vic[0x28] & 0x0F == LEM_FILL_SPRITE_COLOR,
        {
            "d015": enable,
            "pointer": pointers[LEM_FILL_POINTER_INDEX],
            "outline_xy": [vic[0], vic[1]],
            "fill_xy": [vic[2], vic[3]],
            "colour": vic[0x28] & 0x0F,
        },
        "black sprite 1 fill enabled at the lander outline's coordinates",
    )
    report.check(
        "flight.flag_sprite_enabled",
        bool(enable & 0x10) and enable in (COAST_ENABLE, THRUST_ENABLE),
        {"d015": enable, "flag_bit": bool(enable & 0x10)},
        f"$D015 bit 4 set (coast {COAST_ENABLE} or thrust {THRUST_ENABLE})",
    )
    report.equal("flight.flag_sprite_colour_$D02B", vic[0x2B] & 0x0F, FLAG_SPRITE_COLOR)
    report.check(
        "flight.flag_sprite_not_y_expanded",
        not vic[0x17] & 0x10,
        {"d017": vic[0x17]},
        "$D017 bit 4 clear (sprite 4 unexpanded)",
    )
    flag_x = vic[FLAG_POINTER_INDEX * 2] + (256 if vic[0x10] & 0x10 else 0)
    flag_y = vic[FLAG_POINTER_INDEX * 2 + 1]
    report.facts["flag_sprite"] = {
        "pointer": pointers[FLAG_POINTER_INDEX],
        "x": flag_x,
        "y": flag_y,
        "colour": vic[0x2B] & 0x0F,
        "d015": enable,
        "d017": vic[0x17],
    }

    # The pennant field only reads as a layover while it tracks the flag exactly:
    # same X including the $D010 bit, same Y, and enabled behind it.
    field_x = vic[FIELD_POINTER_INDEX * 2] + (256 if vic[0x10] & 0x20 else 0)
    field_y = vic[FIELD_POINTER_INDEX * 2 + 1]
    report.check(
        "flight.field_sprite_enabled",
        bool(enable & 0x20),
        {"d015": enable, "field_bit": bool(enable & 0x20)},
        f"$D015 bit 5 set (coast {COAST_ENABLE} or thrust {THRUST_ENABLE})",
    )
    report.equal("flight.field_sprite_colour_$D02C", vic[0x2C] & 0x0F, FIELD_SPRITE_COLOR)
    report.check(
        "flight.field_sprite_registered_with_flag",
        (field_x, field_y) == (flag_x, flag_y) and not vic[0x17] & 0x20,
        {"field": [field_x, field_y], "flag": [flag_x, flag_y], "d017": vic[0x17]},
        "field X/Y equal to the flag's and sprite 5 unexpanded",
    )
    report.facts["field_sprite"] = {
        "pointer": pointers[FIELD_POINTER_INDEX],
        "x": field_x,
        "y": field_y,
        "colour": vic[0x2C] & 0x0F,
    }

    report.equal(
        "flight.module_sprite_colour_$D02E",
        vic[0x2E] & 0x0F,
        MODULE_SPRITE_COLOR,
    )
    report.equal(
        "flight.module_sprite_y_$D00F",
        vic[MODULE_POINTER_INDEX * 2 + 1],
        MODULE_SPRITE_Y,
    )
    # The lander crossing x=255 rewrites the whole of $D010, so the module can
    # only hold station if its MSB bit is never set. Line 1198 keeps bit 7 out
    # of the right-half mask for exactly this reason.
    report.check(
        "flight.module_x_msb_clear",
        not vic[0x10] & 0x80,
        {"d010": vic[0x10], "module_x": vic[MODULE_POINTER_INDEX * 2]},
        "$D010 bit 7 clear, so sprite 7 keeps a sub-256 X",
    )
    report.facts["module_sprite"] = {
        "pointer": pointers[MODULE_POINTER_INDEX],
        "x": vic[MODULE_POINTER_INDEX * 2],
        "y": vic[MODULE_POINTER_INDEX * 2 + 1],
        "colour": vic[0x2E] & 0x0F,
    }

    colors = list(monitor.memory_paused(0xD800, 0xDBE7))
    # Terrain is drawn with reverse-video spaces, which decode to blanks, so
    # measure the raw screen codes instead of the decoded text.
    codes = session.screen_codes()
    terrain = [
        row
        for row in range(12, 24)
        if any(code not in (0, 32) for code in codes[row * 40 : row * 40 + 40])
    ]
    report.check(
        "flight.procedural_terrain_rows_present",
        len(terrain) >= 8,
        terrain,
        "at least 8 rows from row 12 down holding non-space screen codes",
    )

    # Pads are the RNG-placed runs of the pad-surface tile (100). Their exact
    # columns vary per game, so group contiguous runs and prove each carries the
    # green body colour with grey edge cells.
    pads: list[dict[str, Any]] = []
    for row in range(12, 25):
        col = 0
        while col < 40:
            offset = row * 40 + col
            if codes[offset] == PAD_SURFACE_TILE:
                start = col
                while col < 40 and codes[row * 40 + col] == PAD_SURFACE_TILE:
                    col += 1
                cells = [colors[row * 40 + c] & 0x0F for c in range(start, col)]
                pads.append(
                    {
                        "row": row,
                        "cols": [start, col - 1],
                        "width": col - start,
                        "colours": cells,
                        "edges": [cells[0], cells[-1]],
                    }
                )
            else:
                col += 1
    report.facts["landing_pads"] = pads
    well_formed = [
        pad
        for pad in pads
        if PAD_BODY_COLOR in pad["colours"]
        and pad["edges"] == [PAD_EDGE_COLOR, PAD_EDGE_COLOR]
        and pad["width"] == 4
    ]
    report.check(
        "flight.landing_pads_rendered",
        3 <= len(pads) <= 5,
        {"pad_runs": len(pads), "rows": sorted({pad["row"] for pad in pads})},
        "3-5 pad-surface runs (screen code 100) across the terrain",
    )
    report.check(
        "flight.landing_pad_colour_pattern",
        len(well_formed) >= 3,
        {
            "well_formed": len(well_formed),
            "sample": well_formed[0] if well_formed else None,
        },
        "at least 3 four-cell pads with a green (5) body flanked by grey (7) edges",
    )
    report.check(
        "flight.hud_row_present",
        any("lems" in line for line in screen),
        [line for line in screen if "lems" in line],
        "status row containing 'lems'",
    )
    check_flag_layover_rendered(session, report)
    check_rendered_pixels(session, report, "flight")
    session.snapshot("flight")
    report.facts["flight_screen"] = [line for line in screen if line.strip()]


def check_sprite_data(session: Session, report: Report) -> None:
    monitor = session.monitor
    assert monitor is not None
    sprite_addr, sprites = load_prg(session.args.sprite_prg)
    end = sprite_addr + len(sprites) - 1
    resident = bytearray()
    cursor = sprite_addr
    while cursor <= end:
        chunk_end = min(cursor + 0x0FFF, end)
        resident.extend(monitor.memory_paused(cursor, chunk_end, session.ram))
        cursor = chunk_end + 1
    mismatch = [
        f"${sprite_addr + index:04X}"
        for index, (seen, expected) in enumerate(zip(resident, sprites))
        if seen != expected
    ]
    report.check(
        f"runtime.sprite_data_resident_at_${sprite_addr:04X}",
        not mismatch and len(resident) == len(sprites),
        f"{len(resident)} bytes read, {len(mismatch)} mismatches {mismatch[:4]}",
        f"{len(sprites)} bytes identical to {session.args.sprite_prg.name}",
    )
    bank_base = session.args.vic_bank * 0x4000
    blocks = {}
    for pointer in (187, 194, FLAG_SLOT, FIELD_SLOT, 253, 254):
        address = bank_base + pointer * 64
        offset = address - sprite_addr
        blocks[pointer] = f"${address:04X}"
        report.check(
            f"runtime.pointer_{pointer}_block_matches_file",
            0 <= offset and resident[offset : offset + 64] == sprites[offset : offset + 64],
            f"${address:04X} (file offset {offset})",
            "VIC-visible block equals relocated file content",
        )
    # The flag block must actually carry the patched shape (non-empty) at $BCC0.
    flag_address = bank_base + FLAG_SLOT * 64
    flag_offset = flag_address - sprite_addr
    flag_resident = resident[flag_offset : flag_offset + 64]
    report.check(
        f"runtime.flag_shape_resident_at_${flag_address:04X}",
        flag_address == 0xBCC0 and any(flag_resident),
        f"${flag_address:04X}, {sum(1 for b in flag_resident if b)} non-zero bytes",
        "the refuel flag shape is resident at $BCC0",
    )
    report.facts["pointer_block_addresses"] = blocks


def check_filler(session: Session, report: Report) -> None:
    if session.args.filler is None:
        return
    monitor = session.monitor
    assert monitor is not None
    start, end, value = session.args.filler
    resident = bytearray()
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + 0x0FFF, end)
        resident.extend(monitor.memory_paused(cursor, chunk_end, session.ram))
        cursor = chunk_end + 1
    # The procedural layer's DIM arrays and scalars live just above the compiled
    # PRG end, so BASIC's live data (up to STREND) legitimately overwrites the low
    # part of the filler. Prove the region above STREND -- the true code+data
    # growth headroom up to the music player -- is untouched filler, and report
    # how much BASIC's runtime claimed below it.
    zp = monitor.memory_paused(0x2D, 0x32)
    vartab = zp[0] | zp[1] << 8
    strend = zp[4] | zp[5] << 8
    free_start = max(start, strend)
    bad = [
        f"${start + index:04X}"
        for index, byte in enumerate(resident)
        if start + index >= free_start and byte != value
    ]
    basic_claim = max(0, min(end + 1, strend) - start)
    report.facts["capacity_filler"] = {
        "filler_range": f"${start:04X}-${end:04X}",
        "basic_vartab": f"${vartab:04X}",
        "basic_strend": f"${strend:04X}",
        "basic_claimed_bytes_in_range": basic_claim,
        "free_filler_range": f"${free_start:04X}-${end:04X}",
        "free_filler_bytes": max(0, end - free_start + 1),
    }
    report.check(
        "capacity.free_filler_intact_above_basic_data",
        not bad and end >= free_start,
        f"{max(0, end - free_start + 1)} bytes above STREND ${strend:04X}, "
        f"{len(bad)} altered {bad[:4]}; BASIC claimed {basic_claim} bytes "
        f"(${start:04X}-${strend - 1:04X})",
        f"filler from ${free_start:04X}-${end:04X} still 0x{value:02x}",
    )


def check_memory_pointers(session: Session, report: Report) -> None:
    monitor = session.monitor
    assert monitor is not None
    zp = monitor.memory_paused(0x2B, 0x38)
    pointers = {
        "TXTTAB": zp[0] | zp[1] << 8,
        "VARTAB": zp[2] | zp[3] << 8,
        "ARYTAB": zp[4] | zp[5] << 8,
        "STREND": zp[6] | zp[7] << 8,
        "FRETOP": zp[8] | zp[9] << 8,
        "MEMSIZ": zp[12] | zp[13] << 8,
    }
    report.facts["basic_pointers"] = {
        name: f"${value:04X}" for name, value in pointers.items()
    }
    sprite_addr, sprites = load_prg(session.args.sprite_prg)
    report.check(
        "capacity.string_space_below_relocated_sprites",
        pointers["MEMSIZ"] <= sprite_addr,
        f"MEMSIZ ${pointers['MEMSIZ']:04X}, sprites ${sprite_addr:04X}",
        "BASIC never allocates into the relocated sprite region",
    )
    report.check(
        "capacity.array_space_above_code",
        pointers["STREND"] >= pointers["VARTAB"],
        f"VARTAB ${pointers['VARTAB']:04X}, STREND ${pointers['STREND']:04X}",
        "array/string end at or above the variable table",
    )


def check_pause(session: Session, report: Report) -> None:
    monitor = session.monitor
    assert monitor is not None
    monitor.inject_paused(F1)
    deadline = time.monotonic() + 15.0
    tile = color = None
    while time.monotonic() < deadline:
        tile = monitor.memory_paused(session.screen_base, session.screen_base)[0]
        color = monitor.memory_paused(0xD800, 0xD800)[0] & 0x0F
        monitor.resume()
        if tile == PAUSE_TILE and color == PAUSE_COLOR:
            break
        time.sleep(0.01)
    report.equal(f"pause.tile_at_${session.screen_base:04X}", tile, PAUSE_TILE)
    report.equal("pause.colour_at_$D800", color, PAUSE_COLOR)
    session.snapshot("pause")
    monitor.inject_paused(F1)
    deadline = time.monotonic() + 15.0
    while time.monotonic() < deadline:
        tile = monitor.memory_paused(session.screen_base, session.screen_base)[0]
        monitor.resume()
        if tile == UNPAUSED_TILE:
            break
        time.sleep(0.01)
    report.equal(f"pause.tile_restored_at_${session.screen_base:04X}", tile, UNPAUSED_TILE)


def check_controls(args: argparse.Namespace, report: Report) -> None:
    """Exercise joystick port 2 and both keyboard fallback paths."""
    session = Session(
        args,
        shot_prefix=f"{args.shot_prefix}-controls",
        control_port_io=True,
    )
    monitor = session.monitor
    assert monitor is not None

    def player_pointer() -> int:
        return monitor.memory_paused(session.pointer_base, session.pointer_base)[0]

    def next_player_pointer() -> int:
        monitor.stop_on_store(session.pointer_base)
        return player_pointer()

    try:
        session.wait_for_screen(TITLE_NEEDLES, args.startup_timeout)
        monitor.inject_paused(F7)
        monitor.stop_on_store(0xD000)
        session.wait_for_screen(FLIGHT_NEEDLES, 20.0)
        monitor.stop_on_store(session.pointer_base)
        monitor.set_joyport(1, 0x1F)
        initial = player_pointer()

        monitor.set_joyport(1, 0x17)
        joy_right = next_player_pointer()
        monitor.set_joyport(1, 0x1F)

        monitor.set_joyport(1, 0x1B)
        joy_left = next_player_pointer()
        monitor.set_joyport(1, 0x1F)

        monitor.set_joyport(1, 0x0F)
        # The left-direction checkpoint stopped at pointer 0. Resume through the
        # remaining change-only pointer writes and stop when fire updates $D015.
        monitor.stop_on_store(0xD015)
        joy_fire_pointers = list(
            monitor.memory_paused(
                session.pointer_base,
                session.pointer_base + EXHAUST_POINTER_INDEX,
            )
        )
        joy_fire_enabled = monitor.memory_paused(0xD015, 0xD015)[0]
        monitor.set_joyport(1, 0x1F)

        monitor.inject_paused(CURSOR_RIGHT)
        key_right = next_player_pointer()
        monitor.inject_paused(CURSOR_DOWN)
        key_down = next_player_pointer()

        key_fire_pointers = [0, 0]
        key_fire_enabled = 0
        for _ in range(4000):
            # PEEK(653) is the original modifier-key fallback. Reassert it
            # between bounded instruction runs so the KERNAL keyboard scan
            # cannot make this emulator-driven test timing-dependent.
            monitor.set_memory(653, b"\x01")
            monitor.advance_instructions(50)
            key_fire_pointers = list(
                monitor.memory_paused(
                    session.pointer_base,
                    session.pointer_base + EXHAUST_POINTER_INDEX,
                )
            )
            key_fire_enabled = monitor.memory_paused(0xD015, 0xD015)[0]
            if (
                key_fire_pointers[EXHAUST_POINTER_INDEX] - key_fire_pointers[0] == 8
                and key_fire_enabled == THRUST_ENABLE
            ):
                break
        monitor.set_memory(653, b"\0")

        monitor.inject_paused(F1)
        deadline = time.monotonic() + 15.0
        restart_pause_tile = None
        while time.monotonic() < deadline:
            restart_pause_tile = monitor.memory_paused(
                session.screen_base, session.screen_base
            )[0]
            monitor.resume()
            if restart_pause_tile == PAUSE_TILE:
                break
            time.sleep(0.01)
        monitor.inject_paused(F7)
        restarted = session.wait_for_screen(TITLE_NEEDLES, 20.0)
        restarted_text = "\n".join(restarted).lower()

        report.equal("controls.joystick2_right_rotates", joy_right, initial + 1)
        report.equal("controls.joystick2_left_rotates", joy_left, initial)
        report.check(
            "controls.joystick2_fire_thrusts",
            joy_fire_pointers[EXHAUST_POINTER_INDEX] - joy_fire_pointers[0] == 8
            and joy_fire_enabled == THRUST_ENABLE,
            {"pointers": joy_fire_pointers, "d015": joy_fire_enabled},
            f"sprite 6 exhaust pointer = player + 8 and $D015={THRUST_ENABLE}",
        )
        report.equal("controls.keyboard_right_fallback", key_right, initial + 1)
        report.equal("controls.keyboard_down_fallback", key_down, initial)
        report.check(
            "controls.keyboard_modifier_fallback_thrusts",
            key_fire_pointers[EXHAUST_POINTER_INDEX] - key_fire_pointers[0] == 8
            and key_fire_enabled == THRUST_ENABLE,
            {"pointers": key_fire_pointers, "d015": key_fire_enabled},
            f"PEEK(653) enables sprite 6 exhaust and $D015={THRUST_ENABLE}",
        )
        report.equal(
            f"controls.pause_tile_before_restart_at_${session.screen_base:04X}",
            restart_pause_tile,
            PAUSE_TILE,
        )
        report.check(
            "controls.f7_restart_returns_to_title",
            all(needle in restarted_text for needle in TITLE_NEEDLES),
            [line for line in restarted if line.strip()],
            list(TITLE_NEEDLES),
        )
        report.facts["controls"] = {
            "initial_pointer": initial,
            "joystick2_right_pointer": joy_right,
            "joystick2_left_pointer": joy_left,
            "joystick2_fire": {
                "pointers": joy_fire_pointers,
                "d015": joy_fire_enabled,
            },
            "keyboard_right_pointer": key_right,
            "keyboard_down_pointer": key_down,
            "keyboard_modifier_fire": {
                "pointers": key_fire_pointers,
                "d015": key_fire_enabled,
            },
            "restart_pause_tile": restart_pause_tile,
            "restart_title": [line for line in restarted if line.strip()],
        }
    finally:
        monitor.set_joyport(1, 0x1F)
        session.close()
    report.screenshots.extend(session.screenshots)


def descend_to_explosion(session: Session, timeout: float) -> dict[str, Any]:
    """Free-fall until the explosion starts, sampling collision and sprite state.

    The program clears $D01F by reading it once per input pass, so the latch is
    polled without side effects between those reads rather than reconstructed
    afterwards.
    """
    monitor = session.monitor
    assert monitor is not None
    deadline = time.monotonic() + timeout
    frames: list[list[int]] = []
    enabled_seen: set[int] = set()
    multicolor_seen: set[int] = set()
    latch_union = 0
    first_collision: dict[str, int] | None = None
    max_y = 0
    explosion_y: int | None = None
    while time.monotonic() < deadline:
        vic = monitor.memory_paused(0xD000, 0xD01F)
        pointers = list(
            monitor.memory_paused(session.pointer_base + 4, session.pointer_base + 7)
        )
        monitor.resume()
        latch = vic[0x1F]
        sprite_y = vic[0x01]
        latch_union |= latch
        max_y = max(max_y, sprite_y)
        if latch & 0x01 and first_collision is None:
            first_collision = {"latch": latch, "sprite_y": sprite_y}
        enabled_seen.add(vic[0x15])
        multicolor_seen.add(vic[0x1C])
        low, high = EXPLOSION_POINTER_RANGE
        if vic[0x15] == 252 and all(low <= pointer <= high for pointer in pointers):
            if explosion_y is None:
                explosion_y = sprite_y
            if not frames or frames[-1] != pointers:
                frames.append(pointers)
        if len({frame[0] for frame in frames}) >= 6:
            break
        time.sleep(0.005)
    return {
        "collision_latch_union": latch_union,
        "first_collision": first_collision,
        "max_sprite_y": max_y,
        "explosion_sprite_y": explosion_y,
        "explosion_pointer_frames": frames,
        "sprite_enable_values": sorted(enabled_seen),
        "sprite_multicolour_values": sorted(multicolor_seen),
    }


def check_collision_and_explosion(session: Session, report: Report) -> None:
    monitor = session.monitor
    assert monitor is not None
    observed = descend_to_explosion(session, session.args.explosion_timeout)
    frames = observed["explosion_pointer_frames"]
    report.facts["descent"] = {
        "collision_latch_union": f"${observed['collision_latch_union']:02X}",
        "first_collision": observed["first_collision"],
        "max_sprite_y": observed["max_sprite_y"],
        "explosion_sprite_y": observed["explosion_sprite_y"],
        "explosion_pointer_frames": frames,
        "sprite_enable_values": observed["sprite_enable_values"],
        # Line 480 ends flight on altitude alone; line 630 gates the landing
        # evaluation (and therefore the survivable outcome) on $D01F bit 0.
        "crash_path": (
            "collision-gated evaluation (line 630)"
            if observed["first_collision"]
            else "altitude limit (line 480, po>230)"
        ),
    }
    report.check(
        "crash.sprite_background_collision_latched",
        bool(observed["collision_latch_union"] & 0x01),
        f"$D01F union ${observed['collision_latch_union']:02X}, "
        f"max sprite y {observed['max_sprite_y']}",
        "bit 0 set while the lander overlaps terrain, as line 630 requires",
    )
    # Line 1390 POKEs the four pointers one at a time, so polled frames may be
    # torn; require the first pointer to advance and the settled frames to keep
    # the +10/+20/+30 relation the source writes.
    firsts = [frame[0] for frame in frames]
    settled = [
        frame
        for frame in frames
        if all(frame[index] == frame[0] + 10 * index for index in range(4))
    ]
    report.check(
        "crash.explosion_pointer_progression",
        len(set(firsts)) >= 4
        and firsts == sorted(firsts)
        and len(settled) >= 4,
        f"first pointers {firsts}, {len(settled)} settled frames of {len(frames)}",
        "non-decreasing pointers within 203-242 and at least 4 frames at "
        "ex/ex+10/ex+20/ex+30",
    )
    report.check(
        "crash.explosion_sprites_enabled",
        252 in observed["sprite_enable_values"],
        observed["sprite_enable_values"],
        "$D015=252 during the explosion",
    )
    report.check(
        "crash.explosion_multicolour_enabled",
        240 in observed["sprite_multicolour_values"],
        observed["sprite_multicolour_values"],
        "$D01C=240 during the explosion",
    )
    session.snapshot("explosion")

    deadline = time.monotonic() + session.args.explosion_timeout
    message_rows: list[str] = []
    cause_rows: list[str] = []
    consequence_rows: list[str] = []
    lems = None
    while time.monotonic() < deadline:
        screen = session.screen()
        monitor.resume()
        for line in screen:
            if "points" in line and line not in message_rows:
                message_rows.append(line)
            text = line.strip()
            if not text:
                continue
            if any(phrase in text for phrase in CRASH_CAUSES):
                if text not in cause_rows:
                    cause_rows.append(text)
            if any(phrase in text for phrase in CRASH_CONSEQUENCES):
                if text not in consequence_rows:
                    consequence_rows.append(text)
        for line in screen:
            match = re.search(r"(-?\d+)\s+lems", line)
            if match:
                lems = int(match.group(1))
        if message_rows and lems is not None and lems < 4:
            break
        time.sleep(0.01)
    report.facts["post_crash_message_rows"] = message_rows
    report.facts["crash_cause_rows"] = cause_rows
    report.facts["crash_consequence_rows"] = consequence_rows
    report.check(
        "crash.score_message_after_explosion",
        bool(message_rows),
        message_rows,
        "a 'points' message row",
    )
    report.check(
        "crash.post_mortem_single_message",
        bool(cause_rows) != bool(consequence_rows),
        {"cause": cause_rows, "consequence": consequence_rows},
        "exactly one post-mortem tier before the score message: either a cause "
        f"line from {CRASH_CAUSES} or one of the 13 DATA consequence lines, "
        "never both",
    )
    report.equal("crash.lems_decremented", lems, 3)


def collision_reference(args: argparse.Namespace, report: Report) -> None:
    """Fly the bank-0 fallback artifact so the latch check has a control run."""
    if args.reference_prg is None:
        return
    session = Session(
        args,
        prg=args.reference_prg,
        screen_base=args.reference_screen_base,
        pointer_base=args.reference_pointer_base,
        shot_prefix=f"{args.shot_prefix}-reference",
    )
    try:
        session.wait_for_screen(TITLE_NEEDLES, args.startup_timeout)
        assert session.monitor is not None
        session.monitor.inject_paused(F7)
        session.monitor.stop_on_store(0xD000)
        session.wait_for_screen(FLIGHT_NEEDLES, 20.0)
        observed = descend_to_explosion(session, args.explosion_timeout)
        session.snapshot("descent")
    finally:
        session.close()
    report.facts["collision_reference"] = {
        "artifact": str(args.reference_prg),
        "collision_latch_union": f"${observed['collision_latch_union']:02X}",
        "first_collision": observed["first_collision"],
        "max_sprite_y": observed["max_sprite_y"],
    }
    report.check(
        "reference.sprite_background_collision_latched",
        bool(observed["collision_latch_union"] & 0x01),
        f"$D01F union ${observed['collision_latch_union']:02X} on "
        f"{args.reference_prg.name}, first collision {observed['first_collision']}",
        "the same polling observes the latch on the bank-0 fallback artifact",
    )
    report.screenshots.extend(session.screenshots)


def address(value: str) -> int:
    parsed = int(value, 0)
    if not 0 <= parsed <= 0xFFFF:
        raise argparse.ArgumentTypeError("address must be between 0 and 0xffff")
    return parsed


def filler_spec(value: str) -> tuple[int, int, int]:
    parts = value.split(":")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("filler must be START:END:VALUE")
    start, end, byte = (int(part, 0) for part in parts)
    if not 0 <= start <= end <= 0xFFFF or not 0 <= byte <= 0xFF:
        raise argparse.ArgumentTypeError("filler range or value out of bounds")
    return start, end, byte


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prg", type=Path, required=True)
    parser.add_argument("--code-prg", type=Path, required=True)
    parser.add_argument("--sprite-prg", type=Path, required=True)
    parser.add_argument("--original-sprite-prg", type=Path, required=True)
    parser.add_argument(
        "--patched-sprite-prg",
        type=Path,
        help="shape-patched sprite PRG (pre-rebase) proving the relocated payload "
        "carries the refuel flag in slot 243, the command module in slot 244 and "
        "the flag's pennant field in slot 245",
    )
    parser.add_argument(
        "--rng-prg",
        type=Path,
        help="CPU-side RNG PRG expected at $4400-$4BFF",
    )
    parser.add_argument("--music-prg", type=Path)
    parser.add_argument(
        "--title-charset",
        type=Path,
        help="optional title-only RAM character set embedded at $8800",
    )
    parser.add_argument(
        "--canonical-source",
        type=Path,
        help="bank-0 fallback source used as the byte-identity control for the "
        "shared scoring lines",
    )
    parser.add_argument(
        "--bank2-source",
        type=Path,
        required=True,
        help="promoted canonical bank-2 source under verification",
    )
    parser.add_argument("--screen-base", type=address, default=0x8400)
    parser.add_argument("--pointer-base", type=address, default=0x87F8)
    parser.add_argument("--vic-bank", type=int, choices=(0, 1, 2, 3), default=2)
    parser.add_argument("--expect-d018", type=address, default=0x14)
    parser.add_argument(
        "--patch-d018",
        type=address,
        help="write $D018 once at the title screen to isolate character-base "
        "dependent behaviour; the source is not modified",
    )
    parser.add_argument("--filler", type=filler_spec)
    parser.add_argument(
        "--filler-report",
        type=Path,
        help="bank2-capacity.py report describing the filler range to verify",
    )
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--shot-dir", type=Path, default=Path("build"))
    parser.add_argument("--shot-prefix", default="bank2")
    parser.add_argument("--log", type=Path, default=Path("build/bank2-verify.log"))
    parser.add_argument("--vice", default="x64sc")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--startup-timeout", type=float, default=60.0)
    parser.add_argument("--explosion-timeout", type=float, default=90.0)
    parser.add_argument("--attract-timeout", type=float, default=300.0)
    parser.add_argument(
        "--reference-prg",
        type=Path,
        help="bank-0 fallback artifact flown as a control for the collision latch",
    )
    parser.add_argument("--reference-screen-base", type=address, default=0x0400)
    parser.add_argument("--reference-pointer-base", type=address, default=0x07F8)
    args = parser.parse_args()
    if args.filler_report is not None:
        filler = json.loads(args.filler_report.read_text())["filler"]
        args.filler = (filler["start"], filler["end"], filler["value"])
    return args


def run(args: argparse.Namespace) -> int:
    report = Report()
    static_layout(args, report)
    landing_logic(args, report)

    phases = (
        ("title", check_title),
        ("flight", check_flight),
        ("sprite_data", check_sprite_data),
        ("memory_pointers", check_memory_pointers),
        ("filler", check_filler),
        ("pause", check_pause),
        ("collision_explosion", check_collision_and_explosion),
    )
    session = Session(args)
    try:
        for name, phase in phases:
            print(f"phase: {name}", file=sys.stderr, flush=True)
            try:
                phase(session, report)
            except (ConnectionError, OSError, RuntimeError, TimeoutError) as error:
                report.check(
                    f"{name}.phase_completed",
                    False,
                    f"{type(error).__name__}: {error}",
                    "phase runs to completion",
                )
                traceback.print_exc()
                break
    finally:
        session.close()
    report.screenshots.extend(session.screenshots)
    if session.exit_shot.is_file():
        report.screenshots.append(str(session.exit_shot))

    print("phase: controls", file=sys.stderr, flush=True)
    try:
        check_controls(args, report)
    except (ConnectionError, OSError, RuntimeError, TimeoutError) as error:
        report.check(
            "controls.phase_completed",
            False,
            f"{type(error).__name__}: {error}",
            "phase runs to completion",
        )
        traceback.print_exc()

    print("phase: attract", file=sys.stderr, flush=True)
    try:
        check_attract(args, report)
    except (ConnectionError, OSError, RuntimeError, TimeoutError) as error:
        report.check(
            "attract.phase_completed",
            False,
            f"{type(error).__name__}: {error}",
            "phase runs to completion",
        )
        traceback.print_exc()

    print("phase: collision_reference", file=sys.stderr, flush=True)
    try:
        collision_reference(args, report)
    except (ConnectionError, OSError, RuntimeError, TimeoutError) as error:
        report.check(
            "collision_reference.phase_completed",
            False,
            f"{type(error).__name__}: {error}",
            "phase runs to completion",
        )
        traceback.print_exc()

    report.facts["screenshots"] = report.screenshots
    report.note(
        "Attract mode is entered by advancing the live title jiffy by 1201 ticks, "
        "not by waiting 20 wall-clock seconds. Its verification uses normal player "
        "spawn positions and score changes across complete attempts; no physics "
        "state, collision latch, landing verdict, oracle tolerance, or fixture is "
        "patched by the harness."
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(
            {
                "artifact": str(args.prg),
                "screen_base": f"0x{args.screen_base:04x}",
                "pointer_base": f"0x{args.pointer_base:04x}",
                "facts": report.facts,
                "checks": report.checks,
                "notes": report.notes,
            },
            indent=2,
        )
        + "\n"
    )

    width = max(len(entry["check"]) for entry in report.checks)
    for entry in report.checks:
        status = "pass" if entry["passed"] else "FAIL"
        print(f"{status} {entry['check']:<{width}}  observed: {entry['observed']}")
        if not entry["passed"]:
            print(f"{'':4} {'':<{width}}  expected: {entry['expected']}")
    print(f"\nreport: {args.report}")
    for shot in report.facts["screenshots"]:
        print(f"screenshot: {shot}")
    for note in report.notes:
        print(f"\nnote: {note}")
    failures = report.failures
    if failures:
        print(
            f"\nverify-bank2: {len(failures)} of {len(report.checks)} checks failed",
            file=sys.stderr,
        )
        return 1
    print(f"\nverify-bank2: {len(report.checks)} checks passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run(parse_args()))
    except (ConnectionError, OSError, RuntimeError, TimeoutError) as error:
        print(f"verify-bank2: {error}", file=sys.stderr)
        raise SystemExit(1)
