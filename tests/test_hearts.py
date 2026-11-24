#!/usr/bin/env python3
"""Heart games keep their own A-type high scores.

    .venv/bin/python tests/test_hearts.py

A heart game at level 9 falls at level 19's speed, so its scores and a plain
game's are not the same contest. Each has its own table, and the level select
shows the one for hearts as they are set: Select changes both at once.

The original files, names and draws from one table and is not told there are
two. The table not in use is parked, and exchanged with the live one whenever
hearts change (ADR 0014) - so these tests assert on what is filed where and on
what the player is shown, not on which copy holds it.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.emu import Tetris, sym, hATypeLevel, hIsHardMode  # noqa: E402

ROM = "build/tetrislab.gb"

wScoreBCD = 0xC0A0
hGameState = 0xFFE1
wATypeHighScores = sym("wATypeHighScores")
wLabHiScoreMillions = sym("wLabHiScoreMillions")
wLabOtherHighScores = sym("wLabOtherHighScores")
wLabPickerLevel = sym("wLabPickerLevel")

HISCORE_SIZEOF = 27
GS_A_TYPE_SELECTION_INIT = 0x10
GS_A_TYPE_SELECTION_MAIN = 0x11
GS_ENTERING_HIGH_SCORE = 0x15
LEVEL = 9

# The first of the three dotted rows; its score is the last six cells.
ROW_VRAM = 0x9800 + 13 * 32 + 4
DOT = 0x24


def bcd(n):
    d = f"{n:06d}"
    return [int(d[4:6], 16), int(d[2:4], 16), int(d[0:2], 16)]


def top(t, level=LEVEL, base=wATypeHighScores):
    """The best score in a table's slot for `level`, as a whole number."""
    b = base + level * HISCORE_SIZEOF
    return int(f"{t[b + 2]:02x}{t[b + 1]:02x}{t[b]:02x}")


def shown(t):
    """The best score as the level select draws it, leading blanks dropped."""
    cells = [t[ROW_VRAM + 8 + i] for i in range(6)]
    digits = "".join(str(c) for c in cells if c <= 9)
    return int(digits) if digits else 0


def finish_game(t, score):
    """End the running game worth `score` and accept the name it asks for."""
    for j, byte in enumerate(bcd(score)):
        t.pb.memory[wScoreBCD + j] = byte
    t.pb.memory[hGameState] = GS_A_TYPE_SELECTION_INIT
    t.tick(120)
    assert t.state == GS_ENTERING_HIGH_SCORE, f"did not place: ${t.state:02X}"
    t.press("start")
    t.tick(30)
    assert t.state == GS_A_TYPE_SELECTION_MAIN, f"${t.state:02X}"


def played(score, hearts):
    t = Tetris(ROM)
    t.start_game_at(LEVEL, hearts=hearts)
    t.tick(120)
    finish_game(t, score)
    return t


def toggle_hearts(t):
    t.press("select")
    t.tick(40)


def test_a_heart_score_is_not_a_plain_score():
    with played(123400, hearts=True) as t:
        assert t[hIsHardMode] and shown(t) == 123400, shown(t)

        toggle_hearts(t)
        assert not t[hIsHardMode]
        assert top(t) == 0, f"a heart game is in the plain table: {top(t)}"
        assert shown(t) == 0, f"and on screen with hearts off: {shown(t)}"


def test_a_plain_score_is_not_a_heart_score():
    with played(123400, hearts=False) as t:
        toggle_hearts(t)
        assert t[hIsHardMode]
        assert top(t) == 0, f"a plain game is in the heart table: {top(t)}"
        assert shown(t) == 0, f"and on screen with hearts on: {shown(t)}"


def test_select_brings_each_table_back():
    """Both survive any number of changes, and the panel follows every one."""
    with played(123400, hearts=True) as t:
        for expect in (0, 123400, 0, 123400):
            toggle_hearts(t)
            assert (top(t), shown(t)) == (expect, expect), (
                f"hearts {t[hIsHardMode]}: table {top(t)}, screen {shown(t)}, "
                f"expected {expect}"
            )


