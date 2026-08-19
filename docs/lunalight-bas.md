# `src/lunalight.bas` section map

This is a guided map of the canonical game source,
[`src/lunalight.bas`](../src/lunalight.bas). It explains the code in source-line
order and assumes the reader is new to Commodore 64 BASIC. For the memory map,
build commands, and project history, use [the README](../README.md) and
[feature layering](feature-layering.md).

The physics equations and landing limits are deliberately frozen. This guide
explains them; it is not permission to retune them.

## A quick BASIC/C64 reading primer

The source is compact because it is compiled with the original Blitz! compiler.
Several conventions make it easier to read:

- A colon (`:`) separates statements on one numbered BASIC line. Execution
  continues left-to-right.
- A period (`.`) is BASIC's shortest spelling of numeric zero. For example,
  `e2=.` clears a flag.
- `PEEK(address)` reads one byte of C64 memory; `POKE address,value` writes one.
  The program uses them to control VIC-II graphics, SID sound, and the keyboard.
- `GOSUB line` calls a numbered helper and `RETURN` comes back to the statement
  after the call. `GOTO line` transfers without returning.
- Sprite pointer values are not memory addresses. In VIC bank 2, a pointer such
  as `187` means the shape at bank base `$8000 + 187 * 64`.

The game uses VIC bank 2: screen matrix `$8400`, sprite-pointer table `$87F8`,
title character set `$8800`, character ROM `$9000`, and sprite payload starting
at `$AE7C`.

## Program flow

```text
20   cold-start display and variable clear
30   collect entropy → start title music → title → stop music
40   restore flight display/memory → create terrain and first round
90   spawn a round
160  one flight frame
 ├─ 630  collision / landing decision
 │   ├─ 706  successful landing dust → scoring
 │   └─ 1320 crash explosion → scoring
 └─ 840  prepare next round

1020 title tableau and idle timer
1100 procedural terrain and pads
1920 attract target selection; 1950 attract autopilot
```

Attract mode (`am=1`) uses the normal flight, collision, scoring, and game-over
code. It differs only in how it supplies controls and in never writing the high
score. Any key or joystick input during the demo returns to the cold-start title.

## Boot, memory, and VIC setup (10–30)

| Lines | What happens | Why it matters |
| --- | --- | --- |
| 10 | A historical `REM SAVE` command. | It is a comment; `REM` consumes the rest of the line. |
| 20 | `CLR` clears variables; bank 2, screen `$8400`, and `$D018=$14` are selected. `rv$` and `bl$` are created. | This is also the re-entry point for `GOTO 20` from attract mode, game over and the `F7` pause exit, so everything the title needs must be (re)established here. `MEMSIZ` is deliberately **not** touched: see line 40 and the `$8800` note in the title section. `rv$` is a debug label; `bl$` is 40 spaces for erasing a message row. |
| 25 | Dimension the six pad arrays and the 40-cell terrain-height array. | `DIM` reserves indexed storage before play begins. |
| 30 | Call RNG `collect`, install title music, call the title routine, then uninstall and clear the SID. | The order is load-bearing: the entropy collector uses SID voice 3, which the music IRQ would otherwise overwrite. |

`$D018=$14` selects screen `$8400` and the character ROM image at `$9000`.
Writing `$18` instead would point the VIC at blank RAM at `$A000`; the display
would disappear and the sprite/background collision latch used for landing would
not work.

## Flight setup and first terrain (40–135)

| Lines | What happens |
| --- | --- |
| 40 | Assert `MEMSIZ=$A000`, disable title sprites, restore `$D018=$14`, clear the screen, and cache VIC (`v`), SID (`s`), screen (`sn`), colour RAM (`bc`), and RNG-table (`rb`) addresses. |
| 50 | Define the HUD label strings, initial spawn position/momentum (`ep`/`hp`), and colour-RAM base `lc`. |
| 60 | Set sprite-pointer base `pn=$87F8`, fuel, lives, next spawn speed, and command-module X; build terrain with `GOSUB 1100`. Attract mode also picks its first target. |
| 70–80 | Give sprites 2 and 3 the Earth shapes (253 and 254), colours, and shared position `(60,60)`. Sprite 3 is the blue disc; sprite 2 supplies white detail. |
| 90 | Start a round: `po` is lander Y, `pp` is lander X, and `hm` is horizontal momentum. |
| 91–100 | Move the cosmetic command module 8 pixels per round and advance the next ordinary spawn seed. |
| 110–112 | Clear the lander high-X flag and select the correct `$D010` mask. An attract spawn can begin beyond X=255. |
| 120–135 | Clamp the next vertical spawn speed; select upright LEM shape 187 and its black fill 246; set outline, fill, and exhaust pointers; set sprite colours; draw the score bar. |

