# lunalight

Commodore 64 lunar lander by Steven Hardison (public domain).

Canonical playable source is **`src/lunalight.bas`**, promoted from dad's latest
BASIC-only working binary [`current/luna081426`](current/luna081426) (`luna2`)
and then optimized for uncompiled BASIC V2. "BASIC-only" means the program was
playable without being compiled to machine code.

## Sources

| File | Role |
| ---- | ---- |
| [`src/lunalight.bas`](src/lunalight.bas) | **Canonical** game (joystick, procedural terrain, Moon/Mars, fixed-point physics) |
| [`src/music.s`](src/music.s) | IRQ-driven 6502 soundtrack player and SID voice 2 score |
| [`src/rng.s`](src/rng.s) | CIA TOD entropy collector and the PRNG table the terrain draws from |
| [`current/luna081426`](current/luna081426) | Dad's `luna2` tokenized PRG — latest BASIC-only playable baseline |
| [`current/luna081426-old`](current/luna081426-old) | Earlier `LUNAON4A` tokenized PRG (historical; superseded by `luna2`) |
| [`current/lsprite`](current/lsprite) / [`sprites/lsprite.prg`](sprites/lsprite.prg) | Sprite shapes at `$2E7C` |
| [`src/lunalight-m3x1.bas`](src/lunalight-m3x1.bas) | Reference: 2024 M3X1 rewrite |
| [`src/lunalight-experimental.bas`](src/lunalight-experimental.bas) | Reference: 2024 LUNAON1 fork |
| [`src/lunalight-1985.bas`](src/lunalight-1985.bas) | Reference: 1985 LIST decompilation (joystick semantics) |
| [`src/LUNALIGH.D64`](src/LUNALIGH.D64) | Historical 1985 disk image |

Source text is lowercase: `petcat` maps lowercase ASCII to PETSCII uppercase.

## What changed vs `luna2`

Behaviours kept from the `luna2` baseline:

- **Rotation limiter:** tilt stops at 90° either side of upright (sprites `187`–`189` and `193`–`194`). Inverted-thrust handlers for unreachable orientations are omitted.
- **Soft landing:** horizontal velocity may be in `-2..2` at touchdown; only `|hm| > 2` crashes.
- **Horizontal wrap:** screen-edge wrap carries the overshoot remainder instead of snapping to a fixed column.

Additions and optimizations beyond that baseline:

