PETCAT ?= petcat
X64SC  ?= x64sc
C1541  ?= c1541
PYTHON ?= python3
CA65   ?= ca65
LD65   ?= ld65
NODE   ?= node
JAVA   ?= java

SRC_DIR   := src
BUILD_DIR := build
TOOLS_DIR := tools

# Canonical source: the promoted VIC-bank-2 feature build (music, RNG,
# procedural terrain, refuel flag, joystick, crash text, attract mode).
SRC_CANONICAL := $(SRC_DIR)/lunalight.bas
# Runnable fallback: the pre-promotion bank-0 source, kept byte-for-byte. It is
# also the control the promoted build is compared against.
SRC_BANK0     := $(SRC_DIR)/lunalight-bank0.bas

# Reblitz64: host-side JavaScript port of the Blitz!/Austro-Speed BASIC compiler.
# EXPERIMENTAL. Overruns the bank-0 sprite region; not used for any package.
# Bound to the bank-0 source so it never packages bank-0 assets with bank-2 code.
REBLITZ   := $(TOOLS_DIR)/reblitz64/docs/reblitz64.js
BLITZ_INTVARS ?=
REBLITZ_PRG := $(BUILD_DIR)/lunalight-bank0-reblitz.prg

# Original C64 Blitz! compiler disk — required tracked input (do not modify).
BLITZ_DISK := $(TOOLS_DIR)/BLITZ.d64
BLITZ_DRIVER := $(TOOLS_DIR)/blitz-compile.py

# Canonical original-Blitz artifacts, compiled from the promoted bank-2 source.
BLITZ_PRG  := $(BUILD_DIR)/lunalight-blitz.prg
BLITZ_FULL := $(BUILD_DIR)/lunalight-blitz-full.prg

# Bank-0 fallback artifacts, compiled from the pre-promotion source with the
# original (non-rebased) sprites and music only.
BLITZ_BANK0_PRG  := $(BUILD_DIR)/lunalight-bank0-blitz.prg
BLITZ_BANK0_FULL := $(BUILD_DIR)/lunalight-bank0-blitz-full.prg

BLITZ_GAMEPLAY_DRIVER := $(TOOLS_DIR)/verify-blitz-gameplay.py
# Motion fixture recorded from the bank-0 lineage; unchanged by the promotion.
BLITZ_GAMEPLAY_BASELINE := $(TOOLS_DIR)/fixtures/blitz-gameplay-baseline.json
BLITZ_GAMEPLAY_SCREENSHOT := $(BUILD_DIR)/blitz-gameplay.png

# Canonical bank-2 package: VIC bank 2 ($8000), screen $8400, pointers $87F8,
# sprites rebased to $AE7C.
BANK2_SCREEN_BASE := 0x8400
BANK2_POINTER_BASE := 0x87f8
BANK2_SPRITE_ADDRESS := 0xae7c
BANK2_VERIFY_DRIVER := $(TOOLS_DIR)/verify-bank2.py
BANK2_CAPACITY_DRIVER := $(TOOLS_DIR)/bank2-capacity.py
BANK2_CAPACITY_PRG := $(BUILD_DIR)/lunalight-bank2-capacity.prg
BANK2_CAPACITY_FULL := $(BUILD_DIR)/lunalight-bank2-capacity-full.prg
BANK2_CAPACITY_REPORT := $(BUILD_DIR)/bank2-capacity.json
BANK2_RUNTIME_RESERVE ?= 1536

# MOSpeed: native 6502 BASIC V2 cross-compiler (EgonOlsen71/basicv2).
# Alternate toolchain bound to the bank-0 source: its memholes and
# patch-assets.py place bank-0 assets at $2E7C/$4200/$4400. No bank-2 parity.
MOSPEED_JAR ?= $(TOOLS_DIR)/mospeed/basicv2.jar
MOSPEED_URL ?= https://github.com/EgonOlsen71/basicv2/raw/master/dist/basicv2.jar
# Locked regions matching embed layout: sprites $2E7C-$4073, music+rng $4200-$4BFF
MOSPEED_MEMHOLE := $$2E7C-$$4073,$$4200-$$4BFF
MOSPEED_PRG := $(BUILD_DIR)/lunalight-bank0-mospeed.prg
MOSPEED_FULL := $(BUILD_DIR)/lunalight-bank0-mospeed-full.prg

