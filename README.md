# lunalight

Commodore 64 lunar lander by Steven Hardison (public domain).

![Lunalight title screen and attract-mode landing](docs/lunalight-gameplay.gif)

Canonical playable path: **`src/lunalight.bas`** compiled with the original
**Blitz!** disk [`tools/BLITZ.d64`](tools/BLITZ.d64), producing
[`build/lunalight-blitz-full.prg`](build/lunalight-blitz-full.prg). Physics remain
the original float equations from [`current/luna081426`](current/luna081426)
(`luna2`): unchanged gravity, thrust, drift and landing thresholds.

The canonical package is the **VIC-bank-2 build**. Relocating the screen, sprite
pointers and sprite shapes out of VIC bank 0 freed the `$2E7C` sprite region for
code, which is what made the previously omitted feature layers fit. It carries a
three-voice title soundtrack, the TOD-entropy RNG, procedural terrain with
generated landing pads, the refuel-pad flag sprite, joystick port 2 with keyboard
fallback, the crash post-mortem text, and attract mode.

A runnable fallback remains: **`src/lunalight-bank0.bas`** is the exact
pre-promotion bank-0 source, built by `make blitz-bank0`.

Layer evidence and measured results:
[`docs/feature-layering.md`](docs/feature-layering.md).

## Lineage

| File | Role |
| ---- | ---- |
| [`src/luna081426.bas`](src/luna081426.bas) | Exact detokenized `luna2` baseline; `make verify-baseline` retokenizes to byte-identical [`current/luna081426`](current/luna081426) |
| [`src/lunalight.bas`](src/lunalight.bas) | **Canonical** promoted bank-2 feature build (formerly `src/lunalight-bank2.bas`, now folded in so only one canonical source exists) |
| [`src/lunalight-bank0.bas`](src/lunalight-bank0.bas) | **Fallback**: the exact pre-promotion bank-0 canonical source (baseline plus correctness fixes and IRQ music). Also the control the promoted build is verified against |
| [`src/lunalight-optimized.bas`](src/lunalight-optimized.bas) | Prior evolved source (fixed-point physics, Mars, etc.) — reference only |
| [`tools/BLITZ.d64`](tools/BLITZ.d64) | **Required tracked input**: original C64 Blitz! compiler disk (`blitz compiler`). Do not modify |
| [`current/luna081426`](current/luna081426) | Baseline tokenized PRG — source-of-truth for the baseline round-trip |
| [`current/luna081426-old`](current/luna081426-old) | Earlier `LUNAON4A` tokenized PRG (historical) |
| [`sprites/lsprite.prg`](sprites/lsprite.prg) / [`current/lsprite`](current/lsprite) | Original sprite shapes at `$2E7C`; unmodified |
| [`src/music.s`](src/music.s) | Three-voice IRQ title soundtrack (embedded at `$4200`) |
| [`src/rng.s`](src/rng.s) | TOD-entropy collector and PRNG table at `$4400-$4BFF`; **used** by the canonical package for terrain generation |
| [`src/lunalight-m3x1.bas`](src/lunalight-m3x1.bas) | Reference: 2024 M3X1 rewrite |
| [`src/lunalight-experimental.bas`](src/lunalight-experimental.bas) | Reference: 2024 LUNAON1 fork |
| [`src/lunalight-1985.bas`](src/lunalight-1985.bas) | Reference: 1985 LIST decompilation |
| [`src/LUNALIGH.D64`](src/LUNALIGH.D64) | Historical 1985 disk image |

Source text is lowercase: `petcat` maps lowercase ASCII to PETSCII uppercase.

## What the canonical build contains

Retained from the baseline and required by the motion oracle: float gravity and
thrust (`m2±.6`, `po` via `.1+m2/20`, `hm/4` drift), soft-landing thresholds
`|hm|≤2` and `int(m2)≤5`, the ±90° rotation limiter, and the five-pad scoring
shape. No physics constant or formula was altered by the promotion.

Retained correctness fixes from the bank-0 lineage: 40-column message-row erasure
(`bl$`), explosion pointers assigned before the explosion sprites are enabled and
refreshed before each frame delay, and 9-bit pad X so pads right of x=255
register.

Added by the promotion (all verified, see below):

