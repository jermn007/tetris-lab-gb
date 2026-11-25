# 18. Records live on the cartridge, in their score's place

**Status:** accepted, 2026-11-24

## Context

A game's record (ADR 0016) is 33 bytes and was gone at the next game. Every
A-type high score should keep the record of the game that set it: 23 levels,
three places, two tables - 138 records, 4.6 KB. WRAM has 685 bytes free.

## Decision

**Records are kept on the cartridge only, one slot per high score entry, at
the entry's own position.** `src/lab/records.asm`.

| Range | Contents |
| --- | --- |
| `$A005` | `RECORDS_VERSION`. Anything else and every record is emptied at boot |
| `$AD00` | plain: level x 3 + place, 34 bytes each - the record, then its checksum |
| `$B62A` | hearts, the same |
| `$BF54-$BFFF` | free: 172 bytes, kept for lifetime totals |

Position is the only link between a record and its score. `LabFileHighScore`
already knows the place a score takes; `LabRecordFile` moves the records
under it down and writes this game's there, in the same call.

There is no working copy (unlike ADR 0015). One record at a time is read into
`wLabView`, which is what the stats page now draws from - so the page serves
the game just played and a saved one alike, and looking at an old game does
not cost the last one.

**RECORDS is a row of the Lab menu and a screen on the menu's own state**
(`$0E`, `wLabRecordsOpen`): no new state, no hook. Up/Down walk the last game
and the three places, Left/Right the level, Select the hearts, B goes back.
Every change repaints the page with the LCD off.

## Consequences

* **`SAVE_VERSION` is not bumped.** A version-1 save keeps its scores; its
  records start empty because `$A005` was never written.
* **No record** is one value everywhere: a slot that fails its checksum or has
  `STATSB_DONE` clear. That is a slot never written, a score older than this,
  a trainer's score, and a **seeded game's** - which files its score and
  deliberately keeps no record. An empty slot is all zeros, and the checksum
  of zeros is the seed, so it never passes.
* **A cartridge with no RAM keeps none.** RECORDS still shows the last game.
* **A damaged high score slot and its records can disagree**: the slot comes
  back empty (ADR 0015) and its three records stay. They are overwritten as
  scores are set.
* **B-type has no records**: it has no stats.
* The row is not in Tolstoj's layout. It is written into the empty rows under
  TRAINING at init, row 29.
* The name shown is read from the high score table, live or parked (ADR 0014).
  Characters outside the font are blanked: this screen has the menu's tileset.
* The cartridge is opened for one record at a time, including the 138 writes
  that empty them.
