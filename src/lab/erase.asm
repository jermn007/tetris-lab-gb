; --------------------------------------------------------------------------
; Erase the save
;
; Up and B together on the title screen ask the question; nothing is erased
; until YES is chosen, and the cursor starts on NO. See docs/decisions/0020.
;
;        0         1
;        01234567890123456789
;   5        ERASE ALL SAVES
;   8          - NO
;  10            YES
;  14      A SELECT  B CANCEL
;
; The screen runs on the title's own state behind wLabEraseOpen. Erasing is
; spoiling the header and rebooting: a cartridge with no header of ours is
; started again from nothing by LabSaveBoot, which is the one place that knows
; how.
; --------------------------------------------------------------------------

DEF ERASE_COMBO   EQU PADF_UP | PADF_B
DEF ERASE_NO_CELL EQU _SCRN0 +  8 * 32 + 6
DEF ERASE_YES_CELL EQU _SCRN0 + 10 * 32 + 6
DEF TILE_DASH     EQU $25


; From the title screen's input. nz if the question has been asked and the
; press is spent.
LabEraseAsked::
	ldh  a, [hButtonsHeld]
	and  ERASE_COMBO
	cp   ERASE_COMBO
	jr   nz, .no
	ldh  a, [hButtonsPressed]
	and  ERASE_COMBO
	ret  z                          ; held since before this screen

	ld   a, 1
	ld   [wLabEraseOpen], a
	xor  a
	ld   [wLabEraseYes], a
	ld   a, SND_CONFIRM_OR_LETTER_TYPED
	ld   [wSquareSoundToPlay], a

	call LabStatsPageOpen
	ld   hl, LabEraseText
	ld   b, 4
.label:
	push bc
	call LabStatsLabel
	pop  bc
	dec  b
	jr   nz, .label
	ld   a, TILE_DASH
	ld   [ERASE_NO_CELL], a
	call LabStatsPageShow
	or   1
	ret

.no:
	xor  a
	ret


; Every frame the question is up.
LabErase::
; All four buttons are the reset, and two of them are answers here. While
; they are down this screen answers nothing.
	call LabResetComboHeld
	ret  z

	ldh  a, [hButtonsPressed]
	ld   c, a
	and  PADF_UP | PADF_DOWN
	jr   z, .notMoved

	ld   hl, wLabEraseYes
	ld   a, [hl]
	xor  1
	ld   [hl], a
	ld   a, SND_MOVING_SELECTION
	ld   [wSquareSoundToPlay], a

	ld   a, [wLabEraseYes]
	and  a
	ld   c, TILE_DASH
	jr   z, .onNo
	ld   c, TILE_BLANK
.onNo:
	ld   a, c
	ld   hl, ERASE_NO_CELL
	call LabPutTile                 ; keeps bc
	ld   a, c
	xor  TILE_DASH ^ TILE_BLANK     ; the other of the two
	ld   hl, ERASE_YES_CELL
	jp   LabPutTile

.notMoved:
	bit  PADB_B, c
	jr   nz, .close
	ld   a, c
	and  PADF_A | PADF_START
	ret  z
	ld   a, [wLabEraseYes]
	and  a
	jr   nz, .erase

.close:
	xor  a
	ld   [wLabEraseOpen], a
	ld   a, SND_MOVING_SELECTION
	ld   [wSquareSoundToPlay], a
	jp   LabTitleDraw

; The header's first byte, and then everything in WRAM a cold boot would have
; found empty: both score tables and all of the Lab's state, wLabSaveLoaded
; with it. The reboot does the rest.
.erase:
	ld   a, SAVE_RAM_ON
	ld   [rRAMG], a
	xor  a
	ld   [SAVE_HEADER], a
	ld   [rRAMG], a                 ; SAVE_RAM_OFF

	ld   hl, wBTypeHighScores
.clear:
	xor  a
	ld   [hl+], a
	ld   a, h
	cp   HIGH(wLabStateEnd)
	jr   nz, .clear
	ld   a, l
	cp   LOW(wLabStateEnd)
	jr   nz, .clear
	jp   Reset


PUSHC
SETCHARMAP labfont

LabEraseText:
	dw _SCRN0 +  5 * 32 + 3
	db "ERASE ALL SAVES", $ff
	dw _SCRN0 +  8 * 32 + 8
	db "NO", $ff
	dw _SCRN0 + 10 * 32 + 8
	db "YES", $ff
	dw _SCRN0 + 14 * 32 + 1
	db "A SELECT  B CANCEL", $ff

POPC