The LEM uses three co-registered sprites in flight: outline 0, black interior
fill 1, and exhaust 6. Co-registering means all three receive the same X/Y
coordinates; the exhaust artwork itself provides the visible offset below the
engine.

## Flight input (160–200)

This is the top of the per-frame loop. It is reached again from line 635 after a
frame that has not landed or crashed.

| Lines | What happens |
| --- | --- |
| 160 | Read one keyboard character with `GET z$`, read joystick port 2 into `jv`, then branch to the attract autopilot if `am` is set. The `GET` and the joystick read must stay **unconditional**: the autopilot's own exit test in line 1952 reads that fresh `z$`/`jv`, and guarding them behind `IF am=.` would swallow the branch to 1950 as well, since everything after `THEN` is conditional. |
| 165 | Translate cursor-key fallback input through helper 1980. |
| 168–187 | Rotate the lander. Joystick right increments `p`; left decrements it. The small branches prevent rotation beyond the five supported attitudes. Lines 185–187 choose the matching fill and exhaust pointers. |
| 190 | `F1` writes a pause marker into the top-left screen cell and enters the pause loop. |
| 200 | With no fuel, skip directly to coast. |

`p` is both a visual pointer and an attitude state. The later `ON p-186 GOTO`
uses it to choose the matching thrust equation.

## Thrust, gravity, and fuel (220–290)

| Lines | What happens |
| --- | --- |
| 220 | Fire button or Shift: enable all eight sprites (`$D015=255`), remember that thrust is active in `q`, and configure the engine. |
| 230–235 | Coast: add gravity (`m2=m2+.6`), silence the engine voice, and disable only sprite 6 exhaust (`$D015=191`). |
| 240 | Program SID voice 1 as the engine sound. |
| 245–290 | Dispatch on attitude. Upright thrust subtracts `.6` from vertical momentum and costs one fuel; angled attitudes also alter `hm` and cost two or three fuel. |

These float equations are the original landing feel. Do not change the `.6`,
`.2`, position integration, or fuel figures without explicitly retuning the
motion oracle.

## Motion, wrapping, and sprite placement (330–480)

| Lines | What happens |
| --- | --- |
| 330–340 | Integrate vertical motion. Descending uses `po=po+(.1+m2/20)`; ascending is the symmetrical negative case. |
| 350–420 | Integrate horizontal motion by `hm/4`. Crossing a screen half adjusts `pp`, toggles `e2`, and writes the matching `$D010` high-X mask. |
| 430–435 | Put outline and fill at `pp,po` every frame. When `q` says thrust is active, put the exhaust at the same coordinate too. |
| 460 | Prevent ascent above Y=25. |
| 480 | A fall below Y=230 is an immediate hard crash. |

`$D010` holds one X high bit per sprite. `fm=48` supplies the high bits for the
two flag sprites. `fh=67+fm` additionally enables the high bit for outline,
fill, and exhaust, while intentionally leaving sprite 7's bit clear: the module
must remain below X=256.

## HUD update (500–621)

The HUD is deliberately printed only in the upper rows; printed characters are
solid collision targets for the LEM.

| Lines | What happens |
| --- | --- |
| 500–531 | Choose green/yellow/red from vertical speed and print `VEL` plus `INT(m2)`. |
| 535–571 | Clamp fuel at zero, choose its warning colour, and print `FUEL`. |
| 580–621 | Clamp horizontal speed to displayable values, choose a colour, and print `HORZ`. |

`c$` is a left cursor movement followed by a space. It erases an old final digit
when a displayed number gets shorter.

## Collision, landing, and refuelling (630–706)

