# Feature layering evidence

All sizes are original Blitz! output before asset padding, produced by
`tools/blitz-compile.py` with the tracked `tools/BLITZ.d64`.

The four layers previously omitted for capacity — joystick control, crash
post-mortem text, RNG/procedural terrain/pad metadata/refuel flag, and attract
mode — are now **all retained and promoted**. The canonical source is
`src/lunalight.bas` (the former `src/lunalight-bank2.bas`), and the canonical
artifact is `build/lunalight-blitz-full.prg`. The pre-promotion bank-0 source is
preserved verbatim as `src/lunalight-bank0.bas` and still builds and runs via
`make blitz-bank0`.

The enabling change was the VIC-bank-2 relocation, not a physics or formula
change. No physics constant, threshold, oracle tolerance, or motion fixture was
altered.

## Measured sizes

| Build | Original-Blitz output | Range | Code ceiling | Headroom |
| --- | --- | --- | --- | --- |
| Bank-0 baseline plus correctness fixes | 9,665 bytes | `$0801-$2DBF` | `$2E7B` (sprite start - 1) | 188 bytes |
| Bank-0 fallback, with IRQ music (`src/lunalight-bank0.bas`) | 9,670 bytes | `$0801-$2DC4` | `$2E7B` | 183 bytes |
| Bank-2 relocation only, after the retained optimizations | 9,675 bytes | `$0801-$2DCB` | `$41FF` (music start - 1) | 5,172 bytes |
| **Canonical promoted build (`src/lunalight.bas`)** | **11,433 bytes** | **`$0801-$34A7`** | **`$41FF`** | **3,416 bytes** |
| Canonical build with the orbiting command module | 11,585 bytes | `$0801-$3541` | `$41FF` | 3,262 bytes |
| Canonical build with the suicide-burn attract descent | 11,613 bytes | `$0801-$355D` | `$41FF` | 3,234 bytes |

The last two rows were measured in this promotion run (`make blitz-bank0` and
`make blitz` from a clean `build/`, plus `tools/bank2-capacity.py`). The first and
third rows are carried forward from the earlier layering and optimization work and
were not re-measured, so the derivations below that use the 9,675-byte figure
inherit that provenance. The canonical row was re-measured with `make blitz` on
the current working tree. Its 66-byte growth over the 11,367 bytes recorded at
promotion comes from the post-promotion corrections below — the `SYS 16899` stop
call, two extra cursor-rights on the VEL label, the half-sprite landing offset,
the attract refuel diversion and thrust gate, and the single-line crash
post-mortem — so it is not attributable to any one of them.

Derived from those measurements:

- The bank-2 relocation itself cost **5 bytes** (9,675 versus 9,670).
- All four feature layers together cost **1,758 bytes** (11,433 versus 9,675).
- Under the old bank-0 layout the promoted code would overrun the `$2E7C` sprite
  start by **1,580 bytes**, so it cannot exist there. Reported directly by
  `tools/bank2-capacity.py` as `old_layout.headroom_bytes: -1580`.
- The relocation raised the reachable ceiling from `$2E7B` to `$41FF`, a
  **4,996-byte** headroom gain, and **3,416 bytes** remain free above the
  promoted code.
- The integrated candidate measured during the bank-0 era was 12,316 bytes ending
  `$381A`. The promoted integrated build is **883 bytes smaller**, and the
  earlier estimate that the layer set needed roughly 2,646 additional bytes
  overstated the real cost of 1,758.

## Layer results

Each layer's runtime evidence comes from `make verify-bank2` on the canonical
artifact (`tools/verify-bank2.py`, 87 checks) and from
`make verify-blitz-motion` (six-sample oracle at bank-2 addresses against the
unchanged `tools/fixtures/blitz-gameplay-baseline.json`).

### 1. Joystick port 2 with keyboard fallback

Previously omitted: the isolated bank-0 candidate compiled to 9,732 bytes ending
`$2E02` and moved foreground X by 5 pixels at jiffies 50 and 70 (expected
210/195, observed 215/200; tolerance 1).

