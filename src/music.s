; IRQ-driven SID voice 2 soundtrack for Lunalight.
; Loaded at $4200 and installed with SYS 16896.
;
; Upbeat-but-spacey: a flowing sawtooth melody on voice 2 (~0.5s/step) under
; a continuous low-pass cutoff sweep for movement. Voice 1 stays free for
; effects; voice 3 stays free for terrain randomness.
;
; Each note gets a one-frame gate restart for soft articulation without the
; old ~390ms envelope hole. The 32-step theme leads to a distinct 16-step
; octave-up bridge, then returns for a full 32-step reprise (~38s total).
; Waveform, envelope, filter and volume are rewritten every frame, so the
; game's SID-clearing blip can silence the music for at most one frame.

.setcpu "6502"

.segment "LOADADDR"
    .word $4200

.segment "CODE"

sid_voice2_freq_lo = $d407
sid_voice2_freq_hi = $d408
sid_voice2_ctrl    = $d40b
sid_voice2_ad      = $d40c
sid_voice2_sr      = $d40d
sid_cutoff_lo      = $d415
sid_cutoff_hi      = $d416
sid_res_route      = $d417
sid_mode_vol       = $d418
pal_flag           = $02a6
irq_vector         = $0314

cutoff_min = $60
cutoff_max = $f0

install:
    lda installed
    bne install_done
    sei
    lda irq_vector
    sta old_irq
    lda irq_vector+1
    sta old_irq+1
    lda #<play_irq
    sta irq_vector
    lda #>play_irq
    sta irq_vector+1
    lda #$01
    sta installed
    sta tempo
    sta filt_dir
    lda #$00
    sta note_index
    sta bridge_mode
    lda #cutoff_min
    sta filt
    cli
install_done:
    rts

play_irq:
    ; --- Slow low-pass cutoff sweep, every frame for smooth motion. ---
    lda filt_dir
    beq sweep_down
    lda filt
    clc
    adc #$01
    sta filt
    cmp #cutoff_max
    bcc sweep_write
    lda #$00
    sta filt_dir
    jmp sweep_write
sweep_down:
    lda filt
    sec
    sbc #$01
    sta filt
    cmp #cutoff_min
    bcs sweep_write
    lda #$01
    sta filt_dir
sweep_write:
    lda bridge_mode
    beq theme_filter
    lda #cutoff_max            ; bridge: fully open and more resonant
    sta sid_cutoff_hi
    lda #$00
    sta sid_cutoff_lo
    lda #$32
    bne filter_route
theme_filter:
    lda filt
    sta sid_cutoff_hi
    lda #$00
    sta sid_cutoff_lo
    lda #$12
filter_route:
    sta sid_res_route          ; light resonance, route voice 2 only
    lda #$1f                   ; low-pass on, master volume 15
    sta sid_mode_vol

    ; Sawtooth with the gate held on; rewritten every frame so a cleared SID
    ; recovers immediately without restarting the envelope mid-note.
    lda #$21
    sta sid_voice2_ctrl
    lda #$40                   ; gentle attack, no decay
    sta sid_voice2_ad
    lda #$f8                   ; full sustain, ~0.3s release
    sta sid_voice2_sr

    ; --- Note sequencer advances once per step. ---
    dec tempo
    bne chain_irq

    lda pal_flag
    beq ntsc_tempo
    lda #$18                   ; PAL 50Hz: 24 frames per step (~0.48s)
    bne set_tempo
ntsc_tempo:
    lda #$1c                   ; NTSC 60Hz: 28 frames per step (~0.47s)
set_tempo:
    sta tempo

    ldx note_index
    cpx #theme_length
    bcc theme_note
    cpx #bridge_end
    bcs theme_note
    lda #$01
    bne save_mode
theme_note:
    lda #$00
save_mode:
    sta bridge_mode

    lda frequency_hi,x
    sta sid_voice2_freq_hi
    lda frequency_lo,x
    sta sid_voice2_freq_lo
    lda #$20                   ; one-frame gate-off articulation
    sta sid_voice2_ctrl

    inx
    cpx #sequence_length
    bcc save_index
    ldx #$00
save_index:
    stx note_index

chain_irq:
    jmp (old_irq)

; Main theme: flowing C-minor melody, one bar per chord, eight notes each.
;   Cm : C4 Eb4 G4 Eb4 C4 G3 Eb3 G3
;   Ab : Ab3 C4 Eb4 C4 Ab3 Eb3 C3 Eb3
;   Eb : Eb4 G4 Bb4 G4 Eb4 Bb3 G3 Bb3
;   Bb : D4 F4 Bb4 F4 D4 Bb3 F3 G3
frequency_lo:
    ; THEME
    .byte $67,$b2,$13,$b2, $67,$0a,$59,$0a
    .byte $d0,$67,$b2,$67, $d0,$59,$b4,$59
    .byte $b2,$13,$02,$13, $b2,$81,$0a,$81
    .byte $89,$3b,$02,$3b, $89,$81,$9d,$0a
theme_length = * - frequency_lo
    ; BRIDGE: C5 -> G6 ascent, with the peak held before the octave drop
    .byte $ce,$64,$26,$9c, $64,$26,$04,$9c
    .byte $26,$04,$9c,$c8, $9c,$c8,$4c,$4c
bridge_end = * - frequency_lo
    ; THEME REPRISE
    .byte $67,$b2,$13,$b2, $67,$0a,$59,$0a
    .byte $d0,$67,$b2,$67, $d0,$59,$b4,$59
    .byte $b2,$13,$02,$13, $b2,$81,$0a,$81
    .byte $89,$3b,$02,$3b, $89,$81,$9d,$0a
frequency_hi:
    ; THEME
    .byte $11,$14,$1a,$14, $11,$0d,$0a,$0d
    .byte $0d,$11,$14,$11, $0d,$0a,$08,$0a
    .byte $14,$1a,$1f,$1a, $14,$0f,$0d,$0f
    .byte $13,$17,$1f,$17, $13,$0f,$0b,$0d
    ; BRIDGE
    .byte $22,$29,$34,$45, $29,$34,$3e,$45
    .byte $34,$3e,$45,$52, $45,$52,$68,$68
    ; THEME REPRISE
    .byte $11,$14,$1a,$14, $11,$0d,$0a,$0d
    .byte $0d,$11,$14,$11, $0d,$0a,$08,$0a
    .byte $14,$1a,$1f,$1a, $14,$0f,$0d,$0f
    .byte $13,$17,$1f,$17, $13,$0f,$0b,$0d
sequence_length = * - frequency_hi

installed:
    .byte $00
tempo:
    .byte $01
note_index:
    .byte $00
filt:
    .byte cutoff_min
filt_dir:
    .byte $01
bridge_mode:
    .byte $00
old_irq:
    .word $ea31
