; IRQ-driven three-voice title soundtrack for Lunalight.
; Loaded at $4200. SYS 16896 starts it, SYS 16899 stops it and silences the SID.
;
; The tune belongs to the title screen only, so flight and attract mode run with
; the KERNAL IRQ restored and the SID free for engine and explosion effects.
;
; Voice 1  triangle bass, plucked once per chord and allowed to decay away, so
;          the low end punctuates instead of droning.
; Voice 2  sawtooth melody under a low-pass cutoff sweep locked to the harmony.
; Voice 3  pulse pad holding a tone of the chord now sounding, which is what
;          fills the harmony out into an audible triad.
;
; The 32-step C-minor theme leads to a 16-step octave-up bridge and then loops.
; At 22 ticks per step that is 17.6s, and the title reads the loop length below
; so its attract hand-off stays tied to the music.

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
irq_vector         = $0314

; The KERNAL interrupt is CIA-driven at 60Hz on PAL as well as NTSC, so a single
; constant serves both machines and one step is one beat:
;   22 ticks = 0.367s = 164 BPM   (current)
;   24 ticks = 0.400s = 150 BPM
;   29 ticks = 0.483s = 124 BPM   (only integer tick count inside 122-126 BPM)
step_ticks      = 22

; The chord turns over every four beats. The melody arpeggiates one triad across
; a whole eight-step bar, so each half-bar is re-footed under a bass note that
; keeps every melody tone consonant: the second half of each bar either inverts
; the triad or turns it into a seventh chord.
steps_per_chord = 4
sweep_steps     = 8
sequence_length = 48

; One full up-and-down sweep every sweep_steps beats, so the filter moves with
; the harmony rather than drifting against it.
cutoff_min = $60
cutoff_max = cutoff_min + step_ticks * (sweep_steps / 2)

; Melody table sentinels. No sounding note has a high byte below $08.
note_hold = $00
note_rest = $01

; SYS entry points; their addresses are part of the BASIC contract.
    jmp install
    jmp uninstall

; One song loop in jiffies (sequence_length * step_ticks), published at a fixed
; address immediately after the jump table so the title can time its attract
; hand-off to the music: PEEK(16902)+PEEK(16903)*256. Assembled from the tempo
; and length constants, so the title stays in sync if either changes.
loop_jiffies:
    .word sequence_length * step_ticks

install:
    ; uninstall first so a second SYS 16896 without an intervening SYS 16899
    ; cannot capture play_irq as its own old_irq and chain to itself. It also
    ; silences the SID and re-seats the sequencer at step 0, so every title
    ; entry starts the song from the top and the attract deadline read from
    ; loop_jiffies really is one whole pass.
    jsr uninstall
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
    lda #$10                   ; gates down until the first step loads a note
    sta ctrl1
    lda #$20
    sta ctrl2
    lda #$40
    sta ctrl3
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
    ; --- Cutoff sweep, one cycle per bar, stepped every frame for smoothness.
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
    lda filt
    sta sid_cutoff_hi
    lda #$22                   ; light resonance, route the melody only
    sta sid_res_route
    lda #$1f                   ; low-pass on, master volume 15
    sta sid_mode_vol

    ; Gates are held on here and dropped for a single frame by the sequencer,
    ; which articulates a note without restarting the envelope mid-step. A
    ; resting voice keeps its gate down because the held value has bit 0 clear.
    lda ctrl1
    sta sid_voice1_ctrl
    lda ctrl2
    sta sid_voice2_ctrl
    lda ctrl3
    sta sid_voice3_ctrl

    ; --- Note sequencer advances once per step. ---
    dec tempo
    beq next_step
    jmp chain_irq
next_step:
    lda #step_ticks
    sta tempo

    ; Envelopes are restored on every step rather than once at install, so a
    ; caller that wipes the SID between notes only loses one step of tone.
    lda #$0a                   ; bass: instant attack, long decay
    sta sid_voice1_ad
    lda #$28                   ; bass: low sustain, so each pulse breathes
    sta sid_voice1_sr
    lda #$40                   ; melody: gentle attack, no decay
    sta sid_voice2_ad
    lda #$f8                   ; melody: full sustain, ~300ms release
    sta sid_voice2_sr
    lda #$2a                   ; pad: soft attack, long decay
    sta sid_voice3_ad
    lda #$a9                   ; pad: high sustain, so the chord stays under
    sta sid_voice3_sr
    lda #$08                   ; pad: 50% pulse
    sta sid_voice3_pw+1

    ldx note_index
    lda frequency_hi,x
    beq melody_done            ; note_hold: let the previous note ring on
    cmp #note_rest
    bne melody_note
    lda #$20                   ; note_rest: gate down and left down
    sta ctrl2
    sta sid_voice2_ctrl
    jmp melody_done