# Sprite shapes for pointers 187-194/203-212/253/254
SPRITES := sprites/lsprite.prg
SPRITES_BANK2 := $(BUILD_DIR)/lsprite-bank2.prg
# Same shapes plus the refuel-pad flag in spare slot 243 and the orbiting
# command module in spare slot 244 (MOSpeed/interpreted alt)
SPRITES_OUT := $(BUILD_DIR)/lsprite-shapes.prg
# Bank-2 payload: added shapes patched into their spare slots, then rebased
# $2E7C->$AE7C so slot 243 lands at VIC-bank-2 $BCC0 and slot 244 at $BD00.
SPRITES_BANK2_SHAPES := $(BUILD_DIR)/lsprite-shapes-bank2.prg
MUSIC_SRC := $(SRC_DIR)/music.s
MUSIC_CFG := $(TOOLS_DIR)/music.cfg
MUSIC_OBJ := $(BUILD_DIR)/music.o
MUSIC_PRG := $(BUILD_DIR)/music.prg
# TOD entropy collector + PRNG table at $4400-$4BFF; the canonical package's
# procedural terrain calls it (SYS 17408 / SYS 17411).
RNG_SRC   := $(SRC_DIR)/rng.s
RNG_CFG   := $(TOOLS_DIR)/rng.cfg
RNG_OBJ   := $(BUILD_DIR)/rng.o
RNG_PRG   := $(BUILD_DIR)/rng.prg

# Tokenized BASIC for both lineages.
BASIC_PRG := $(BUILD_DIR)/lunalight.prg $(BUILD_DIR)/lunalight-bank0.prg
# Interpreted BASIC V2 + assets is a bank-0-only alternate (bank-0 asset layout).
FULL_PRG  := $(BUILD_DIR)/lunalight-bank0-full.prg

# Canonical disk: self-contained promoted original-Blitz full PRG.
D64 := $(BUILD_DIR)/lunalight.d64
# Alternate MOSpeed multi-file disk (former default d64 output), bank-0 lineage.
D64_MOSPEED := $(BUILD_DIR)/lunalight-bank0-mospeed.d64

# The canonical image spans $0801-$C073, so a single ",8,1" load moves ~47KB over
# the serial bus: measured still loading at 110,000,000 cycles and showing the
# title at 130,000,000 (autoload, then ~3.2s of TOD entropy collection for the
# RNG). 135,000,000 lands inside the title's 20-second window, before attract
# mode starts. The bank-0 fallback is a third of the size and needs far less.
SMOKE_CYCLES ?= 135000000
# 200,000,000 unwarped cycles: autoload, title, then attract-mode flight at
# normal speed, which is what makes this run useful for judging cadence. The SID
# dump device does not throttle to 100%, so the measured wall time is ~100s.
BENCH_CYCLES ?= 200000000

GIF := docs/lunalight-gameplay.gif
GIF_DRIVER := $(TOOLS_DIR)/make-gameplay-gif.py

.PHONY: all prg full run run-blitz run-basic run-mospeed smoke bench clean \
	blitz blitz-bank2 run-bank2 blitz-bank0 run-bank0 reblitz mospeed \
	d64 d64-boot d64-mospeed gif \
	verify-baseline record-blitz-baseline verify-blitz-gameplay verify-blitz-motion \
	verify-bank0-motion verify-bank2-motion verify-bank2 verify-bank2-capacity \
	bank2-capacity

# Every VICE-driven target owns the emulator, its binary monitor port and its
# screenshots; parallel makes would interleave them.
.NOTPARALLEL:

# Default: canonical original-Blitz compile of the promoted bank-2 source plus
# the music, RNG and rebased flag-sprite embed.
all: blitz

prg: $(BASIC_PRG)

# Interpreted BASIC V2 + bank-0 assets (alternate; not the canonical package).
full: $(FULL_PRG)

mospeed: $(MOSPEED_FULL)

d64: $(D64)

d64-mospeed: $(D64_MOSPEED)

# Title then attract-mode autopilot; regenerates the README gameplay GIF.
gif: $(GIF)

$(GIF): $(BLITZ_FULL) $(GIF_DRIVER) $(TOOLS_DIR)/vice_monitor.py
	$(PYTHON) $(GIF_DRIVER) --prg $(BLITZ_FULL) --output $@

verify-baseline:
	@set -eu; \
	tmpdir=$$(mktemp -d "$${TMPDIR:-/tmp}/lunalight-roundtrip.XXXXXX"); \
	trap 'rm -rf "$$tmpdir"' EXIT; \
	$(PETCAT) -w2 -o "$$tmpdir/luna081426" -- $(SRC_DIR)/luna081426.bas; \
	cmp current/luna081426 "$$tmpdir/luna081426"; \
	echo "verify-baseline: exact byte match"

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(BUILD_DIR)/%.prg: $(SRC_DIR)/%.bas | $(BUILD_DIR)
	$(PETCAT) -w2 -o $@ -- $<

$(MUSIC_OBJ): $(MUSIC_SRC) | $(BUILD_DIR)
	$(CA65) -o $@ $<

$(MUSIC_PRG): $(MUSIC_OBJ) $(MUSIC_CFG)
	$(LD65) -C $(MUSIC_CFG) -o $@ $(MUSIC_OBJ)

$(RNG_OBJ): $(RNG_SRC) | $(BUILD_DIR)
	$(CA65) -o $@ $<

$(RNG_PRG): $(RNG_OBJ) $(RNG_CFG)
	$(LD65) -C $(RNG_CFG) -o $@ $(RNG_OBJ)

$(SPRITES_OUT): $(SPRITES) $(TOOLS_DIR)/make-shapes.py | $(BUILD_DIR)
	$(PYTHON) $(TOOLS_DIR)/make-shapes.py $(SPRITES) $@

$(SPRITES_BANK2): $(SPRITES) $(TOOLS_DIR)/rebase-prg-load.py | $(BUILD_DIR)
	$(PYTHON) $(TOOLS_DIR)/rebase-prg-load.py $(SPRITES) $@ \
		--from-address 0x2e7c \
		--to-address 0xae7c

# Shapes patched (make-shapes) then rebased into VIC bank 2. They land in the
# original sprite payload's spare slots before the load address changes.
$(SPRITES_BANK2_SHAPES): $(SPRITES_OUT) $(TOOLS_DIR)/rebase-prg-load.py | $(BUILD_DIR)
	$(PYTHON) $(TOOLS_DIR)/rebase-prg-load.py $(SPRITES_OUT) $@ \
		--from-address 0x2e7c \
		--to-address 0xae7c

$(BUILD_DIR)/%-full.prg: $(BUILD_DIR)/%.prg $(SPRITES_OUT) $(MUSIC_PRG) $(RNG_PRG) $(TOOLS_DIR)/embed-sprites.py
	$(PYTHON) $(TOOLS_DIR)/embed-sprites.py $< $(SPRITES_OUT) $(MUSIC_PRG) $(RNG_PRG) $@

# Canonical: compile the promoted source with the original Blitz! disk, then
# append music, RNG and the rebased flag sprites in ascending address order.
blitz: $(BLITZ_FULL)

# Bank-2 names kept as aliases; the canonical package *is* the bank-2 package.
blitz-bank2: blitz