Now retained. In the promoted build the motion oracle passes at all six samples
with no retuning of physics, and the control paths are exercised directly:
`controls.joystick2_right_rotates`, `controls.joystick2_left_rotates`,
`controls.joystick2_fire_thrusts` (companion pointer = player + 8 with
`$D015=31`), plus the keyboard fallbacks
`controls.keyboard_right_fallback`, `controls.keyboard_down_fallback` and
`controls.keyboard_modifier_fallback_thrusts` via `PEEK(653)`. Pause and `F7`
restart also pass (`controls.pause_tile_before_restart_at_$8400`,
`controls.f7_restart_returns_to_title`).

### 2. Crash post-mortem and out-of-flight text

Previously omitted: the isolated bank-0 candidate compiled to 10,107 bytes ending
`$2F79`, overlapping the sprite start by 254 bytes.

Now retained. The verified descent latched `$D01F` bit 0 at sprite Y 180 and took
the collision-gated path at line 630 (`crash.sprite_background_collision_latched`,
`descent.crash_path`), the explosion advanced through six settled pointer frames
at `ex`/`ex+10`/`ex+20`/`ex+30` with `$D015=252` and `$D01C=240`
(`crash.explosion_pointer_progression`, `crash.explosion_sprites_enabled`,
`crash.explosion_multicolour_enabled`), and the post-mortem rendered. Lems
decremented 4 → 3 (`crash.lems_decremented`).

The post-mortem prints **exactly one** line per crash. Line 1902 draws a byte
from the RNG table through the existing `gosub900` helper and branches on
`rv<128`: the low half reads a consequence from the 13-entry `DATA` table, the
high half falls through to the cause lines derived from `xz`, `hm`, `p` and
`m2`. Both branches clear the off-pad marker `xz` before returning, so the
marker still lives exactly one crash. `crash.post_mortem_single_message`
replaces the former `crash.post_mortem_cause_message` and
`crash.post_mortem_consequence_message` pair and asserts the exclusive-or: one
tier present, never both. Three VICE seeds exercised both branches — seed 1
`new crater 186 feet deep`, seed 2 `houston is billing your estate`, seed 3
`new crater 168 feet deep` — with the opposite tier absent every time.

The pad-failure fallthrough gained the single marker `xz=1:` so the post-mortem
knows a crash happened off-pad; the landing statement it precedes is still byte
for byte the bank-0 text, and the shared scoring lines (752, 753, 754, 755, 760)
are held byte-identical against `src/lunalight-bank0.bas`
(`landing.shared_scoring_identical`).

### 3. RNG, procedural terrain, pad metadata and refuel flag

Previously omitted: only 212 bytes remained when this layer was reached, and the
preserved integrated candidate was 12,316 bytes ending `$381A`, 2,463 bytes past
the sprite boundary.

Now retained. `src/rng.s` loads at `$4400-$4BFF`
(`static.rng_cpu_side_load_range`) between the music player and the relocated
sprites (`static.rng_clear_of_code_and_sprites`,
`static.assets_in_ascending_order`), and the canonical artifact covers it
(`static.full_artifact_covers_rng`). `SYS 17408` collects TOD-phase entropy
before the title; `SYS 17411` refills the table for each game.

The verified flight drew procedural terrain across the lower rows
(`flight.procedural_terrain_rows_present`) and five generated pads
(`flight.landing_pads_rendered`), each a run of screen code 100 with a green body
flanked by grey edge cells (`flight.landing_pad_colour_pattern`); the observed
run was rows 14, 14, 18, 21, 22 at widths 3-4. The landing verdict is now the
generic `px`/`pw`/`py`/`pb`/`rf` pad loop rather than hard-coded windows, pinned
by `landing.generic_pad_verdict_logic`, with the float velocity threshold 5 and
the tilt and upright-shape gates unchanged.

