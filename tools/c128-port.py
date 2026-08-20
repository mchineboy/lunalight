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

# The flight HUD is written with POKEs, not with PRINT and not with CHAR.
#
# Three measurements forced this, in order:
#
#   PRINT with cursor codes: {down} steps by logical line on the C128, so the
#   readouts drifted four rows per pass down to row 24 and scrolled the terrain
#   away. Anchoring every print with {home} did not help, because the anchor was
#   never wrong -- the steps were.
#
#   CHAR at absolute positions: fixed the drift, but a write reaching column 39
#   makes the editor insert a physical row and push everything below it down.
#   Terrain went from rows 14-24 to 18-24 in one frame and sat there.
#
#   CHAR kept inside column 38: correct at last, and catastrophically slow.
#   Native compiled flight ran 0.52 fps with these six readouts and 9.98 fps
#   with them stubbed out, so they were costing about 95% of the frame. The
#   cause is nine string allocations per frame -- LEFT$(STR$(x)+"    ",5) three
#   times over -- and compiled strings live behind bank-1 descriptors.
#
# POKEs settle all three at once. They cannot drift, they cannot make the editor
# insert anything, and they allocate nothing. It is also what the terrain and pad
# routines have always done, so the flight loop now touches the editor nowhere.
#
# Digits are extracted arithmetically rather than through STR$, right-aligned in
# a five-cell field, which also generalises the stale-digit clearing that c$ did
# on the C64. The labels are static, so they are drawn once per round instead of
# rebuilt every frame.
#
# Colour: the C64 selects green/yellow/red by PRINTing a colour code before each
# readout. Those become a colour number in cc, written to colour RAM alongside.
HUD_REWRITES = {
    # colour selection: PRINT of a colour code becomes a colour number
    "500": "ifm2<3thencc=5:goto530",
    "510": "cc=7",
    "515": "ifm2>5thencc=2",
    "540": "iffe>399thencc=5:goto570",
    "550": "iffe<100thencc=2:goto570",
    "560": "cc=7",
    "600": "ifhm=.thencc=5:goto620",
    "605": "ifhm>-3thenifhm<3thencc=7:goto620",
    "610": "cc=2",
    # readouts: label offset then value. rows 2/4/6 label, 3/5/7 value,
    # columns 35 and 34, exactly where the C64 puts them.
    "530": "la=115",
    "531": "xv=int(m2):sa=154:gosub2150",
    "570": "la=195",
    "571": "xv=fe:sa=234:gosub2150",
    "620": "la=275",
    "621": "xv=hm:sa=314:gosub2150",
    # the status bar is drawn once per round, so CHAR is affordable there, and
    # it seeds the static labels at the same time
    "1500": 'char0,0,24,"{rvon}{lblu}"+left$(bl$,39):gosub2160',
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
HUD_SUB = """\
 2150 rem hud value: xv right-aligned in five cells at screen offset sa, with
 2151 rem the four label cells at la recoloured to cc. pokes only, so nothing
 2152 rem here can drift, scroll, insert a row or allocate a string.
 2153 vv=abs(int(xv)):lp=4
 2154 forii=4to.step-1
 2155 dd=32:ifii=4orvv>.thendd=48+vv-int(vv/10)*10:vv=int(vv/10):lp=ii
 2156 poke1024+sa+ii,dd:poke55296+sa+ii,cc:nextii
 2157 ifxv<.andlp>.thenpoke1024+sa+lp-1,45:poke55296+sa+lp-1,cc
 2158 forii=.to3:poke55296+la+ii,cc:nextii
 2159 return
 2160 rem the three static labels, reverse video, drawn once per round
 2161 poke1139,150:poke1140,133:poke1141,140:poke1142,160
 2162 poke1219,134:poke1220,149:poke1221,133:poke1222,140
 2163 poke1299,136:poke1300,143:poke1301,146:poke1302,154
 2164 return
"""

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
        "--no-hud",
        action="store_true",
        help="stub out the six flight HUD readouts. Measurement only: it "
        "isolates how much of the flight frame time the HUD costs, so a "
        "rewrite can be justified before it is written.",
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

    hud = dict(HUD_REWRITES)
    if args.no_hud:
        # Keep the colour-selection lines; blank only the six writes, so the
        # control flow and the arithmetic feeding them are untouched and the
        # difference measured is the display cost alone.
        for number in ("531", "571", "621"):
            hud[number] = "rem hud stubbed for measurement"

    rewritten, seen = [], set()
    for line in text.splitlines():
        number = line.strip().split(" ")[0] if line.strip() else ""
        body = hud.get(number)
        if body is not None:
            indent = line[: len(line) - len(line.lstrip())]
            line = f"{indent}{number} {body}"
            seen.add(number)
        rewritten.append(line)
    missing = set(hud) - seen
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
    lines += HUD_SUB.rstrip("\n").split("\n")

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
