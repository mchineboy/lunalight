#!/usr/bin/env python3
"""Derive the native-C128 BASIC source from the canonical C64 source.

The C128 edition is a port, not a rewrite, and the physics and scoring
invariants say so explicitly. Keeping a hand-edited copy of a 250-line BASIC
program alongside the original is how those two silently drift apart, so the
C128 source is generated instead: this tool applies an explicit, auditable set
of substitutions to src/lunalight.bas and nothing else.

Every rule below is one measured difference from docs/c128-vic-design.md. After
applying them the output is scanned for any C64 constant that should no longer
be there, so a new POKE in the canonical source fails the build rather than
quietly producing a broken C128 edition.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# The whole VIC window moves from bank 2 to bank 0, and every screen, colour and
# sprite-pointer address in the source is a plain literal in this span.
SCREEN_LOW, SCREEN_HIGH, SCREEN_SHIFT = 33792, 34815, 32768

# Ordered textual rules. Each runs once over the whole program, before the
# uniform screen rebase, so none of the addresses introduced here get rebased.
RULES: list[tuple[str, str, str]] = [
    (
        "poke56576,(peek(56576)and252)or1:poke648,132:",
        "",
        "VIC bank 0 and screen $0400 are the C128 defaults; $DD00 needs no "
        "write and 648 carries nothing on the C128",
    ),
    (
        "poke55,0:poke56,160:",
        "",
        "MEMSIZ has no C128 meaning; BASIC 7 keeps variables, arrays and "
        "strings in RAM bank 1, so the string-heap guard has nothing to guard",
    ),
    (
        "poke53272,18",
        "poke2604,24:poke53272,24",
        "title charset moves from $8800 to $2000, and the editor's interrupt "
        "reloads $D018 from its shadow at $0A2C, so the shadow is the register "
        "that actually selects it",
    ),
    (
        "poke53272,20",
        "poke2604,20:poke53272,20",
        "flight uses the character ROM, and $14 happens to be the C128's own "
        "default, so this looked like it needed no change. It does: once the "
        "title has set the shadow to 24, the editor's interrupt drags $D018 "
        "back to the title charset and flight renders in the wrong font",
    ),
    ("poke214,", "poke235,", "the cursor row lives at $EB on the C128, not $D6"),
    (
        "poke679,",
        "poke6016,",
        "the wait argument moves from $02A7, which is not free low memory on "
        "the C128, to $1780 inside the helper window",
    ),
    ("sys16896", "sys4864", "title player install moves from $4200 to $1300"),
    ("sys16899", "sys4867", "title player uninstall"),
    ("sys17408", "sys5376", "RNG collect moves from $4400 to $1500"),
    ("sys17411", "sys5379", "RNG refill"),
    ("sys17420", "sys5388", "fixed jiffy wait"),
    ("peek(16902)", "peek(4870)", "published loop length, low byte"),
    ("peek(16903)", "peek(4871)", "published loop length, high byte"),
    (
        "bc=21504",
        "bc=54272",
        "colour-RAM bias: $D800 minus the screen base, which is $0400 here",
    ),
    ("rb=18432", "rb=6144", "RNG table moves from $4800 to $1800"),
    (
        "ifpeek(v+31)and1then",
        "ifbump(2)and1then",
        "BASIC 7 accumulates the sprite-background latch inside the KERNAL "
        "interrupt and clears $D01F, so PEEK would read zero; BUMP(2) is the "
        "value the latch actually reached",
    ),
    (
        "if(jvand16)=.orpeek(653)then",
        "gosub2140:if(jvand16)=.ormkthen",
        "653 is not a shift flag on the C128: it reads 255 with no key held, "
        "so the alternate fire would be permanently on",
    ),
    (
        'ifz$<>""or(jvand31)<>31orpeek(653)then',
        'gosub2140:ifz$<>""or(jvand31)<>31ormkthen',
        "same for the attract-mode any-key wake",
    ),
    (
        "ds=sgn(tg-hh):gosub900:ifrv<64thends=ds*2",
        "dz=sgn(tg-hh):gosub900:ifrv<64thendz=dz*2",
        "DS is a reserved system variable in BASIC 7 (disk status), so the "
        "terrain step direction has to be renamed; assigning to it is a syntax "
        "error, and the C64 has no such reservation",
    ),
    (
        "hh=hh+ds:ifhh<1thenhh=1",
        "hh=hh+dz:ifhh<1thenhh=1",
        "the other half of the DS rename",
    ),
]

# Variables BASIC 7 reserves that BASIC 2 does not. Assigning to one of these is
# a syntax error at run time, in a line that looks perfectly ordinary, and only
# on the line that happens to execute -- so it is worth failing the build over.
# TI and ST are reserved on both machines; the canonical source uses TI on
# purpose as the jiffy clock, so they are not listed here.
C128_RESERVED_VARIABLES = ("ds", "er", "el")

# The flight HUD cannot be positioned with cursor control codes on the C128.
#
# The C64 walks the cursor there with {home}, a run of {down} and a run of
# {rght}. Anchoring every one of the six prints with {home} is not enough:
# printing t1$ at column 35 fills row 2 through to column 39, which links rows
# 2 and 3 into one logical line, and {down} on the C128 steps by logical line
# rather than by physical row. So each {down} count lands a row late, the error
# compounds down the block, and the readouts march down the screen -- fuel and
# horz repeating every four rows to row 24, scrolling the terrain away as they
# go.
#
# CHAR writes at an absolute column and row, honours the {rvon}/{rvof} codes
# already inside t1$/t2$/t3$, and never scrolls; all three were measured before
# this was written. The positions below are the C64's own, read off
# build/bank2-flight.png: labels at column 35 on rows 2, 4 and 6, values at
# column 34 on rows 3, 5 and 7.
#
# STR$ formats exactly as PRINT does, leading space on non-negative values
# included, so the readouts keep their C64 spacing. The single trailing space
# does what c$ did on the C64: clear one stale digit when a value shrinks.
# One further rule, and it is the one that actually stopped the displacement: a
# write that reaches column 39 makes the C128 editor extend that logical line by
# inserting a physical row, pushing everything below it down one. Measured:
# terrain extent went 14-24 to 18-24 between the first and second frame, losing
# the bottom four rows off the screen, and four was exactly the number of HUD
# writes that ended at column 39 (t1$, t2$, " 1000 " and t3$). It fires once,
# because later passes write into lines already linked.
#
# So every write stops at column 38. Appearance is preserved: the labels keep
# their four reverse-video characters at columns 35-38 by dropping only the
# trailing non-reverse space, which fell on column 39 and is a space anyway; the
# values are padded to a fixed five characters at 34-38, which also does the
# stale-digit clearing that c$ did on the C64, and does it for every width
# rather than one character.
HUD_REWRITES = {
    "530": 'char0,35,2,"{rvon}vel {rvof}"',
    "531": 'char0,34,3,left$(str$(int(m2))+"    ",5)',
    "570": 'char0,35,4,"{rvon}fuel{rvof}"',
    "571": 'char0,34,5,left$(str$(fe)+"    ",5)',
    "620": 'char0,35,6,"{rvon}horz{rvof}"',
    "621": 'char0,34,7,left$(str$(hm)+"    ",5)',
    # The bottom status bar is the same C64 idiom -- poke the cursor row, PRINT a
    # newline into row 24, then print the bar. Converting only the readouts left
    # it in place, and it alone still displaced the terrain once at flight start:
    # 272 cells down to 121, then stable. CHAR at explicit columns removes the
    # last editor-mediated write from the flight path.
    #
    # Columns match the C64's TAB stops exactly: 0, 17 and 32. The C64 prints a
    # number with PRINT n; which emits a leading AND a trailing space, whereas
    # STR$ gives only the leading one -- which is precisely what c$ existed to
    # rewrite -- so " lems" carries the space that PRINT would have produced,
    # keeping "4 LEMS" spaced as on the C64.
    "1500": 'char0,0,24,"{rvon}{lblu}"+left$(bl$,39)',
    "1510": 'char0,0,24,"{rvon}{lblu} hi"+str$(hs):char0,17,24,'
            '"{rvon}{lblu}score"+str$(pt):char0,32,24,'
            '"{rvon}{lblu}"+str$(nm)+" lems"',
    "1515": 'ifamthenchar0,0,0,"{rvon}{lblu} attract "',
}

# Inserted after the leading REM. GRAPHIC 1 has to run before anything else
# because it clears variables, and the BLOADs have to run after it because it
# zeroes bank 0 above $4000 and because it is what frees $2000-$3FFF for them.
PROLOGUE = """\
 11 rem native commodore 128 vic-iie edition. see docs/c128-vic-design.md.
 12 rem graphic 1 lifts basic text to $4001 and frees the whole vic window. it
 13 rem also zeroes bank 0 above $4000, so the assets are bloaded after it.
 14 graphic1:graphic0:ifpeek(215)and128thensys65375
 15 bload"music",b0,p4864:bload"rng",b0,p5376
 16 bload"charset",b0,p8192:bload"sprites",b0,p11900