$(BLITZ_DISK):
	@echo "error: missing required compiler disk $(BLITZ_DISK)" >&2; \
	echo "Track tools/BLITZ.d64 in git; do not substitute Reblitz64 or MOSpeed." >&2; \
	exit 1

$(BLITZ_PRG): $(BUILD_DIR)/lunalight.prg $(BLITZ_DISK) $(BLITZ_DRIVER) $(TOOLS_DIR)/vice_monitor.py | $(BUILD_DIR)
	$(PYTHON) $(BLITZ_DRIVER) \
		--compiler-disk $(BLITZ_DISK) \
		--source $< \
		--build $(BUILD_DIR) \
		--output $@ \
		--vice $(X64SC) \
		--c1541 $(C1541)

# Ascending embed order: code, music $4200, RNG $4400-$4BFF, flag sprites $AE7C.
$(BLITZ_FULL): $(BLITZ_PRG) $(MUSIC_PRG) $(RNG_PRG) $(SPRITES_BANK2_SHAPES) $(TOOLS_DIR)/embed-sprites.py
	$(PYTHON) $(TOOLS_DIR)/embed-sprites.py $(BLITZ_PRG) $(MUSIC_PRG) $(RNG_PRG) $(SPRITES_BANK2_SHAPES) $@

# Bank-0 fallback: pre-promotion source, original sprites at $2E7C, music $4200.
blitz-bank0: $(BLITZ_BANK0_FULL)

$(BLITZ_BANK0_PRG): $(BUILD_DIR)/lunalight-bank0.prg $(BLITZ_DISK) $(BLITZ_DRIVER) $(TOOLS_DIR)/vice_monitor.py | $(BUILD_DIR)
	$(PYTHON) $(BLITZ_DRIVER) \
		--compiler-disk $(BLITZ_DISK) \
		--source $< \
		--build $(BUILD_DIR) \
		--output $@ \
		--vice $(X64SC) \
		--c1541 $(C1541)

$(BLITZ_BANK0_FULL): $(BLITZ_BANK0_PRG) $(SPRITES) $(MUSIC_PRG) $(TOOLS_DIR)/embed-sprites.py
	$(PYTHON) $(TOOLS_DIR)/embed-sprites.py $(BLITZ_BANK0_PRG) $(SPRITES) $(MUSIC_PRG) $@

# The record target intentionally mutates the tracked motion fixture. The
# fixture describes the bank-0 lineage, so it is recorded from the bank-0
# fallback artifact at bank-0 addresses, never from the promoted build.
record-blitz-baseline: $(BLITZ_BANK0_FULL) $(BLITZ_GAMEPLAY_DRIVER) $(TOOLS_DIR)/vice_monitor.py
	$(PYTHON) $(BLITZ_GAMEPLAY_DRIVER) \
		--record \
		--prg $(BLITZ_BANK0_FULL) \
		--baseline $(BLITZ_GAMEPLAY_BASELINE) \
		--screenshot $(BUILD_DIR)/bank0-gameplay.png \
		--log $(BUILD_DIR)/bank0-gameplay.log \
		--vice $(X64SC)

# Canonical aggregate: the motion oracle plus the full promoted-runtime suite
# (title, HUD, procedural terrain, pads, refuel flag, sprite residency, BASIC
# memory pointers, pause, joystick/keyboard controls, collision, crash
# post-mortem, attract mode, and a bank-0 collision control descent).
verify-blitz-gameplay: verify-blitz-motion verify-bank2
	@echo "verify-blitz-gameplay: canonical aggregate passed" \
		"(motion oracle + $(BANK2_VERIFY_DRIVER) runtime suite on $(BLITZ_FULL))"

