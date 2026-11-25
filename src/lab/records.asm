; --------------------------------------------------------------------------
; Saved records
;
; Every A-type high score keeps the record of the game that set it, and the
; RECORDS row of the menu reads them back on the stats page. See
; docs/decisions/0018.
;
;   $A005  RECORDS_VERSION
;   $AD00  plain   23 levels x 3 places   a record, then its checksum
;   $B62A  hearts  the same
;
; A record's slot is its entry's: level x 3 + place, so nothing has to say
; which score a record belongs to. They are filed together and shifted
; together (LabFileHighScore), and that is the whole of the bookkeeping.
;
; Cartridge only. 138 records are 4.6 KB and WRAM has a seventh of that
; free, so unlike the scores there is no working copy: one record at a time is
; read into wLabView when somebody asks to see it. A cartridge with no RAM
; keeps none, and the page says so.
;
; A record that fails its checksum, or was never finished, is no record. That
; covers a slot never written, a score set before records existed, and a game
; that keeps none: a trainer, or one played on a seed.
; --------------------------------------------------------------------------

DEF RECORDS_VERSION    EQU 1
DEF SAVE_RECORDS_MARK  EQU SAVE_HEADER + 5
DEF SAVE_RECORDS       EQU $ad00

DEF RECORD_SIZEOF      EQU wLabStatsRecordEnd - wLabStats
DEF RECORD_SLOT        EQU RECORD_SIZEOF + 1
DEF RECORDS_PER_TABLE  EQU (MAX_LEVEL + 1) * 3
DEF RECORDS_COUNT      EQU RECORDS_PER_TABLE * 2

	ASSERT SAVE_RECORDS + RECORD_SLOT * RECORDS_COUNT <= $c000

DEF REC_LAST           EQU 0        ; wLabRecEntry: the game just played


; Once per power-on, after the scores are in. Records written to a layout
; other than this one are not read: they are emptied.
LabRecordsCheck::
	ld   a, SAVE_RAM_ON
	ld   [rRAMG], a
	ld   a, [SAVE_RECORDS_MARK]
	ld   b, a
	xor  a                          ; SAVE_RAM_OFF
	ld   [rRAMG], a
	ld   a, b
	cp   RECORDS_VERSION
	ret  z
; fall through

; Every record empty. A slot at a time, so the cartridge is never left open
; across a frame.
LabRecordsClear::
	call LabViewClear
	xor  a

.slot:
	push af
	call LabRecordAddress
	call LabRecordPutEmpty
	pop  af
	inc  a
	cp   RECORDS_COUNT
	jr   c, .slot

	ld   a, SAVE_RAM_ON
	ld   [rRAMG], a
	ld   a, RECORDS_VERSION
	ld   [SAVE_RECORDS_MARK], a
	xor  a
	ld   [rRAMG], a
	ret


LabViewClear:
	ld   hl, wLabView
	ld   b, RECORD_SIZEOF
	xor  a
.clear:
	ld   [hl+], a
	dec  b
	jr   nz, .clear
	ret


; a = a record's number. Returns hl = its slot on the cartridge.
LabRecordAddress:
	ld   hl, SAVE_RECORDS
	and  a
	ret  z
	ld   de, RECORD_SLOT
.next:
	add  hl, de
	dec  a
	jr   nz, .next
	ret


; a = place 0-2, b = level, c = hearts. Returns a = the record's number.
LabRecordNumber:
	add  b
	add  b
	add  b
	inc  c
	dec  c
	ret  z
	add  RECORDS_PER_TABLE
	ret


; hl = a slot. wLabView goes into it - or, at PutEmpty, nothing does: the
; checksum of a slot of zeros is the seed, so a zero there never passes.
LabRecordPut:
	ld   b, SAVE_SUM_SEED
	jr   LabRecordPutEmpty.write

LabRecordPutEmpty:
	ld   b, 0
.write:
	ld   a, SAVE_RAM_ON
	ld   [rRAMG], a
	ld   de, wLabView
	ld   c, RECORD_SIZEOF
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