The refuel flag is the original payload's previously empty slot 243, patched by
`tools/make-shapes.py` and carried through the rebase: only that 64-byte block
and slot 244's, added later for the command module, differ from
`sprites/lsprite.prg` (`static.only_patched_slots_differ_from_original`,
`static.patched_slots_were_spare_now_hold_shapes`), it resolves to `$BCC0`
(`static.flag_block_maps_to_bank2_address`,
`runtime.flag_shape_resident_at_$BCC0`), and at runtime it is pointer 4 = 243,
light blue, unexpanded, enabled in `$D015` (`flight.flag_pointer[4]_at_$87FC`,
`flight.flag_sprite_colour_$D02B`, `flight.flag_sprite_not_y_expanded`,
`flight.flag_sprite_enabled`).

The shape is an Earth wire-globe pennant, not the earlier national flag, and it
renders at the sprite's natural 21-pixel height. Line 1198 therefore places it
at `fy=py(rz)-7` instead of `py(rz)-27` so the mast base still rests on the pad
line.

### 4. Attract mode

Previously omitted: its autopilot depends on the procedural layer's `px`, `pw`,
`py` and pad-selection metadata, which had not been retained.

Now retained, because that metadata exists. Advancing the live title jiffy past
the 20-second idle deadline started the demo (`attract.jiffy_timeout_starts_demo`).
Across three attempts the autopilot spawned at three distinct generated pads
(sprite X 44, 108, 172 — `attract.targets_advance_across_attempts`) and landed
successfully twice with no explosions, score advancing 0 → 573 → 801
(`attract.repeatable_successful_landings`). The demo never wrote the high score
(`attract.demo_never_updates_high_score`), and keyboard input, joystick input and
a final input all returned to the title
(`attract.keyboard_input_returns_to_title`,
`attract.joystick_input_returns_to_title`,
`attract.final_input_exit_returns_to_title`).

Those scores are the as-layered figures. The autopilot was reworked afterwards;
see "Attract mode now plays to win" below.

## Post-promotion corrections

### Landing windows were misregistered by half a sprite

`px(i)=24+cs*8` is the sprite-X value that puts the sprite's *left edge* on a
pad's left edge, but line 660 tested `pf`, that same left edge, against
`[px, px+pw*8)`. The lander graphic fills its 24-pixel sprite, so its visible
centre is `pf+12`. Three consequences followed:

- The centre bonus at line 740 was unreachable by anyone. The band where the
  craft physically sits on the pad and the band where `ABS(pf-cx)<3` holds do not
  intersect at either pad width.
- The attract autopilot's target, `px+(pw-3)*4`, is the visually centred
  position, which for a three-cell pad equals `px` exactly — the leftmost pixel
  that still counts as a landing, with no margin at all.
- A player could be credited with a landing while the craft hung entirely off
  the pad's right end.

Dad's fixed pads did not have this problem: pad 1's window was `pf` 71–88 with
the bullseye at 79/80, which is the visual centre sitting over the pad. The
half-sprite offset was baked into his hand-tuned constants and was lost when the
procedural layer started generating windows from `px`. Line 649 now reads
`pf=int(pp)+12`, which restores that calibration; the verifier pins the constant
through `SPRITE_CENTRE_OFFSET`. No physics constant changed, and the motion
oracle is unaffected because `pf` is only evaluated at touchdown.

### Attract mode now plays to win

Five autopilot changes, all behind `IF am`:

| Change | Line | Effect |
| --- | --- | --- |
| Steering no longer holds the thruster on | 1970-1977 | `jt` carries the fire bit separately, so a rotation frame only burns fuel when descent actually needs braking. Fuel burn is subtracted 1:1 from score at line 754 |
| Random destination without immediate repeats | 1922-1924 | A byte from the RNG table selects one of the five generated pads; an immediate repeat advances to the next pad |
| Refuel diversion | 1924 | Below 400 fuel the demo targets `rz` when that pad carries `rf()`, instead of cycling into a game over |
| Two-phase swoop | 1951-1967 | A cruise phase crosses the map at altitude and cancels the starting horizontal momentum; once aligned over the pad within a pixel with `hm=0`, `ap` latches and the descent phase begins |
| Suicide-burn descent | 1965 | Free-fall at `av=60` (no thrust) until the remaining altitude reaches the physics braking distance `bd=m2*m2/24+m2`, then brake at `av=4` to ride the landing gate down |

