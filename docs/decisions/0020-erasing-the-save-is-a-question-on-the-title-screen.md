# 20. Erasing the save is a question on the title screen

**Status:** accepted, 2026-11-24

## Context

A save that cannot be cleared is a cartridge you cannot lend. The one
combination players already press by habit is `A+B+Select+Start`, and an
erase must not be reachable from it.

## Decision

**`Up` and `B` together on the title screen open `ERASE ALL SAVES`, with the
cursor on `NO`.** `src/lab/erase.asm`.

| Press | Does |
| --- | --- |
| `Up` / `Down` | move between `NO` and `YES` |
| `A` or `Start` | choose the one the cursor is on |
| `B` | cancel |

The screen runs on the title's own state (`$07`) behind `wLabEraseOpen`: no
new state, no hook.

**Erasing is spoiling the header and rebooting.** `YES` zeroes the first byte
of `TLAB`, clears WRAM from the B-type table to the end of the Lab's state,
and jumps to `Reset`. `LabSaveBoot` then finds no save of ours and starts one
- tables, records and settings - which is the only code that knows how. The
result is byte for byte a cartridge that was never played.

## Consequences

* **The reset combination answers nothing here.** Two of its buttons are
  answers on this screen, so while all four are held the screen ignores
  input, and `Select` moves nothing.
* `Up` and `B` do nothing else on the title screen, so the combination costs
  no existing input. It is asked only there.
* The link ping stops while the question is up. A partner waits.
* `LabSaveBoot`'s fresh path now also empties the settings block, so settings
  left by a save of another version are not read either.
* The 172 bytes kept for lifetime totals are not touched: nothing is in them.
