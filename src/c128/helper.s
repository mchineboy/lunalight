; Phase 0 native-C128 machine-code gateway for the VIC-IIe edition.
;
; Loaded at $1300, inside the 2,304 bytes of free bank-0 RAM ($1300-$1BFF) that
; no C128 ROM shadows. The C64 edition's helpers live at $4200 (music) and
; $4400/$4800 (RNG code and table); on the C128 that whole span reads back as
; BASIC LO ROM, so the first thing this file has to prove is that machine code
; can reach RAM underneath the ROM and return to BASIC with I/O intact.
;
; Entry points, all reached with BANK 15 selected so I/O is mapped:
;   SYS 4864  probe          fill the results block below
;   SYS 4867  irq_on         chain the KERNAL IRQ, as the music player must
;   SYS 4870  irq_off        restore the KERNAL vector
;
; The MMU load-configuration register at $FF00 is visible in every memory
; configuration, which is what makes the round trip safe: save it, switch to
; all-RAM, read, switch back. Interrupts are masked across the window because
; the KERNAL ROM at $E000-$FFFF is swapped out while it is open.

.setcpu "6502"

mmu_cfg        = $ff00          ; MMU load configuration register, always visible
cfg_ram0_io    = $3e            ; RAM bank 0 at $4000-$FFFF, I/O still at $D000
irq_vector     = $0314          ; KERNAL IRQ vector, same address as the C64

probe_c64_music = $4200         ; C64 music entry: BASIC LO ROM on the C128
probe_c64_table = $4800         ; C64 RNG table: BASIC LO ROM on the C128
probe_c64_screen = $8400        ; C64 bank-2 screen: BASIC HI ROM on the C128

.segment "LOADADDR"
    .word $1300

; ---------------------------------------------------------------- $1300 vectors
.segment "VECTORS"
    jmp probe                   ; $1300
    jmp irq_on                  ; $1303
    jmp irq_off                 ; $1306

; ---------------------------------------------------------------- $1340 results
; Fixed addresses so the verifier can assert them without parsing a map file.
.segment "RESULTS"
signature:      .byte $4c, $31, $32, $38   ; $1340 "L128"
ram_music:      .byte 0                    ; $1344 $4200 read under all-RAM
ram_table:      .byte 0                    ; $1345 $4800 read under all-RAM
ram_screen:     .byte 0                    ; $1346 $8400 read under all-RAM
rom_music:      .byte 0                    ; $1347 $4200 read under BANK 15
saved_cfg:      .byte 0                    ; $1348 $FF00 on entry
restored_cfg:   .byte 0                    ; $1349 $FF00 after the round trip
io_raster:      .byte 0                    ; $134a $D012, proves I/O still mapped
irq_count:      .word 0                    ; $134b IRQ ticks while chained
installed:      .byte 0                    ; $134d chain state
old_irq:        .word 0                    ; $134e vector displaced by irq_on
probe_done:     .byte 0                    ; $1350 set once probe returns

; ------------------------------------------------------------------- $1380 code
.segment "CODE"

; Read RAM that BASIC ROM normally hides, then hand control back to BASIC.
probe:
    lda mmu_cfg
    sta saved_cfg
    php
    sei
    lda #cfg_ram0_io
    sta mmu_cfg
    lda probe_c64_music
    sta ram_music
    lda probe_c64_table
    sta ram_table
    lda probe_c64_screen
    sta ram_screen
    lda saved_cfg
    sta mmu_cfg
    plp
    lda mmu_cfg
    sta restored_cfg
    ; Back in the caller's configuration: ROM reads and I/O must both work.
    lda probe_c64_music
    sta rom_music
    lda $d012
    sta io_raster
    lda #1
    sta probe_done
    rts

; Chain rather than replace. The C64 title player already chains through
; old_irq; on the C128 chaining is mandatory, because BASIC 7 services sprite
; motion and accumulates the collision latches that BUMP() reports from inside
; the KERNAL interrupt. Replacing the vector would silence BUMP(2).
irq_on:
    jsr irq_off
    php
    sei
    lda irq_vector
    sta old_irq
    lda irq_vector+1
    sta old_irq+1
    lda #<tick
    sta irq_vector
    lda #>tick
    sta irq_vector+1
    lda #0
    sta irq_count
    sta irq_count+1
    lda #1
    sta installed
    plp
    rts

irq_off:
    lda installed
    beq irq_off_done
    php
    sei
    lda old_irq
    sta irq_vector
    lda old_irq+1
    sta irq_vector+1
    lda #0
    sta installed
    plp
irq_off_done:
    rts

tick:
    inc irq_count
    bne tick_chain
    inc irq_count+1
tick_chain:
    jmp (old_irq)
