# `src/lunalight.bas` section map

Companion to the canonical BASIC source. This is a reading guide, not a
substitute for `[docs/feature-layering.md](feature-layering.md)` or the
`[README.md](../README.md)` memory map and build notes. Line numbers refer to
`[src/lunalight.bas](../src/lunalight.bas)`.

Physics constants (`m2±.6`, `po` via `.1+m2/20`, `hm/4`, soft-landing gates)
are frozen; this doc describes *where* they live, not how to change them.

## Program flow

```text
20  VIC bank 2 + arrays
30  RNG collect → music on → title → music off → SID clear
40…  constants, first terrain
90…  round spawn → flight loop (160…)
       ├─ soft land → score (720…) → 840 → next round
       └─ crash → explosion (1320) → 710 → score path
1020  title / attract idle
1100  procedural terrain + pads
1920 / 1950  attract pad pick + autopilot (branched from 160)
```

Attract mode (`am=1`) reuses the same flight and scoring path. It never writes
the high score. Any key or stick input during the demo restarts at line 20.
When the demo itself reaches game over it announces the message, then takes the
same cold restart so the title idles for another song-length wait.

---

## Boot and VIC setup (10–30)


| Lines | Role                                                                                                                                                                                                             |
| ----- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 10    | Historical disk-save REM; not executed meaningfully                                                                                                                                                              |
| 20    | `CLR`; disable SHIFT+Commodore charset flip (`CHR$(8)`); select VIC bank 2 (`$DD00` low bits `01`); screen base `$8400` (`POKE 648,132`); `$D018=$14` so character ROM is visible at `$9000`; init `rv$` / `bl$` |
| 25    | Dimension pad arrays (`px`/`pw`/`py`/`pb`/`rf`/`ph`) and the 40-column height map `h()`                                                                                                                          |
| 30    | **Load-bearing order:** `SYS 17408` (RNG collect) **before** `SYS 16896` (music install); title subroutine 1020; `SYS 16899` stops music for flight; 990 clears the SID                                          |


`$D018=$18` would select blank RAM at `$A000`: invisible screen and no
sprite/background collision latch, so landing never fires.

---

## Game constants and first round (40–135)


| Lines   | Role                                                                                                                                                                                         |
| ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 40      | Clear screen; bind VIC (`v=53248`) and SID (`s=54272`); screen/colour base addresses for bank 2 (`sn`/`bc`); RNG read base `rb=18432`; border/background colours; `rz` starts as pad index 1 |
| 50      | HUD label strings; first-spawn seeds `ep`/`hp`; colour RAM base `lc`                                                                                                                         |
| 60      | Sprite-pointer base `pn=$87F8`; fuel `fe`/`fu`; lives `nm`; vertical spawn ratchet `n2`; command-module X `mx`; build terrain (`GOSUB 1100`); if attract, pick a demo pad (`1920`)           |
| 70–80   | Earth decoration sprites 2/3 (pointers 253/254, colours, fixed at 60,60)                                                                                                                     |
| 90      | Round spawn: vertical position `po`, horizontal `pp` from `ep`, horizontal momentum `hm` from `hp`                                                                                           |
| 91–92   | Step the command module 8 px right each round; wrap at 240 → 104; poke sprite 7 X                                                                                                            |
| 95–100  | Ratchet next-round spawn (`ep` leftward, `hp` more rightward drift); wrap when exhausted                                                                                                     |
| 110–112 | Clear X-MSB to flag mask `fm`; attract may already be past x=255 and needs `fh`                                                                                                              |
| 120–135 | Cap spawn vertical speed; set upright shape `p=187` and fill `f=246`; initialize outline/fill/exhaust pointers; set velocity, collision bit and colours; refresh score bar (`1500`) |


---

## Flight loop: input (160–200)

Entered every frame until collision or out-of-bounds.


| Lines   | Role                                                                                                                                |
| ------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| 160     | Read keyboard (`GET`) and joystick port 2 (`PEEK(56320)`); attract jumps to autopilot `1950`                                        |
| 165     | Non-empty key → keyboard→joystick map (`1980`)                                                                                      |
| 168–187 | Rotate: right (`AND 15 = 7`) increments `p`, left (`= 11`) decrements; ±90° limiter wraps through the pointer band; map `p` to fill `f` and refresh moving pointers |
| 190     | `F1` → pause (`1270`), with a visible pause tile                                                                                    |
| 200     | If out of fuel, skip thrust                                                                                                         |


