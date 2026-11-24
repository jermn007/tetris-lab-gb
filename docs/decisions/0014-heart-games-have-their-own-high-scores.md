# 14. Heart games have their own high scores, by exchanging tables

**Status:** accepted, 2026-11-24

## Context

A heart game at level 9 falls at level 19's speed, but its score was filed in
level 9's three slots beside plain games. The two are not the same contest.

Everything that touches an A-type entry indexes `wATypeHighScores` directly:
the original's filing, name entry and display, and the Lab's own ranking. A
second table chosen by `hIsHardMode` would need every one of those taught about
it - a hook in each original routine.

## Decision

Keep one **live** table where the original expects it, and park the other in
`wLabOtherHighScores` / `wLabOtherMillions`. `LabSyncHeartTables` exchanges the
two whenever hearts change: on Select, where the picker forces hearts off at L
and M, and before a finished game is filed.

`wLabTablesAreHearts` records which table is live. `hIsHardMode` cannot: the
soft reset clears HRAM and leaves `$D000-$DFFF` alone.

## Consequences

* **No hook, and no change to how a score is filed or drawn.** Code written
  against `wATypeHighScores` is right without knowing there are two tables.
* **The exchange is 690 bytes, a little under a frame.** Fine on a menu; never
  call it during play.
* **Anything that reads a table by address reads the live one.** To reach a
  specific table, check `wLabTablesAreHearts` first. Persistence will need to.
* L and M have heart slots that can never be filled, since hearts are withheld
  there. 60 bytes, spent to keep both tables one shape.
* **B-type is not split.** Its level select has no heart toggle of its own; it
  inherits whatever the A-type screen last set.