| Lines | What happens |
| --- | --- |
| 630–635 | Read `$D01F`, the sprite/background collision latch. Only collisions below Y=120 count as terrain contact; otherwise continue flying. |
| 640–644 | Enforce the soft-landing gates: `ABS(hm)<=2`, upright pointer 187, and `INT(m2)<=5`. Failure jumps to the crash routine. |
| 649 | Calculate verdict centre `pf=INT(pp)+12`; add 256 when `e2` says the lander is in the high-X half. |
| 650–690 | Search all five pads. A match needs centre X inside its width and lander Y within four pixels of its stored pad height. |
| 700 | No matching pad means an off-pad crash; set `xz` so the post-mortem can describe it. |
| 705–706 | On the refuel pad, fuel at or below 399 becomes 1000; then show the landing dust and continue to scoring. |

`px(i)` is a pad's left edge, not its centre. The `+12` in line 649 converts the
24-pixel lander sprite coordinate into its centre before comparison.

## Resolution, scoring, and the next round (710–840)

| Lines | What happens |
| --- | --- |
| 710 | Crash path: lose a LEM, make the next spawn gentler, and clear the landing index. |
| 720 | Hide lander/exhaust, restore flag high-X bits, and call 1210 to re-arm the fill, flag field, and command module. |
| 730 | Silence the engine and wait 26 jiffies before calculating results. |
| 740 | A landing within three pixels of the pad centre earns a two-thirds pad-value bonus. |
| 752–760 | Apply vertical-speed, horizontal-speed, and fuel penalties; add the bonus; add the turn total to session score. These lines are byte-identical to the bank-0 control source. |
| 770–780 | Show exactly one crash post-mortem when needed, then bonus, points, and refuel messages. |
| 785–795 | Handle game over. Normal play may update `hs`; attract mode cannot. An attract game-over goes back to line 20. |
| 835 | In attract mode, choose the next demo target. |
| 839–840 | Clear round bookkeeping, force a string collection with `gc=FRE(.)`, wait 10 jiffies, re-enter the flag placement at 1197 (which also rewrites the sprite pointers via 1210), drop the lander/fill/exhaust enable bits, and spawn the next round. |

The forced `FRE(.)` is essential. `MEMSIZ` is `$A000` throughout; without a
collection, BASIC's descending string heap eventually reaches the title
character page at `$8800-$8FFF` and then the screen matrix and sprite pointers
at `$8400-$87FF`. Re-running 1197 immediately after the collection restores the
eight sprite pointers, so a collection that ever did reach them cannot leave the
next round with garbage shapes.

## Random, messages, and SID helpers (900–1010)

| Lines | What happens |
| --- | --- |
| 900 | Read the next byte from the RNG table at `$4800` and increment `ri`. |
| 960–980 | Wait for `F7` after game over; reset game counters, clear the old message, rebuild terrain, and continue. |
| 982–986 | Centre a message on row 8, type one character at a time with SID clicks, wait 153 jiffies, then erase its full 40-column row. |
| 990–1010 | Clear SID registers, make the short click, wait one jiffy, and release the gate. |

All waits use the RNG module's `wait` entry: `POKE 679,n:SYS 17420`. This waits
for KERNAL jiffies rather than burning CPU cycles in an empty `FOR` loop.

## Title tableau and attract idle (1020–1097)

The title is a title-only graphics mode. It uses its own RAM character set and
all eight sprites, then line 40 returns the machine to the normal flight mode.

| Lines | What happens |
| --- | --- |
| 1020 | Turn off inherited sprites, select title character RAM with `$D018=$12`, clear the screen, and set border/background colours. |
| 1025–1028 | Assign all eight title sprite pointers, positions, colours, and normal-priority settings. The title scene uses LEM outline/fill/exhaust, Earth pair, flag pair, and module. |
| 1030–1035 | Print the text title, then replace its letter cells with custom character codes 240–247 to make the chunky logo. |
| 1040–1070 | Print license/contributor credits and the `F7` start prompt; write eight dim star characters; initialise title animation state (`ta`, `tm`, `ty`, `bd`, `tw`). `bd` is the bob direction and must stay separate from terrain colour `td`; `tw` is the twinkle phase. |
| 1072–1088 | Read music-loop length from `$4206/$4207`; start attract mode after one whole song without input. Any other key or joystick movement resets the timer. |
| 1092–1097 | Every four jiffies, move the module, bob the LEM, co-register its fill and exhaust, alternate the exhaust enable bit, and twinkle selected stars. The twinkle phase is the bounded counter `tw=(tw+1)and3`, **not** `TI AND 8`: `TI` passes 32767 jiffies after roughly nine minutes of uptime and `AND` would then raise `ILLEGAL QUANTITY`. |

