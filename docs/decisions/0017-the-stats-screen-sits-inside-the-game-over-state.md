# 17. The stats screen sits inside the game over state

**Status:** accepted, 2026-11-24

## Context

A finished TETRIS game has a record (ADR 0016) and nowhere to show it. The
page has to come after the game over screen and before the name entry, and
the original's state table has no slot between them.

## Decision

**No new state and no new hook. The page is a second phase of state `$04`,
which is already hooked.** `src/lab/stats_screen.asm`.

| Press on `$04` | What happens |
| --- | --- |
| first `A` or `Start` | the Lab paints the page; the original handler does not run |
| second | the original handler runs, untouched: name entry if the score placed, else the level select |

`wLabStatsShown` tells the two apart. It lives in the range `LabStatsArm`
clears, so every game starts on the first.

The page is painted once with the LCD off, like every screen, so the tetris
rate is worked out there and nothing runs in VBlank. It draws only font
tiles, which are under every tileset, so it loads none.

## Consequences

* **A game with no record gets no page.** Trainers, B-type and 2-player leave
  `STATSB_DONE` clear, and the first press is the original's as before.
* **Opening the page clears `hRowsShiftingDownState`**, as the original does on
  the same press (`$1D0F`). The game over box is still being sent a row a
  frame, and would be sent over the page.
* **A level not reached has no row**, and the rows close up: a game from level
  15 shows `END` then `L20`.
* **Tetris rate is the share of lines cleared four at a time**, rounded down -
  the NES community's definition. Counted out in a hundred additions; there is
  no divide.
* **The restart combination works from the page**, because it is still `$04`.
* Every test that walked a TETRIS game past game over with one press needs two.
* Saving records, and the RECORDS screen that reuses this page: ADR 0018.