melody_note:
    sta sid_voice2_freq+1
    lda frequency_lo,x
    sta sid_voice2_freq
    lda #$21
    sta ctrl2
    lda #$20
    sta sid_voice2_ctrl
melody_done:

    txa                        ; bass pulses once per chord
    and #steps_per_chord - 1
    bne skip_bass
    txa                        ; each turn costs the sweep a frame, so re-anchor
    and #sweep_steps - 1       ; it on the downbeat rather than let it drift
    bne skip_sweep_reset
    lda #cutoff_min
    sta filt
    lda #$01
    sta filt_dir
skip_sweep_reset:
    txa
    lsr
    lsr
    tay
    lda bass_hi,y
    sta sid_voice1_freq+1
    lda bass_lo,y
    sta sid_voice1_freq
    lda #$11
    sta ctrl1
    lda #$10
    sta sid_voice1_ctrl
skip_bass:

    txa                        ; pad moves on alternate steps
    and #$01
    bne skip_pad
    txa                        ; two positions ahead inside the current chord, so
    eor #$02                   ; the pad is always a tone of the chord sounding.
    tay                        ; Only exact because the pad fires on even steps:
                               ; that keeps the flip inside one steps_per_chord
                               ; group instead of crossing into the next chord.
    lda frequency_hi,y
    cmp #note_rest + 1         ; a sentinel just leaves the pad sustaining
    bcc skip_pad
    sta sid_voice3_freq+1
    lda frequency_lo,y
    sta sid_voice3_freq
    lda #$41
    sta ctrl3
    lda #$40
    sta sid_voice3_ctrl
skip_pad:

    inx
    cpx #sequence_length
    bcc save_index
    ldx #$00
save_index:
    stx note_index

chain_irq:
    jmp (old_irq)

; Main theme: flowing C-minor melody, one bar per chord, eight beats each. Beat
; 3 of every bar holds the peak and beat 7 rests, which is what opens the gaps
; the pad and the decaying bass sit in.
;   Cm : C4  Eb4 G4  -   C4 G3  Eb3 .
;   Ab : Ab3 C4  Eb4 -   Ab3 Eb3 C3 .
;   Eb : Eb4 G4  Bb4 -   Eb4 Bb3 G3 .
;   Bb : D4  F4  Bb4 -   D4  Bb3 F3 .
frequency_lo:
    ; THEME
    .byte $67,$b2,$13,$00, $67,$0a,$59,$00
    .byte $d0,$67,$b2,$00, $d0,$59,$b4,$00
    .byte $b2,$13,$02,$00, $b2,$81,$0a,$00
    .byte $89,$3b,$02,$00, $89,$81,$9d,$00
    ; BRIDGE: C5 -> G6 ascent, unbroken so it reads as a build
    .byte $ce,$64,$26,$9c, $64,$26,$04,$9c
    .byte $26,$04,$9c,$c8, $9c,$c8,$4c,$4c
frequency_hi:
    ; THEME
    .byte $11,$14,$1a,$00, $11,$0d,$0a,$01
    .byte $0d,$11,$14,$00, $0d,$0a,$08,$01
    .byte $14,$1a,$1f,$00, $14,$0f,$0d,$01
    .byte $13,$17,$1f,$00, $13,$0f,$0b,$01
    ; BRIDGE
    .byte $22,$29,$34,$45, $29,$34,$3e,$45
    .byte $34,$3e,$45,$52, $45,$52,$68,$68
sequence_end:

.assert (frequency_hi - frequency_lo) = sequence_length, error, "melody low table"
.assert (sequence_end - frequency_hi) = sequence_length, error, "melody high table"

; Bass note per chord, one every four beats. The melody arpeggiates a single
; triad per bar, so the odd entries re-foot that same triad rather than fight it:
;   C2  Eb2 | Ab1 F1  | Eb2 C2  | Bb1 G1  | C2  Eb2 | C2  G1
;   Cm  Cm/Eb  Ab  Fm7   Eb  Cm7   Bb  Gm7   Cm  Eb6    Cm7 Cm/G
bass_lo:
    .byte $59,$2c, $74,$e7, $2c,$59, $e0,$42, $59,$2c, $59,$42
bass_hi:
    .byte $04,$05, $03,$02, $05,$04, $03,$03, $04,$05, $04,$03
bass_end:

.assert (bass_hi - bass_lo) = sequence_length / steps_per_chord, error, "bass low table"
.assert (bass_end - bass_hi) = sequence_length / steps_per_chord, error, "bass high table"

installed:
    .byte $00
tempo:
    .byte $01
note_index:
    .byte $00
ctrl1:
    .byte $10
ctrl2:
    .byte $20
ctrl3:
    .byte $40
filt:
    .byte cutoff_min
filt_dir:
    .byte $01
old_irq:
    .word $ea31
