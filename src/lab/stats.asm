; --------------------------------------------------------------------------
; Game statistics
;
; What a finished A-type game looked like: the score and lines at the moment
; it reached level 10 and level 20, how its lines were cleared, and the
; longest run of pieces without an I. See docs/decisions/0016.
;
; Nothing here is a hook and nothing is drawn. The per-frame gameplay hook
; runs in front of the original handler, so this reads what the last frame
; left behind and counts the changes. The game is never told it is watched.
;
; TETRIS only. A trainer starts from a state nobody played their way to, and
; B-type has no levels to pass.
; --------------------------------------------------------------------------

DEF STATSB_TRACKING EQU 0       ; this game is one we count
DEF STATSB_DONE     EQU 1       ; and it ended: wLabStatsFinal is filled in
DEF STATSB_HEARTS   EQU 2
DEF STATSB_SEEDED   EQU 3
DEF STATSB_L10      EQU 4       ; wLabStatsL10 holds a checkpoint
DEF STATSB_L20      EQU 5


; Every game begins here. Called after LabArmSeed, which is what decides
; whether this one is seeded.
LabStatsArm::
	ld   hl, wLabStats
	ld   b, wLabStatsEnd - wLabStats
	xor  a

.clear:
	ld   [hl+], a
	dec  b
	jr   nz, .clear

	ldh  a, [hGameType]
	cp   GAME_TYPE_A_TYPE
	ret  nz
	ld   a, [wLabMode]
	and  a                          ; MODE_TETRIS
	ret  nz
	ldh  a, [hIs2Player]
	and  a
	ret  nz

	ld   b, 1 << STATSB_TRACKING
	ldh  a, [hIsHardMode]
	and  a
	jr   z, .noHearts
	set  STATSB_HEARTS, b

.noHearts:
	ldh  a, [hLabSpsEnabled]
	and  a
	jr   z, .noSeed
	set  STATSB_SEEDED, b

.noSeed:
	ld   a, b
	ld   [wLabStatsFlags], a

	ldh  a, [hATypeLevel]
	ld   [wLabStatsStartLevel], a
	ld   [wLabStatsLevelSeen], a
	ld   a, 1
	ld   [wLabStatsAwaitSpawn], a   ; the first piece is dealt by the init
	ret


; Every gameplay frame, before the original handler.
LabStatsTrack::
	ld   a, [wLabStatsFlags]
	bit  STATSB_TRACKING, a
	ret  z

; --- a level reached ---
; The level goes up in VBlank, while the cleared rows are still being redrawn
; ($239A) - eleven steps after the main loop added the points for that clear
; ($1F91), and before the next piece exists. So on the first frame the new
; level is visible here, the score and the lines are exactly what the clear
; left behind.
	ldh  a, [hATypeLinesThresholdToPassForNextLevel]
	ld   hl, wLabStatsLevelSeen
	cp   [hl]
	jr   z, .pieces
	ld   [hl], a

	ld   de, wLabStatsL10
	ld   b, 1 << STATSB_L10
	cp   10
	jr   z, .checkpoint
	ld   de, wLabStatsL20
	ld   b, 1 << STATSB_L20
	cp   20
	jr   nz, .pieces

.checkpoint:
	ld   hl, wLabStatsFlags
	ld   a, [hl]
	or   b
	ld   [hl], a
	call LabStatsSnapshot

; --- a piece locked, or the next one dealt ---
.pieces:
	ldh  a, [hPieceFallingState]
	ld   hl, wLabStatsWasState
	ld   b, [hl]
	ld   [hl], a
	cp   FALLING_PIECE_ALL_ROWS_PROCESSED_AFTER_DROP
	jr   nz, .notLocked
	cp   b
	ret  z                          ; still the same lock

; The frame after InGameCheckIfAnyTetrisRowsComplete ($213E) counted the rows.
; Its own per-size counters cannot be used: they are emptied as each clear is
; scored. hNumCompletedTetrisRows is also scratch for the falling piece ($20C6),
; but nothing falls between that count and this frame.
	ld   a, 1
	ld   [wLabStatsAwaitSpawn], a

	ldh  a, [hNumCompletedTetrisRows]
	and  a
	ret  z
	cp   5
	ret  nc
	dec  a
	add  a
	ld   e, a
	ld   d, 0
	ld   hl, wLabStatsClears
	add  hl, de
	jr   LabStatsInc16

; The next piece is dealt in VBlank: with the lock when no row was complete,
; and once the rows have finished shifting down when one was. Either way it is
; the first frame after a lock with nothing settling and nothing shifting.
.notLocked:
	and  a
	ret  nz
	ldh  a, [hRowsShiftingDownState]
	and  a
	ret  nz
	ld   hl, wLabStatsAwaitSpawn
	ld   a, [hl]
	and  a
	ret  z
	ld   [hl], 0

	ld   hl, wLabStatsPieces
	call LabStatsInc16

; A drought is counted in pieces dealt, from the first one, and the piece on
; screen when the game ends is part of it.
	ld   a, [wSpriteSpecs + SPR_SPEC_SpecIdx]
	and  $fc
	cp   SPRITE_SPEC_STRAIGHT_PIECE
	ld   hl, wLabStatsDroughtNow
	jr   nz, .dry
	xor  a
	ld   [hl+], a
	ld   [hl], a
	ret

.dry:
	call LabStatsInc16

	ld   hl, wLabStatsDroughtNow    ; longest = max(longest, now)
	ld   a, [hl+]
	ld   c, a
	ld   b, [hl]
	ld   hl, wLabStatsDrought + 1
	ld   a, [hl-]
	cp   b
	jr   c, .longer
	ret  nz
	ld   a, [hl]
	cp   c
	ret  nc

.longer:
	ld   hl, wLabStatsDrought
	ld   a, c
	ld   [hl+], a
	ld   [hl], b
	ret


; The game over screen, every frame of it, and acted on once. Here because it
; is the one place every finished game passes through and no other does: a game
; left by the instant restart or by B while paused never arrives, and is not a
; finished game.
LabStatsFinish::
	ld   hl, wLabStatsFlags
	ld   a, [hl]
	bit  STATSB_TRACKING, a
	ret  z
	bit  STATSB_DONE, a
	ret  nz
	set  STATSB_DONE, [hl]

	ldh  a, [hATypeLinesThresholdToPassForNextLevel]
	ld   [wLabStatsLevel], a
	ld   de, wLabStatsFinal
; fall through

; de = a checkpoint to fill with the score and the lines as they are now.
LabStatsSnapshot:
	ld   hl, wScoreBCD
	ld   b, 3

.score:
	ld   a, [hl+]
	ld   [de], a
	inc  de
	dec  b
	jr   nz, .score

	ld   a, [wLabScoreMillions]
	ld   [de], a
	inc  de
	ldh  a, [hNumLinesCompletedBCD]
	ld   [de], a
	inc  de
	ldh  a, [hNumLinesCompletedBCD + 1]
	ld   [de], a
	ret


; hl = a word, low byte first.
LabStatsInc16:
	inc  [hl]
	ret  nz
	inc  hl
	inc  [hl]
	ret