Keyboard fallback (cursor keys) is applied in 1980 before the rotate/thrust tests
see `jv`.

---

## Flight loop: thrust, gravity, fuel (220–290)


| Lines   | Role                                                                                                                            |
| ------- | ------------------------------------------------------------------------------------------------------------------------------- |
| 220     | Fire button (`jv AND 16 = 0`) or SHIFT (`PEEK(653)`): enable all sprites (`255`), keep `q=8`, go thrust                        |
| 230–235 | Coast: gravity `m2=m2+.6`, silence voice, mask `191` (all except sprite-6 exhaust); first coast frame clears `q`               |
| 240     | Engine voice setup (volume, ADSR, frequency, gate)                                                                              |
| 245–290 | `ON p-186` dispatches attitude → thrust deltas and fuel burn: upright `m2-.6` / 1 fuel; angled mixes of `m2`/`hm` with 2–3 fuel |


These are the original float equations. Do not retune without an explicit plan
for the motion oracle.

---

## Flight loop: motion and wrap (330–480)


| Lines   | Role                                                                                                                                                       |
| ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 330–340 | Vertical integrate: `po` moves by `.1+                                                                                                                     |
| 350–420 | Horizontal integrate: `pp` by `hm/4`; crossing 0 or 255 toggles `e2` and `$D010` between `fm` (flag MSBs) and `fh=67+fm` (outline/fill/exhaust + flags, module bit clear) |
| 430–435 | Co-register outline sprite 0 and fill sprite 1 every loop; move exhaust sprite 6 only while thrust is active                                               |
| 460     | Ceiling clamp at `po=25`                                                                                                                                   |
| 480     | Floor: `po>230` forces a crash with `hm=10`                                                                                                                |


`$D010` is rewritten wholesale on wrap. `fm=48` holds both flag sprites’ MSB;
`fh=67+fm` adds the outline/fill/exhaust MSBs while leaving sprite 7 clear so
the module stays below X 256.

---

## Flight loop: HUD (500–621)

Printed into the upper-right columns only (above the terrain collision zone).


| Lines   | Role                                                            |
| ------- | --------------------------------------------------------------- |
| 500–531 | Vertical velocity colour (green / yellow / red) and `VEL` value |
| 535–571 | Fuel clamp to 0; colour bands; `FUEL` value                     |
| 580–621 | Clamp `                                                         |


`c$` is a backspace+space eraser so shorter numbers do not leave digits behind.

---

## Soft landing and pad match (630–706)


| Lines   | Role                                                                                                  |
| ------- | ----------------------------------------------------------------------------------------------------- |
| 630–635 | Sprite–background collision on the lander (`$D01F AND 1`) only counts when `po>120`; else loop to 160 |
| 640–644 | Soft-landing gates: `                                                                                 |
| 649     | Verdict X = lander centre `INT(pp)+12` (+256 if `e2`). `px(i)` is the pad’s **left** edge             |
| 650–690 | Scan pads 1–5 for X overlap and `                                                                     |
| 700     | No pad → `xz=1` (off-pad cause) and crash                                                             |
| 705–706 | Refuel pad (`rf(lz)`) with `fe≤399` fills to 1000 and sets message flag `e7`                          |


Successful landings fall through to 720.

---

## Scoring and round reset (710–840)


| Lines       | Role                                                                                                                                        |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| 710         | Crash entry: lose a life, ease next spawn `n2`, clear `lz`                                                                                  |
| 720         | Disable lander/exhaust; restore `$D010` to `fm`; re-arm flag + module (`1210`)                                                              |
| 730         | Silence engine; fixed jiffy pause via `POKE 679,n` + `SYS 17420`                                                                            |
| 740         | Centre-hit bonus: within 3 px of pad centre → `bs = INT(pb*2/3)`                                                                            |
| **752–760** | **Shared scoring lines — byte-identical to bank-0.** Velocity/horizontal/fuel penalties, bonus, accumulate `pt`                             |
| 770         | If this was a crash (`cr`), print post-mortem (`1900`)                                                                                      |
| 775–780     | Bonus / points / “fuel tanks full” messages via 982                                                                                         |
| 785–795     | Game-over when out of lives or fuel; high score only if not attract; attract prints “game over” then cold-restarts at line 20               |
| 835         | Attract: pick next demo pad (live rounds only; attract game-over no longer reaches here)                                                    |
| 839–840     | Zero turn score; `fu=fe`; `**gc=FRE(.)` forced string collect** (screen at `$8400` sits in the heap descent); short pause; next round at 90 |


