# 19. Settings are remembered from the last game started

**Status:** accepted, 2026-11-24

## Context

Level, hearts and music live in HRAM and the name in nobody's memory at all:
every power-on began at level 0, no hearts, A-type music and `A.....`.

## Decision

**Ten bytes at `$A006`: level, hearts, music, the last name typed, a checksum.
WRAM (`wLabSet*`) is the working copy.** `src/lab/settings.asm`.

| When | What |
| --- | --- |
| a game starts (`$0A`) | level, hearts and music are kept and written |
| a name entry finishes | the name is kept and written |
| every boot, cold or soft | the kept three go back into HRAM |
| a name entry begins | the kept name replaces `A.....`, in the table and on screen |

## Consequences

* **Only starting a game changes them.** Moving the cursor, toggling hearts or
  auditioning a song and switching off changes nothing.
* **A soft reset keeps them too.** It clears HRAM and leaves WRAM, so the same
  boot path puts them back. Before this a reset went back to level 0.
* **Start alone signs a score** with the offered name. Typing is the
  original's, untouched: `A` moves on and starts the next letter at `A`,
  whatever was offered there.
* Settings that fail the checksum, or hold a level, heart flag or music the
  game cannot have, are not used. Hearts above level 20 count as that
  (`LabLevelSelectPost`).
* The seed is not remembered: nobody asked, and a seed left on by accident
  costs records (ADR 0018).
* The test harness sets hearts to what a test asks for instead of toggling
  them from "off" (`tools/emu.py`).
