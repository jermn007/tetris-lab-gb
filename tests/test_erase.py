#!/usr/bin/env python3
"""Erasing the save: Up+B on the title screen, then YES.

    .venv/bin/python tests/test_erase.py

The question must be hard to answer wrongly and the answer must be complete
(docs/decisions/0020). These ask it, back out of it every way there is, and
then say yes and look for anything left.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from tools.emu import (Tetris, sym, hATypeLevel, hIsHardMode,        # noqa: E402
                       GS_TITLE_SCREEN_MAIN, GS_GAME_TYPE_MAIN)
import test_stats as game                                             # noqa: E402
from test_stats_screen import page, lines                             # noqa: E402
from test_records import play, to_records, show                       # noqa: E402

ROM = game.ROM
wLabEraseOpen = sym("wLabEraseOpen")
wATypeHighScores, wBTypeHighScores = 0xD654, 0xD000
HISCORE_SIZEOF = 27
ASKED = [["ERASE", "ALL", "SAVES"], ["-", "NO"], ["YES"],
         ["A", "SELECT", "B", "CANCEL"]]


def saved():
    """A cartridge with a heart score, its record, and settings on it."""
    t = Tetris(ROM)
    play(t, 7, plays=(4,), hearts=True)
    return t.power_off()


def ask(t):
    if t.state != GS_TITLE_SCREEN_MAIN:
        t.to_title()
        t.tick(20)
    t.hold("up")
    t.tick(2)
    t.hold("b")
    t.tick(4)
    t.release("up", "b")
    t.tick(6)
    return t


def has_score(t):
    """Anything at all in the B-type table or either A-type one."""
    tables = list(range(wBTypeHighScores, sym("wLabState"))) +         list(range(sym("wLabHiScoreMillions"), sym("wLabTablesAreHearts"))) +         list(range(sym("wLabOtherHighScores"), sym("wLabSaveLoaded")))
    return any(t[a] for a in tables)


def rebooted(t):
    """Wait out the reboot the erase ends in."""
    t.run_until(lambda: t.state != GS_TITLE_SCREEN_MAIN, limit=600, what="the reboot")
    t.run_until_state(GS_TITLE_SCREEN_MAIN, limit=600)
    t.tick(30)


# --- asking --------------------------------------------------------------------

def test_up_and_b_on_the_title_screen_ask_and_the_cursor_is_on_no():
    with Tetris(ROM) as t:
        ask(t)
        assert t[wLabEraseOpen] and t.state == GS_TITLE_SCREEN_MAIN
        assert lines(t) == ASKED, "\n".join(page(t))


def test_either_button_alone_asks_nothing():
    for button in ("up", "b"):
        with Tetris(ROM) as t:
            t.to_title()
            t.tick(20)
            t.press(button, hold=6)
            t.tick(6)
            assert not t[wLabEraseOpen], button


def test_it_is_only_asked_on_the_title_screen():
    with Tetris(ROM) as t:
        t.to_menu()
        t.hold("up")
        t.tick(2)
        t.hold("b")
        t.tick(4)
        t.release("up", "b")
        t.tick(6)
        assert not t[wLabEraseOpen] and t.state == GS_GAME_TYPE_MAIN


# --- backing out ---------------------------------------------------------------

def test_every_way_out_but_yes_erases_nothing():
    ram = saved()
    for way in (("a",), ("start",), ("b",), ("down", "b"), ("down", "up", "a"),
                ("select", "a"), ("left", "right", "start")):
        with Tetris(ROM, ram=ram) as t:
            ask(t)
            for button in way:
                t.press(button)
                t.tick(4)
            t.tick(20)
            assert not t[wLabEraseOpen], f"{way}: still asking"
            assert t.state == GS_TITLE_SCREEN_MAIN, f"{way}: ${t.state:02X}"
            assert has_score(t), f"{way}: erased"
            assert bytes(t.power_off()) == bytes(ram), f"{way}: the cartridge changed"


def test_the_title_screen_is_back_and_works():
    with Tetris(ROM) as t:
        ask(t)
        t.press("b")
        t.tick(20)
        assert lines(t) != ASKED and t[0xFF40] & 0x80
        t.press("start")
        t.run_until_state(GS_GAME_TYPE_MAIN)


def test_the_reset_combination_does_not_answer_yes():
    """Two of its four buttons are answers here, and it is pressed by habit."""
    ram = saved()
    for order in (("down", "a", "b", "select", "start"),
                  ("down", "start", "select", "b", "a")):
        with Tetris(ROM, ram=ram) as t:
            ask(t)
            t.press(order[0])
            t.tick(4)
            held = []
            for button in ("a", "b", "select", "start"):
                held.append(button)
            t.hold(*held)
            t.tick(6)
            t.release(*held)
            t.run_until_state(GS_TITLE_SCREEN_MAIN, limit=600)
            t.tick(30)
            assert has_score(t), f"{order}: erased"
            assert not t[wLabEraseOpen]


# --- yes -----------------------------------------------------------------------

def test_yes_erases_scores_records_and_settings():
    t = Tetris(ROM, ram=saved())
    ask(t)
    t.press("down")
    t.tick(4)
    assert lines(t)[1:3] == [["NO"], ["-", "YES"]], "\n".join(page(t))
    t.hold("a")
    t.tick(1)
    t.release("a")
    rebooted(t)
    assert not t[wLabEraseOpen]
    assert not has_score(t), "a score is still in memory"
    assert (t[hATypeLevel], t[hIsHardMode]) == (0, 0), "the settings are still set"

    ram = t.power_off()
    blank = Tetris(ROM)
    blank.to_title()
    blank.tick(30)
    never_played = blank.power_off()
    assert bytes(ram) == bytes(never_played), "not the same as a cartridge never played"

    with Tetris(ROM, ram=ram) as t:
        t.to_menu()
        assert not has_score(t)
        to_records(t)
        assert show(t, 7, 1, hearts=True)[-1] == ["NO", "RECORD"], page(t)


def test_the_game_plays_and_saves_again_afterwards():
    t = Tetris(ROM, ram=saved())
    ask(t)
    t.press("down")
    t.tick(4)
    t.hold("start")
    t.tick(1)
    t.release("start")
    rebooted(t)
    final = play(t, 3, plays=(4,))
    with Tetris(ROM, ram=t.power_off()) as t:
        t.to_menu()
        top = wATypeHighScores + 3 * HISCORE_SIZEOF
        assert game.unbcd([t[top + i] for i in range(3)]) == final


def test_cartridge_ram_is_closed_throughout():
    with Tetris(ROM, ram=saved()) as t:
        ask(t)
        for button in ("down", "up", "down"):
            t.press(button)
            for _ in range(8):
                t.tick()
                assert t[0xA000] == 0xFF, f"open after {button}"
        t.hold("a")                              # yes: a new save is written,
        t.tick(1)                                # a slot at a time
        t.release("a")
        rebooted(t)
        for _ in range(30):
            t.tick()
            assert t[0xA000] == 0xFF, "left open by the erase"


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