; hl = a slot, into wLabView. One that is not sound comes back with no flags,
; which is what "no record" is everywhere else.
LabRecordGet:
	ld   a, SAVE_RAM_ON
	ld   [rRAMG], a
	ld   de, wLabView
	ld   b, SAVE_SUM_SEED
	ld   c, RECORD_SIZEOF
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
	ret  z
	xor  a
	ld   [wLabViewFlags], a
	ret


; A score has just placed. b = the place it takes, 0-2, in the live table at
; hATypeLevel. The records under it move down with their scores and this
; game's goes in. Preserves bc, de and hl.
LabRecordFile::
	push hl
	push de
	push bc
	ld   a, b
	ld   [wLabRecPos], a

	cp   2
	jr   z, .store
	ld   a, 1
	call .down
	ld   a, [wLabRecPos]
	and  a
	call z, .down

; A game that kept a record and was not played on a seed: a seeded game can be
; learned, so its record says less than it seems to.
.store:
	ld   a, [wLabStatsFlags]
	and  (1 << STATSB_DONE) | (1 << STATSB_SEEDED)
	cp   1 << STATSB_DONE
	push af
	call z, LabStatsViewLast
	pop  af
	call nz, LabViewClear

	ld   a, [wLabRecPos]
	call .slot
	ld   a, [wLabViewFlags]
	and  a
	jr   z, .empty
	call LabRecordPut
	jr   .done

.empty:
	call LabRecordPutEmpty

.done:
	pop  bc
	pop  de
	pop  hl
	ret

; a = a place. Its record goes one down.
.down:
	push af
	call .slot
	call LabRecordGet
	pop  af
	inc  a
	call .slot
	ld   a, [wLabViewFlags]
	and  a
	jp   nz, LabRecordPut
	push hl                         ; the slot
	call LabViewClear
	pop  hl
	jp   LabRecordPutEmpty

; a = a place in the table being filed into. Returns hl = its slot.
.slot:
	push af
	ldh  a, [hATypeLevel]
	ld   b, a
	ld   a, [wLabTablesAreHearts]
	ld   c, a
	pop  af
	call LabRecordNumber
	jp   LabRecordAddress


; --------------------------------------------------------------------------
; The RECORDS screen
;
; The stats page again, on the menu's own state, with a line above it saying
; whose game this is:
;
;        0         1
;        01234567890123456789
;   0     LEVEL 9 HEART NO.1        or nothing, for the last game
;   1           TOLSTO              or LAST GAME
;   3 on  the page, or NO RECORD
;
; Up/Down walk LAST, 1, 2, 3. Left/Right change the level, Select the hearts.
; B goes back. Every change repaints the page whole, LCD off: it is a page
; turn, and nothing here is in a hurry.
; --------------------------------------------------------------------------

LabRecordsOpen::
	ld   a, 1
	ld   [wLabRecordsOpen], a

; On the game just played, when there is one to show.
	ld   a, [wLabStatsFlags]
	bit  STATSB_DONE, a
	ld   a, REC_LAST
	jr   nz, .have
	inc  a
.have:
	ld   [wLabRecEntry], a
	ld   a, SND_CONFIRM_OR_LETTER_TYPED
	ld   [wSquareSoundToPlay], a
	jp   LabRecordsDraw


; Every frame the screen is up.
LabRecords::
	ldh  a, [hButtonsPressed]
	ld   c, a
	bit  PADB_B, c
	jr   nz, .close

	ld   hl, wLabRecEntry
	bit  PADB_DOWN, c
	jr   z, .notDown
	ld   a, [hl]
	inc  a
	jr   .setEntry

.notDown:
	bit  PADB_UP, c
	jr   z, .notUp
	ld   a, [hl]
	dec  a
.setEntry:
	and  3
	ld   [hl], a
	jr   .changed

.notUp:
	ld   a, c
	and  PADF_LEFT | PADF_RIGHT | PADF_SELECT
	ret  z

; The last game is in no table. The first press that asks for one goes to the
; top of the table last looked at.
	ld   a, [hl]
	and  a
	jr   nz, .inTables
	inc  [hl]
	jr   .changed

