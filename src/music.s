; IRQ-driven three-voice title soundtrack for Lunalight.
; Loaded at $4200. SYS 16896 starts it, SYS 16899 stops it and silences the SID.
;
; The tune belongs to the title screen only, so flight and attract mode run with
; the KERNAL IRQ restored and the SID free for engine and explosion effects.
;
; Voice 1  triangle bass, one chord root per eight-step bar.
; Voice 2  sawtooth melody under a continuous low-pass cutoff sweep.
; Voice 3  pulse echo, the melody note from four steps back, plucked on alternate
;          steps so the arpeggio gains movement instead of a second lead line.
;
; The 32-step C-minor theme leads to a 16-step octave-up bridge, then returns for
; a full 32-step reprise (~38s total).

.setcpu "6502"

.segment "LOADADDR"
    .word $4200

.segment "CODE"

sid                = $d400
sid_voice1_freq    = $d400
sid_voice1_ctrl    = $d404
sid_voice1_ad      = $d405
sid_voice1_sr      = $d406
sid_voice2_freq    = $d407
sid_voice2_ctrl    = $d40b
sid_voice2_ad      = $d40c
sid_voice2_sr      = $d40d
sid_voice3_freq    = $d40e
sid_voice3_pw      = $d410
sid_voice3_ctrl    = $d412
sid_voice3_ad      = $d413
sid_voice3_sr      = $d414
sid_cutoff_hi      = $d416
sid_res_route      = $d417
sid_mode_vol       = $d418
pal_flag           = $02a6
irq_vector         = $0314

cutoff_min = $60
cutoff_max = $f0

theme_length    = 32
bridge_end      = 48
sequence_length = 80

; SYS entry points; their addresses are part of the BASIC contract.
    jmp install
    jmp uninstall

install:
    lda installed
    bne install_done
    jsr silence
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

uninstall:
    lda installed
    beq silence
    sei
    lda old_irq
    sta irq_vector
    lda old_irq+1
    sta irq_vector+1
    lda #$00
    sta installed
    cli
silence:
    lda #$00
    ldx #$18
silence_loop:
    sta sid,x
    dex
    bpl silence_loop
    rts

play_irq:
    ; --- Slow low-pass cutoff sweep, every frame for smooth motion. ---
    lda filt_dir
    beq sweep_down
    inc filt
    lda filt
    cmp #cutoff_max
    bcc sweep_write
    lda #$00
    sta filt_dir
    beq sweep_write
sweep_down:
    dec filt
    lda filt
    cmp #cutoff_min
    bcs sweep_write
    lda #$01
    sta filt_dir
sweep_write:
    lda bridge_mode
    beq theme_filter
    lda #cutoff_max            ; bridge: fully open and more resonant
    sta sid_cutoff_hi
    lda #$32
    bne filter_route
theme_filter:
    lda filt
    sta sid_cutoff_hi
    lda #$12
filter_route:
    sta sid_res_route          ; light resonance, route the melody only
    lda #$1f                   ; low-pass on, master volume 15
    sta sid_mode_vol

    ; Gates are held on here and dropped for a single frame by the sequencer,
    ; which articulates each note without restarting the envelope mid-step.
    lda #$11
    sta sid_voice1_ctrl
    lda #$21
    sta sid_voice2_ctrl
    lda #$41
    sta sid_voice3_ctrl

    ; --- Note sequencer advances once per step. ---
    dec tempo
    beq next_step
    jmp chain_irq
next_step:
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

    ; Envelopes are restored on every step rather than once at install, so a
    ; caller that wipes the SID between notes only loses one step of tone.
    lda #$08                   ; bass: instant attack, medium decay
    sta sid_voice1_ad
    lda #$a8                   ; bass: strong sustain, ~300ms release
    sta sid_voice1_sr
    lda #$40                   ; melody: gentle attack, no decay
    sta sid_voice2_ad
    lda #$f8                   ; melody: full sustain, ~300ms release
    sta sid_voice2_sr
    lda #$07                   ; echo: instant attack, short decay
    sta sid_voice3_ad
    lda #$08                   ; echo: no sustain, so each hit plucks
    sta sid_voice3_sr
    lda #$04                   ; echo: 25% pulse width
    sta sid_voice3_pw+1

    txa
    tay
    jsr fold
    lda frequency_hi,y
    sta sid_voice2_freq+1
    lda frequency_lo,y
    sta sid_voice2_freq
    lda #$20
    sta sid_voice2_ctrl

    txa                        ; bass changes on bar lines only
    and #$07
    bne skip_bass
    txa
    lsr
    lsr
    lsr
    tay
    lda bass_hi,y
    sta sid_voice1_freq+1
    lda bass_lo,y
    sta sid_voice1_freq
    lda #$10
    sta sid_voice1_ctrl
skip_bass:
    txa                        ; echo plucks on alternate steps
    and #$01
    bne skip_echo
    txa
    sec
    sbc #$04
    bcs echo_index
    adc #sequence_length       ; carry is clear here, so this wraps exactly
echo_index:
    tay
    jsr fold
    lda frequency_hi,y
    sta sid_voice3_freq+1
    lda frequency_lo,y
    sta sid_voice3_freq
    lda #$40
    sta sid_voice3_ctrl
skip_echo:

    inx
    cpx #sequence_length
    bcc save_index
    ldx #$00
save_index:
    stx note_index

chain_irq:
    jmp (old_irq)

; The reprise replays the theme, so the note tables stop after the bridge and
; steps 48-79 fold back onto steps 0-31.
fold:
    cpy #bridge_end
    bcc fold_done
    tya
    sbc #bridge_end            ; carry is set by the comparison above
    tay
fold_done:
    rts

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
    ; BRIDGE: C5 -> G6 ascent, with the peak held before the octave drop
    .byte $ce,$64,$26,$9c, $64,$26,$04,$9c
    .byte $26,$04,$9c,$c8, $9c,$c8,$4c,$4c
frequency_hi:
    ; THEME
    .byte $11,$14,$1a,$14, $11,$0d,$0a,$0d
    .byte $0d,$11,$14,$11, $0d,$0a,$08,$0a
    .byte $14,$1a,$1f,$1a, $14,$0f,$0d,$0f
    .byte $13,$17,$1f,$17, $13,$0f,$0b,$0d
    ; BRIDGE
    .byte $22,$29,$34,$45, $29,$34,$3e,$45
    .byte $34,$3e,$45,$52, $45,$52,$68,$68
sequence_end:

.assert (frequency_hi - frequency_lo) = bridge_end, error, "melody low table"
.assert (sequence_end - frequency_hi) = bridge_end, error, "melody high table"

; Chord roots, one per bar: Cm Ab Eb Bb | bridge C, G | Cm Ab Eb Bb
bass_lo:
    .byte $59,$74,$2c,$e0, $59,$42, $59,$74,$2c,$e0
bass_hi:
    .byte $04,$03,$05,$03, $04,$03, $04,$03,$05,$03
bass_end:

.assert (bass_hi - bass_lo) = sequence_length / 8, error, "bass low table"
.assert (bass_end - bass_hi) = sequence_length / 8, error, "bass high table"

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
