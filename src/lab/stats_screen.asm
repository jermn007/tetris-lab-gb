; --------------------------------------------------------------------------
; The stats screen
;
; One page, between the game over screen and wherever the original goes next:
; the first A or Start opens it, the second is the original's to act on. See
; docs/decisions/0017.
;
;        0         1
;        01234567890123456789
;   1         GAME STATS
;   3     START    9  END   15
;   4     HEARTS      SEEDED          each only if it was
;   5            SCORE LINES
;   6     END   1019000   215
;   7     L10     62000   100         a level not reached has no row
;   8     L20    306000   200
;  10     SINGLES          12
;  11     DOUBLES           8
;  12     TRIPLES           4
;  13     TETRISES         20
;  15     TETRIS RATE      55         percent of lines that came in fours
;  16     MAX DROUGHT      34
;
; Painted once with the LCD off, the way every screen is, so nothing here is
; in VBlank and the arithmetic is free. The tileset is the one the game was
; played in: the font is under every tileset, and that is all this draws.
; --------------------------------------------------------------------------

DEF STATS_NUMBER_COL EQU 15         ; four digits, ending on column 18
DEF STATS_SCORE_COL  EQU 5          ; eight, ending on column 12


; The game over screen, after LabStatsFinish. z if this frame is the
; original's: a game that kept no record, or a page already read.
LabStatsScreen::
	ld   a, [wLabStatsFlags]
	bit  STATSB_DONE, a
	ret  z

	ld   hl, wLabStatsShown
	ld   a, [hl]
	and  a
	jr   nz, .original

	ldh  a, [hButtonsPressed]
	and  PADF_A | PADF_START
	jr   z, .ours
	ld   [hl], 1

; The game over box is still being sent to the screen a row a frame. The
; original stops that on the same press ($1D0F), for the same reason.
	xor  a
	ldh  [hRowsShiftingDownState], a
	ld   a, SND_CONFIRM_OR_LETTER_TYPED
	ld   [wSquareSoundToPlay], a
	call LabStatsDraw

.ours:
	or   1
	ret

.original:
	xor  a
	ret


LabStatsDraw:
	call LabStatsViewLast
	call LabStatsPageOpen
	ld   hl, LabStatsTitle
	call LabStatsLabel
	call LabStatsBody
; fall through

LabStatsPageShow::
	ldh  a, [rLCDC]
	or   LCDCF_ON
	ldh  [rLCDC], a
	ret


; The game just played, into the record the page draws.
LabStatsViewLast::
	ld   hl, wLabStats
	ld   de, wLabView
	ld   b, wLabStatsRecordEnd - wLabStats
.copy:
	ld   a, [hl+]
	ld   [de], a
	inc  de
	dec  b
	jr   nz, .copy
	ret


; A blank page, with the LCD off.
LabStatsPageOpen::
	call TurnOffLCD
	call Clear_wOam
	xor  a
	ldh  [rSCY], a                  ; the menu scrolls; nothing else does

	ld   hl, _SCRN0
	ld   bc, _SCRN1 - _SCRN0
.clear:
	ld   a, TILE_BLANK
	ld   [hl+], a
	dec  bc
	ld   a, b
	or   c
	jr   nz, .clear
	ret


; Everything under the title, from wLabView.
LabStatsBody::
	ld   hl, LabStatsLabels
.labels:
	call LabStatsLabel
	ld   a, [hl]
	inc  a                          ; $FF where a cell's low byte would be
	jr   nz, .labels

; --- how it started and ended ---
	ld   a, [wLabViewStartLevel]
	ld   de, _SCRN0 + 3 * 32 + 6
	call LabStatsPutA
	ld   a, [wLabViewLevel]
	ld   de, _SCRN0 + 3 * 32 + STATS_NUMBER_COL
	call LabStatsPutA

	ld   a, [wLabViewFlags]
	bit  STATSB_HEARTS, a
	ld   hl, LabStatsHearts
	call nz, LabStatsLabel
	ld   a, [wLabViewFlags]
	bit  STATSB_SEEDED, a
	ld   hl, LabStatsSeeded
	call nz, LabStatsLabel

; --- the checkpoints, closed up: a level not reached leaves no gap ---
	ld   de, _SCRN0 + 6 * 32 + 1
	ld   hl, LabStatsRowNames
	ld   bc, wLabViewFinal
	call LabStatsRow

	ld   a, [wLabViewFlags]
	bit  STATSB_L10, a
	ld   hl, LabStatsRowNames + 3
	ld   bc, wLabViewL10
	call nz, LabStatsRow

	ld   a, [wLabViewFlags]
	bit  STATSB_L20, a
	ld   hl, LabStatsRowNames + 6
	ld   bc, wLabViewL20
	call nz, LabStatsRow

; --- singles, doubles, triples, tetrises ---
	ld   hl, wLabViewClears
	ld   de, _SCRN0 + 10 * 32 + STATS_NUMBER_COL
	ld   b, 4
.clears:
	push bc
	push de
	ld   a, [hl+]
	ld   c, a
	ld   a, [hl+]
	push hl
	ld   h, a
	ld   l, c
	call LabStatsPutHL
	pop  hl
	pop  de
	ld   a, e
	add  32
	ld   e, a
	jr   nc, .sameHigh
	inc  d
.sameHigh:
	pop  bc
	dec  b
	jr   nz, .clears

	call LabStatsRate
	ld   de, _SCRN0 + 15 * 32 + STATS_NUMBER_COL
	call LabStatsPutHL

	ld   hl, wLabViewDrought
	ld   a, [hl+]
	ld   h, [hl]
	ld   l, a
	ld   de, _SCRN0 + 16 * 32 + STATS_NUMBER_COL
	jp   LabStatsPutHL