- **Explosion:** sprite pointers `203/213/223/233` assigned before enabling explosion sprites; each frame updates pointers before the delay (removes first-frame garbage).
- **Joystick port 2:** `PEEK(56320)` for tilt (left/right) and fire; keyboard `{rght}`/`{down}` and `PEEK(653)` remain as fallbacks. (`luna2` declared `js` but never read it.)
- **Hot loop:** physics steps follow jiffy `TI` with catch-up capped at 3; HUD labels drawn once; velocity/fuel/horz digits and colors update only when values change. Hot variables are created first (BASIC scans its variable table linearly) and the VIC registers poked every step are held in pre-computed variables.
- **HUD:** all three readouts sit in a four-cell field at columns 35–38, right-aligned on column 38, so fuel's four digits no longer overhang the label by a column. Colour bands follow `luna2`: velocity green below 3, yellow up to `sl`, red above; fuel green at 400+, yellow below that, red below 100; horizontal green at zero, yellow inside the ±2 landing tolerance, red beyond it. A screen-code POKE does not touch colour RAM, so the label row and the digit row are recoloured across the whole field — colouring only the field's first cell left it invisible, because that cell is the leading pad space of a right-justified number.
- **Physics scale:** uncompiled BASIC V2 sustains only about 1.5 physics steps per second, so motion is scaled per *step*, not per jiffy. Velocity stays in tenths; each step moves the lander `m2*ka` pixels (`ka=.03`) and adds `gv` tenths of velocity: Moon `gv=20`/`th=20`, Mars `gv=46`/`th=34`. Horizontal drift moves `hm` pixels per step. Safe touchdown speed is `sl=5` (Moon) / `8` (Mars).
- **Landing verdict:** velocity is re-read at touchdown instead of reusing the HUD copy, which could be up to three steps stale. Pads right of x=255 now register, since the check adds the sprite X MSB rather than truncating to `pp`.
- **Message row:** the bonus/points banner on row 8 is blanked with a 40-space string, not `SPC(40)`. On the C64, `SPC` emits cursor-rights and erases nothing, so the old banner survived into the next flight and the lander latched a background collision when it fell through it.
- **Terrain:** short SID-random mountain segments form stepped ridges and valleys; two high pads, two low pads, and one middle pad are generated once per new game; landing uses pad metadata (`px/pw/py/pb/rf/ph`). (`luna2` used static PRINT art.) Terrain bytes come from the entropy collector in `src/rng.s`, seeded from the CIA TOD phase; see "Where the randomness comes from" below.
- **Pad colours:** yellow edge cells and green interior, as `luna2` did at line `1790`. Pads here are 3–4 cells rather than a fixed 5, so a 3-cell pad reads yellow-green-yellow.
- **Refuel flag:** the pad that refills the tanks carries a cyan flag on sprite 4, Y-expanded so its 42-pixel mast stands clear above the lander with the base resting on the pad line. It has to be a sprite, not a character: line 470 latches a crash on any sprite-0 background collision, so a glyph in the row above the pad would destroy the lander on approach. A sprite is safe because only bit 0 of `$D01F` is read and sprite-sprite collision at `$D01E` is never read. The explosion borrows sprites 4–7, so line `1210` re-establishes the flag's pointer, position, colour, Y-expansion and multicolour bit after every landing or crash, and the `$D010` writes carry the flag's X-MSB bit in `fm`/`fh` rather than the old literals `0`/`243`.
- **Crash post-mortem:** every crash prints a cause line derived from the impact (crater depth scaled by touchdown velocity, cartwheel distance by drift, tilted attitude, or landing off a pad) followed by one of thirteen consequence gags read from `DATA` at 2100. Several riff on Atari Lunar Lander's megabuck-lander, crater, lost-fuel and no-survivor reports without copying its wording. The index comes from the jiffy clock at `$A2`, not SID oscillator 3: the message routine resets the SID for each character's blip, so an `osc3` read at that point is effectively constant and always picked the same gag.
- **Planets:** title `F5` Moon / `F3` Mars / `F7` start.
- **Attract mode:** after 20 seconds without input, an autopilot demonstrates the selected planet using normal physics and fuel. It targets a different pad on every attempt, spawns within 56 pixels of it, cruises in a band that clears the tallest ridge until it is aligned, then descends straight down. It aims at the pad's left cell rather than its centre, because the lander sprite is exactly three cells wide and any overhang strikes the neighbouring cell before the pad. Any keyboard or joystick input returns to the title.
- **Soundtrack:** a PAL/NTSC-adjusted sawtooth melody runs from the KERNAL IRQ on SID voice 2, leaving voice 1 for effects and voice 3 as noise for the entropy collector to mix. Its ~38-second form is a 32-step C-minor theme, a distinct 16-step octave-up bridge with a brighter resonant filter and held peak, then a 32-step reprise. A one-frame gate restart softly articulates each note without the earlier long envelope gaps. Waveform, envelope, filter and master volume are rewritten every frame so the BASIC blip routine (which zeroes all of `$D400-$D418`) can only interrupt the music for one frame.

## Controls

| Input | Action |
| ----- | ------ |
| Joystick 2 left/right or `{down}`/`{rght}` | Rotate lander (limited to 90° either side of upright) |
| Joystick 2 fire or space (`PEEK(653)`) | Thrust |
| `F1` | Pause / resume |
| `F5` / `F3` | Select Moon / Mars (title) |
| `F7` | Start / restart after game over |
| Any input | Leave attract mode and return to the title |

## Build / run (VICE)

```bash
make            # build/lunalight-full.prg (BASIC + sprites + music)
make prg        # tokenized BASIC only
make run        # x64sc autostart
make smoke      # warp headless screenshot
make bench      # normal-speed short run + screenshot
make clean
```

Plain `.prg` without sprite embed shows garbage lander shapes. Always use `*-full.prg`.
The full build requires the `ca65` and `ld65` tools from cc65.