| Feature | Implementation |
| ------- | -------------- |
| VIC bank 2 | `$DD00` low bits `01`, `poke648,132`, `$D018=$14`; screen `$8400`, pointers `$87F8`, sprites rebased to `$AE7C` |
| Title soundtrack | Three voices: triangle bass on the chord root, sawtooth melody under a low-pass cutoff sweep, and a pulse echo of the melody four steps back. `SYS 16896` installs the player embedded at `$4200-$43E5`; `SYS 16899` restores the KERNAL IRQ and silences the SID, so flight and attract run without music and leave the chip to the engine and explosion effects |
| RNG | `SYS 17408` collects TOD-phase entropy (~3.2 s before the title), `SYS 17411` refills the 1024-byte table at `$4800`; BASIC reads it with `PEEK(18432+ri)` |
| Procedural terrain | A random-walk height map across all 40 columns, redrawn every game, with slope smoothing around each pad |
| Landing pads | Five generated pads, always four glyphs (32 pixels) wide, with `px`/`pw`/`py` geometry, `pb()` point values (500/600/800 by altitude band), and centre-hit bonus `pb*2/3`. The fixed width gives the 24-pixel LEM four pixels of visual clearance on each side, including inset pads. The verdict compares the lander's centre, `INT(pp)+12`, because `px()` is the sprite-X of the pad's *left* edge |
| Refuel pad | One low pad per game carries `rf()`; landing there refills fuel to 1000 and prints “fuel tanks full” |
| Refuel flag sprite | The flag shape is patched into the original payload’s spare slot 243 by [`tools/make-shapes.py`](tools/make-shapes.py), then the whole payload is rebased so slot 243 resolves to `$BCC0`. Drawn on sprite 4, light blue, unexpanded. The pennant carries an Earth wire-globe emblem |
| Command module | A cosmetic spacecraft holding station in the sky, patched into spare slot 244 (`$BD00`) and drawn on sprite 7, light grey, at Y 55. Sprite 7 is otherwise explosion-only, so line 1212 re-establishes its pointer, colour, position and enable bit after every round. It steps 8 pixels right per round and wraps at X 240, which reads as orbital motion without costing anything in the flight loop |
| Joystick | Port 2 (`PEEK(56320)`) for rotate and thrust, with the original keyboard controls kept as a fallback |
| Crash post-mortem | Exactly one line per crash. An RNG-table coin flip picks either a cause line derived from the crash state (tilt, sideways, velocity, off-pad) or one of 13 `DATA` consequence lines, rotated by `PEEK(162)` |
| Attract mode | 20 seconds idle on the title screen starts a float autopilot demo; any key or joystick input returns to the title. The demo never writes the high score. Each flight uses the normal `ep`/`hp` spawn and momentum sequence and selects a random pad without immediately repeating one. It crosses high, releases into a ballistic dive 90 pixels out, and finishes with one continuous late burn that bends onto the pad. The first three approaches aim at the centre for the bonus; every fourth deliberately aims just outside the left edge and crashes, demonstrating failure at an exact 25% cadence. It diverts to the refuel pad below 400 fuel |

The original sprite payload, the physics constants, the oracle tolerances and the
motion fixture are unchanged by the promotion. Only the sprite payload’s **load
address** is rebased; its bytes are untouched apart from the flag and command
module written into the previously empty slots 243 and 244.

## Controls

| Input | Action |
| ----- | ------ |
| Joystick 2 left / right | Rotate lander (±90° from upright) |
| Joystick 2 fire | Thrust |
| `{rght}` / `{down}` | Rotate lander (keyboard fallback) |
| Shift / Ctrl / C= (`PEEK(653)`) | Thrust (keyboard fallback) |
| `F1` | Pause / resume |
| `F7` | Start, and restart after game over |
| `{home}` while paused | Stop to BASIC (`luna2`) |
| Any input during attract | Return to the title screen |

## Build / run

Requires `petcat`, `x64sc`, `c1541` (VICE), and `ca65`/`ld65` (cc65). The
original Blitz compile also needs the tracked disk
[`tools/BLITZ.d64`](tools/BLITZ.d64).

### Canonical (promoted bank-2, original Blitz!)

```bash
make                 # build/lunalight-blitz-full.prg
make blitz           # same
make blitz-bank2     # alias of the above; the canonical package *is* bank 2
make run             # x64sc autostart of the canonical full PRG
make run-bank2       # alias of make run
make d64             # build/lunalight.d64 — self-contained canonical full PRG as LUNALIGHT
make d64-boot        # directory listing + headless boot screenshot of that disk
make smoke           # warp headless title screenshot of the canonical artifact
make bench           # normal-speed run of the canonical artifact
make gif             # regenerate docs/lunalight-gameplay.gif (title + attract)
make clean
```

`LOAD"*",8,1` then `RUN` on the D64 (or autostart the full PRG). Sprites, music
and the RNG are already embedded; do not use the bare `lunalight-blitz.prg` for
play.

The canonical load image spans `$0801-$C073`, so a single `,8,1` load moves about
47 KB over the serial bus — roughly three times the bank-0 fallback. Measured with
`-warp`: still loading at 110,000,000 cycles, title screen up at 130,000,000.
`SMOKE_CYCLES` is therefore 135,000,000, which lands inside the title's
20-second window before attract mode starts, and `BENCH_CYCLES` is 200,000,000 so
the unwarped run covers the load, the title and normal-speed attract flight (about
100 s of wall clock, since the SID dump device does not throttle to 100%). Decode
any screenshot with
`python3 tools/readscreen.py build/lunalight-blitz-full-smoke.png`.