Without line 840’s `FRE(.)`, attract play eventually corrupts the screen matrix
and sprite pointers.

---

## Helpers: RNG, messages, SID click (900–1010)


| Lines    | Role                                                                             |
| -------- | -------------------------------------------------------------------------------- |
| 900      | Next PRNG byte: `PEEK(rb+ri)`, advance `ri`                                      |
| 960–980  | Game-over wait loop; `F7` resets score/lives/fuel and rebuilds terrain           |
| 982–986  | Centre a message on row 8, type it with SID clicks, long pause, erase with `bl$` |
| 990–1010 | Short SID “key click”; used by title path and message typing                     |


All in-game pauses use the RNG module’s `wait` entry (`SYS 17420`), not empty
`FOR` loops (those measure CPU work and MOSpeed deletes them).

---

## Title and attract idle (1020–1090)


| Lines     | Role                                                                                                                       |
| --------- | -------------------------------------------------------------------------------------------------------------------------- |
| 1020–1070 | Clear `$D015` first (literal `POKE 53269,0` — `v` is not bound yet on the first title call), then clear screen and draw title / “press F7”; music is still running from line 30 |
| 1072      | Read published song length in jiffies from `$4206/$4207` (`PEEK(16902)+…`)                                                 |
| 1074–1090 | Idle until `F7` (return `am=0`) or elapsed ≥ one song pass (`am=1`); any other key or stick activity resets the idle timer |


Attract timeout therefore tracks music tempo/length automatically.

---

## Procedural terrain and pads (1100–1200)


| Lines     | Role                                                                                                                                                                                                                                                  |
| --------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1100      | Clear; sprites off; `SYS 17411` refill RNG table; terrain/colour defaults                                                                                                                                                                             |
| 1102–1136 | Random-walk height map `h(0..39)` in 1–12, with short segment runs and a light noise pass                                                                                                                                                             |
| 1136–1165 | Five pad slots on column anchors 1/9/17/25/33; each pad is **four glyphs (32 px)** wide; altitude band sets `pb` (500/600/800); exactly one low pad gets `rf=1` and becomes `rz`; slope feathering around pad edges; `py`/`px` stored in sprite space |
| 1175–1190 | Paint terrain cells (`sc` slope glyphs 108/123 or solid 160) into screen `$8400` + colour RAM; greys 11/12                                                                                                                                            |
| 1192–1196 | Overpaint pad tops as green bar with yellow ends                                                                                                                                                                                                      |
| 1197–1198 | Flag X/Y from refuel pad; build `fm` / `fh` MSB masks; place sprites (`1210`)                                                                                                                                                                         |
| 1200      | Ready cursor/colour poke; return                                                                                                                                                                                                                      |


---

## Fill, flag and command module sprites (1210–1215)


| Lines | Role                                                                                                                      |
| ----- | ------------------------------------------------------------------------------------------------------------------------- |
| 1210  | Sprite 4: flag outline/mast, pointer 243, white (`v+43`), at `fx`/`fy`                                                    |
| 1211  | Sprite 5: pennant field, pointer 245, blue (`v+44`), same XY (behind)                                                     |
| 1212  | Sprite 7: command module, pointer 244, grey, Y 55; `PEEK(v+21) OR 162` re-enables LEM fill + field + module after line 720 clears them |
| 1214  | If lander is in the high X half (`e2`), keep lander MSB set                                                               |


Never use colours 11 or 12 for the flag: they match the terrain greys.

Flight enable masks: **191** coast / **255** thrust. Line 720 is a protected
scoring neighbour, so fill/field/module bits are restored here instead.

---

## Pause (1270–1310)


| Lines     | Role                                         |
| --------- | -------------------------------------------- |
| 1270–1280 | `F1` again resumes to the thrust test        |
| 1290      | `F7` cold-restarts at line 20                |
| 1300      | `HOME` prints `rv$` and `STOP` (debug break) |