[`tools/make-title-charset.py`](../tools/make-title-charset.py) copies the normal
character ROM into `$8800-$8FFF` and replaces only the logo and star glyphs.
That page lies in the string heap's descent path, but **do not** lower `MEMSIZ`
to `$8800` to protect it: `MEMSIZ` is the top of string space, so the heap's
first byte would be `$87FF` and the collection forced by line 840 would rewrite
the sprite pointers at `$87F8-$87FF`. `MEMSIZ` stays at `$A000` and that same
per-round collection is what keeps the heap clear of `$8FFF`. Line 40 asserts
`MEMSIZ=$A000` and restores `$D018=$14`; the latter is required for the visible
character ROM and landing collision latch.

## Procedural terrain and pads (1100–1200)

| Lines | What happens |
| --- | --- |
| 1100 | Clear the display, hide title sprites, refill the RNG table, reset the random index, and choose terrain greys. |
| 1102–1136 | Generate 40 terrain heights. It chooses short random target runs, moves toward them, then applies a small noise pass while clamping every height to 1–12. |
| 1136–1165 | Define five pad bands, choose a shifted ordering of height classes, choose each four-character-wide pad, and store both display and sprite-space geometry. Exactly one low pad becomes the refuel pad. |
| 1175–1190 | Paint each terrain cell into screen RAM and colour RAM. Slope glyphs 108/123 are used at height transitions; solid terrain uses reverse space 160. |
| 1192–1196 | Paint each pad surface green with yellow end caps. |
| 1197–1200 | Compute the flag position and high-X masks, install the flag/module sprites, and restore the normal cursor tile. Line 1197 computes `fx`/`fm` and line 1198 computes `fh`/`fy` before `GOSUB 1210`; both tails must stay **unconditional**. Folding them into the `IF fx>255` clause makes 1197 fall through into 1198's `GOSUB 1197` and recurse without bound, which presents as a hang plus spreading RAM corruption right after the terrain is drawn. Line 840 re-enters here at 1197. |

The pad width is always four glyphs, or 32 pixels. Because the LEM is 24 pixels
wide, that leaves four pixels of visible clearance on each side.

## Flight sprites: flag, fill, and module (1210–1215)

| Lines | What happens |
| --- | --- |
| 1210 | Sprite 4: white flag outline/mast, pointer 243, at `fx,fy`. |
| 1211 | Sprite 5: blue solid pennant field, pointer 245, at the same coordinate and behind sprite 4. |
| 1212 | Sprite 7: light-grey command module, pointer 244 at Y=55; re-enable fill, field, and module bits after line 720. |
| 1213–1215 | Document the mask repair; keep the lander high-X bit set if required; return. |

The two-sprite flag is intentional: a single high-resolution sprite cannot
contain both white outline/emblem and blue field. Colours 11 and 12 are avoided
because they are terrain greys.

## Pause, explosion, and status (1270–1520)

| Lines | What happens |
| --- | --- |
| 1270–1310 | Pause loop. `F1` resumes; `F7` cold-restarts at line 20; `HOME` prints `rv$` and stops for debugging. |
| 1320–1420 | Crash presentation. It silences the engine, assigns four explosion pointers before enabling them, packs high-X bits, animates pointers 203–212 with six-jiffy frames, then leaves the Earth pair visible. |
| 1500–1520 | Draw the bottom status line: high score, score, and LEM count. Attract mode adds `ATTRACT` at home. |

## Landing dust (1700–1705)

After a successful landing, sprite 6 temporarily changes from exhaust pointer
`p+8` to dust pointer 251. It is placed at the LEM's same `pp,po` coordinate,
coloured light grey, enabled for ten jiffies, then normal resolution continues.
The dust shape itself supplies its ground-level offset.

## Crash post-mortem (1900–1918)

The game deliberately prints one sentence per crash, never a stack of messages.

| Lines | What happens |
| --- | --- |
| 1902 | Take one RNG byte and choose the cause branch or consequence branch. |
| 1903–1913 | Build a cause message: off-pad boulder, excessive horizontal speed, sideways landing, or vertical-speed crater. Clear `xz` before returning. |
| 1914–1918 | Choose one of 13 consequence `DATA` strings using a rotating, jiffy-salted index; clear `xz`; print it. |