# Canonical motion regression: promoted bank-2 addresses, original fixture.
verify-blitz-motion verify-bank2-motion: $(BLITZ_FULL) $(BLITZ_GAMEPLAY_BASELINE) $(BLITZ_GAMEPLAY_DRIVER) $(TOOLS_DIR)/vice_monitor.py
	$(PYTHON) $(BLITZ_GAMEPLAY_DRIVER) \
		--mode motion \
		--prg $(BLITZ_FULL) \
		--screen-base $(BANK2_SCREEN_BASE) \
		--pointer-base $(BANK2_POINTER_BASE) \
		--sprite-embed-address $(BANK2_SPRITE_ADDRESS) \
		--baseline $(BLITZ_GAMEPLAY_BASELINE) \
		--screenshot $(BLITZ_GAMEPLAY_SCREENSHOT) \
		--log $(BUILD_DIR)/blitz-gameplay.log \
		--vice $(X64SC)

# Same oracle against the bank-0 fallback at bank-0 addresses.
verify-bank0-motion: $(BLITZ_BANK0_FULL) $(BLITZ_GAMEPLAY_BASELINE) $(BLITZ_GAMEPLAY_DRIVER) $(TOOLS_DIR)/vice_monitor.py
	$(PYTHON) $(BLITZ_GAMEPLAY_DRIVER) \
		--mode motion \
		--prg $(BLITZ_BANK0_FULL) \
		--baseline $(BLITZ_GAMEPLAY_BASELINE) \
		--screenshot $(BUILD_DIR)/bank0-gameplay.png \
		--log $(BUILD_DIR)/bank0-gameplay.log \
		--vice $(X64SC)

# Canonical layout and runtime verification: bank/register configuration, screen
# and pointer relocation, sprite residency, procedural terrain and pads, refuel
# flag, controls, pause, collision, crash text, attract mode. The bank-0
# fallback supplies the collision-latch control descent, and its source is the
# byte-identity control for the shared scoring lines.
verify-bank2: $(BLITZ_FULL) $(BLITZ_BANK0_FULL) $(BANK2_VERIFY_DRIVER) $(TOOLS_DIR)/vice_monitor.py
	$(PYTHON) $(BANK2_VERIFY_DRIVER) \
		--prg $(BLITZ_FULL) \
		--code-prg $(BLITZ_PRG) \
		--reference-prg $(BLITZ_BANK0_FULL) \
		--sprite-prg $(SPRITES_BANK2_SHAPES) \
		--original-sprite-prg $(SPRITES) \
		--patched-sprite-prg $(SPRITES_OUT) \
		--music-prg $(MUSIC_PRG) \
		--rng-prg $(RNG_PRG) \
		--canonical-source $(SRC_BANK0) \
		--bank2-source $(SRC_CANONICAL) \
		--screen-base $(BANK2_SCREEN_BASE) \
		--pointer-base $(BANK2_POINTER_BASE) \
		--report $(BUILD_DIR)/bank2-verify.json \
		--shot-dir $(BUILD_DIR) \
		--shot-prefix bank2 \
		--log $(BUILD_DIR)/bank2-verify.log \
		--vice $(X64SC)

# Capacity artifact: pad the canonical compiled code through the freed $2E7C
# region, keeping a zero-filled runtime workspace for BASIC's variables.
bank2-capacity: $(BANK2_CAPACITY_FULL)

$(BANK2_CAPACITY_PRG) $(BANK2_CAPACITY_REPORT): $(BLITZ_PRG) $(SPRITES_BANK2_SHAPES) $(SPRITES) $(MUSIC_PRG) $(BANK2_CAPACITY_DRIVER)
	$(PYTHON) $(BANK2_CAPACITY_DRIVER) \
		--code-prg $(BLITZ_PRG) \
		--sprite-prg $(SPRITES_BANK2_SHAPES) \
		--original-sprite-prg $(SPRITES) \
		--music-prg $(MUSIC_PRG) \
		--output $(BANK2_CAPACITY_PRG) \
		--report $(BANK2_CAPACITY_REPORT) \
		--reserve-bytes $(BANK2_RUNTIME_RESERVE)

$(BANK2_CAPACITY_FULL): $(BANK2_CAPACITY_PRG) $(MUSIC_PRG) $(RNG_PRG) $(SPRITES_BANK2_SHAPES) $(TOOLS_DIR)/embed-sprites.py
	$(PYTHON) $(TOOLS_DIR)/embed-sprites.py $(BANK2_CAPACITY_PRG) $(MUSIC_PRG) $(RNG_PRG) $(SPRITES_BANK2_SHAPES) $@

verify-bank2-capacity: $(BANK2_CAPACITY_FULL) $(BANK2_CAPACITY_REPORT) $(BLITZ_BANK0_FULL) $(BANK2_VERIFY_DRIVER) $(BLITZ_GAMEPLAY_BASELINE) $(BLITZ_GAMEPLAY_DRIVER) $(TOOLS_DIR)/vice_monitor.py
	$(PYTHON) $(BLITZ_GAMEPLAY_DRIVER) \
		--mode motion \
		--prg $(BANK2_CAPACITY_FULL) \
		--screen-base $(BANK2_SCREEN_BASE) \
		--pointer-base $(BANK2_POINTER_BASE) \
		--sprite-embed-address $(BANK2_SPRITE_ADDRESS) \
		--baseline $(BLITZ_GAMEPLAY_BASELINE) \
		--screenshot $(BUILD_DIR)/bank2-capacity-gameplay.png \
		--log $(BUILD_DIR)/bank2-capacity-gameplay.log \
		--vice $(X64SC)
	$(PYTHON) $(BANK2_VERIFY_DRIVER) \
		--prg $(BANK2_CAPACITY_FULL) \
		--code-prg $(BANK2_CAPACITY_PRG) \
		--reference-prg $(BLITZ_BANK0_FULL) \
		--sprite-prg $(SPRITES_BANK2_SHAPES) \
		--original-sprite-prg $(SPRITES) \
		--patched-sprite-prg $(SPRITES_OUT) \
		--music-prg $(MUSIC_PRG) \
		--rng-prg $(RNG_PRG) \
		--canonical-source $(SRC_BANK0) \
		--bank2-source $(SRC_CANONICAL) \
		--screen-base $(BANK2_SCREEN_BASE) \
		--pointer-base $(BANK2_POINTER_BASE) \
		--filler-report $(BANK2_CAPACITY_REPORT) \
		--report $(BUILD_DIR)/bank2-capacity-verify.json \
		--shot-dir $(BUILD_DIR) \
		--shot-prefix bank2-capacity \
		--log $(BUILD_DIR)/bank2-capacity-verify.log \
		--vice $(X64SC)

# EXPERIMENTAL host-side JavaScript port (bank-0 BASIC only; no asset embed).
reblitz: $(REBLITZ_PRG)

$(REBLITZ_PRG): $(BUILD_DIR)/lunalight-bank0.prg $(REBLITZ) | $(BUILD_DIR)
	$(NODE) $(REBLITZ) $< $@ $(BLITZ_INTVARS)

$(MOSPEED_JAR):
	mkdir -p $(dir $@)
	curl -fsSL -o $@ $(MOSPEED_URL)

$(MOSPEED_PRG): $(SRC_BANK0) $(MOSPEED_JAR) | $(BUILD_DIR)
	$(JAVA) -cp $(MOSPEED_JAR) com.sixtyfour.cbmnative.shell.MoSpeedCL \
		$< \
		/target=$@ \
		/compactlevel=4 \
		'/memhole=$(MOSPEED_MEMHOLE)'

$(MOSPEED_FULL): $(MOSPEED_PRG) $(SPRITES_OUT) $(MUSIC_PRG) $(RNG_PRG) $(TOOLS_DIR)/patch-assets.py
	$(PYTHON) $(TOOLS_DIR)/patch-assets.py $< $(SPRITES_OUT) $(MUSIC_PRG) $(RNG_PRG) $@

# Canonical disk: self-contained promoted original-Blitz full PRG (LOAD"*",8,1 / RUN).
$(D64): $(BLITZ_FULL)
	$(C1541) -format "lunalight,24" d64 $@ \
		-write $(BLITZ_FULL) lunalight