The first correction cheated visually: line 90 replaced the real spawn with
`pp=tx:hm=0`, placing the craft directly over the selected pad, which reduced
the flight to short vertical braking bursts. That override is removed. Attract
now enters from the exact normal `ep`/`hp` player sequence with its initial
horizontal momentum, crosses the terrain toward the random destination, aligns,
and then descends.

The descent itself was reworked from a low velocity clamp (12/8/4/1) into a
suicide burn so it matches how the game is meant to be flown: let the LEM fall
and thrust late for a just-in-time landing. The clamp is derived, not guessed —
`tools/verify-blitz-gameplay.py` only samples the first 70 jiffies, so the
descent profile was tuned against a one-dimensional model of the exact flight
loop (`m2+=.6` coast, `m2-=.6` thrust, `po+=.1+m2/20`, gate `int(m2)<=5`). The
braking distance `v^2/24 + v` px comes from that model: it is the altitude a
full straight-up burn needs to arrest velocity `v` to the gate. Swept across
every realistic descent start it never crashes, peaks at a 20-36 fall velocity
(against the old ~12 crawl), and touches down at `m2` 3.4-4.4, inside the gate
with margin for VICE timing. Two clean bonus landings per demo run verify
(`attract.repeatable_successful_landings`, `attract.lands_on_the_bonus_bullseye`);
the distinct real-play entries are pinned by
`attract.normal_spawn_sequence_across_attempts`.

### VEL label column

Line 530 printed its label after 33 cursor-rights while FUEL and HORZ used 35.
The value rows were already aligned at column 34, so only the one label moved.

### Soundtrack is title-only, in three voices

`src/music.s` gained a second entry point: `SYS 16896` installs, `SYS 16899`
restores `$0314` and clears `$D400-$D418`. Line 30 calls the stop entry the
moment `gosub1020` returns, whether that return came from F7 or from the attract
timeout, so neither real play nor the demo runs with music. The verifier checks
`$0314` in all three phases (`title.music_irq_installed`,
`flight.music_irq_uninstalled`, `attract.music_irq_uninstalled`).

Freeing the SID from flight duty is what paid for the extra voices: triangle bass
on the chord root, the existing sawtooth melody, and a pulse echo of the melody
four steps back, plucked on alternate steps. The player fits the same
`$4200`-to-`$4400` hole because the 32-step reprise now folds onto the theme
table instead of duplicating it, which bought back 64 bytes against 20 bytes of
bass table. Envelopes are rewritten on each note step rather than once at
install, so a caller that wipes the SID between notes — the bank-0 fallback does,
at line 990 — loses one step of tone instead of the rest of the tune.

Removing roughly one percent of per-frame CPU from flight did not move the motion
oracle: 6 of 6 samples still inside the recorded tolerances. The fixture was
recorded from the bank-0 fallback, which does have music in flight, so this was
the change most at risk of drifting and it did not.

## Orbiting command module

A cosmetic spacecraft added to the sky on sprite 7. Measured cost, compiling the
same tree twice with the original Blitz disk: **69 bytes** (11,587 versus 11,518
bytes of PRG), leaving 3,262 bytes of headroom below the music player.

The shape needed no new memory. Nine 64-byte slots of the original payload
(244-252) were still empty after the flag took 243, so `tools/make-shapes.py`
generalises the former `make-flag.py` to patch a table of slots. Slot 244
resolves to `$BD00` in bank 2. The load image is still 47,221 bytes and the
embed layout is unchanged; only 63 zero bytes inside the payload became shape
data. `static.only_patched_slots_differ_from_original` and
`static.patched_slots_were_spare_now_hold_shapes` were generalised from their
flag-only predecessors to assert exactly that for both slots.

Sprite 7 was the only defensible choice of the three sprites free during flight:

- Sprites 5, 6 and 7 carry no flight duty, but all three belong to the explosion
  cluster, so whichever one is borrowed has to be re-established after a round.
  Line 1212 does that alongside the flag, which line 720 already refreshes.