"""

# The C64 KERNAL builds SHFLAG at 653 by scanning the keyboard matrix; the C128
# keeps no equivalent the game can read, so the game does the same scan itself.
MODIFIER_SUB = """\
 2140 rem c128 stand-in for peek(653): read the modifier rows out of the matrix
 2141 rem the way the kernal does, because 653 is not a shift flag here.
 2142 poke56320,253:mk=((peek(56321)and128)=.)
 2143 poke56320,191:mk=mkor((peek(56321)and16)=.)
 2144 poke56320,127:mk=mkor((peek(56321)and36)<>36)
 2145 poke56320,255:return
"""

# Anything here left in the output means a C64 assumption survived the port.
FORBIDDEN = [
    (r"\bpoke56576\b", "$DD00 VIC bank select"),
    (r"\bpoke648\b", "C64 screen page pointer"),
    (r"\bpoke5[56],", "MEMSIZ"),
    (r"\bpoke214,", "C64 cursor row"),
    (r"\bpoke679,", "C64 wait argument at $02A7"),
    (r"\b653\b", "C64 shift flag"),
    (r"\bsys1[0-9]{4}\b", "C64 helper entry point"),
    (r"peek\(v\+31\)", "raw $D01F collision latch"),
    (r"\bpoke53272,18\b", "C64 title $D018 value"),
]


def rebase_screen(line: str) -> str:
    """Shift screen-range literals down a bank, leaving string contents alone."""
    out: list[str] = []
    for index, part in enumerate(line.split('"')):
        if index % 2:                      # inside a string literal
            out.append(part)
            continue

        def shift(match: re.Match[str]) -> str:
            value = int(match.group(0))
            if SCREEN_LOW <= value <= SCREEN_HIGH:
                return str(value - SCREEN_SHIFT)
            return match.group(0)

        out.append(re.sub(r"\d+", shift, part))
    return '"'.join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--explain", action="store_true", help="print each rule and its hit count"
    )
    parser.add_argument(
        "--instrument",
        action="store_true",
        help="add a frame counter at $1784 to the flight loop, for measuring "
        "frames per second. Measurement only: it costs about one statement per "
        "frame and must never be in a shipped build.",
    )
    args = parser.parse_args()

    text = args.source.read_text()
    failures: list[str] = []

    for needle, replacement, why in RULES:
        hits = text.count(needle)
        if not hits:
            failures.append(f"rule never matched: {needle!r} ({why})")
        text = text.replace(needle, replacement)
        if args.explain:
            print(f"  {hits} x {needle!r}\n      -> {replacement!r}\n      {why}")

    if args.instrument:
        # Line 160 is the flight loop head and `goto160` is its only back edge,
        # so one increment here counts exactly one frame. $1784 is free space in
        # the RNG scratch region, above the code and clear of the wait argument.
        needle = "160 getz$:"
        if needle not in text:
            failures.append("cannot instrument: no '160 getz$:' loop head")
        text = text.replace(
            needle, "160 poke6020,(peek(6020)+1)and255:getz$:", 1
        )

    rewritten, seen = [], set()
    for line in text.splitlines():
        number = line.strip().split(" ")[0] if line.strip() else ""
        body = HUD_REWRITES.get(number)
        if body is not None:
            indent = line[: len(line) - len(line.lstrip())]
            line = f"{indent}{number} {body}"
            seen.add(number)
        rewritten.append(line)
    missing = set(HUD_REWRITES) - seen
    if missing:
        failures.append(f"HUD lines not found in the source: {sorted(missing)}")
    text = "\n".join(rewritten)

    lines = [rebase_screen(line) for line in text.splitlines()]

    marker = next((i for i, l in enumerate(lines) if l.strip().startswith("10 rem")), None)
    if marker is None:
        failures.append("no leading '10 rem' line to insert the prologue after")
    else:
        lines[marker + 1 : marker + 1] = PROLOGUE.rstrip("\n").split("\n")
    lines += MODIFIER_SUB.rstrip("\n").split("\n")

    ported = "\n".join(lines) + "\n"
    for pattern, description in FORBIDDEN:
        for line in ported.splitlines():
            stripped = line.strip()
            if stripped.startswith(tuple(f"{n} rem" for n in range(2140, 2146))):
                continue
            if re.search(pattern, line) and " rem " not in line:
                failures.append(f"{description} survived the port: {line.strip()[:70]}")

    for name in C128_RESERVED_VARIABLES:
        for number, line in enumerate(ported.splitlines(), start=1):
            stripped = re.sub(r'"[^"]*"', '""', line)
            if " rem " in stripped or stripped.strip().endswith(" rem"):
                stripped = stripped.split(" rem ")[0]
            if re.search(rf"(?<![a-z0-9$]){name}(?![a-z0-9$]) *=", stripped):
                failures.append(
                    f"assignment to BASIC 7 reserved variable {name.upper()} on "
                    f"output line {number}: {line.strip()[:60]}"
                )

    if failures:
        for failure in failures:
            print(f"error: {failure}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(ported)
    print(
        f"{args.output} : {len(ported.splitlines())} lines from "
        f"{args.source} ({len(RULES)} rules, screen rebased by -${SCREEN_SHIFT:04X})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