; hl = a cell, then its text, then $FF. Leaves hl after it.
LabStatsLabel::
	ld   a, [hl+]
	ld   e, a
	ld   a, [hl+]
	ld   d, a
.char:
	ld   a, [hl+]
	cp   $ff
	ret  z
	ld   [de], a
	inc  de
	jr   .char


; hl = three characters, bc = a checkpoint, de = column 1 of its row.
; Leaves de on the row below.
LabStatsRow:
	push de
	push bc
	ld   b, 3
.name:
	ld   a, [hl+]
	ld   [de], a
	inc  de
	dec  b
	jr   nz, .name
	inc  de                         ; STATS_SCORE_COL

; The score, millions first, then the lines the same way.
	pop  hl
	inc  hl
	inc  hl
	inc  hl
	ld   b, 4
	call LabStatsPutBCD
	ld   bc, STATS_CHECKPOINT_SIZEOF    ; hl is one under the checkpoint
	add  hl, bc
	inc  de
	inc  de                         ; STATS_NUMBER_COL
	ld   b, 2
	call LabStatsPutBCD

	pop  hl
	ld   de, 32
	add  hl, de
	ld   d, h
	ld   e, l
	ret


; hl = the top byte of a BCD number, b = its bytes, de = its first cell.
LabStatsPutBCD:
	ld   c, 0
.byte:
	ld   a, [hl]
	swap a
	and  $0f
	call LabStatsDigit
	ld   a, [hl-]
	and  $0f
	call LabStatsDigit
	dec  b
	jr   nz, .byte
	jr   LabStatsUnits


; A, or HL, under 10000, as four cells at de.
LabStatsPutA:
	ld   l, a
	ld   h, 0

LabStatsPutHL:
	push de
	call LabDigits4
	pop  de
	ld   hl, wLabDigits
	ld   bc, 4 << 8
.digit:
	ld   a, [hl+]
	call LabStatsDigit
	dec  b
	jr   nz, .digit
; fall through

; Nothing but zeros is a nought, not a gap.
LabStatsUnits:
	ld   a, c
	and  a
	ret  nz
	dec  de
	ld   [de], a                    ; the font's 0 is tile 0
	inc  de
	ret


; a = a digit for the cell at de. c = a digit has been drawn, and until one
; has, a zero is a blank.
LabStatsDigit:
	and  a
	jr   nz, .draw
	ld   a, c
	and  a
	ld   a, TILE_BLANK
	jr   z, .put
	xor  a
.draw:
	ld   c, 1
.put:
	ld   [de], a
	inc  de
	ret


; The percentage of the game's lines that were cleared four at a time, into hl.
; The NES community's "tetris rate", and no divide: 100 x fours / lines is
; counted out by adding the fours a hundred times and taking the lines off
; whenever they fit, which they do at most once a step.
LabStatsRate:
	xor  a
	ld   [wLabDigits], a            ; the answer; LabStatsPutHL takes it over

	ld   hl, wLabViewClears + 6
	ld   a, [hl+]
	ld   h, [hl]
	ld   l, a
	add  hl, hl
	add  hl, hl
	ld   b, h
	ld   c, l                       ; bc = lines in tetrises

	ld   a, [wLabViewClears + 4]
	ld   e, a
	ld   a, [wLabViewClears + 5]
	ld   d, a
	add  hl, de
	add  hl, de
	add  hl, de
	ld   a, [wLabViewClears + 2]
	ld   e, a
	ld   a, [wLabViewClears + 3]
	ld   d, a
	add  hl, de
	add  hl, de
	ld   a, [wLabViewClears]
	ld   e, a
	ld   a, [wLabViewClears + 1]
	ld   d, a
	add  hl, de                     ; hl = lines

	ld   a, h
	or   l
	jr   z, .done                   ; no lines: nought, not a divide by it

	ld   a, l
	cpl
	ld   e, a
	ld   a, h
	cpl
	ld   d, a
	inc  de                         ; de = -lines

	ld   hl, 0
	ld   a, 100
.step:
	push af
	add  hl, bc
	push hl
	add  hl, de
	jr   c, .fits
	pop  hl
	jr   .next

.fits:
	inc  sp
	inc  sp
	push hl
	ld   hl, wLabDigits
	inc  [hl]
	pop  hl

.next:
	pop  af
	dec  a
	jr   nz, .step

.done:
	ld   a, [wLabDigits]
	ld   l, a
	ld   h, 0
	ret


PUSHC
SETCHARMAP labfont

LabStatsTitle:
	dw _SCRN0 +  1 * 32 + 5
	db "GAME STATS", $ff

LabStatsLabels:
	dw _SCRN0 +  3 * 32 + 1
	db "START", $ff
	dw _SCRN0 +  3 * 32 + 12
	db "END", $ff
	dw _SCRN0 +  5 * 32 + 8
	db "SCORE LINES", $ff
	dw _SCRN0 + 10 * 32 + 1
	db "SINGLES", $ff
	dw _SCRN0 + 11 * 32 + 1
	db "DOUBLES", $ff
	dw _SCRN0 + 12 * 32 + 1
	db "TRIPLES", $ff
	dw _SCRN0 + 13 * 32 + 1
	db "TETRISES", $ff
	dw _SCRN0 + 15 * 32 + 1
	db "TETRIS RATE", $ff
	dw _SCRN0 + 16 * 32 + 1
	db "MAX DROUGHT", $ff
	db $ff

LabStatsHearts:
	dw _SCRN0 + 4 * 32 + 1
	db "HEARTS", $ff

LabStatsSeeded:
	dw _SCRN0 + 4 * 32 + 13
	db "SEEDED", $ff

LabStatsRowNames:
	db "END"
	db "L10"
	db "L20"

POPC