# Alternate MOSpeed disk (former default): bank-0 compiled PRG + tokenized
# bank-0 source + assets.
$(D64_MOSPEED): $(MOSPEED_FULL) $(BUILD_DIR)/lunalight-bank0.prg $(MUSIC_PRG) $(RNG_PRG)
	$(C1541) -format "lunalight,24" d64 $@ \
		-write $(MOSPEED_FULL) lunalight \
		-write $(BUILD_DIR)/lunalight-bank0.prg lunalight.bas \
		-write $(MUSIC_PRG) music \
		-write $(RNG_PRG) rng

run run-blitz run-bank2: $(BLITZ_FULL)
	$(X64SC) -autostart $<

run-bank0: $(BLITZ_BANK0_FULL)
	$(X64SC) -autostart $<

run-basic: $(FULL_PRG)
	$(X64SC) -autostart $<

run-mospeed: $(MOSPEED_FULL)
	$(X64SC) -autostart $<

# VICE does not clock the SID under `-sounddev dummy`, so sid-dependent code
# freezes. `dump` keeps the SID clocked without needing an audio device.
SOUNDDEV ?= dump

# Headless warp smoke of the canonical Blitz artifact; inspect build/*-smoke.png,
# or decode it with `python3 tools/readscreen.py build/lunalight-blitz-full-smoke.png`.
smoke: $(BLITZ_FULL)
	@prg=$(BLITZ_FULL); \
	shot=$${prg%.prg}-smoke.png; \
	echo "smoke: $$prg -> $$shot"; \
	$(X64SC) -default -warp +autostart-delay-random \
		-sounddev $(SOUNDDEV) -soundarg $${prg%.prg}-sid.dump \
		-limitcycles $(SMOKE_CYCLES) -exitscreenshot $$shot \
		-autostart $$prg > $${prg%.prg}-smoke.log 2>&1 || true; \
	test -s $$shot || { echo "smoke FAILED: no screenshot for $$prg"; exit 1; }

# Headless warp boot of the canonical disk: directory listing plus a screenshot
# taken after the disk autoloads, so the packaged D64 is proven to run.
d64-boot: $(D64)
	$(C1541) -attach $(D64) -list
	@$(X64SC) -default -warp +autostart-delay-random \
		-sounddev $(SOUNDDEV) -soundarg $(BUILD_DIR)/lunalight-d64-boot-sid.dump \
		-limitcycles $(SMOKE_CYCLES) \
		-exitscreenshot $(BUILD_DIR)/lunalight-d64-boot.png \
		-autostart $(D64) > $(BUILD_DIR)/lunalight-d64-boot.log 2>&1 || true
	@test -s $(BUILD_DIR)/lunalight-d64-boot.png || { echo "d64-boot FAILED: no screenshot"; exit 1; }
	@echo "d64-boot ok: $(BUILD_DIR)/lunalight-d64-boot.png"

# Normal-speed short run for timing feel (no warp)
bench: $(BLITZ_FULL)
	@echo "bench: normal-speed $(BENCH_CYCLES) cycles"
	$(X64SC) -default +autostart-delay-random \
		-sounddev $(SOUNDDEV) -soundarg $(BUILD_DIR)/lunalight-blitz-bench-sid.dump \
		-limitcycles $(BENCH_CYCLES) \
		-exitscreenshot $(BUILD_DIR)/lunalight-blitz-bench.png \
		-autostart $(BLITZ_FULL) \
		> $(BUILD_DIR)/lunalight-blitz-bench.log 2>&1 || true
	@test -s $(BUILD_DIR)/lunalight-blitz-bench.png || { echo "bench FAILED"; exit 1; }
	@echo "bench ok: $(BUILD_DIR)/lunalight-blitz-bench.png"

clean:
	rm -rf $(BUILD_DIR)
