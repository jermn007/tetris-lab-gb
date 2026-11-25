# 16. Game statistics are counted by watching, not by hooking

**Status:** accepted, 2026-11-24

## Context

Players asked for a record of each game: the score and lines on reaching
level 10 and level 20, tetris rate, longest drought. The obvious build hooks
the three places those happen - the level-up, the row count, the piece deal -
and each is a new edit to bank 0.

## Decision

**No hook. `LabStatsTrack` runs from the existing per-frame gameplay hook and
counts what changed since the last frame.** `src/lab/stats.asm`.

| Event | How it is seen |
| --- | --- |
| Level reached | `hATypeLinesThresholdToPassForNextLevel` differs from last frame |
| Piece locked | `hPieceFallingState` becomes `ALL_ROWS_PROCESSED`; `hNumCompletedTetrisRows` is the clear |
| Piece dealt | first frame after a lock with nothing settling and no rows shifting |
| Game finished | the game over screen, state `$04`, once |

The record is 33 bytes at `wLabStats`, laid out to be copied whole when
records are saved.

## Consequences

* **A checkpoint is the score and lines the clear left**, with nothing to
  correct. The clear's points go in at row-shift step 5 (`$1F91`), the level
  goes up at step 16 (`$239A`), the next piece comes at step 19 - so the first
  frame that shows the new level has the old level's points and no later ones.
* **The original's per-size counters are no use.** `wLinesClearedStructs` is
  emptied as each clear is scored. The Lab keeps its own four words.
* **A clear raises the level by one at most**, so a start on level 7 with 90
  lines is level 8, not 9. A test here had that wrong first.
* **Droughts count pieces dealt**, from the first, including the one on screen
  when the game ends.
* **TETRIS only.** B-type, 2-player and every trainer leave the record zeroed.
  Seeded games are recorded and flagged, so a later change can decline to
  save them.
* **A game is finished only if it reached the game over screen.** Instant
  restart and B-while-paused leave `STATSB_DONE` clear.
* **Tetris rate is not stored.** It is the four counts, divided when drawn.
* Not done here: saving. The screen is ADR 0017.
