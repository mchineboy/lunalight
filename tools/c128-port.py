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