### Bank-0 fallback

```bash
make blitz-bank0     # build/lunalight-bank0-blitz-full.prg from src/lunalight-bank0.bas
make run-bank0       # x64sc autostart of the fallback
```

The fallback uses the original sprites at `$2E7C` and music at `$4200`; it has no
RNG, procedural terrain, flag, joystick, crash text or attract mode. It is also
the artifact the verifier flies as the bank-0 collision-latch control, and its
source is the byte-identity control for the shared scoring lines. It predates the
title-only soundtrack, so it never calls `SYS 16899` and its music plays through
flight; the player restores its own envelopes on each note step, so the in-game
SID clear at line 990 costs it one step of tone rather than silencing it.

### Verification

```bash
make verify-baseline        # petcat round-trip of src/luna081426.bas ↔ current/luna081426
make verify-blitz-motion    # canonical bank-2 motion oracle vs the original fixture
make verify-bank2-motion    # same target under its bank-2 name
make verify-blitz-gameplay  # canonical aggregate: motion oracle + full runtime suite
make verify-bank2           # the runtime suite alone
make verify-bank2-capacity  # capacity artifact: motion oracle + suite + filler integrity
make verify-bank0-motion    # motion oracle against the bank-0 fallback
make record-blitz-baseline  # explicit fixture mutation only — do not run casually
```

`verify-blitz-motion` reads the relocated screen (`$8400`) and pointer table
(`$87F8`) and compares the promoted artifact against the **unchanged** bank-0
motion fixture within its recorded tolerances.
`record-blitz-baseline` is bound to the bank-0 fallback at bank-0 addresses,
because the fixture describes that lineage.

The verifier’s `--mode strict` additionally requires the whole decoded screen to
match the fixture. That only ever described the bank-0 static-terrain screen, so
it is not a canonical gate: the promoted build draws procedural terrain that
differs every game by design. The canonical aggregate replaces it.

VICE-driven targets own the emulator and its monitor port, so the Makefile
declares `.NOTPARALLEL`; do not run them with `make -j`.

### Alternate toolchains (bank-0 lineage, explicit names)

These paths embed or patch assets at the bank-0 addresses (`$2E7C` sprites), so
they are bound to `src/lunalight-bank0.bas`. They are **not** bank-2 capable and
claim no parity with the canonical package.

| Target | Output | Notes |
| ------ | ------ | ----- |
| `make prg` | `build/lunalight.prg`, `build/lunalight-bank0.prg` | Tokenized BASIC for both lineages |
| `make full` | `build/lunalight-bank0-full.prg` | Interpreted BASIC + flag sprites + music + RNG embed, bank-0 layout |
| `make run-basic` | — | Autostart the interpreted bank-0 full PRG |
| `make mospeed` | `build/lunalight-bank0-mospeed-full.prg` | MOSpeed cross-compile of the bank-0 source + asset patch |
| `make run-mospeed` | — | Autostart the MOSpeed bank-0 full PRG |
| `make d64-mospeed` | `build/lunalight-bank0-mospeed.d64` | Former default disk: MOSpeed PRG + `.bas` + `music` + `rng` |
| `make reblitz` | `build/lunalight-bank0-reblitz.prg` | **Experimental** JS Reblitz64 port of the bank-0 source; overruns sprites; not packaged |

MOSpeed needs Java and downloads `tools/mospeed/basicv2.jar` on first use.
Reblitz needs a local `tools/reblitz64` checkout (gitignored).

### Compiler distinctions

| Compiler | What it is | Role here |
| -------- | ---------- | --------- |
| **Original Blitz!** (`tools/BLITZ.d64`) | C64 Blitz!/Austro-Speed run under VICE via [`tools/blitz-compile.py`](tools/blitz-compile.py) | **Canonical** playable binary |
| **Reblitz64** | Host-side JS reimplementation | Experimental only; not the original Blitz! compiler |
| **MOSpeed** | Java 6502 BASIC V2 cross-compiler | Alternate; different codegen and packaging |
| **Interpreted BASIC V2** | `petcat` tokenize + embed | Slow; useful for source debugging |

## Memory map (canonical bank-2 package)

CPU-side load image, single `,8,1` load:

| Range | Contents |
| --- | --- |
| `$0801`–`$361A` | Blitz machine code (11,804-byte PRG for the promoted source) |
| `$361B`–`$41FF` | Free: BASIC/Blitz variables and arrays grow up from here; 3,045 bytes of headroom to the music player |
| `$4200`–`$43E5` | Three-voice title soundtrack player; 26 bytes of slack before the RNG |
| `$4400`–`$47FF` | RNG entry points (`collect`, `refill`, `stir`) |
| `$4800`–`$4BFF` | 1024-byte PRNG table BASIC PEEKs |
| `$8400`–`$87FF` | Screen matrix and sprite pointers, also seen by the VIC below |
| `$9FFF` downward | BASIC string heap (`MEMSIZ $A000`). The screen lies in its descent path and `STREND` is too low for BASIC to collect on its own, so line 840 forces one collection per round with `gc=fre(.)` |
| `$AE7C`–`$C073` | Sprite shapes, rebased from `$2E7C`; flag in slot 243, command module in slot 244 |

What the VIC sees in bank 2 (`$8000-$BFFF`):

| Range | Contents |
| --- | --- |
| `$8400`–`$87E7` | Screen matrix (`poke648,132`, `$D018=$14`) |
| `$87F8`–`$87FF` | Sprite pointers |
| `$9000`–`$97FF` | Character ROM image. `$D018` must select this; `$18` selects blank RAM at `$A000`, which makes the display invisible and prevents the sprite/background collision latch that gates landing |
| `$AEC0`–`$B0BF` | Lander shapes, pointers 187-194 |
| `$B2C0`–`$BCBF` | Explosion shapes, pointers 203-242 |
| `$BCC0`–`$BCFF` | Refuel flag, pointer slot 243 |
| `$BF40`–`$BFBF` | Decoration shapes, pointers 253 and 254 |

`$D018` reads back as `$15` because bit 0 is unused. The sprite payload’s tail
runs past `$C000`, outside the bank; every pointer the game actually uses
(187-194, 203-242, 243, 253, 254) resolves below `$BFFF`, which the verifier
checks. `tools/embed-sprites.py` fails the build if segments would overlap.

The bank-0 fallback keeps the original layout: code `$0801-$2DC4`, sprites
`$2E7C-$4073`, music `$4200-$43E5`, screen `$0400`, pointers `$07F8`.

## Verification workflow

1. `make verify-baseline` — exact tokenized match for the frozen `luna081426` text.
2. `make` / `make blitz` — original compiler disk → `lunalight-blitz.prg` → embed music, RNG and rebased flag sprites → `lunalight-blitz-full.prg`.
3. `make verify-blitz-gameplay` — the canonical aggregate: the six-sample motion oracle at bank-2 addresses plus the runtime suite (title, HUD, procedural terrain rows, generated pads and their colour pattern, refuel flag sprite, sprite residency, BASIC memory pointers, pause tile, joystick and keyboard controls, collision latch, explosion progression, the single-line crash post-mortem, attract mode with repeatable autopilot landings, string-heap reclamation between rounds, and a bank-0 control descent).
4. `make verify-bank2-capacity` — proves the freed region is genuinely usable: the padded artifact still passes the motion oracle and the suite, and the filler above BASIC’s live data is byte-intact.
5. `make smoke` / `make bench` — title screenshots of the canonical artifact.
6. `make d64` / `make d64-boot` — package `build/lunalight.d64` (one 186-block `lunalight` PRG, 478 blocks free) and boot it headless; the exit screenshot decodes to the title screen.

Measured results for each layer are in
[`docs/feature-layering.md`](docs/feature-layering.md).

Subjective handling still needs manual confirmation; the oracle catches timing and
position drift, not feel.

## Tools

| Tool | Use |
| ---- | --- |
| [`tools/blitz-compile.py`](tools/blitz-compile.py) | Drive original Blitz! under VICE binary monitor |
| [`tools/verify-blitz-gameplay.py`](tools/verify-blitz-gameplay.py) | Record/compare Blitz gameplay traces (motion and strict modes) |
| [`tools/verify-bank2.py`](tools/verify-bank2.py) | Canonical layout and runtime suite |
| [`tools/bank2-capacity.py`](tools/bank2-capacity.py) | Measure bank-2 headroom and emit the padded capacity artifact |
| [`tools/rebase-prg-load.py`](tools/rebase-prg-load.py) | Change a PRG load address without touching its payload |
| [`tools/make-shapes.py`](tools/make-shapes.py) | Write the refuel flag and command module into spare sprite slots 243 and 244 |
| [`tools/vice_monitor.py`](tools/vice_monitor.py) | Shared VICE monitor helpers |
| [`tools/embed-sprites.py`](tools/embed-sprites.py) | Merge PRG + address-sorted asset PRGs |
| [`tools/attract-sim.py`](tools/attract-sim.py) | Python sim of the attract/terrain path |
| [`tools/make-gameplay-gif.py`](tools/make-gameplay-gif.py) | Capture the README title+attract GIF via VICE’s binary monitor |
| [`tools/readscreen.py`](tools/readscreen.py) | Decode VICE screenshots via character ROM |

Note: the lander collides with any character on screen; debug text below row 7
causes false crashes.