def test_each_table_ranks_only_its_own_games():
    """A plain 500 000 must not push a heart 100 000 off the top of its table."""
    with played(100000, hearts=True) as t:
        toggle_hearts(t)                         # hearts off
        t.pb.memory[hATypeLevel] = LEVEL
        t.press("start")
        t.run_until_state(0x00)
        t.tick(120)
        finish_game(t, 500000)
        assert shown(t) == 500000, shown(t)

        toggle_hearts(t)
        assert shown(t) == 100000, f"the heart table changed: {shown(t)}"


def test_the_name_is_kept_with_its_table():
    """Names live in the same slot as their scores, and move with them."""
    with played(123400, hearts=True) as t:
        name = wATypeHighScores + LEVEL * HISCORE_SIZEOF + 9
        t.pb.memory[name] = 0x0A                 # "A" as the first letter
        toggle_hearts(t)
        assert t[name] != 0x0A, "the heart name stayed in the plain table"
        toggle_hearts(t)
        assert t[name] == 0x0A, "the heart name did not come back"


def test_a_soft_reset_does_not_cross_the_tables():
    """The soft reset clears hearts - they are HRAM - and leaves the tables in
    WRAM. Whichever table was live must still be the heart one afterwards."""
    with played(123400, hearts=True) as t:
        t.hold("a", "b", "select", "start")
        t.tick(6)
        t.release("a", "b", "select", "start")
        t.run_until_state(0x07, limit=600)

        t.tick(20)
        t.press("start")
        t.run_until_state(0x0E)
        t.tick(20)
        t.to_mode(0)
        t.press("start")
        t.run_until_state(GS_A_TYPE_SELECTION_MAIN)
        t.tick(40)

        if t[hIsHardMode]:
            toggle_hearts(t)
        t.pb.memory[hATypeLevel] = LEVEL
        t.press("left")                          # make the panel repaint
        t.press("right")
        t.tick(40)
        assert top(t) == 0, f"hearts off, but the heart score is live: {top(t)}"

        toggle_hearts(t)
        assert top(t) == 123400, f"the heart score was lost: {top(t)}"


def test_hearts_forced_off_at_l_shows_the_plain_table():
    """L and M cannot be played with hearts, so the picker clears them on the
    way up. The table has to follow, or L would show - and file into - the
    heart table with no heart on screen."""
    with Tetris(ROM) as t:
        t.to_level_select(hearts=True)
        slot = 21 * HISCORE_SIZEOF
        for j, byte in enumerate(bcd(777000)):
            t.pb.memory[wLabOtherHighScores + slot + j] = byte   # plain L
            t.pb.memory[wATypeHighScores + slot + j] = 0         # heart L

        t.pb.memory[hATypeLevel] = 9
        t.press("right")                         # into the level field, at A
        for _ in range(11):                      # A -> L
            t.press("up")
        t.tick(40)

        assert t[wLabPickerLevel] == 21, t[wLabPickerLevel]
        assert not t[hIsHardMode], "hearts are still on at L"
        assert top(t, 21) == 777000, f"L is not on the plain table: {top(t, 21)}"
        assert shown(t) == 777000, f"and the panel does not show it: {shown(t)}"


def test_the_heart_is_on_screen_while_the_name_is_typed():
    """Reported from an EverDrive. The heart is drawn by the level select's own
    first frame, and a game that places goes to the name entry instead - so the
    one screen that files a heart score did not say it was one."""
    HEART_CELL = 0x9800 + 4 * 32 + 14
    TILE_HEART = 0x27
    for hearts in (True, False):
        with Tetris(ROM) as t:
            t.start_game_at(LEVEL, hearts=hearts)
            t.tick(120)
            for j, byte in enumerate(bcd(123400)):
                t.pb.memory[wScoreBCD + j] = byte
            t.pb.memory[hGameState] = GS_A_TYPE_SELECTION_INIT
            t.tick(120)
            assert t.state == GS_ENTERING_HIGH_SCORE, f"${t.state:02X}"
            assert (t[HEART_CELL] == TILE_HEART) == hearts, (
                f"hearts {hearts}: the cell holds ${t[HEART_CELL]:02X}"
            )


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("test_")]

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
