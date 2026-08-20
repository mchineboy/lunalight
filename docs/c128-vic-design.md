# Design: native Commodore 128 VIC-IIe edition

## Purpose

Create a **native C128-mode**, 40-column **VIC-IIe** edition of Lunalight.
It must retain the current game's play feel and visual identity while using the
C128's native startup, BASIC 7 environment and extra RAM where it is genuinely
useful.

This is not a request to replace the canonical C64 game. The C64 build remains
the shipping reference:

```text
src/lunalight.bas -> original Blitz! -> build/lunalight-blitz-full.prg
```

The C128 edition is a new target with separate source, packaging and
verification. Do not modify the C64 canonical source, the bank-0 control, the
motion fixture, or `tools/BLITZ.d64` while working on it.

## Product decision

Use the VIC-IIe (the C128's 40-column display), not the 80-column VDC.

The VIC-IIe path deliberately preserves:

- the existing 40x25 character terrain and HUD;
- eight hardware sprites, including the two-sprite refuel flag;
- sprite-background collision latching used by the landing/crash path;
- SID music and effects; and
- joystick-port-2 behavior.

Do **not** pursue a VDC edition as part of this work. The VDC has no hardware
sprites, so it would require software sprites and new collision detection,
which is a remake rather than a port.

The C128's 2 MHz mode is not a gameplay performance feature on this target.
The VIC 40-column display is unavailable/incoherent in FAST mode. Keep all
visible flight and title operation at 1 MHz. FAST is permitted only during an
intentional blank-screen load or offline preprocessing step, and it must always
return to SLOW before enabling the VIC display.

### Use BASIC 7's native graphics, sprite and sound commands

BASIC 7 is not BASIC 2 with more RAM. It ships hardware commands that replace
whole classes of C64 POKE plumbing, and this edition uses them:

| C64 plumbing | BASIC 7 replacement |
| --- | --- |
| `POKE v+21` / `v+39..46` / `v+23` / `v+29` | `SPRITE n,on,colour,priority,xexp,yexp,mode` |
| `POKE v+0..15` plus `$D010` MSB masking | `MOVSPR n,x,y` with a 0-511 X |
| `PEEK(v+31)` latch polling | `BUMP(2)` |
| sprite position read-back arithmetic | `RSPPOS(n,0)`, `RSPPOS(n,1)` |
| screen/charset base juggling in `$D018` | `GRAPHIC 0` and the `GRAPHIC` reserve |

`MOVSPR` taking a 0-511 X coordinate is the single most valuable one: it retires
the `$D010` bit-7 trap and the high-X special cases the C64 build works around,
including the constraint that keeps the command module below X=256. Phase 0
measured this directly (`MOVSPR 1,300,120` -> `RSPPOS(1,0)` = 300, `$D010`
bit 0 set), so the high-X rules are relaxed for the C128 edition **by
demonstrated hardware behavior**, which is exactly the exemption the Phase 2
note below allows.

Sprite handling: **BASIC 7 native** (`SPRITE`/`MOVSPR`/`SPRSAV`).
Collision: **polled `BUMP(2)`**, the direct analogue of the existing
`PEEK($D01F)` structure, not the interrupt-driven `COLLISION 2` handler.

Sound is the one place the native commands are rejected. `PLAY`/`ENVELOPE`
would change the title theme audibly, and the theme is part of the visual and
audio identity this port is required to preserve. The existing IRQ player is
**ported** instead (see below). Do not mix `SOUND`/`PLAY`/`VOL` into a build
that also runs the ported player: those commands rewrite SID registers the
player owns.

## Evidence gathered before implementation

Items 1-5 were the pre-Phase-0 desk analysis. Items 6-21 are measured, and
`make verify-c128-vic` re-measures them on every change.

1. `petcat -w70` tokenizes the present BASIC text as C128 BASIC 7.0 at `$1C01`
   without syntax errors. This is encouraging, but it is not a runnable port.
2. The existing full Blitz PRG has a C64 load address of `$0801` and begins with
   a C64 BASIC stub, `SYS 2076`. Under native `x128`, it loads but does not
   auto-start the game; native BASIC starts at `$1C01`.
3. C128 native mode maps BASIC ROM across `$4000-$BFFF` by default. Therefore
   the current C64 helper entry points at `$4200` (music) and `$4400` (RNG)
   cannot be called unchanged with `SYS` from native BASIC.
4. The current C64 code writes `$37/$38` (decimal 55/56) to control `MEMSIZ`.
   Those addresses do not have that C64-BASIC meaning in C128 BASIC 7. They
   must not be copied into the C128 edition.
5. The VIC-IIe still uses a C64-style 16 KB video window. The C64 build's
   geometry (VIC bank 2 at `$8000`, screen `$8400`, charset `$8800`, sprites
   `$AE7C`) is **not** carried over; see the layout decision below.
6. The displaced C64 region is larger than two entry points. `tools/music.cfg`
   and `tools/rng.cfg` place the player at `$4200`, the RNG at `$4400` and its
   table at `$4800`; the Makefile declares the whole hole as
   `$4200-$4BFF`, 2,560 bytes. `src/lunalight.bas:109` reads that table with
   `PEEK(rb+ri)`, and lines 91/119 read player state at `PEEK(16902/16903)`.
   All three are reads inside C128 BASIC ROM.
7. On the C128, CPU **writes** to `$4000-$BFFF` fall through to the RAM
   underneath, but **reads** return ROM. Measured: `BANK 15: POKE 16896,111`
   then `PEEK(16896)` returns 84, a BASIC ROM byte; `BANK 0: PEEK(16896)`
   returns 111. Any ported code that PEEKs that span silently reads ROM.
8. `BANK 0` / `BANK 15` is the BASIC-level gateway. `BANK 0` selects all-RAM
   bank 0 for `PEEK`/`POKE`/`SYS`; `BANK 15` restores ROM and I/O. `SYS` under
   `BANK 0` runs with the KERNAL swapped out, so machine code is entered under
   `BANK 15` and does its own switching.
9. The machine-code gateway is MMU register `$FF00`, which is visible in every
   memory configuration. `src/c128/helper.s` saves it, writes `$3E` (bit 0 clear
   to keep the I/O block selected, bits 1-5 set for RAM across `$4000-$FFFF`,
   bits 6-7 clear for bank 0), reads, and restores. Measured: `$FF00` is `$00`
   on entry and `$00` again after the window; the read of `$4200` inside it
   returns the RAM byte; `$D012` reads correctly after the restore. The probe
   does not exercise I/O *inside* the window, and nothing needs to: the window
   exists only to read RAM under ROM, and the ported player runs in the normal
   configuration. Interrupts are masked across the window because the KERNAL ROM
   is swapped out inside it.
10. `GRAPHIC 1` reserves `$2000-$3FFF` and relocates BASIC text from `$1C01` to
    `$4001`, **and a running program survives the relocation**. Measured:
    `TXTTAB` reads `$1C01` before and `$4001` after, with execution continuing.
    Variables do not survive it, so anything needed across the call is stored
    before it.
11. Native defaults measured under `x128 +go64`: `$D505` = `$B7`, `$D506` =
    `$04` (VIC RAM bank bits 6-7 clear, so bank 0), `$DD00` = `$C7` (bits 0-1
    set, so the VIC's 16 KB window is `$0000-$3FFF`), `$D018` = `$15` (screen
    `$0400`, character source `$1000`), `$D7` = 0 (40 columns).
12. BASIC 7's sprite image area is `$0E00-$0FFF`: the screen's sprite pointers
    at `$07F8-$07FF` come up preset to 56-63. Measured `PEEK(2040)` = 56.
13. `BUMP(2)` reports a real sprite-background hit in this configuration. The
    probe writes a lit cell with `CHAR 0,10,20`, clears the stale latch, moves a
    solid sprite onto it and reads `BUMP(2)` = `$01`. Polled collision is proven
    rather than assumed, so the C64 landing/crash structure transfers.
14. **The C128's KERNAL interrupt runs at 50 Hz on PAL while the jiffy clock is
    still stepped to 60 Hz nominal.** Measured: `SLEEP 1` advances `TI` by 61 and
    `$A2` by 63, so the clock is ~60 Hz and `$A2` is its low byte; but the RNG's
    change-counting wait came back 6/5 too long at every count (60 requested ->
    72 elapsed, 15 -> 18, unchanged with sprites active). One interrupt in six
    advances the clock by two, so counting changes counts five where six
    elapsed. Dividing gives the interrupt rate directly: 60x60/72 = 50.0 and
    60x15/18 = 50.0.

    This is the single most consequential difference found so far, because the
    C64 helpers assume a ~60 Hz CIA-driven interrupt on both PAL and NTSC. Two
    things had to change, both behind defines:

    - `wait` compares against a target instead of counting changes, which is
      exact whatever the step size;
    - the player's `step_ticks` drops from 22 to 18, because a tick is one
      interrupt: 18/50 = 0.360 s against the C64's 22/60 = 0.367 s.

    The published loop length needed a unit fix as well. `src/lunalight.bas:135`
    compares it against `TI`, so it must be in jiffies, and ticks are only
    jiffies when the interrupt runs at the jiffy rate. It is now
    `sequence_length * step_ticks * LOOP_JIFFY_NUM / LOOP_JIFFY_DEN`: 1,056 on
    the C64 (48 x 22 x 1/1), 1,036 on the C128 (48 x 18 x 6/5).

    Measured on PAL `x128` only. NTSC needs its own measurement before the
    edition claims to run there.
15. **The C128 editor's interrupt reloads `$D018` from a shadow at `$0A2C`, so
    `POKE 53272` alone does not switch character sets.** Found by accident: two
    consecutive Phase 1 runs disagreed, one reading back the poked charset
    fields and the next reading `$15`, which is the shadow's default `$14` with
    the unused bit 0 set. The register write wins only until the next interrupt.
    Write the shadow at `2604` as well, and verify the selection a full second
    later rather than immediately, or the test measures a race instead of the
    mechanism. This is not cosmetic: the title/flight charset switch is a Phase 1
    deliverable and would have worked intermittently.

    Related, and worth stating once: bit 0 of `$D018` is unused on the VIC-IIe
    and reads back as 1, so a `POKE` of `$18` reads as `$19`. Assert the screen
    and charset fields, never the whole byte.
16. **`GRAPHIC 1` zeroes bank-0 RAM above the relocated text, and nothing
    below it.** Measured by writing a marker to every candidate staging address
    and reading them back afterwards:

    | address | after `GRAPHIC 1` |
    | --- | --- |
    | `$1300`, `$1B00`, `$1C00` | survives |
    | `$2000`, `$2800`, `$3000`, `$3FFF` | survives |
    | `$4000`, `$5000`, `$6000`, `$8D00` | zeroed |

    A 29 KB autostart PRG does load in full -- `$6000` and `$8D00` both read
    back correctly under `BANK 0` before `GRAPHIC 1` runs -- so this is the
    relocation clearing memory, not a truncated load.

    Phase 1 survives this only because it copies **before** `GRAPHIC 1`. Phase 2
    cannot: its destinations are `$2000-$27FF` and `$2E7C-$3FFF`, which the
    BASIC text occupies at load time, so its copy must happen *after* the
    relocation, from a stage the relocation has already wiped. The Phase 2
    probe reached exactly that wall: `SYS` into a loader of zeroes, `BRK` at
    `$0E02`.

    Staging below `$4000` does not rescue it. After the probe's text ends at
    `$26D8` there are 6,439 bytes to `$3FFF` against 6,532 needed for the
    charset and sprites -- 93 bytes short, and worse as the program grows. For
    the full game it is hopeless: the C64 source tokenizes to `$1C01-$422F`, so
    the text alone covers the whole VIC window and the relocation is not
    optional.

    **Therefore in-PRG staging cannot load this edition's assets.** The layout
    itself is sound and unchanged -- the window, the pointer numbering, the
    charset slots all still hold. What has to change is how bytes reach it. See
    the open decision below.
17. **BASIC 7 colours run 1-16 where the VIC registers run 0-15.** `SPRITE
    2,1,0,...` fails with `?ILLEGAL QUANTITY ERROR` because 0 is not a BASIC 7
    colour. Every colour handed to `SPRITE` is therefore the C64 register value
    plus one: the C64 title writes `$D027-$D02E` as 1,0,1,6,1,6,7,15, so BASIC 7
    wants 2,1,2,7,2,7,8,16. Verified by reading the registers back afterwards.

    And the upper nibble of `$D027-$D02E` is unused, reading back as 1s, so
    `$D027` reads `$F1` for colour 1. Same trap as bit 0 of `$D018`: assert the
    field, never the byte. Two register-readback conventions, both of which cost
    a verification cycle to find.
18. **`SPRITE` does not touch the sprite pointers.** Measured immediately after
    eight `SPRITE` calls: `$07F8-$07FF` still held 187, 246, 253, 254, 243, 245,
    195, 244. So the C64 pointer values can be written once and left alone, and
    BASIC 7's own `$0E00` sprite area is never consulted. That is what makes the
    un-renumbered payload workable and what frees `$0E00` for other use.
19. **Direct writes to the VIC sprite coordinate registers do not take effect on
    the C128.** BASIC 7 owns `$D000-$D010` and rewrites them from its own sprite
    table inside the interrupt, so a `POKE` there is discarded within a statement
    or two. Measured:

    ```text
    POKE 53248,124            -> PEEK(53248) reads 0, immediately and after 1s
    MOVSPR 1,124,104          -> PEEK(53248) reads 124, PEEK(53249) reads 104
    POKE 53248,60 afterwards  -> still reads 124; the POKE is ignored
    ```

    This is not a variant of the `$D018`/`$0A2C` shadow, where the write lands
    and is later overwritten. Here the write never lands at all.

    So `MOVSPR` is **mandatory**, not stylistic: the "BASIC 7 native sprites"
    decision is now forced by the hardware rather than chosen for elegance. The
    scope is narrower than it sounds, because the other sprite registers behave
    normally -- measured at the C128 title, with the C64's own `POKE`s
    unchanged:

    | register | C64 `POKE` on the C128 |
    | --- | --- |
    | `$D000-$D010` positions | **discarded**; use `MOVSPR` |
    | `$D015` enable | works (`$FF` observed) |
    | `$D027-$D02E` colour | works (1,0,1,6,1,6,7,15 observed) |
    | `$07F8-$07FF` pointers | works (evidence item 18) |

    Converting the positions is not a mechanical substitution, because `MOVSPR`
    sets both coordinates at once while the C64 code updates X and Y
    independently and manages the `$D010` MSB by hand. `MOVSPR n,x,RSPPOS(n,1)`
    covers an X-only update and `MOVSPR n,RSPPOS(n,0),y` a Y-only one, but the
    high-X logic has to be read rather than rewritten blindly: it is where the
    landing-verdict geometry lives, and that is a stated invariant.
20. **`DS` is a reserved system variable in BASIC 7.** `DS` and `DS$` return the
    disk status, and `ER`/`EL` come with `TRAP`, none of which the C64 reserves.
    The canonical source uses `ds` as the terrain step direction, so
    `src/lunalight.bas:154` runs on the C64 and is a `?SYNTAX ERROR` on the C128
    -- raised only when that line happens to execute, which is why it surfaced
    as a crash out of attract mode rather than at load. `TI` is reserved on both
    machines and the source uses it deliberately as the jiffy clock, so it stays.
21. The C64 editor and keyboard constants, measured with the cursor deliberately
    parked on row 8:

    | C64 use | C64 address | C128 finding |
    | --- | --- | --- |
    | cursor row | `214` / `$D6` | reads 0; the row is at `235` / `$EB` |
    | screen page | `648` | reads 0; carries nothing |
    | screen/charset | -- | `2604` / `$0A2C` holds a `$D018`-format value (`$14`), not a page |
    | shift/ctrl/CBM flag | `653` | reads **255** with no key held, so it is not a shift flag |

    `648` needs no replacement: the screen stays at the C128 default `$0400`, so
    `POKE 648,132` simply has no purpose in this layout. `214` maps cleanly onto
    `235`. `653` is the one that does not map, and it is load-bearing:
    `src/lunalight.bas:31` and `:241` use `PEEK(653)` as an alternate fire and
    an any-key wake, so on the C128 both would read as permanently pressed.
    Finding its replacement needs a probe that can hold a modifier key down,
    which the binary monitor's keyboard-buffer injection cannot do. Open item,
    tracked as verification row 16a.

Useful external references:

- [Commodore 128 Programmer's Reference Guide](https://www.pagetable.com/docs/Commodore%20128%20Programmer%27s%20Reference%20Guide.pdf)
- [C128 MMU memory model](https://www.c64-wiki.com/wiki/Commodore_128/Memory_Model)
- [VICE C128 options](https://vice-emu.sourceforge.io/manual/vice.pdf)

## Memory layout

The C64 build's `$8000` window is abandoned. Everything the VIC needs lives in
VIC bank 0, where no BASIC ROM shadows it, so no `BANK` switching is needed for
any video access.

```text
$0400-$07E7  40x25 text screen                  VIC bank 0, C128 default
$07F8-$07FF  sprite pointers                    preset to 56-63 by the KERNAL
$0E00-$0FFF  sprite images, 8 blocks            BASIC 7 SPRITE/SPRSAV area
$1000-$1FFF  character ROM shadow, VIC side     see the note below
$1300-$1BFF  free bank-0 RAM: machine code      2,304 bytes, no ROM over it
$2000-$3FFF  reserved by GRAPHIC 1              title/flight RAM charsets here
$4001-....   BASIC 7 program text               relocated by GRAPHIC 1
             variables, arrays, strings         RAM bank 1, not bank 0
$D800-$DBE7  colour RAM                         unchanged from the C64
```

Two properties of this layout are worth stating because they remove hazards
rather than relocate them:

- **The gateway RAM is invisible to the VIC.** `$1300-$1BFF` lies under the
  VIC's character-ROM shadow at `$1000-$1FFF`. The CPU sees RAM there; the VIC
  sees character ROM. Machine code and video fetches cannot corrupt each other,
  and no `MEMSIZ`-style guard is needed to keep them apart.
- **Strings cannot reach the screen.** BASIC 7 puts variables, arrays and
  strings in RAM **bank 1**. The C64 `POKE 55/56` string-heap-versus-screen
  collision class does not exist here. Do not port the workaround, and do not
  spend Phase 1 measuring for a hazard that the bank split has already removed.
  The long re-entry test stays in the verification plan as proof, not as a
  hunt.

A RAM character set must sit on a 2 KB boundary inside the VIC's 16 KB window,
which leaves `$2000`, `$2800`, `$3000` and `$3800`. `$1000` and `$1800` are
unusable because the VIC sees character ROM there. All four usable slots are
inside the `GRAPHIC 1` reserve, which is why the reserve is taken even though
this edition draws no bitmap: `GRAPHIC 1:GRAPHIC 0` claims `$2000-$3FFF` and
returns to 40-column text in one statement.

The window is 2,304 bytes against the C64 hole's declared 2,560. Measured, the
helpers need 2,057 and fit with 247 bytes to spare, because the C64 figure
counted the declared hole rather than its contents:

```text
$1300-$14EB  title player           492 bytes  (unchanged from the C64 blob)
$1500-$1735  RNG code               566 bytes  (541 + 25 for the C128 guard)
$1736-$177F  probe results          74 bytes   (free; zero-filled at load)
$1780        wait argument          1 byte     (was $02A7 on the C64)
$1800-$1BFF  RNG table            1,024 bytes  (page-aligned)
```

So no part of the payload has to move to RAM bank 1. That option stays open for
Phase 3 if the table's kilobyte is later wanted for something else.

## Non-negotiable gameplay invariants

The C128 edition may refactor plumbing, but it must preserve these behaviors:

- Original float physics and constants: gravity, thrust deltas, vertical
  position equation, horizontal drift, landing speed gates and +/-90 degree
  rotation limit.
- Landing geometry: pad `px(i)` is its left edge; verdict center is
  `INT(pp)+12` plus 256 when on the high X side.
- Scoring semantics, refuelling, crashes, post-mortem's one-line rule, attract
  behavior, and no high-score updates during attract mode.
- The feature inventory: keyboard + joystick, procedural terrain, pads, flag
  layover, LEM fill, title tableau, command module, title music and RNG.
- The look of the existing VIC build: 40 columns, C64 palette, sprite artwork,
  terrain rows and HUD placement.
- The title theme as the ported player produces it, not a `PLAY` re-scoring.

Do not port the numeric physics to fixed point or change constants merely to
make a native build work. The existing C64 motion oracle is the behavioral
baseline; create a C128-specific equivalent rather than weakening either test.

Switching sprite plumbing to `SPRITE`/`MOVSPR`/`BUMP` is a plumbing change, not
a behavior change: the same sprite is enabled in the same colour at the same
coordinate, and the verdict arithmetic above is untouched. The `SPRITE_CENTRE_OFFSET`
of 12 still applies, because it describes the artwork, not the register.

## Proposed repository shape

Add new files without changing the roles of existing C64 paths. Phase 0 files
exist; the rest are planned.

```text
src/c128/phase0.bas             Native bootstrap probe                DONE
src/c128/helper.s               $1300 gateway: MMU window, IRQ chain  DONE
tools/c128-helper.cfg           ld65 config for the gateway           DONE
tools/c128-build.py             Build driver; never invokes Blitz!    DONE
tools/verify-c128-vic.py        Native-C128 checks under x128         DONE
docs/c128-vic-design.md         This document                         DONE
src/c128/phase1.bas             Native runtime-model probe             DONE
src/c128/phase2.bas             VIC asset and title-tableau probe      DONE
tools/c128-asset.py             Headers and truncates one asset file   DONE
tools/c128-music.cfg            Player linked into the gateway window  DONE
tools/c128-rng.cfg              RNG and its table, same window         DONE
tools/c128-parity.py            Proves the C64 helper blobs unchanged  DONE
tools/c128-port.py              Generates the C128 BASIC source          DONE
build/c128-lunalight.bas        Generated; never hand-edited, never committed
```

There is deliberately no `src/c128/music.s` or `src/c128/rng.s`. The two
editions **share** `src/music.s` and `src/rng.s` and differ only by
assembly-time defines:

```text
C64    ca65 src/music.s                              -> $4200
C128   ca65 -D LOAD_ADDR=$1300 src/music.s           -> $1300
C64    ca65 src/rng.s                                -> $4400, table $4800
C128   ca65 -D C128=1 -D LOAD_ADDR=$1500 \
            -D WAITJ=$1780 src/rng.s                 -> $1500, table $1800
```

A fork would let the title theme and the PRNG drift apart silently, which is
exactly what the identity invariants forbid. The cost is C128 conditionals
inside files the canonical C64 build depends on, so `make c128-parity` re-links
both helpers with no defines at all and requires the result to be byte-identical
to the packaged C64 blobs. It runs as the first step of `make verify-c128-vic`.

C128 artifacts are distinguishable:

```text
build/lunalight-c128-phase0.prg   Phase 0 bootstrap probe             DONE
build/c128-phase0-layout.json     Machine-readable layout report      DONE
build/lunalight-c128-vic.prg
build/lunalight-c128-vic.d71      Optional, only after PRG boot is proven
```

## Implementation strategy

### Phase 0: prove a native bootstrap -- COMPLETE

`make c128-vic && make verify-c128-vic` builds and verifies
`build/lunalight-c128-phase0.prg`. All six original Phase 0 requirements are
met, each by an assertion rather than an assumption:

1. starts from a valid BASIC 7 `$1C01` stub -- the builder rejects any other
   load address;
2. 40-column VIC display selected -- `$D7` is asserted 0, and the probe calls
   the KERNAL `SWAPPER` at `$FF5F` (`SYS 65375`) if it comes up in 80 columns;
3. MMU/VIC RAM-bank state established -- `$D506` bits 6-7 and `$DD00` bits 0-1
   are asserted, not assumed;
4. text placed in the VIC screen at `$0400`;
5. a machine-code helper installed, entered, and returned from, including a
   round trip through an all-RAM configuration and a read of RAM under BASIC
   ROM; and
6. boots under `x128 +go64` in native mode.

The chosen mapping and its restore path are documented in the header of
`src/c128/helper.s` and in the Memory layout section above.

Phase 0 also proved two things beyond its original brief, both of which change
later phases: the `GRAPHIC 1` text relocation survives a running program, and
`MOVSPR` handles the X MSB.

### Phase 1: establish the native source/runtime model -- COMPLETE except 653

`make c128-vic && make verify-c128-phase1` builds and verifies
`build/lunalight-c128-phase1.prg`. The ported player and RNG live in the gateway
window, the wait argument is re-homed, the charset slots work, and the player
coexists with `BUMP(2)` and `MOVSPR`. The one item not closed is the `653`
replacement, for the reason given in evidence item 15.

Start with BASIC 7 because it preserves the original float expressions and
makes semantic comparison practical. A native BASIC compiler may be evaluated,
but original Blitz! is explicitly not a C128 compiler and must not be repurposed
or replaced in the C64 pipeline.

Port only the C64-specific runtime assumptions first:

- delete the `$37/$38` `MEMSIZ` manipulation; RAM bank 1 replaces it;
- re-home the `$02A7` (decimal 679) argument byte. Seven sites pair
  `POKE 679,n` with `SYS 17420` to select a sound effect; `$02A7` is not free
  low memory on the C128, so the ported helper takes its argument from an
  address inside `$1300-$1BFF`;
- replace the C64 editor and keyboard constants per the measured table in
  evidence item 21: drop `648` entirely, map `214` onto `235`, and treat `653`
  as an open item rather than a translation;
- give the title music, RNG and fixed-jiffy wait helper native C128 entry
  points inside the gateway window; and
- make the title/flight character-set switch explicit, using two of the four
  2 KB slots inside the `GRAPHIC 1` reserve, and switch it through the `$0A2C`
  shadow rather than `$D018` alone (evidence item 15).

Do not execute BASIC ROM by accident: every `SYS` target must be inside
`$1300-$1BFF`, which the builder enforces.

### Phase 1a: port the title player

The player is ported rather than re-scored. Three things make it a port and not
a rewrite:

- **It already chains.** `src/music.s` saves `$0314/$0315` into `old_irq` and
  ends with `jmp (old_irq)`. The C128 keeps the KERNAL IRQ vector at `$0314`,
  so the install/uninstall structure transfers unchanged, and Phase 0 verified
  a chained handler ticking and freezing again on restore.
- **Chaining is now mandatory, not merely polite.** BASIC 7 services sprite
  motion and accumulates the sprite collision latches that `BUMP()` reports
  from inside the KERNAL interrupt, so a player that replaced the vector rather
  than chaining would be expected to silence `BUMP(2)` and freeze `MOVSPR`
  speeds. Phase 0 proved the chained case works and that `BUMP(2)` latches; it
  did **not** measure the replacing case. Verification check 10 exists to make
  that a measurement instead of an inference. Until it runs, treat "must chain"
  as a design rule, not as evidence.
- **The tempo constant survives.** `step_ticks = 22` assumes a 60 Hz
  CIA-driven KERNAL interrupt on PAL and NTSC alike. The C128 KERNAL also
  drives its interrupt from CIA 1 at 60 Hz. Verify the rate before trusting
  the 17.6 s loop length the attract hand-off is tied to.

What must change: the load address and the `SYS` entry points move out of
`$4200` into the gateway window, and the SID equates stay as they are because
the SID is at `$D400` in native mode.

### Phase 2: port VIC assets and flight -- assets and title tableau DONE

The asset *layout* is settled and better than the doc originally assumed. The 61
distinct sprite slots the game pokes span pointers 187-254, which in VIC bank 0
resolve to `$2EC0-$3FBF`, inside the `GRAPHIC 1` reserve. A 2 KB title charset at
`$2000` takes pointers 128-159 and collides with none of them. So:

- **the C64 pointer numbering carries over unchanged**, and an attitude change
  stays a single pointer `POKE` rather than the 64-byte block copy this document
  previously budgeted for;
- **the sprite payload is used un-rebased.** `build/lsprite-shapes.prg` already
  loads at `$2E7C`, which is its VIC bank 0 home; the `$AE7C` rebase exists only
  to reach bank 2 on the C64, so the C128 reuses the payload more literally
  byte-for-byte than the C64's own bank-2 build does;
- **only one RAM character set is needed.** Flight uses the character ROM at
  `$1000` (`$D018` `$14`, the C128 default, matching the C64's `$9000` char-ROM
  shadow in bank 2); only the title needs RAM, at `$2000` (`$D018` `$18`);
- the payload's last 116 bytes fall in pointer slots 256 and above, which an
  8-bit pointer cannot reach, so the builder drops them and says so.

### Resolved: assets reach the window from disk

Evidence item 16 forced this. `GRAPHIC 1` clears everything above `$4000`, the
destinations sit under the load-time BASIC text, and below `$4000` there is not
enough room to stage them -- 93 bytes short even for the probe, and hopeless for
the full game whose text alone covers `$1C01-$422F`. In-PRG staging cannot
deliver these assets.

So the edition loads them the way the C128 was designed to: `GRAPHIC 1` first,
then one `BLOAD` per region straight to its address in bank 0.

```basic
graphic1:graphic0
bload"music",b0,p4864     : rem $1300
bload"rng",b0,p5376       : rem $1500
bload"charset",b0,p8192   : rem $2000
bload"sprites",b0,p11900  : rem $2E7C
```

Each asset ships as a PRG already headered with its destination, so the `P`
parameter and the file header agree. `tools/c128-asset.py` stamps the header and
performs the one truncation the payload needs.

This makes the disk image a **prerequisite**, not packaging polish, and
"disk format is not a prerequisite for gameplay" is withdrawn as falsified. The
compensation is that the artifact the definition of done prefers -- a
self-booting disk -- is now on the critical path rather than deferred behind it.
An autoboot sector is the remaining piece; `-autostart image.d71:phase2` stands
in for it during verification.

### Measured: interpreted BASIC 7 is far too slow, and that is the real blocker

The canonical C64 artifact is **compiled** with Blitz!. The C128 port is
interpreted, and that difference dominates everything else. Measured on the
ported disk under `x128 +go64`:

- terrain generation draws about **5.6 cells per second** and takes roughly
  **50 seconds** for a 273-cell field. The compiled C64 build does it in a
  second or two.
- flight is reached about 70 seconds after F7.

A micro-benchmark in a program padded to the same length as the port, so the
line-search cost is realistic, shows where it goes:

| operation | per second | each |
| --- | --- | --- |
| empty `FOR` iteration | 472 | 2.1 ms |
| `POKE` | 90 | 11.1 ms |
| `PEEK` into a variable | 98 | 10.1 ms |
| `pk=1504+ii*40` | 73 | 13.7 ms |
| backward `GOSUB` | 49 | 20.1 ms |

These are ordinary interpreted-CBM-BASIC figures, made worse by BASIC 7 keeping
every variable in RAM bank 1 behind a bank-switched fetch. There is no defect to
fix here: the terrain inner loop runs roughly fifteen statements per cell, and
fifteen statements at these rates *is* 5.6 cells per second.

So the risk row "BASIC 7 flight is slower than C64 Blitz" is now measured rather
than anticipated, and the decision it defers has to be taken. Note what is
**not** available: `tools/BLITZ.d64` is a C64 compiler and this document already
forbids repurposing it, and MOSpeed compiles BASIC V2, which cannot handle the
`GRAPHIC`, `BLOAD`, `SPRITE`, `MOVSPR`, `BUMP`, `CHAR` and `BANK` statements the
port depends on. FAST mode is worth at most 2x and only with the screen blanked,
which the terrain step could use but flight cannot.

### Phase 2b: the flight port -- title renders, flight BLOCKED

`src/c128/lunalight.bas` does not exist and deliberately never will. Keeping a
hand-edited copy of a 250-line BASIC program beside the original is how a port
and its source drift apart, and the invariants forbid exactly that. The C128
program is **generated** instead: `tools/c128-port.py` applies an explicit,
commented rule set to `src/lunalight.bas` and fails the build if a C64 constant
survives or a BASIC 7 reserved variable is assigned to. `make c128-vic` produces
`build/lunalight-c128-vic.d71`.

What works: the disk boots into the title under `x128 +go64`, the licence and
contributor text, the star field, `PRESS F7 TO START`, `$D015` = `$FF`, the
title character set at `$2000`, the eight C64 sprite pointers, and the C64
title colours 1,0,1,6,1,6,7,15 read back exactly.

What does not: flight is unusably slow (see the measurement above), and every sprite is at X=0 because of evidence item 19 -- the C64's
position `POKE`s are discarded. The title tableau is therefore unpositioned and
flight cannot be assessed until the positions go through `MOVSPR`. That is the
next piece of work, and it is the first one in this port that touches gameplay
logic rather than plumbing, so it needs the motion oracle alongside it rather
than after it.

### Phase 2 bring-up order, once unblocked

Re-use `sprites/lsprite.prg` and `tools/make-shapes.py` output byte-for-byte
where possible. The allowed changed sprite slots remain exactly the established
spare slots. Do not redraw the original sprite payload.

The sprite payload is re-homed, not re-rebased to `$AE7C`: BASIC 7 reads sprite
images from `$0E00-$0FFF`, which holds exactly the eight live shapes. The C64
build's pointer table of 8 slots drawn from a much larger payload becomes a
copy step: the shape needed in a slot is written into that slot's 64 bytes,
which is what `SPRSAV` and a `POKE` loop both do. Attitude changes that were a
pointer write on the C64 become a 64-byte block copy on the C128; measure that
cost during Phase 2 before committing to it, because it lands in the flight
loop.

Bring up the display in this order:

1. screen and PETSCII terrain at `$0400`;
2. sprite images and Earth sprites, via `SPRITE`;
3. LEM outline/fill/exhaust;
4. two-sprite white-on-blue flag;
5. title RAM charset/tableau inside the `GRAPHIC 1` reserve; and
6. `BUMP(2)` latch, landing and explosion.

The high-X rules are relaxed here, on Phase 0 evidence: `MOVSPR` accepts a
0-511 X, so the command module is no longer confined below X=256 and the
`$D010` bit-7 trap does not apply. Sprite *assignments* stay as they are.

### Phase 3: use the extra RAM deliberately

Extra C128 RAM is optional for the first playable build. RAM bank 1 already
carries every variable, array and string, so the first real use of "extra RAM"
is not a feature, it is the reason the string-heap hazard is gone.

If more is used, use it for non-VIC working data: terrain-generation buffers,
replay/attract state, precomputed title data, staging assets, or the RNG table
if the gateway window proves too tight. Do not move live VIC screen or sprite
data out of VIC bank 0.

The edition is successful without an additional gameplay feature. A larger map,
more sprites, bitmap graphics or VDC support are separate proposals.

## Build and packaging requirements

- `make c128-vic`, `make run-c128-vic` and `make verify-c128-vic` exist and do
  not change the meaning of `make`, `make blitz`, or any existing C64 target.
- Use `x128` with `+go64` so the machine stays in C128 mode across the reset,
  and 40-column display mode for C128 checks. `x128 -console` plus its binary
  monitor is suitable for headless verification.
- `tools/c128-build.py` rejects overlapping regions, rejects a gateway that
  escapes `$1300-$1BFF`, rejects a BASIC load address other than `$1C01`, and
  writes `build/c128-phase0-layout.json`.
- Phase 0 embeds the gateway as BASIC `DATA`, so the artifact is one ordinary
  BASIC 7 program with no custom loader. 2,057 bytes of helper would need about
  8 KB of `DATA` text, so Phase 1 switched to a **staged payload**: the builder
  pads the PRG out to a fixed stage address, appends the payload image there,
  and the BASIC program's first action copies it down into `$1300-$1BFF`.
  No loader, so no address that has not been proven.
- **The staged copy must run under `BANK 0`.** The stage sits above the BASIC
  text, therefore under BASIC LO ROM, so a `BANK 15` `PEEK` of the stage returns
  ROM instead of the payload that was just loaded there. This is evidence item 7
  biting in practice: the first Phase 1 run copied 2,278 bytes of BASIC ROM into
  the gateway window and hung in the RNG's TOD wait. `BANK 0` for the loop and
  `BANK 15` immediately after is the whole fix, and it is the pattern every
  future access to staged data must follow.
- The copy loop is interpreted BASIC and takes a couple of seconds. That is a
  one-time title-screen cost and buys the absence of an unproven loader; revisit
  it only if it lands somewhere the player notices.
- The artifact is a `.d71`, built with `c1541`, carrying the BASIC program and
  one PRG per asset region. This is a prerequisite rather than a final flourish,
  for the reason given under "Resolved: assets reach the window from disk".
  A C128 autoboot sector is the one remaining piece; until it lands,
  `-autostart image.d71:progname` stands in.
- Never use `make -j` for emulator-driven checks. The Makefile is
  `.NOTPARALLEL`.

## Verification plan

`tools/verify-c128-vic.py` is C128-specific and shares no address assumptions
with `verify-bank2.py`. Its checks, and their state:

| # | Check | State |
| --- | --- | --- |
| 1 | native boot: BASIC 7 at `$1C01`, `+go64`, no `GO64` path | done |
| 2 | 40-column VIC screen at `$0400`, `$D7` = 0 | done |
| 3 | `$D018`, `$DD00` bits 0-1, `$D506` bits 6-7, `$D505` | done |
| 3a | charset switch survives an interrupt via the `$0A2C` shadow | done |
| 4 | `GRAPHIC 1` relocation: `TXTTAB` `$1C01` -> `$4001` | done |
| 5 | RAM under ROM: `BANK 15` vs `BANK 0` vs the `$FF00` window | done |
| 6 | gateway entered, returned, `$FF00` restored, I/O intact | done |
| 7 | IRQ chain installs, ticks, and freezes on restore | done |
| 8 | `$0E00` sprite area selected; `MOVSPR` X above 255; `$D010` MSB | done |
| 8a | `BUMP(2)` reports a forced sprite-background hit | done |
| 9 | all eight sprite pointers, positions, colours and MSBs | Phase 2 |
| 10 | title music install/uninstall leaves `BUMP()` and `MOVSPR` working | Phase 1a |
| 11 | RNG and all jiffy waits execute and return | Phase 1 |
| 12 | one controlled flight, motion samples against a C128 oracle | Phase 2 |
| 13 | controlled landing, crash/`BUMP(2)`, refuel and explosion | Phase 2 |
| 14 | attract entry/exit and high-score suppression | Phase 2 |
| 15 | long re-entry test: strings in bank 1 cannot reach bank-0 video | Phase 2 |
| 16 | joystick reads at `$DC00` survive the C128 keyboard scan | done |
| 16a | a C128 replacement for `PEEK(653)`, needing a held-modifier probe | **open** |
| 17 | interpreted wait is exact at two different counts (no 6/5 error) | done |
| 18 | player publishes its loop length in C128 jiffies | done |
| 19 | the C64 helper blobs are byte-identical to their pre-C128 hashes | done |

Every check prints its observed value, so a failure names the offending
register or address instead of only the expectation.

The C64 suite (`make verify-blitz-gameplay`) must still pass unchanged after
every C128 change. Do not re-record the C64 motion fixture or relax C64 test
tolerances.

## Definition of done for the first C128 milestone

The first milestone is complete when all of the following are true:

- A native-C128 VIC artifact reaches the title without entering C64 mode. For
  a PRG that means `LOAD` then `RUN`; a self-booting `.d71` closes this item
  outright and is the preferred form.
- Flight, landing, crashing, refuelling, score/lives, pause, F7 restart and
  attract mode work with the same visible rules as the C64 build.
- The full eight-sprite flight/title budget, including flag layover, LEM fill
  and command module, is present.
- The C128 verifier passes under `x128 +go64` in 40-column mode.
- The canonical C64 build and all its verification gates remain unchanged and
  passing.
- The C128 memory layout and MMU gateway are documented in the README or a
  dedicated C128 section before the target is presented as playable.

## Risks and decisions that require evidence

| Risk | Required response |
| --- | --- |
| BASIC 7 flight is slower than C64 Blitz | **Measured, and it is decisive**: 90 POKEs and 49 backward GOSUBs per second, terrain generation 50s against the compiled C64's one or two. The canonical C64 build is compiled and the port is interpreted. A playable C128 edition needs either a C128 BASIC compiler or the hot loops in machine code; neither `tools/BLITZ.d64` nor MOSpeed can do it. Decision pending. |
| ~~Attitude changes become 64-byte copies~~ | Closed. The used slots 187-254 land at `$2EC0-$3FBF` inside the reserve, `SPRITE` does not touch the pointer table, and the payload is used un-rebased, so a shape change stays one `POKE`. |
| ~~Gateway window is 256 bytes too small~~ | Closed by measurement. The helpers assemble to 2,057 bytes against the window's 2,304; the C64 figure of 2,560 was the declared hole, not its contents. |
| The 50 Hz interrupt breaks other C64 timing assumptions | `wait` and `step_ticks` are fixed and verified. Audit anything else that counts interrupts or treats a tick as a jiffy before Phase 2, and measure NTSC separately. |
| `PEEK(653)` reads 255 on the C128, so the alternate fire is stuck on | Open. Do not ship the C128 edition with `653` in the input path; verification row 16a must land first. |
| A ported player replaces the IRQ instead of chaining | Rejected on design grounds: `BUMP()` accumulation and `MOVSPR` motion both run in the KERNAL interrupt. Not yet measured; verification check 10 must confirm it before the claim is treated as evidence. |
| `SOUND`/`PLAY`/`VOL` mixed into the build | Rejected. They rewrite SID registers the ported player owns. Effects stay in the ported helper. |
| C128 keyboard scan interferes with `PEEK(56320)` joystick reads | Add verification check 16 before trusting the joystick path; the C128 scans more key lines than the C64. |
| C128 character ROM differs from the C64 font used by the title builder | Capture/verify the native VIC charset, then regenerate only the title charset if necessary. Preserve custom title glyph design. |
| 2 MHz is proposed as a flight optimization | Reject it for this VIC-IIe edition; it disables the visible 40-column display. |
| Staged data is assumed to survive `GRAPHIC 1` | It does not, above `$4000`. Anything the relocation must not eat has to live below `$4000` or come off disk after the fact. |
| A VIC register write is assumed to land | Sprite positions do not land at all; `$D018` lands and is then overwritten. Neither can be asserted by reading straight back, and neither is safe to POKE. Check the register through VICE's `io` bank, not the CPU bank, or the read returns character ROM. |
| A `$D018` write is assumed to stick | The editor's interrupt reloads it from `$0A2C`. Write the shadow, and never assert a video register immediately after writing it; wait an interrupt first. |
| A change also modifies C64 behavior | Stop and separate the code paths. The C64 canonical game has priority. |

## Explicit non-goals

- A VDC/80-column port.
- A C64-mode wrapper marketed as native C128 software.
- Replacing the original Blitz! toolchain for the canonical C64 build.
- Fixed-point physics, rewritten collision rules, or altered scoring to simplify
  the port.
- Re-scoring the title theme with `PLAY`/`ENVELOPE`.
- New gameplay content justified solely by the C128's extra RAM.
