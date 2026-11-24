# 15. High scores are mirrored to cartridge RAM, a slot at a time

**Status:** accepted, 2026-11-24

## Context

The cartridge has declared 8 KB of battery RAM since M0.5 and nothing used it:
every score was lost at power-off. `Begin2` clears `$D000-$DFFF` on a cold boot.

Moving the tables into cartridge RAM - what the one existing save hack does,
by repointing `$D000` and `$D654` at `$A000` and `$A654` - would mean the
original reads and writes it for whole screens at a time. That needs RAM left
open, a hook at every table reference, and has no answer for erased RAM.

## Decision

**WRAM stays the working copy; cartridge RAM mirrors it.** Nothing that files,
names or draws a score changes.

| When | What |
| --- | --- |
| First state of a cold boot | Read the save into WRAM, or start one if the header is not ours |
| Name entry begins | Write everything |
| Name entry ends | Write everything again, now with the name |

Layout, `src/lab/save.asm`:

| Range | Contents |
| --- | --- |
| `$A000-$A004` | `TLAB`, version. Written last. |
| `$A005-$A03F` | Reserved for settings |
| `$A040-$A308` | A-type, plain: 23 slots of 27 + 3 + 1 |
| `$A340-$A608` | A-type, hearts: the same |
| `$A640-$ACCF` | B-type: 60 slots of 27 + 1 |
| `$AD00-$BFFF` | Free |

A **slot** is one level's three entries as the original lays them out, plus
their seventh digits and a checksum. It is the unit a score changes and the
unit a power cut can damage, so one bad slot loads as empty and the rest of
the table is kept.

## Consequences

* **No hook.** Name entry was already routed through `LabDispatch`; it now
  calls the original handler itself so it is still there on the frame the name
  completes. That handler reaches nothing in bank 1.
* **RAM is opened for one slot and closed again**, never across a screen.
  `tests/test_save.py` reads `$A000` every frame of a game to prove it.
* **A write is everything, about two and a half frames.** Rewriting a byte
  with its own value risks nothing, and finding the one slot that changed means
  working back from the original's pointers. Menus only.
* **A soft reset does not read the save back.** WRAM survived and is newer.
  `wLabSaveLoaded` sits in the range `Begin2` clears, so it is zero once per
  power-on and that is the whole test.
* **The cartridge regions are named for their table, not for which is live**
  (ADR 0014): the walk checks `wLabTablesAreHearts` to pair them up.
* **A different version is started again, not migrated.** The first release
  with a second layout must add the migration and bump `SAVE_VERSION`.
* **No RAM, no harm.** A `--no-sram` cartridge reads `$FF` and drops writes,
  so it starts a save every boot and keeps scores for the session, as before.
* **The checksum is a sum, seeded** so that erased RAM - all `$00` or all
  `$FF` - never passes. It catches a torn write, not deliberate editing.
* Not done here: settings, and anything on real hardware.
