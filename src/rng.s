; TOD-phase entropy collector and byte-table PRNG for Lunalight.
;
; The C64 clocks the CIA TOD pin from the 50/60Hz mains, which is independent of
; the system crystal. The phase between TOD ticks and a Phi2-driven counter is
; therefore the only true entropy the machine has. Everything else the game can
; read -- raster, jiffies, SID oscillator 3 -- is a function of elapsed cycles
; and repeats exactly on a cold boot.
;
; Entry points and data, all at fixed addresses so BASIC can reach them:
;
;   $4400 / 17408  collect  start TOD and timer, absorb 32 TOD transitions
;                           (~3.2s at 10 ticks/sec), then refill
;   $4403 / 17411  refill   regenerate the table from the current state
;   $4406 / 17414  stir     absorb one cheap sample; call on human input
;   $4800 / 18432  table    1024 random bytes for BASIC to PEEK
;
; Commandeers CIA2 timer B and SID voice 3. Intended for terrain seeding.

.setcpu "6502"

.segment "LOADADDR"
    .word $4400

CIA1_TOD10   = $DC08
CIA1_TODSEC  = $DC09
CIA1_TODMIN  = $DC0A
CIA1_TODHR   = $DC0B
CIA1_CRB     = $DC0F

CIA2_TBLO    = $DD06
CIA2_TBHI    = $DD07
CIA2_ICR     = $DD0D
CIA2_CRB     = $DD0F

VIC_RASTER   = $D012

SID3_FREQ_LO = $D40E
SID3_FREQ_HI = $D40F
SID3_CTRL    = $D412
SID_OSC3     = $D41B

PTR          = $FB              ; $FB-$FE are free of both BASIC and the KERNAL

NUM_SAMPLES  = 32

.segment "CODE"

    jmp collect
    jmp refill
    jmp stir
    jmp starttod

; --------------------------------------------------------------- starttod ---
; A write to the hours register halts the TOD and only a write to tenths
; restarts it. Miss this and the sample loop spins forever.

starttod:
    lda CIA1_CRB
    and #$7f                    ; address the clock, not the alarm
    sta CIA1_CRB
    lda #$01
    sta CIA1_TODHR
    lda #$00
    sta CIA1_TODMIN
    sta CIA1_TODSEC
    sta CIA1_TOD10              ; this write starts it
    rts

; ---------------------------------------------------------------- collect ---

collect:
    jsr starttod

    lda #$02                    ; bit 7 clear: mask off timer B interrupts
    sta CIA2_ICR
    lda #$00
    sta CIA2_CRB
    lda #$ff                    ; free-running 16-bit Phi2 counter
    sta CIA2_TBLO
    sta CIA2_TBHI
    lda #$11                    ; start + force load, continuous, Phi2
    sta CIA2_CRB

    lda #$ff                    ; voice 3 noise, gate off
    sta SID3_FREQ_LO
    sta SID3_FREQ_HI
    lda #$80
    sta SID3_CTRL

    lda #$6d
    sta x0
    lda #$2b
    sta x1
    lda #$79
    sta x2
    lda #$a5
    sta x3

    lda CIA1_TOD10
    sta old_tod
    lda #NUM_SAMPLES
    sta nsamp

sample:
wait_tod:
    lda CIA1_TOD10
    cmp old_tod
    beq wait_tod
    sta old_tod

    ; Both timer bytes carry the phase. Reading them non-atomically can
    ; straddle a borrow, which only adds noise.
    lda CIA2_TBLO
    sta raw_lo
    lda CIA2_TBHI
    eor raw_lo
    eor VIC_RASTER
    eor SID_OSC3
    jsr mix
    lda raw_lo
    jsr mix

    dec nsamp
    bne sample

    jsr nonzero
    jmp refill

; ----------------------------------------------------------------- refill ---

; One xorshift step yields 32 bits, so emit all four bytes per call: 256 steps
; for the 1024-byte table instead of 1024. xorshift clobbers Y, so Y is always
; reloaded here rather than carried across the call.

refill:
    lda #<table
    sta PTR
    lda #>table
    sta PTR+1
    lda #$00
    sta pages                   ; dec-first gives 256 iterations
rquad:
    jsr xorshift
    ldy #$00
    lda x0
    sta (PTR),y
    iny
    lda x1
    sta (PTR),y
    iny
    lda x2
    sta (PTR),y
    iny
    lda x3
    sta (PTR),y

    lda PTR
    clc
    adc #$04
    sta PTR
    bcc rnocarry
    inc PTR+1
rnocarry:
    dec pages
    bne rquad
    rts

; ------------------------------------------------------------------- stir ---

stir:
    lda CIA2_TBLO
    eor CIA2_TBHI
    eor VIC_RASTER
    eor SID_OSC3
    jmp mix

; -------------------------------------------------------------------- mix ---
; state = rotl32(state,5); state += a; state += $9e3779b9; state[2] ^= a

mix:
    sta mixin
    ldx #$05
mrot:
    clc
    rol x0
    rol x1
    rol x2
    rol x3
    bcc mnowrap
    inc x0                      ; bit 0 is clear after the rol, so this
mnowrap:                        ; inserts the bit that fell off the top
    dex
    bne mrot

    clc
    lda x0
    adc mixin
    sta x0
    lda x1
    adc #$00
    sta x1
    lda x2
    adc #$00
    sta x2
    lda x3
    adc #$00
    sta x3

    clc
    lda x0
    adc #$b9
    sta x0
    lda x1
    adc #$79
    sta x1
    lda x2
    adc #$37
    sta x2
    lda x3
    adc #$9e
    sta x3

    lda x2
    eor mixin
    sta x2
    rts

; --------------------------------------------------------------- xorshift ---
; xorshift32: x ^= x<<13; x ^= x>>17; x ^= x<<5. Undefined for x = 0.

xorshift:
    lda #$00                    ; t = x << 13, built as (x << 8) << 5
    sta t0
    lda x0
    sta t1
    lda x1
    sta t2
    lda x2
    sta t3
    ldy #$05
shl13:
    asl t0
    rol t1
    rol t2
    rol t3
    dey
    bne shl13
    jsr eortmp

    lda x2                      ; t = x >> 17, built as (x >> 16) >> 1
    sta t0
    lda x3
    sta t1
    lda #$00
    sta t2
    sta t3
    lsr t3
    ror t2
    ror t1
    ror t0
    jsr eortmp

    lda x0                      ; t = x << 5
    sta t0
    lda x1
    sta t1
    lda x2
    sta t2
    lda x3
    sta t3
    ldy #$05
shl5:
    asl t0
    rol t1
    rol t2
    rol t3
    dey
    bne shl5
                                ; falls through, and its rts ends xorshift
eortmp:
    lda x0
    eor t0
    sta x0
    lda x1
    eor t1
    sta x1
    lda x2
    eor t2
    sta x2
    lda x3
    eor t3
    sta x3
    rts

nonzero:
    lda x0
    ora x1
    ora x2
    ora x3
    bne nzdone
    lda #$a5
    sta x0
nzdone:
    rts

x0:      .byte 0
x1:      .byte 0
x2:      .byte 0
x3:      .byte 0
t0:      .byte 0
t1:      .byte 0
t2:      .byte 0
t3:      .byte 0
mixin:   .byte 0
old_tod: .byte 0
raw_lo:  .byte 0
nsamp:   .byte 0
idx:     .byte 0
pages:   .byte 0

.segment "RNGTAB"

table:
    .res 1024, 0
