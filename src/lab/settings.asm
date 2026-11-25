; --------------------------------------------------------------------------
; Remembered settings
;
; The level, hearts and music the last game was started with, and the last
; name typed, so the cartridge comes back on the way it was left.
;
;   $A006  level, hearts, music, name x 6, checksum
;
; WRAM holds the working copy (wLabSet*), which is also what carries them
; across a soft reset: that clears HRAM, where the game keeps all three.
; Written when a game starts and when a name is finished - never in between,
; so trying a level or a song and switching off changes nothing.
; --------------------------------------------------------------------------

DEF SAVE_SETTINGS   EQU SAVE_HEADER + 6
DEF SETTINGS_SIZEOF EQU wLabSetEnd - wLabSetLevel
DEF NAME_LEN        EQU 6


; Every boot, cold or soft, once the save is in.
LabSettingsBoot::
	ld   a, [wLabSetValid]
	and  a
	ret  z

	ld   a, [wLabSetLevel]
	ldh  [hATypeLevel], a
	ld   a, [wLabSetHearts]
	ldh  [hIsHardMode], a
	ld   a, [wLabSetMusic]
	ldh  [hMusicType], a
	ret


; A cold boot only. Settings that do not add up, or could not have been
; written by this, are not used: the game starts as it always did.
LabSettingsLoad::
	ld   a, SAVE_RAM_ON
	ld   [rRAMG], a
	ld   hl, SAVE_SETTINGS
	ld   de, wLabSetLevel
	ld   b, SAVE_SUM_SEED
	ld   c, SETTINGS_SIZEOF
.byte:
	ld   a, [hl+]
	ld   [de], a
	add  b
	ld   b, a
	inc  de
	dec  c
	jr   nz, .byte
	ld   a, [hl]
	cp   b
	ld   a, SAVE_RAM_OFF            ; ld leaves the flags alone
	ld   [rRAMG], a
	jr   nz, .none

	ld   a, [wLabSetLevel]
	cp   MAX_LEVEL + 1
	jr   nc, .none
	cp   21                         ; no hearts up here: see LabLevelSelectPost
	ld   a, [wLabSetHearts]
	jr   c, .heartsAllowed
	and  a
	jr   nz, .none
.heartsAllowed:
	cp   2
	jr   nc, .none
	ld   a, [wLabSetMusic]
	sub  MUSIC_TYPES_START
	cp   4
	jr   nc, .none

	ld   a, 1
	ld   [wLabSetValid], a
	ret

.none:
	xor  a
	ld   [wLabSetValid], a
	ld   [wLabSetName], a           ; and no name to offer
	ret


; A game is starting, or a name is in: these are the settings now.
LabSettingsKeep::
	ldh  a, [hATypeLevel]
	ld   [wLabSetLevel], a
	ldh  a, [hIsHardMode]
	ld   [wLabSetHearts], a
	ldh  a, [hMusicType]
	ld   [wLabSetMusic], a
	ld   a, 1
	ld   [wLabSetValid], a

	ld   a, SAVE_RAM_ON
	ld   [rRAMG], a
	ld   hl, SAVE_SETTINGS
	ld   de, wLabSetLevel
	ld   b, SAVE_SUM_SEED
	ld   c, SETTINGS_SIZEOF
.byte:
	ld   a, [de]
	ld   [hl+], a
	add  b
	ld   b, a
	inc  de
	dec  c
	jr   nz, .byte
	ld   [hl], b
	xor  a                          ; SAVE_RAM_OFF
	ld   [rRAMG], a
	ret


; The first frame of a name entry. The original has just put "A....." in the
; table and pointed hTypedTextCharLoc at it; the last name typed goes over
; that, in the table and on the screen, so Start alone signs the score.
;
; Typing still works the original's way: A moves on and starts the next
; letter at "A", whatever was offered there.
LabNameOffer::
	ldh  a, [hTypedTextCharLoc]
	ld   d, a
	ld   [wLabNamePtr], a
	ldh  a, [hTypedTextCharLoc + 1]
	ld   e, a
	ld   [wLabNamePtr + 1], a

	ld   a, [wLabSetName]
	and  a
	ret  z                          ; nobody has typed one

; Where the original draws this name ($1915): the third place's row, and up
; one for each place better.
	ldh  a, [hReversedHighScoreRanking]
	ld   hl, _SCRN0 + $1e4
	ld   bc, -$20
.row:
	dec  a
	jr   z, .haveRow
	add  hl, bc
	jr   .row

.haveRow:
	ld   bc, wLabSetName
	ld   a, NAME_LEN
.char:
	push af
	ld   a, [bc]
	ld   [de], a
	call LabPutTile                 ; keeps bc, de and hl
	inc  bc
	inc  de
	inc  hl
	pop  af
	dec  a
	jr   nz, .char
	ret


; The name entry has just finished: the name in the table is the one to
; offer next time.
LabNameKeep::
	ld   hl, wLabNamePtr
	ld   a, [hl+]
	ld   l, [hl]
	ld   h, a
	ld   de, wLabSetName
	ld   b, NAME_LEN
.char:
	ld   a, [hl+]
	ld   [de], a
	inc  de
	dec  b
	jr   nz, .char
	jp   LabSettingsKeep
