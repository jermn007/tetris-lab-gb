#!/usr/bin/env python3
"""Saved records, and the RECORDS screen that reads them back.

    .venv/bin/python tests/test_records.py

Every A-type high score keeps the record of the game that set it (ADR 0018).
These play games to their end, file them the way a player does, and read the
RECORDS screen as text - before and after the power goes off.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from tools.emu import (Tetris, sym, hATypeLevel, GS_IN_GAME_MAIN,     # noqa: E402
                       GS_GAME_TYPE_MAIN, GS_A_TYPE_SELECTION_MAIN)
import test_stats as game                                             # noqa: E402
from test_stats_screen import page, lines, open_stats                 # noqa: E402

ROM = game.ROM
MODE_RECORDS = 7
GS_NAME_ENTRY = 0x15
RECORDS, SLOT, PER_TABLE = 0x0D00, 34, 69     # offsets into cartridge RAM
MARK = 0x0005
FONT = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ.-"

wLabMode = sym("wLabMode")
wLabSeedLo = sym("wLabSeedLo")
wLabRecordsOpen = sym("wLabRecordsOpen")
wATypeHighScores = 0xD654
HISCORE_SIZEOF = 27


def play(t, level, plays=(), hearts=False, seed=0):
    """A whole game from the level select, filed, and back on the level select.
    Returns the final score."""
    if t.state != GS_A_TYPE_SELECTION_MAIN:
        t.to_level_select(hearts=hearts)
    t.pb.memory[wLabSeedLo] = seed
    t.pb.memory[hATypeLevel] = level
    t.press("start")
    t.run_until_state(GS_IN_GAME_MAIN)
    t.tick(4)
    for n in plays:
        game.complete_rows(t, n)
        game.lock(t)
    game.top_out(t)
    final = game.score(t)
    open_stats(t)
    t.press("a")
    t.run_until(lambda: t.state in (GS_NAME_ENTRY, GS_A_TYPE_SELECTION_MAIN),
                what="the name entry or the level select")
    if t.state == GS_NAME_ENTRY:
        t.tick(30)
        t.press("start")
        t.run_until_state(GS_A_TYPE_SELECTION_MAIN)
    t.tick(30)
    return final


def to_records(t):
    if t.state == GS_A_TYPE_SELECTION_MAIN:
        t.press("b")
        t.run_until_state(GS_GAME_TYPE_MAIN)
        t.tick(20)
    t.to_mode(MODE_RECORDS)
    t.press("a")
    t.tick(10)
    assert t[wLabRecordsOpen], "RECORDS did not open"
    return t


def header(t):
    return page(t)[0].split()


def show(t, level, entry, hearts=False):
    """Walk the open screen to a table entry and read it."""
    for _ in range(4):
        if header(t)[-1:] == [f"NO.{entry}"]:
            break
        t.press("down")
        t.tick(6)
    want = FONT[level]
    for _ in range(24):
        if header(t)[1] == want:
            break
        t.press("right")
        t.tick(6)
    if ("HEART" in header(t)) != hearts:
        t.press("select")
        t.tick(6)
    h = header(t)
    assert (h[:2] == ["LEVEL", want] and h[-1] == f"NO.{entry}"
            and ("HEART" in h) == hearts), page(t)
    return lines(t)


def switched_on(ram):
    t = Tetris(ROM, ram=ram)
    t.to_menu()
    return to_records(t)


# --- the row and the screen ---------------------------------------------------

def test_records_is_a_row_of_the_menu():
    with Tetris(ROM) as t:
        t.to_menu()
        t.to_mode(MODE_RECORDS)
        t.tick(10)
        row = "".join(FONT[t[0x9800 + 29 * 32 + c]] for c in range(2, 9))
        assert row == "RECORDS", row
        t.press("start")
        t.tick(10)
        assert t[wLabRecordsOpen] and t.state == GS_GAME_TYPE_MAIN


def test_with_nothing_played_it_opens_on_an_empty_table():
    with Tetris(ROM) as t:
        t.to_menu()
        to_records(t)
        assert lines(t) == [["LEVEL", "0", "NO.1"], ["NO", "RECORD"]], page(t)


def test_b_goes_back_to_the_menu_where_it_was():
    with Tetris(ROM) as t:
        t.to_menu()
        to_records(t)
        t.press("b")
        t.tick(20)
        assert not t[wLabRecordsOpen] and t.state == GS_GAME_TYPE_MAIN
        assert t[wLabMode] == MODE_RECORDS
        assert t[0xFF40] & 0x80, "the LCD is off"
        assert t[0xFF42] == (29 - 15) * 8, f"scrolled to {t[0xFF42]}"
        t.press("up")
        assert t[wLabMode] != MODE_RECORDS, "the menu does not answer"


def test_the_screen_is_not_scrolled_with_the_menu():
    with Tetris(ROM) as t:
        t.to_menu()
        to_records(t)
        assert t[0xFF42] == 0, f"SCY is {t[0xFF42]}"


def test_a_reset_from_the_screen_does_not_leave_it_up():
    with Tetris(ROM) as t:
        t.to_menu()
        to_records(t)
        t.hold("a", "b", "select", "start")
        t.tick(6)
        t.release("a", "b", "select", "start")
        t.run_until_state(0x07, limit=600)
        t.tick(20)
        t.press("start")
        t.run_until_state(GS_GAME_TYPE_MAIN)
        t.tick(20)
        assert not t[wLabRecordsOpen]
        t.press("up")
        assert t[wLabMode] != MODE_RECORDS, "the menu does not answer"


def test_the_last_game_is_there_whether_or_not_it_placed():
    with Tetris(ROM) as t:
        t.to_level_select()
        for entry in range(3):                   # nothing beats these
            t.pb.memory[wATypeHighScores + 5 * HISCORE_SIZEOF + entry * 3 + 2] = 0x99
        final = play(t, 5, plays=(4, 1))
        to_records(t)
        rows = lines(t)
        assert rows[0] == ["LAST", "GAME"], page(t)
        assert ["END", str(final), "5"] in rows and ["TETRISES", "1"] in rows, page(t)
        assert show(t, 5, 1)[-1] == ["NO", "RECORD"], page(t)


def test_up_and_down_walk_the_last_game_and_the_three_places():
    with Tetris(ROM) as t:
        play(t, 5, plays=(1,))
        to_records(t)
        seen = []
        for _ in range(5):
            seen.append(header(t)[-1] if page(t)[0] else "LAST")
            t.press("down")
            t.tick(6)
        assert seen == ["LAST", "NO.1", "NO.2", "NO.3", "LAST"], seen
        for _ in range(2):                       # back past the last game
            t.press("up")
            t.tick(6)
        assert header(t)[-1] == "NO.3", page(t)


def test_left_and_right_walk_every_level_and_wrap():
    with Tetris(ROM) as t:
        t.to_menu()
        to_records(t)
        t.press("left")
        t.tick(6)
        assert header(t)[:2] == ["LEVEL", "M"], page(t)
        t.press("right")
        t.tick(6)
        assert header(t)[:2] == ["LEVEL", "0"], page(t)


# --- what is kept --------------------------------------------------------------

def test_a_score_that_places_keeps_its_record():
    with Tetris(ROM) as t:
        final = play(t, 5, plays=(4, 2))
        to_records(t)
        rows = show(t, 5, 1)
        assert ["START", "5", "END", "5"] in rows, page(t)
        assert ["END", str(final), "6"] in rows, page(t)
        assert ["DOUBLES", "1"] in rows and ["TETRISES", "1"] in rows, page(t)
        assert ["TETRIS", "RATE", "66"] in rows, page(t)


def test_the_name_is_shown_with_it():
    with Tetris(ROM) as t:
        play(t, 5, plays=(4,))
        name = [t[wATypeHighScores + 5 * HISCORE_SIZEOF + 9 + i] for i in range(6)]
        typed = "".join(FONT[c] if c < len(FONT) else " " for c in name).split()
        assert typed, f"harness: no name in {name}"
        to_records(t)
        show(t, 5, 1)
        assert page(t)[1].split() == typed, page(t)


def test_it_survives_the_power_going_off():
    t = Tetris(ROM)
    final = play(t, 5, plays=(4, 3))
    with switched_on(t.power_off()) as t:
        assert lines(t)[0] == ["LEVEL", "0", "NO.1"], "there is no last game now"
        rows = show(t, 5, 1)
        assert ["END", str(final), "7"] in rows, page(t)
        assert ["TRIPLES", "1"] in rows and ["TETRISES", "1"] in rows, page(t)


def test_a_better_score_moves_the_record_down_with_its_score():
    t = Tetris(ROM)
    first = play(t, 5, plays=(1,))
    second = play(t, 5, plays=(4,))
    third = play(t, 5, plays=(2,))
    assert second > third > first, (first, second, third)
    with switched_on(t.power_off()) as t:
        for entry, score, clear, n in ((1, second, "TETRISES", 4), (2, third, "DOUBLES", 2),
                                       (3, first, "SINGLES", 1)):
            rows = show(t, 5, entry)
            assert [clear, "1"] in rows, f"NO.{entry}:\n" + "\n".join(page(t))
            assert ["END", str(score), str(n)] in rows, page(t)


def test_a_fourth_score_pushes_the_last_record_off():
    with Tetris(ROM) as t:
        for plays in ((1,), (2,), (3,), (4,)):
            play(t, 5, plays=plays)
        to_records(t)
        assert ["TETRISES", "1"] in show(t, 5, 1), page(t)
        assert ["TRIPLES", "1"] in show(t, 5, 2), page(t)
        assert ["DOUBLES", "1"] in show(t, 5, 3), page(t)


def test_heart_games_keep_theirs_apart():
    t = Tetris(ROM)
    play(t, 5, plays=(4,), hearts=True)
    with switched_on(t.power_off()) as t:
        assert show(t, 5, 1)[-1] == ["NO", "RECORD"], page(t)
        rows = show(t, 5, 1, hearts=True)
        assert ["TETRISES", "1"] in rows and ["HEARTS"] in rows, page(t)


def test_a_letter_level_is_filed_under_its_letter():
    t = Tetris(ROM)
    play(t, 20, plays=(4,))
    with switched_on(t.power_off()) as t:
        rows = show(t, 20, 1)                    # K
        assert ["START", "20", "END", "20"] in rows, page(t)
        assert show(t, 9, 1)[-1] == ["NO", "RECORD"], page(t)


def test_a_seeded_game_files_its_score_and_no_record():
    with Tetris(ROM) as t:
        final = play(t, 5, plays=(4,), seed=0x5A)
        top = [t[wATypeHighScores + 5 * HISCORE_SIZEOF + i] for i in range(3)]
        assert final and int("".join(f"{b:02x}" for b in reversed(top))) == final, top
        to_records(t)
        assert ["SEEDED"] in lines(t), "the last game is still shown"
        assert show(t, 5, 1)[-1] == ["NO", "RECORD"], page(t)


def test_a_seeded_score_still_moves_the_records_under_it():
    with Tetris(ROM) as t:
        play(t, 5, plays=(1,))
        play(t, 5, plays=(4,), seed=0x5A)
        to_records(t)
        assert show(t, 5, 1)[-1] == ["NO", "RECORD"], page(t)
        assert ["SINGLES", "1"] in show(t, 5, 2), page(t)


def test_a_score_with_no_record_takes_none_down_with_it():
    """The place under a seeded score had a record, and must not keep it."""
    with Tetris(ROM) as t:
        play(t, 5, plays=(1,))
        play(t, 5, plays=(2,), seed=0x5A)
        play(t, 5, plays=(4,))
        to_records(t)
        assert ["TETRISES", "1"] in show(t, 5, 1), page(t)
        assert show(t, 5, 2)[-1] == ["NO", "RECORD"], page(t)
        assert ["SINGLES", "1"] in show(t, 5, 3), page(t)


def test_filing_writes_nothing_outside_the_record_it_draws_from():
    with Tetris(ROM) as t:
        play(t, 5, plays=(1,), seed=0x5A)
        after = sym("wLabRecPos") + 1
        for a in range(after, after + 64):
            t.pb.memory[a] = 0xEE
        play(t, 5, plays=(4,))
        assert all(t[a] == 0xEE for a in range(after, after + 64)), "WRAM was written"


# --- what can go wrong ---------------------------------------------------------

def test_a_damaged_record_is_no_record_and_costs_no_other():
    t = Tetris(ROM)
    play(t, 5, plays=(1,))
    play(t, 5, plays=(4,))
    ram = bytearray(t.power_off())
    ram[RECORDS + (5 * 3) * SLOT + 9] ^= 0x40
    with switched_on(bytes(ram)) as t:
        assert show(t, 5, 1)[-1] == ["NO", "RECORD"], page(t)
        assert ["SINGLES", "1"] in show(t, 5, 2), page(t)


def test_a_save_from_before_records_keeps_its_scores_and_starts_none():
    """Whatever was in that part of the cartridge is not a record, however
    well it happens to add up."""
    t = Tetris(ROM)
    play(t, 5, plays=(4,))
    ram = bytearray(t.power_off())
    ram[MARK] = 0xFF
    with switched_on(bytes(ram)) as t:
        assert show(t, 5, 1)[-1] == ["NO", "RECORD"], page(t)
        best = wATypeHighScores + 5 * HISCORE_SIZEOF
        assert t[best] | t[best + 1] | t[best + 2], "the score went too"
        again = bytes(t.power_off())
    assert again[MARK] == 1
    assert not any(again[RECORDS:RECORDS + 2 * PER_TABLE * SLOT]), "not emptied"


def test_nothing_but_records_is_written_past_them():
    t = Tetris(ROM)
    play(t, 22, plays=(4,), hearts=True)         # the last slot's level
    ram = t.power_off()
    end = RECORDS + 2 * PER_TABLE * SLOT
    assert set(ram[end:0x2000]) <= {0xFF}, "the space kept for totals was written"
    assert any(ram[RECORDS + (PER_TABLE + 22 * 3) * SLOT:][:SLOT])


def test_cartridge_ram_is_closed_while_looking():
    with Tetris(ROM) as t:
        play(t, 5, plays=(4,))
        to_records(t)
        for button in ("down", "down", "right", "select", "up", "b"):
            t.press(button)
            for _ in range(8):
                t.tick()
                assert t[0xA000] == 0xFF, f"open after {button}"


def test_nothing_on_the_screen_is_outside_the_font():
    with Tetris(ROM) as t:
        play(t, 9, plays=(4, 3, 2, 1), hearts=True)
        to_records(t)
        for _ in range(4):
            assert not any("#" in row for row in page(t)), "\n".join(page(t))
            t.press("down")
            t.tick(6)


TESTS = [v for k, v in sorted(globals().items())
         if k.startswith("test_") and callable(v)]

if __name__ == "__main__":
    failures = 0
    for fn in TESTS:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL  {fn.__name__}: {exc}")
    print(f"\n{len(TESTS) - failures}/{len(TESTS)} passed")
    raise SystemExit(1 if failures else 0)
