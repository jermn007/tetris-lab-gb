; --------------------------------------------------------------------------
; Battery save
;
; High scores survive a power cycle. WRAM stays the working copy - everything
; that files, names or draws a score is unchanged - and cartridge RAM is a
; mirror of it, written when a score is filed and read once per power-on.
; See docs/decisions/0015.
;
;   $A000  "TLAB", version              the header, written last
;   $A040  A-type, plain   23 slots     entries, seventh digits, checksum
;   $A340  A-type, hearts  23 slots     the same
;   $A640  B-type          60 slots     entries, checksum
;   $A005  the records' own version
;   $A006  settings: settings.asm
;   $AD00  records         138 slots    one per A-type entry: records.asm
;   $BF54  free                         172 bytes, kept for lifetime totals
;
; A slot is one level's three entries exactly as the original keeps them, so a
; slot is the unit a score changes - and the unit a power cut can damage. Each
; carries its own checksum for that reason: one bad slot comes back empty and
; the rest of the table is kept.
;
; Cartridge RAM is opened for one slot at a time and closed again. It is never
; left open while anything else runs.
; --------------------------------------------------------------------------

DEF SAVE_VERSION   EQU 1
DEF SAVE_SUM_SEED  EQU $5a      ; so a slot of zeros does not sum to zero, and
                                ; erased RAM - all $00 or all $FF - never passes

DEF SAVE_HEADER    EQU $a000
DEF SAVE_PLAIN     EQU $a040
DEF SAVE_HEART     EQU $a340
DEF SAVE_BTYPE     EQU $a640

DEF SAVE_A_SLOTS   EQU MAX_LEVEL + 1
DEF SAVE_B_SLOTS   EQU 10 * 6   ; level by height, as wBTypeHighScores is laid out
DEF SAVE_MILLIONS  EQU 3        ; seventh digits per slot, one per entry

DEF SAVE_PUT       EQU 0        ; wLabSaveDir: WRAM to cartridge
DEF SAVE_GET       EQU 1        ; cartridge to WRAM
DEF SAVE_SKIP      EQU 2        ; step over a slot that failed its checksum

DEF SAVE_RAM_ON    EQU $0a
DEF SAVE_RAM_OFF   EQU $00


; Once per power-on: bring the saved tables into WRAM, or start a save if the
; cartridge does not hold one of ours.
;
; Not on a soft reset. That leaves $D000-$DFFF as it was, so WRAM is already
; the newer copy - and wLabSaveLoaded, which sits there too, is still set. A
; cold boot clears it along with the tables (Begin2, $020C).
;
; A cartridge with no RAM reads back $FF and ignores writes, so it lands on the
; "start a save" path every boot and nothing comes of it: scores last the
; session, as they did before. That is --no-sram, and D9.
LabSaveBoot::
	ld   hl, wLabSaveLoaded
	ld   a, [hl]
	and  a
	jp   nz, LabSettingsBoot        ; a soft reset: only HRAM was lost
	inc  [hl]

	call LabSaveHeaderIsOurs
	jr   nz, .fresh

	ld   a, SAVE_GET
	call LabSaveWalk
	call LabRecordsCheck
	call LabSettingsLoad
	jp   LabSettingsBoot

.fresh:
	call LabSaveAll
	jp   LabRecordsClear


; Write every table and then the header. A few frames, so only ever from a
; menu: when a name entry begins and ends, and when there was no save to load.
;
; Everything rather than the slot that changed, because most of it is already
; there - rewriting a byte with the value it holds risks nothing - and finding
; the one slot would mean working back from the original's pointers.
LabSaveAll::
	xor  a                          ; SAVE_PUT
	call LabSaveWalk

	ld   a, SAVE_RAM_ON
	ld   [rRAMG], a
	ld   hl, SAVE_HEADER
	ld   de, LabSaveMagic
	ld   c, LabSaveMagic.end - LabSaveMagic

.header:
	ld   a, [de]
	ld   [hl+], a
	inc  de
	dec  c
	jr   nz, .header

	xor  a                          ; SAVE_RAM_OFF
	ld   [rRAMG], a
	ret


; a = SAVE_PUT or SAVE_GET.
;
; The plain table is the live one unless hearts are on (ADR 0014), so which
; half of WRAM each A-type region mirrors depends on wLabTablesAreHearts.
LabSaveWalk:
	ld   [wLabSaveDir], a

	ld   a, [wLabTablesAreHearts]
	and  a
	ld   hl, SAVE_PLAIN
	jr   z, .liveFirst
	ld   hl, SAVE_HEART