- The flight loop rewrites the whole of `$D010` every time the lander crosses
  x=255, and the right-half mask `fh=227+fm` set the X-MSB of sprites 5, 6 **and**
  7. That was harmless only because those sprites were disabled. A module on any
  of them would jump 256 pixels sideways at each crossing. Sprite 7 is the one
  whose MSB the crash code already leaves clear (it writes `$D010=96` for the
  right-hand explosion pair, sprites 5 and 6), so clearing bit 7 for flight as
  well — `fh=99+fm` — is consistent with the existing explosion geometry rather
  than a new special case. `flight.module_x_msb_clear` pins it.
- The resulting sub-256 X limit costs nothing: the HUD occupies columns 34-39,
  which is sprite X 296 and up, so the module has to stay left of it anyway.

Nothing reads the module. Sprite-sprite collision (`$D01E`) is never consulted,
and the landing gate at line 630 masks `$D01F` down to bit 0, so an extra sprite
latching its own background-collision bit changes no verdict. Sprite 7 has the
lowest display priority, so the lander passes in front of it.

Motion is per-round rather than per-frame, which keeps the hot loop untouched:
line 91 steps `mx` by 8 and wraps at 240, line 92 writes it, and line 1212
re-writes pointer, colour, position and the `$D015` bit after the explosion has
finished with sprite 7. The flight masks became 157 (coast) and 159 (thrust).
Line 720 could not carry the enable bit because it is one of the landing lines
held byte-identical to the bank-0 fallback, hence the `peek(v+21)or128` in 1212.

## Bank-2 layout and register findings

`$DD00` low bits `01` select bank 2; the screen and pointer table move to
`$8400`/`$87F8` (`poke648,132`), and the unchanged sprite payload is rebased from
`$2E7C` to `$AE7C`. Observed at both title and flight: `$DD00=$C5`, VIC bank
`$8000`, `$D018=$15`, screen matrix `$8400`, character base `$9000` resolved to
the character ROM image, `hibase=$84`.

`$D018` must select `$14` (reading back as `$15`, bit 0 unused). `$18` selects
blank RAM at `$A000`, which makes the display invisible and prevents the
sprite/background collision latch that gates landing.

The sprite payload occupies `$AE7C-$C073`, whose tail runs past the `$BFFF` bank
edge; every pointer the game uses spans `$AEC0-$BFBF`, inside the bank
(`static.used_pointer_blocks_inside_vic_bank`). BASIC's variables and arrays live
above the code (`VARTAB $3207`, `ARYTAB $3468`, `STREND $362A`) and string space
stays below the relocated sprites (`FRETOP $9FFF`, `MEMSIZ $A000` —
`capacity.string_space_below_relocated_sprites`).

## Optimization experiments (bank-2 relocation era)

| Experiment | Original-Blitz result | Motion result | Decision |
| --- | --- | --- | --- |
| Move sprite-colour POKEs from every loop to flight initialization | 9,719 bytes, size-neutral | Pass | Retained |
| Create hot variables first | 9,737 bytes, +18 | Pass | Rejected: compiled code only grew |
| Precomputed VIC/SID/pointer address bundle | 9,858 bytes, +139 | Fail | Rejected |
| Individual address aliases | 0 to +80 bytes | Not run when no size reduction | Rejected |
| One-time labels and change-only HUD | 9,960 bytes, +241 | Fail: position/velocity drift | Rejected |
| Remove unused `js`/`sn` initialization and empty separator | 9,675 bytes, -44 | Pass | Retained |

No fixed-point/TI physics, gravity, thrust, fuel, horizontal scaling, spawn
retune, change-only hot-loop HUD, Mars mode, or machine-code feature rewrite was
retained.

## Capacity of the freed region

`make verify-bank2-capacity` pads the canonical compiled code through the freed
range and proves the result still runs. With `BANK2_RUNTIME_RESERVE=1536`:

| Region | Range | Bytes |
| --- | --- | --- |
| Canonical code, with the command module | `$0801-$355D` | 11,613 |
| Zero-filled runtime workspace for BASIC's variables | `$355E-$3B5D` | 1,536 |
| `0xAA` filler through the ceiling | `$3B5E-$41FF` | 1,698 |

The padded artifact passes the motion oracle and the full runtime suite,
including the demo landings, and the filler above BASIC's live data reads back
byte-intact (`capacity.free_filler_intact_above_basic_data`). The `$2E7C-$4073`
range the sprites used to occupy is therefore genuinely available to code, not
merely unclaimed on paper.

The reserve was raised from 512 to 1,536 bytes. BASIC's live variables, arrays
and strings grow above the code as the game runs; the startup `STREND` snapshot
(`$3720`) understates the peak, and with only a 512-byte reserve the `0xAA`
filler overwrote live runtime data, perturbing emulation timing and the demo's
descent. The larger reserve keeps the filler clear of that working set, so the
capacity proof measures free space without disturbing the running program. It
still demonstrates ~1.7 KB of contiguous filler plus the reserve above the code,
well clear of the music player at `$4200`.

## Verification summary

| Check | Result |
| --- | --- |
| `make verify-baseline` | Exact byte match: `src/luna081426.bas` retokenizes to `current/luna081426` |
| `make verify-blitz-motion` (canonical, `$8400`/`$87F8`/`$AE7C`) | 6 of 6 samples within the recorded tolerances |
| `make verify-bank0-motion` (fallback, `$0400`/`$07F8`) | 6 of 6 samples within the recorded tolerances |
| `make verify-bank2` (canonical runtime suite) | 87 of 87 checks passed, including `flight.pointer[7]_at_$87FF`, `flight.module_sprite_colour_$D02E`, `flight.module_sprite_y_$D00F` and `flight.module_x_msb_clear` |
| `make verify-blitz-gameplay` (canonical aggregate) | Motion oracle plus the 87-check suite, 0 failures |
| `make verify-bank2-capacity` | Padded artifact (`BANK2_RUNTIME_RESERVE=1536`): 6 of 6 motion samples plus 90 of 90 checks, including the demo landings and `capacity.free_filler_intact_above_basic_data` |
| Bank-0 collision control descent | `$D01F` union `$D1`, first latch at sprite Y 204 on `build/lunalight-bank0-blitz-full.prg` (`reference.sprite_background_collision_latched`) |
| `make smoke` | Exit screenshot decodes to the title: `l u n a l i g h t`, `press f7 to start`, `attract mode in 20 seconds` |
| `make d64-boot` | `build/lunalight.d64` lists one 186-block `lunalight` PRG with 478 blocks free, autoloads, and reaches the same title screen |

## Load cost of the promoted package

The canonical load image spans `$0801-$C073` (47,221 bytes) because a single
`,8,1` load must place the code, music, RNG and the sprites at `$AE7C`. The bank-0
fallback image is 15,239 bytes. Measured under `-warp`: still loading at
110,000,000 cycles, title screen up at 130,000,000, attract mode by 150,000,000.
`SMOKE_CYCLES` was raised from 80,000,000 (which captured a mid-load
`searching for *` / `loading` screen) to 135,000,000, and `BENCH_CYCLES` from
100,000,000 to 200,000,000 so the unwarped run reaches attract-mode flight. Both
runs pass `+autostart-delay-random` so the capture point is deterministic. The
bench run measured ~100 s of wall clock, because the SID dump device does not
throttle emulation to 100%.

| Artifact | Load image | Bytes |
| --- | --- | --- |
| Canonical `build/lunalight-blitz-full.prg` | `$0801-$C073` | 47,221 |
| Bank-0 fallback `build/lunalight-bank0-blitz-full.prg` | `$0801-$43E5` | 15,335 |
| Capacity `build/lunalight-bank2-capacity-full.prg` | `$0801-$C073` | 47,221 |

The `strict` mode of `tools/verify-blitz-gameplay.py` compares the entire decoded
screen. That only ever described the bank-0 static-terrain screen, so it is no
longer a canonical gate: the promoted build generates different terrain every
game by design. It remains available in the tool for bank-0 lineage work, and
`make record-blitz-baseline` is bound to the bank-0 fallback so the fixture keeps
describing the lineage it was recorded from.

Successful landing is not input-driven by the six-sample oracle, but attract mode
demonstrates it end to end, and the collision latch that gates it is exercised in
both the canonical and bank-0 descents. Gameplay feel still wants Dad's
confirmation.
