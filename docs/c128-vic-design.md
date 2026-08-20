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

Items 1-5 were the pre-Phase-0 desk analysis. Items 6-13 are measured, and
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

The 2,304 bytes of gateway RAM are 256 bytes short of the C64's
`$4200-$4BFF` hole. The ported music player, RNG and jiffy-wait helper must fit
in `$1300-$1BFF` together, or the RNG's 1 KB table must move to RAM bank 1 and
be read through the `$FF00` window. Measure the assembled sizes before
choosing; do not assume the C64 layout transfers.

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
src/c128/lunalight.bas          Native BASIC 7 gameplay/control source
src/c128/music.s                C128 port of the title player
src/c128/rng.s                  C128 port of the RNG/wait helper
src/c128/loader.s              Loader for the real helper blobs, once DATA
                               embedding stops being big enough
```

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

### Phase 1: establish the native source/runtime model

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
- replace/encapsulate direct C64 editor/screen cursor locations (`648`, `214`)
  and keyboard state locations (`653`) after confirming their C128 meanings;
  `POKE 648,132` in particular has no purpose in this layout, because the
  screen stays at the C128 default `$0400`;
- give the title music, RNG and fixed-jiffy wait helper native C128 entry
  points inside the gateway window; and
- make the title/flight character-set switch explicit, using two of the four
  2 KB slots inside the `GRAPHIC 1` reserve.

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

### Phase 2: port VIC assets and flight

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
  BASIC 7 program with no custom loader. That stops scaling once the real
  music and RNG blobs are involved; `src/c128/loader.s` takes over then.
- The initial artifact is a PRG. A PRG cannot self-boot: reaching the title
  still costs a `RUN`. A `.d71` with a C128 autoboot sector is the only way to
  get a true boot, and it is the last milestone-1 item, not a prerequisite.
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
| 16 | joystick reads at `$DC00` survive the C128 keyboard scan | Phase 1 |

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
| BASIC 7 flight is slower than C64 Blitz | Measure motion/timing first. BASIC 7's interpreter loop and its heavier KERNAL interrupt both cost more per statement than BASIC 2, and `SPRITE`/`MOVSPR` shift work from POKEs into the interpreter. Do not alter physics; choose a C128-native compiler or a tightly scoped helper only after an evidence-backed decision. |
| Attitude changes become 64-byte copies | The C64 build swaps a sprite pointer; `$0E00` holds only eight live shapes, so a shape change is a block copy. Measure it in the flight loop in Phase 2; a pointer-swap scheme inside `$0E00-$0FFF` is the fallback. |
| Gateway window is 256 bytes too small | `$1300-$1BFF` is 2,304 bytes against the C64 hole's 2,560. Measure the assembled music and RNG sizes; move the 1 KB RNG table to bank 1 behind the `$FF00` window if needed. |
| A ported player replaces the IRQ instead of chaining | Rejected on design grounds: `BUMP()` accumulation and `MOVSPR` motion both run in the KERNAL interrupt. Not yet measured; verification check 10 must confirm it before the claim is treated as evidence. |
| `SOUND`/`PLAY`/`VOL` mixed into the build | Rejected. They rewrite SID registers the ported player owns. Effects stay in the ported helper. |
| C128 keyboard scan interferes with `PEEK(56320)` joystick reads | Add verification check 16 before trusting the joystick path; the C128 scans more key lines than the C64. |
| C128 character ROM differs from the C64 font used by the title builder | Capture/verify the native VIC charset, then regenerate only the title charset if necessary. Preserve custom title glyph design. |
| 2 MHz is proposed as a flight optimization | Reject it for this VIC-IIe edition; it disables the visible 40-column display. |
| A change also modifies C64 behavior | Stop and separate the code paths. The C64 canonical game has priority. |

## Explicit non-goals

- A VDC/80-column port.
- A C64-mode wrapper marketed as native C128 software.
- Replacing the original Blitz! toolchain for the canonical C64 build.
- Fixed-point physics, rewritten collision rules, or altered scoring to simplify
  the port.
- Re-scoring the title theme with `PLAY`/`ENVELOPE`.
- New gameplay content justified solely by the C128's extra RAM.