[`tools/make-flag.py`](tools/make-flag.py) patches the refuel-pad flag into spare sprite
slot 243 (`$3CC0`) of `lsprite.prg` on the way through, leaving the original asset
untouched. The shape is ASCII art in that file, so it can be redrawn without a sprite editor.

## Baseline notes

| Metric | `luna2` baseline | Optimized |
| ------ | ---------------- | --------- |
| Main loop HUD | Full `{rght}` PRINT chains every iteration | Change-only POKE digits and colour |
| Landing pads | Five fixed 5-cell pads, yellow edge / green interior | Procedural 3–4 cell pads, same colours, flag on the refuel pad |
| Input | Keyboard only (`js` unused) | Port 2 + keyboard |
| Terrain | Static PRINT art | SID-random ridges and high/low pads once per new game |
| Gravity | Float `.1`/`/20` | Integer tenths; Moon/Mars table; per-step scale |
| Rotation | ±90° limiter | Same limiter; dead inverted-thrust code removed |
| Soft landing | `|hm| ≤ 2` | Same tolerance |
| Horizontal wrap | Overshoot remainder | Same wrap math |
| Explosion frame 0 | Pointers after sprite enable | Pointers before enable |

`make smoke` reaches the title screen. Gameplay verification uses attract-mode warp runs; `make bench` exercises normal-speed boot.

## Verification tools

| Tool | Use |
| ---- | --- |
| [`tools/attract-sim.py`](tools/attract-sim.py) | Replays the terrain generator, physics and pixel-level sprite/background collision in Python, so autopilot and physics changes can be checked over hundreds of landings before spending emulator time |
| [`tools/readscreen.py`](tools/readscreen.py) | Decodes a VICE screenshot back into C64 text by matching the character ROM, so HUD values can be read exactly instead of eyeballed |

Note that the lander collides with *any* character on screen, so debug text printed
below row 7 causes false crashes.

## Where the randomness comes from

The generator does not use BASIC V2 `RND`, and it no longer reads SID oscillator
3 directly. [`src/rng.s`](src/rng.s) collects entropy and fills a 1024-byte
table that BASIC indexes with a single `PEEK`:

| Address | | |
| --- | --- | --- |
| `$4400` / `17408` | `collect` | start the clocks, absorb 32 TOD transitions, then refill |
| `$4403` / `17411` | `refill` | regenerate the table from the current state |
| `$4406` / `17414` | `stir` | absorb one cheap sample; called on human input |
| `$4409` / `17417` | `starttod` | start the TOD alone (diagnostic) |
| `$4800` / `18432` | `table` | 1024 random bytes |

Line 1072 calls `collect` once when the title is drawn, line 1105 calls `refill`
and resets the index `ri` before each terrain, and line 1900 is now just
`rv=peek(rb+ri):ri=ri+1`. A terrain needs at most 654 draws, comfortably inside
the table, but **that budget is what makes the table size safe** — adding draws
per column or per cell can push it past 1024 and start reading whatever follows.

The entropy itself is the phase between CIA1's TOD and CIA2 timer B. This
matters because the TOD pin is clocked from the 50/60Hz mains and everything
else the machine can read — raster, jiffy clock, SID oscillator 3 — is a
function of elapsed cycles and so repeats exactly on a cold boot. The mains and
the system crystal are independent oscillators, which makes their relative phase
at power-on the only true entropy available. Timer B's two bytes, the raster and
oscillator 3 are all mixed in at each transition.

Collection blocks for 3.2-3.8 seconds (32 TOD tenths; the spread is because CIA
control register A bit 7 defaults to expecting 60Hz while a PAL machine supplies
50Hz), which is why it sits on the title screen. Line 1072 is placed *before*
line 1075 deliberately: the `F5`/`F3` planet toggles at lines 1080 and 1085 jump
back to 1075, so switching planets does not re-run the collection.

A proposed Von Neumann debiaser on timer bit 0 was deliberately left out. It
assumes independent bits with a fixed bias, and the low bit of a free-running
counter sampled at TOD edges is neither; if the sampling interval were an even
constant, that bit would never change, every pair would be discarded, and the
stage would silently contribute nothing. Mixing both whole timer bytes carries
strictly more information.

Two constraints keep that source alive:

- **Voice 3 must be running before anything reads it.** The noise shift register
  only advances when the phase accumulator's bit 19 rises, so a zero frequency
  freezes it. `gosub1850` therefore runs at line 35 *before* the title screen,
  and the blip routine at line 990 clears voices 1-2, the filter and volume
  while skipping voice 3's registers (`$D40E-$D414`).
- **VICE must be told to clock the SID.** Under `-sounddev dummy` VICE never runs
  the SID, so `PEEK(54299)` returns one frozen byte and the terrain collapses to
  a single fixed landscape. `smoke` and `bench` use `-sounddev dump`, which needs
  no audio device; override with `make smoke SOUNDDEV=...` if required.

On real hardware the register advances strictly with elapsed cycles, so attract
mode reached by the fixed 20-second timeout on a cold boot still produces the
same opening landscape every time. Human play varies, and attract varies from
one regeneration to the next within a session.

## BASIC V2 traps this source has already hit

Both of these produced silent, working-but-wrong code rather than an error, so
they are worth checking before adding anything similar.

**There is no `XOR`.** Line 1182 once read `if((rvxor(c*17+ln*31))and3)=0`, which
tokenized as `RV OR (...)` because the tokenizer greedily matches the `OR`
inside the identifier. That demanded both operands have their low two bits clear
and made the darker terrain speckle roughly 1 cell in 16 instead of 1 in 4. It
now uses the equivalent that needs no exclusive-or, since `(a xor b) and 3 = 0`
holds exactly when the low bits match:

```
1182 ... if(rvand3)=((c*17+ln*31)and3)thenpokepk+bc,td
```

**Only the first two characters of a name are significant.** `oc1`, `oc2` and
`oc3` were all one variable `OC`, which defeated the change-only colour cache at
lines 532, 552 and 572. They are now `o1`, `o2` and `o3`. Because the old shared
cache disagreed with all three values almost every frame, it re-poked the colours
constantly and so accidentally repaired the HUD labels after `gosub1600`
re-printed them — `PRINT` writes colour RAM too. A correct cache does not repair
them, so line 135 now invalidates `o1`/`o2`/`o3` after the labels are printed.

The crash consequences at lines 2102-2130 are indexed by `cn`, drawn from the
jiffy clock because oscillator 3 is deterministic at that point. There are 13
entries, so line 1714 masks to 0-15 and then wraps with `ifcn>12thencn=cn-13`.
**Changing the number of entries requires changing that wrap**, or `restore:forx=.tocn:readq$:next`
will run off the end and raise `?OUT OF DATA` inside the crash report.

## Traps in `src/rng.s`

**The 6526 TOD does not run until you start it.** Writing the hours register
halts the clock and only a write to the tenths register restarts it. Nothing in
the KERNAL starts CIA1's TOD, so it reads a constant 0 forever and a naive
`wait for the tenths register to change` loop hangs the machine. `starttod`
clears control register B bit 7 to address the clock rather than the alarm, then
writes hours, minutes, seconds and tenths, in that order, with tenths last.

**`xorshift` clobbers Y.** `refill` originally carried its byte index in Y
across the call, so every iteration stored to offset 0 and the loop never
terminated. Both loop counters now live in memory rather than in registers.
Nothing here is fast enough for register pressure to be worth a hidden contract
between routines.

## Memory map

Space is tight: BASIC must end before the sprite data at `$2E7C`. The build
prints the end address, and `tools/embed-sprites.py` fails the build on overlap.

| Range | Contents |
| --- | --- |
| `$0801`-`$2DD2` | BASIC program |
| `$2E7C`-`$4073` | sprite shapes |
| `$4200`-`$4385` | soundtrack player |
| `$4400`-`$4BFF` | entropy collector and its 1024-byte table |
| `$4C00`- | BASIC variables and arrays |

Note the last row: `LOAD",8,1"` sets the start of variable space to the end of
the *loaded image*, not the end of the BASIC text, which is what keeps variables
from overwriting the sprites. That also rules out putting code at `$C000` — the
single-blob load would have to pad the image out to there, pushing variables to
`$D000` and colliding with the string area descending from `$A000`. New assets
have to sit immediately above the existing ones.