.liveFirst:
	push af
	ld   de, wATypeHighScores
	ld   bc, wLabHiScoreMillions
	call .aType
	pop  af

	ld   hl, SAVE_HEART
	jr   z, .otherSecond
	ld   hl, SAVE_PLAIN

.otherSecond:
	ld   de, wLabOtherHighScores
	ld   bc, wLabOtherMillions
	call .aType

	ld   hl, SAVE_BTYPE
	ld   de, wBTypeHighScores
	xor  a
	ld   [wLabSaveMil], a           ; B-type never passes a million: its score
	ld   a, SAVE_B_SLOTS            ; is counted up from the lines at the end
	jr   .slots

.aType:
	ld   a, b
	ld   [wLabSaveMil], a
	ld   a, c
	ld   [wLabSaveMil + 1], a
	ld   a, SAVE_A_SLOTS

; hl = the first slot on the cartridge, de = its entries in WRAM, a = how many.
; wLabSaveMil = their seventh digits, or a zero high byte for none.
.slots:
	ld   [wLabSaveCount], a

.slot:
	ld   a, SAVE_RAM_ON
	ld   [rRAMG], a

	ld   a, [wLabSaveDir]
	and  a
	jr   z, .transfer
	call .slotIsSound
	jr   z, .transfer
	ld   a, SAVE_SKIP               ; leave WRAM's slot as it is: empty
	ld   [wLabSaveDir], a

.transfer:
	ld   b, SAVE_SUM_SEED
	ld   c, HISCORE_SIZEOF
	call .move

	ld   a, [wLabSaveMil]
	and  a
	jr   z, .checksum

	push de
	ld   d, a
	ld   a, [wLabSaveMil + 1]
	ld   e, a
	ld   c, SAVE_MILLIONS
	call .move
	ld   a, d
	ld   [wLabSaveMil], a
	ld   a, e
	ld   [wLabSaveMil + 1], a
	pop  de

.checksum:
	ld   a, [wLabSaveDir]
	and  a
	jr   nz, .afterChecksum
	ld   [hl], b

.afterChecksum:
	inc  hl
	cp   SAVE_SKIP
	jr   nz, .close
	dec  a                          ; back to SAVE_GET for the next slot
	ld   [wLabSaveDir], a

.close:
	xor  a                          ; SAVE_RAM_OFF
	ld   [rRAMG], a

	ld   a, [wLabSaveCount]
	dec  a
	ld   [wLabSaveCount], a
	jr   nz, .slot
	ret

; hl = cartridge, de = WRAM, c = bytes, b = the checksum so far. All four
; come back advanced.
.move:
	ld   a, [wLabSaveDir]
	and  a
	jr   z, .put
	dec  a
	jr   z, .get

.skip:
	inc  hl
	inc  de
	dec  c
	jr   nz, .skip
	ret

.put:
	ld   a, [de]
	ld   [hl+], a
	add  b
	ld   b, a
	inc  de
	dec  c
	jr   nz, .put
	ret

.get:
	ld   a, [hl+]
	ld   [de], a
	inc  de
	dec  c
	jr   nz, .get
	ret

; hl = a slot on the cartridge. Z if its checksum matches. Preserves hl and de.
.slotIsSound:
	push hl
	ld   c, HISCORE_SIZEOF
	ld   a, [wLabSaveMil]
	and  a
	jr   z, .haveLength
	ld   c, HISCORE_SIZEOF + SAVE_MILLIONS

.haveLength:
	ld   b, SAVE_SUM_SEED

.sum:
	ld   a, [hl+]
	add  b
	ld   b, a
	dec  c
	jr   nz, .sum

	ld   a, [hl]
	cp   b
	pop  hl
	ret


; Z if the cartridge holds a save this version wrote. A different version is
; not read: it is started again, which is what architecture.md 4.3 asks for.
LabSaveHeaderIsOurs:
	ld   a, SAVE_RAM_ON
	ld   [rRAMG], a
	ld   hl, SAVE_HEADER
	ld   de, LabSaveMagic
	ld   c, LabSaveMagic.end - LabSaveMagic

.compare:
	ld   a, [de]
	cp   [hl]
	jr   nz, .done
	inc  hl
	inc  de
	dec  c
	jr   nz, .compare

.done:
	push af
	xor  a                          ; SAVE_RAM_OFF
	ld   [rRAMG], a
	pop  af
	ret


LabSaveMagic:
	db   $54, $4c, $41, $42         ; "TLAB", in ASCII whatever the charmap is
	db   SAVE_VERSION
.end:
