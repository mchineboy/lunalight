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
| **Canonical promoted build (`src/lunalight.bas`)** | **11,367 bytes** | **`$0801-$3467`** | **`$41FF`** | **3,480 bytes** |

The last two rows were measured in this promotion run (`make blitz-bank0` and
`make blitz` from a clean `build/`, plus `tools/bank2-capacity.py`). The first and
third rows are carried forward from the earlier layering and optimization work and
were not re-measured, so the derivations below that use the 9,675-byte figure
inherit that provenance.

Derived from those measurements:

- The bank-2 relocation itself cost **5 bytes** (9,675 versus 9,670).
- All four feature layers together cost **1,692 bytes** (11,367 versus 9,675).
- Under the old bank-0 layout the promoted code would overrun the `$2E7C` sprite
  start by **1,516 bytes**, so it cannot exist there. Reported directly by
  `tools/bank2-capacity.py` as `headroom_under_old_sprite_layout_bytes: -1516`.
- The relocation raised the reachable ceiling from `$2E7B` to `$41FF`, a
  **4,996-byte** headroom gain, and **3,480 bytes** remain free above the
  promoted code.
- The integrated candidate measured during the bank-0 era was 12,316 bytes ending
  `$381A`. The promoted integrated build is **949 bytes smaller**, and the
  earlier estimate that the layer set needed roughly 2,646 additional bytes
  overstated the real cost of 1,692.

## Layer results

Each layer's runtime evidence comes from `make verify-bank2` on the canonical
artifact (`tools/verify-bank2.py`, 80 checks, 0 failures) and from
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
`crash.explosion_multicolour_enabled`), and both message tiers rendered:
cause `new crater 189 feet deep` (`crash.post_mortem_cause_message`) and
consequence `taxpayers demand an inquiry` from the 13-entry `DATA` table
(`crash.post_mortem_consequence_message`). Lems decremented 4 → 3
(`crash.lems_decremented`).

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
`tools/make-flag.py` and carried through the rebase: only that 64-byte block
differs from `sprites/lsprite.prg`
(`static.only_flag_slot_differs_from_original`,
`static.flag_slot_was_spare_now_holds_shape`), it resolves to `$BCC0`
(`static.flag_block_maps_to_bank2_address`,
`runtime.flag_shape_resident_at_$BCC0`), and at runtime it is pointer 4 = 243,
cyan, Y-expanded, enabled in `$D015` (`flight.flag_pointer[4]_at_$87FC`,
`flight.flag_sprite_colour_$D02B`, `flight.flag_sprite_y_expanded`,
`flight.flag_sprite_enabled`).

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
range and proves the result still runs. With `BANK2_RUNTIME_RESERVE=512`:

| Region | Range | Bytes |
| --- | --- | --- |
| Canonical code | `$0801-$3467` | 11,367 |
| Zero-filled runtime workspace for BASIC's variables | `$3468-$3667` | 512 |
| `0xAA` filler through the ceiling | `$3668-$41FF` | 2,968 |

The padded artifact passes the motion oracle and the runtime suite, and the
filler above BASIC's live data reads back byte-intact
(`capacity.free_filler_intact_above_basic_data`). The `$2E7C-$4073` range the
sprites used to occupy is therefore genuinely available to code, not merely
unclaimed on paper.

## Verification summary

| Check | Result |
| --- | --- |
| `make verify-baseline` | Exact byte match: `src/luna081426.bas` retokenizes to `current/luna081426` |
| `make verify-blitz-motion` (canonical, `$8400`/`$87F8`/`$AE7C`) | 6 of 6 samples within the recorded tolerances |
| `make verify-bank0-motion` (fallback, `$0400`/`$07F8`) | 6 of 6 samples within the recorded tolerances |
| `make verify-bank2` (canonical runtime suite) | 80 of 80 checks passed |
| `make verify-blitz-gameplay` (canonical aggregate) | Motion oracle plus the 80-check suite, 0 failures |
| `make verify-bank2-capacity` | Padded artifact: 6 of 6 motion samples plus 83 of 83 checks, including `capacity.free_filler_intact_above_basic_data` |
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
| Bank-0 fallback `build/lunalight-bank0-blitz-full.prg` | `$0801-$4385` | 15,239 |
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