## Attract target selection and autopilot (1920–1984)

| Lines | What happens |
| --- | --- |
| 1920–1926 | Pick a pad different from the previous one. Below 400 fuel, prefer the refuel pad. Normally aim `tx=px(al)+4`, which puts the LEM centre over the pad centre; every fourth target deliberately aims 16 pixels left of the pad. |
| 1950–1952 | Any real key, stick movement, or Shift restarts at line 20. Do not add a `PEEK(197)` guard around a `GET` here: `PEEK(197)` reads 64 when no key is down, so the test is always true and the extra `GET` would clear the `z$` line 160 just read. |
| 1953–1967 | Measure horizontal/vertical error; remain high while crossing, then choose a late-burn vertical target and desired horizontal correction. |
| 1968–1975 | Turn the desired correction into the same synthetic joystick bits (`jv`) used by human input, then fall through to normal rotation/thrust handling at line 170. |
| 1980–1984 | Keyboard fallback: cursor right/down set the same rotate bits while preserving the stick's fire bit. |

The autopilot does not have a special physics path. It simply manufactures the
same controls a player would provide, so its demo remains a valid demonstration
of the real game.

## `DATA` consequence lines (2100–2130)

Thirteen yellow post-mortem sentences. Line 1916 uses `RESTORE` then repeated
`READ` operations to select one. If lines are added or removed, the wrap in line
1914 (`cn>12`) must change too.

## Embedded machine-code helpers

Two modules are packed into the canonical full PRG. BASIC uses decimal `SYS`
addresses to call their fixed entry points.

| Module | Address | BASIC calls | Purpose |
| --- | --- | --- | --- |
| [`src/music.s`](../src/music.s) | `$4200-$43F0` | 16896 install; 16899 uninstall | Three-voice IRQ title music. `$4206/$4207` publishes the title song's length in jiffies. |
| [`src/rng.s`](../src/rng.s) | `$4400-$4BFF` | 17408 collect; 17411 refill; 17420 wait | TOD/RNG collection, 1024-byte table at `$4800`, and jiffy-clock delays. |

The `wait` call reads its delay count from address 679. For example,
`POKE 679,26:SYS 17420` waits about 26/60 of a second on both PAL and NTSC
because the KERNAL jiffy interrupt runs at 60 Hz.

## Variable cheat sheet

| Name | Meaning |
| --- | --- |
| `po` / `pp` | LEM Y / X; `e2` marks the X>=256 half. |
| `m2` / `hm` | Vertical / horizontal momentum. |
| `p` / `f` / `q` | LEM outline pointer / matching black fill / thrust-active flag. |
| `fe` / `fu` | Current fuel / fuel at the start of this round. |
| `px` / `pw` / `py` / `pb` | Pad left X, width in glyphs, Y, and point value. |
| `rf` / `rz` / `fx` / `fy` | Refuel-pad marker/index and its flag sprite position. |
| `pf` / `lz` / `xz` | Landing verdict centre, matched pad index, and off-pad crash marker. |
| `fm` / `fh` | `$D010` X-high masks for flags only / lander plus flags. |
| `tp` / `pt` / `bs` / `hs` | Turn points, session score, centre bonus, high score. |
| `nm` / `nf` / `cr` | LEMs remaining, game-over flag, crash-resolution flag. |
| `am` / `al` / `tx` / `ap` | Attract flag, target pad, target X, and descent phase. |
| `ta` / `tm` / `ty` / `td` | Title animation time, module X, LEM Y, and LEM Y direction. |
| `v` / `s` / `pn` | VIC base, SID base, sprite-pointer base. |
| `rb` / `ri` | RNG-table base `$4800` and next-byte index. |

## Related docs

| Document | Use it for |
| --- | --- |
| [README.md](../README.md) | Controls, build commands, packaging, and memory map. |
| [feature-layering.md](feature-layering.md) | Capacity measurements, verification evidence, and design constraints. |
| [src/music.s](../src/music.s) | Title music implementation and tempo constants. |
| [src/rng.s](../src/rng.s) | Entropy collector, PRNG table, and jiffy wait implementation. |
