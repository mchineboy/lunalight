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

# Reblitz64: host-side JavaScript port of the Blitz!/Austro-Speed BASIC compiler.
# EXPERIMENTAL. Overruns the sprite region; not used for the D64 package.
REBLITZ   := $(TOOLS_DIR)/reblitz64/docs/reblitz64.js
BLITZ_INTVARS ?=
BLITZ_PRG := $(BUILD_DIR)/lunalight-blitz.prg

# MOSpeed: native 6502 BASIC V2 cross-compiler (EgonOlsen71/basicv2).
# Memholes keep sprites/music/RNG at their fixed addresses; patch-assets.py
# fills those holes. Physics (gv/th/ka/sl) remain interpreter-tuned.
MOSPEED_JAR ?= $(TOOLS_DIR)/mospeed/basicv2.jar
MOSPEED_URL ?= https://github.com/EgonOlsen71/basicv2/raw/master/dist/basicv2.jar
# Locked regions matching embed layout: sprites $2E7C-$4073, music+rng $4200-$4BFF
MOSPEED_MEMHOLE := $$2E7C-$$4073,$$4200-$$4BFF
MOSPEED_PRG := $(BUILD_DIR)/lunalight-mospeed.prg
MOSPEED_FULL := $(BUILD_DIR)/lunalight-mospeed-full.prg

# Sprite shapes for pointers 187-194/203-212/253/254
SPRITES := sprites/lsprite.prg
# Same shapes plus the refuel-pad flag in spare slot 243
SPRITES_OUT := $(BUILD_DIR)/lsprite-flag.prg
MUSIC_SRC := $(SRC_DIR)/music.s
MUSIC_CFG := $(TOOLS_DIR)/music.cfg
MUSIC_OBJ := $(BUILD_DIR)/music.o
MUSIC_PRG := $(BUILD_DIR)/music.prg
# TOD entropy collector + PRNG table; must link above the music
RNG_SRC   := $(SRC_DIR)/rng.s
RNG_CFG   := $(TOOLS_DIR)/rng.cfg
RNG_OBJ   := $(BUILD_DIR)/rng.o
RNG_PRG   := $(BUILD_DIR)/rng.prg

VARIANTS  := lunalight
BASIC_PRG := $(addprefix $(BUILD_DIR)/,$(addsuffix .prg,$(VARIANTS)))
FULL_PRG  := $(addprefix $(BUILD_DIR)/,$(addsuffix -full.prg,$(VARIANTS)))

D64 := $(BUILD_DIR)/lunalight.d64

# Enough cycles to reach the title screen and then gameplay; the ~4s of TOD
# entropy collection at line 1072 delays everything after it
SMOKE_CYCLES ?= 150000000
# ~10s at ~1MHz for a normal-speed sanity capture
BENCH_CYCLES ?= 10000000

.PHONY: all prg full run smoke bench clean blitz mospeed d64

all: full

prg: $(BASIC_PRG)

full: $(FULL_PRG)

mospeed: $(MOSPEED_FULL)

d64: $(D64)

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

$(SPRITES_OUT): $(SPRITES) $(TOOLS_DIR)/make-flag.py | $(BUILD_DIR)
	$(PYTHON) $(TOOLS_DIR)/make-flag.py $(SPRITES) $@

$(BUILD_DIR)/%-full.prg: $(BUILD_DIR)/%.prg $(SPRITES_OUT) $(MUSIC_PRG) $(RNG_PRG) $(TOOLS_DIR)/embed-sprites.py
	$(PYTHON) $(TOOLS_DIR)/embed-sprites.py $< $(SPRITES_OUT) $(MUSIC_PRG) $(RNG_PRG) $@

# EXPERIMENTAL Blitz! compile of the tokenized BASIC (BASIC-only; no asset embed).
blitz: $(BLITZ_PRG)

$(BLITZ_PRG): $(BUILD_DIR)/lunalight.prg $(REBLITZ) | $(BUILD_DIR)
	$(NODE) $(REBLITZ) $< $@ $(BLITZ_INTVARS)

$(MOSPEED_JAR):
	mkdir -p $(dir $@)
	curl -fsSL -o $@ $(MOSPEED_URL)

$(MOSPEED_PRG): $(SRC_DIR)/lunalight.bas $(MOSPEED_JAR) | $(BUILD_DIR)
	$(JAVA) -cp $(MOSPEED_JAR) com.sixtyfour.cbmnative.shell.MoSpeedCL \
		$< \
		/target=$@ \
		/compactlevel=4 \
		'/memhole=$(MOSPEED_MEMHOLE)'

$(MOSPEED_FULL): $(MOSPEED_PRG) $(SPRITES_OUT) $(MUSIC_PRG) $(RNG_PRG) $(TOOLS_DIR)/patch-assets.py
	$(PYTHON) $(TOOLS_DIR)/patch-assets.py $< $(SPRITES_OUT) $(MUSIC_PRG) $(RNG_PRG) $@

# Disk: runnable MOSpeed build + tokenized BASIC source + MUSIC + RNG assets.
$(D64): $(MOSPEED_FULL) $(BUILD_DIR)/lunalight.prg $(MUSIC_PRG) $(RNG_PRG)
	$(C1541) -format "lunalight,24" d64 $@ \
		-write $(MOSPEED_FULL) lunalight \
		-write $(BUILD_DIR)/lunalight.prg lunalight.bas \
		-write $(MUSIC_PRG) music \
		-write $(RNG_PRG) rng

run: $(BUILD_DIR)/lunalight-full.prg
	$(X64SC) -autostart $<

# VICE does not clock the SID under `-sounddev dummy`, so PEEK($D41B) returns a
# frozen byte and the terrain generator degenerates to one fixed landscape.
# `dump` keeps the SID clocked without needing an audio device.
SOUNDDEV ?= dump

# Headless warp smoke; inspect build/*-smoke.png
smoke: $(FULL_PRG)
	@for prg in $(FULL_PRG); do \
		shot=$${prg%.prg}-smoke.png; \
		echo "smoke: $$prg -> $$shot"; \
		$(X64SC) -default -warp -sounddev $(SOUNDDEV) -soundarg $${prg%.prg}-sid.dump \
			-limitcycles $(SMOKE_CYCLES) -exitscreenshot $$shot \
			-autostart $$prg > $${prg%.prg}-smoke.log 2>&1 || true; \
		test -s $$shot || { echo "smoke FAILED: no screenshot for $$prg"; exit 1; }; \
	done

# Normal-speed short run for timing feel (no warp)
bench: $(BUILD_DIR)/lunalight-full.prg
	@echo "bench: normal-speed $(BENCH_CYCLES) cycles"
	$(X64SC) -default -sounddev $(SOUNDDEV) -soundarg $(BUILD_DIR)/lunalight-bench-sid.dump \
		-limitcycles $(BENCH_CYCLES) \
		-exitscreenshot $(BUILD_DIR)/lunalight-bench.png \
		-autostart $(BUILD_DIR)/lunalight-full.prg \
		> $(BUILD_DIR)/lunalight-bench.log 2>&1 || true
	@test -s $(BUILD_DIR)/lunalight-bench.png || { echo "bench FAILED"; exit 1; }
	@echo "bench ok: $(BUILD_DIR)/lunalight-bench.png"

clean:
	rm -rf $(BUILD_DIR)
