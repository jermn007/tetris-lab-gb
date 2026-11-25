#!/usr/bin/env python3
"""Remembered settings: level, hearts, music, and the last name typed.

    .venv/bin/python tests/test_settings.py

The cartridge comes back on the way it was left (src/lab/settings.asm). These
leave it one way, switch it off, and look at what the next session finds.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from tools.emu import (Tetris, sym, hATypeLevel, hIsHardMode,        # noqa: E402
                       GS_IN_GAME_MAIN, GS_A_TYPE_SELECTION_MAIN)
import test_stats as game                                             # noqa: E402
from test_records import play                                         # noqa: E402

ROM = game.ROM
hMusicType = 0xFFC1
MUSIC_A, MUSIC_B = 0x1C, 0x1D
MODE_MUSIC = 6
GS_NAME_ENTRY = 0x15
SETTINGS, SIZE = 0x0006, 9                    # offsets into cartridge RAM
A, B, DOT = 0x0A, 0x0B, 0x60

wLabPickerLevel = sym("wLabPickerLevel")
wLabFocus = sym("wLabFocus")
wATypeHighScores = 0xD654
HISCORE_SIZEOF = 27


def name_of(t, level, place=0):
    at = wATypeHighScores + level * HISCORE_SIZEOF + 9 + place * 6
    return [t[at + i] for i in range(6)]


def to_name_entry(t, level, plays=(4,)):
    if t.state != GS_A_TYPE_SELECTION_MAIN:
        t.to_level_select()
    t.pb.memory[hATypeLevel] = level
    t.press("start")
    t.run_until_state(GS_IN_GAME_MAIN)
    t.tick(4)
    for n in plays:
        game.complete_rows(t, n)
        game.lock(t)
    game.top_out(t)
    t.tick(40)
    t.press("a")
    t.tick(10)
    t.press("a")
    t.run_until_state(GS_NAME_ENTRY)
    t.tick(30)


def left_with(level, hearts, music_presses=0):
    """A session that started one game those ways, then was switched off."""
    t = Tetris(ROM)
    t.to_menu()
    t.to_mode(MODE_MUSIC)
    for _ in range(music_presses):
        t.press("right")
    t.to_mode(0)                                 # TETRIS
    t.press("start")
    t.run_until_state(GS_A_TYPE_SELECTION_MAIN)
    t.tick(20)
    if hearts:
        t.press("select")
    t.pb.memory[hATypeLevel] = level
    t.press("start")
    t.run_until_state(GS_IN_GAME_MAIN)
    t.tick(30)
    return t.power_off()


# --- level, hearts, music -------------------------------------------------------

def test_a_cartridge_never_played_starts_as_it_always_did():
    with Tetris(ROM) as t:
        t.to_menu()
        assert (t[hATypeLevel], t[hIsHardMode], t[hMusicType]) == (0, 0, MUSIC_A)


def test_the_level_hearts_and_music_come_back():
    ram = left_with(7, hearts=True, music_presses=1)
    with Tetris(ROM, ram=ram) as t:
        t.to_menu()
        assert (t[hATypeLevel], t[hIsHardMode], t[hMusicType]) == (7, 1, MUSIC_B)


def test_a_letter_level_comes_back_in_the_picker():
    ram = left_with(15, hearts=False)
    with Tetris(ROM, ram=ram) as t:
        t.to_level_select()
        assert t[wLabFocus] == 1 and t[wLabPickerLevel] == 15, (
            t[wLabFocus], t[wLabPickerLevel])
        t.press("start")
        t.run_until_state(GS_IN_GAME_MAIN)
        assert t[hATypeLevel] == 15


def test_the_heart_table_comes_back_with_the_hearts():
    t = Tetris(ROM)
    final = play(t, 7, plays=(4,), hearts=True)
    with Tetris(ROM, ram=t.power_off()) as t:
        t.to_title()
        t.tick(20)
        t.press("start")
        t.run_until_state(0x0E)
        t.tick(20)
        t.to_mode(0)
        t.press("start")
        t.run_until_state(GS_A_TYPE_SELECTION_MAIN)
        t.tick(30)
        assert t[hIsHardMode] == 1
        top = wATypeHighScores + 7 * HISCORE_SIZEOF
        assert game.unbcd([t[top + i] for i in range(3)]) == final, "plain table is live"
        assert t[0x9800 + 4 * 32 + 14] == 0x27, "no heart on the level select"


def test_they_survive_a_soft_reset_too():
    with Tetris(ROM) as t:
        t.start_game_at(7, hearts=True)
        t.tick(30)
        t.pb.memory[0xFFE1] = 0x0D               # game over, then out to a menu
        t.run_until_state(0x04)
        t.tick(40)
        t.press("a")
        t.tick(10)
        t.press("a")
        t.run_until_state(GS_A_TYPE_SELECTION_MAIN)
        t.tick(30)
        t.hold("a", "b", "select", "start")
        t.tick(6)
        t.release("a", "b", "select", "start")
        t.run_until_state(0x07, limit=600)
        t.tick(30)
        assert (t[hATypeLevel], t[hIsHardMode]) == (7, 1), (t[hATypeLevel], t[hIsHardMode])


def test_looking_without_playing_changes_nothing():
    ram = left_with(7, hearts=True)
    t = Tetris(ROM, ram=ram)
    t.to_level_select(hearts=False)              # hearts off, cursor moved, no game
    t.press("left")
    t.tick(10)
    assert bytes(t.power_off()[SETTINGS:SETTINGS + SIZE + 1]) == \
        bytes(ram[SETTINGS:SETTINGS + SIZE + 1])


def test_settings_that_do_not_add_up_are_not_used():
    ram = bytearray(left_with(7, hearts=True, music_presses=1))
    for damage in ((0, 0x01), (2, 0x40)):        # the level; the music
        bad = bytearray(ram)
        bad[SETTINGS + damage[0]] ^= damage[1]
        with Tetris(ROM, ram=bytes(bad)) as t:
            t.to_menu()
            assert (t[hATypeLevel], t[hIsHardMode], t[hMusicType]) == (0, 0, MUSIC_A), damage


def test_a_level_that_cannot_be_is_not_used_even_if_it_adds_up():
    ram = bytearray(left_with(7, hearts=False))
    block = bytearray(ram[SETTINGS:SETTINGS + SIZE])
    block[0] = 40
    ram[SETTINGS:SETTINGS + SIZE] = block
    ram[SETTINGS + SIZE] = (0x5A + sum(block)) & 0xFF
    with Tetris(ROM, ram=bytes(ram)) as t:
        t.to_menu()
        assert t[hATypeLevel] == 0, t[hATypeLevel]


# --- the name ---------------------------------------------------------------------

def test_the_first_name_starts_the_way_the_original_does():
    with Tetris(ROM) as t:
        to_name_entry(t, 5)
        assert name_of(t, 5) == [A, DOT, DOT, DOT, DOT, DOT], name_of(t, 5)


def test_the_last_name_typed_is_offered_and_start_signs_with_it():
    t = Tetris(ROM)
    to_name_entry(t, 5)
    t.press("up")                                # B
    t.press("a")
    t.press("up")                                # BB
    t.press("start")
    t.run_until_state(GS_A_TYPE_SELECTION_MAIN)
    t.tick(30)
    typed = name_of(t, 5)
    assert typed[:2] == [B, B], typed

    with Tetris(ROM, ram=t.power_off()) as t:
        to_name_entry(t, 6)
        assert name_of(t, 6) == typed, f"offered {name_of(t, 6)}"
        row = [t[0x9800 + 0x1A4 + i] for i in range(6)]
        t.tick(8)
        row2 = [t[0x9800 + 0x1A4 + i] for i in range(6)]
        assert row[1:] == typed[1:] and row2[1:] == typed[1:], (row, row2, typed)
        t.press("start")
        t.run_until_state(GS_A_TYPE_SELECTION_MAIN)
        t.tick(30)
        assert name_of(t, 6) == typed


def test_the_offered_name_goes_on_the_right_row():
    t = Tetris(ROM)
    to_name_entry(t, 5, plays=(4,))
    t.press("up")
    t.press("start")
    t.run_until_state(GS_A_TYPE_SELECTION_MAIN)
    t.tick(30)
    to_name_entry(t, 5, plays=(1,))              # second place
    assert name_of(t, 5, 1)[0] == B, name_of(t, 5, 1)
    assert t[0x9800 + 0x1C4] in (B, 0x2F), f"${t[0x9800 + 0x1C4]:02X}"
    assert name_of(t, 5, 0)[0] == B and t[0x9800 + 0x1A4] == B
    t.close()


def test_typing_over_the_offered_name_still_works():
    t = Tetris(ROM)
    to_name_entry(t, 5)
    t.press("up")
    t.press("start")
    t.run_until_state(GS_A_TYPE_SELECTION_MAIN)
    t.tick(30)
    to_name_entry(t, 6)
    t.press("down")                              # B back to A
    t.press("start")
    t.run_until_state(GS_A_TYPE_SELECTION_MAIN)
    t.tick(30)
    assert name_of(t, 6)[0] == A, name_of(t, 6)
    t.close()


def test_cartridge_ram_is_closed_after_every_write():
    with Tetris(ROM) as t:
        t.start_game_at(5)
        for _ in range(30):
            t.tick()
            assert t[0xA000] == 0xFF, "open after a game started"


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