---

## Crash explosion (1320–1420)


| Lines     | Role                                                                                                                                   |
| --------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| 1320–1328 | Kill engine voice; yellow explosion colours; snapshot crash X; set `cr=1`; assign explosion pointers **before** enabling those sprites |
| 1330–1370 | Place explosion sprite cluster left/right of the lander; pack `$D010`; enable mask `252`                                               |
| 1380      | Multicolour explosion setup                                                                                                            |
| 1390–1400 | Animate pointers 203→212 with fading volume and jiffy delays                                                                           |
| 1410      | Silence; hide lander; leave Earth sprites on                                                                                           |
| 1420      | Join the scoring path at 710                                                                                                           |


---

## Score bar (1500–1520)

Bottom status line: high score, current score, LEM count. Attract prefixes
`ATTRACT` on the home line. Called at round start and when the high score
updates.

---

## Crash post-mortem (1900–1918)

Exactly **one** line per crash, then clear `xz`.


| Lines     | Role                                                                            |
| --------- | ------------------------------------------------------------------------------- |
| 1902      | Coin flip on RNG byte: cause branch vs consequence branch                       |
| 1903–1913 | Cause: off-pad (`xz`), cartwheel (`                                             |
| 1914–1918 | Consequence: rotate through 13 `DATA` strings (2100+) with a jiffy-salted index |


---

## Attract: pad pick and autopilot (1920–1984)


| Lines     | Role                                                                                                                                                                                   |
| --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1920–1926 | Choose a pad ≠ last; divert to refuel pad when fuel < 400; every fourth approach aim left of the pad (`tx = px-16`) to demo a crash                                                    |
| 1950–1951 | Any real input → full restart at 20                                                                                                                                                    |
| 1952–1974 | Float autopilot: compute error to target, cross high, dive when close, one late burn; synthesize `jv` (direction + optional thrust) and fall into the normal rotate/thrust code at 170 |


Keyboard map (1980–1984): cursor right/down set rotate bits while preserving the
fire bit from the stick.

---

## `DATA` consequence lines (2100–2130)

Thirteen yellow one-liners for the post-mortem consequence branch. Indexed by
`RESTORE` + counted `READ` in 1916. Do not insert/delete lines without updating
the `cn` wrap (`>12 → cn-13`).

---

## Variable cheat sheet (hot path)


| Name                          | Meaning                                                         |
| ----------------------------- | --------------------------------------------------------------- |
| `po` / `pp`                   | Lander Y / X (0–255; `e2` marks X≥256)                          |
| `m2` / `hm`                   | Vertical / horizontal momentum                                  |
| `p` / `q`                     | Lander shape pointer / exhaust offset (8 when thrusting)        |
| `f`                           | Attitude-matched black LEM fill pointer (246-250)               |
| `fe` / `fu`                   | Current fuel / fuel at round start (scoring)                    |
| `e2`                          | High-X half-screen flag for lander                              |
| `fm` / `fh`                   | `$D010` masks: flags only / outline+fill+exhaust+flags          |
| `px`/`pw`/`py`/`pb`/`rf`/`ph` | Pad left X, width (glyphs), Y, points, refuel flag, height band |
| `lz` / `pf` / `xz`            | Landing pad index, verdict centre X, off-pad crash mark         |
| `am`                          | Attract mode                                                    |
| `tp` / `pt` / `bs` / `hs`     | Turn points, session score, centre bonus, high score            |
| `nm` / `nf`                   | Lives left / game-over flag                                     |
| `cr`                          | Crash this resolution (triggers post-mortem)                    |
| `fx`/`fy`/`rz`                | Flag sprite XY and which pad owns it                            |
| `mx`                          | Command-module X                                                |
| `v` / `s` / `pn`              | VIC base, SID base, sprite-pointer base `$87F8`                 |
| `rb` / `ri`                   | RNG table base `$4800` and read index                           |


---

## Related docs


| Doc                                               | Use when                          |
| ------------------------------------------------- | --------------------------------- |
| `[README.md](../README.md)`                       | Controls, build, memory map       |
| `[docs/feature-layering.md](feature-layering.md)` | Why bank-2, sizes, layer evidence |