.inTables:
	bit  PADB_SELECT, c
	jr   z, .level
	ld   hl, wLabRecHearts
	ld   a, [hl]
	xor  1
	ld   [hl], a
	jr   .changed

.level:
	ld   b, 1
	bit  PADB_RIGHT, c
	jr   nz, .haveStep
	ld   b, -1
.haveStep:
	ld   hl, wLabRecLevel
	ld   a, [hl]
	add  b
	cp   MAX_LEVEL + 1
	jr   c, .setLevel
	bit  7, a
	ld   a, 0
	jr   z, .setLevel
	ld   a, MAX_LEVEL
.setLevel:
	ld   [hl], a

.changed:
	call LabMenuSound
	jr   LabRecordsDraw

.close:
	xor  a
	ld   [wLabRecordsOpen], a
	call LabMenuSound
	jp   LabMenuDraw


LabRecordsDraw:
	ld   a, [wLabRecEntry]
	and  a
	jr   nz, .saved

	call LabStatsViewLast
	call LabStatsPageOpen
	ld   hl, LabRecLastTitle
	call LabStatsLabel
	jr   .body

.saved:
	dec  a
	push af
	ld   a, [wLabRecLevel]
	ld   b, a
	ld   a, [wLabRecHearts]
	ld   c, a
	pop  af
	call LabRecordNumber
	call LabRecordAddress
	call LabRecordGet
	call LabStatsPageOpen

	ld   hl, LabRecHeader
	call LabStatsLabel
	call LabStatsLabel
	ld   a, [wLabRecLevel]          ; 0-9 then A-M: the font's own order
	ld   [_SCRN0 + 7], a
	ld   a, [wLabRecEntry]
	ld   [_SCRN0 + 18], a
	ld   a, [wLabRecHearts]
	and  a
	call nz, LabStatsLabel          ; hl is on the heart's label
	call LabRecordsName

.body:
	ld   a, [wLabViewFlags]
	bit  STATSB_DONE, a
	jr   z, .none
	call LabStatsBody
	jp   LabStatsPageShow

.none:
	ld   hl, LabRecNone
	call LabStatsLabel
	jp   LabStatsPageShow


; The name beside the score this record belongs to. The table for the hearts
; being looked at is the live one or the parked one (ADR 0014).
LabRecordsName:
	ld   a, [wLabTablesAreHearts]
	ld   b, a
	ld   a, [wLabRecHearts]
	cp   b
	ld   hl, wATypeHighScores + HISCORE_Name1
	jr   z, .haveTable
	ld   hl, wLabOtherHighScores + HISCORE_Name1

.haveTable:
	ld   de, HISCORE_SIZEOF
	ld   a, [wLabRecLevel]
	call .skip
	ld   de, 6
	ld   a, [wLabRecEntry]
	dec  a
	call .skip

; An entry nobody has set has no name, and its bytes are noughts.
	push hl
	ld   b, 6
	xor  a
.any:
	or   [hl]
	inc  hl
	dec  b
	jr   nz, .any
	pop  hl
	and  a
	ret  z

	ld   de, _SCRN0 + 1 * 32 + 7
	ld   b, 6
.char:
	ld   a, [hl+]
	cp   LAB_FONT_TILES             ; the name entry has characters this
	jr   c, .put                    ; screen's tileset does not
	ld   a, TILE_BLANK
.put:
	ld   [de], a
	inc  de
	dec  b
	jr   nz, .char
	ret

.skip:
	and  a
	ret  z
.next:
	add  hl, de
	dec  a
	jr   nz, .next
	ret


PUSHC
SETCHARMAP labfont

LabRecLastTitle:
	dw _SCRN0 + 1 * 32 + 5
	db "LAST GAME", $ff

LabRecHeader:
	dw _SCRN0 + 1
	db "LEVEL", $ff
	dw _SCRN0 + 15
	db "NO.", $ff
	dw _SCRN0 + 9
	db "HEART", $ff

LabRecNone:
	dw _SCRN0 + 8 * 32 + 5
	db "NO RECORD", $ff

POPC
