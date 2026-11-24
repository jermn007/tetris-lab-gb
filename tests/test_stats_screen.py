#!/usr/bin/env python3
"""The page a finished game ends on.

    .venv/bin/python tests/test_stats_screen.py

After the game over screen and before whatever the original does next, a
TETRIS game shows its record on one page (ADR 0017). tests/test_stats.py checks
the record; these check that the page says what the record holds, and that the
game still goes where it always went afterwards.

The page is read back off the background map as text, so every expectation is
what a player would read.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from tools.emu import (Tetris, sym, hATypeLevel, GS_IN_GAME_MAIN,     # noqa: E402
                       GS_A_TYPE_SELECTION_MAIN)
import test_stats as game                                             # noqa: E402
from test_stats import I, O, S, T, Z                                  # noqa: E402

ROM = game.ROM
FONT = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ.-"
BLANK = 0x2F
GS_LEVEL_ENDED, GS_NAME_ENTRY = 0x04, 0x15

wLabSeedLo = sym("wLabSeedLo")


def page(t):
    """The screen as text, a row a string. Anything not in the font is `#`."""
    rows = []
    for r in range(18):
        row = ""
        for c in range(20):
            v = t[0x9800 + r * 32 + c]
            row += FONT[v] if v < len(FONT) else " " if v == BLANK else "#"
        rows.append(row.rstrip())
    return rows


def lines(t):
    """The page without its blank rows, each row's words."""
    return [row.split() for row in page(t) if row]


def is_stats(t):
    return ["GAME", "STATS"] in lines(t)


def open_stats(t, button="a"):
    t.tick(40)
    t.press(button)
    t.tick(10)


def finished(level, hearts=False, plays=()):
    """A game played to its end. `plays` is rows to complete, one lock each."""
    t = game.started(level, hearts=hearts)
    for n in plays:
        game.complete_rows(t, n)
        game.lock(t)
    game.top_out(t)
    return t


# --- getting there, and leaving ---------------------------------------------

def test_the_game_over_screen_waits_for_a_press_as_it_always_did():
    with finished(5) as t:
        t.tick(200)
        assert t.state == GS_LEVEL_ENDED, f"${t.state:02X}"
        assert not is_stats(t), "the stats came up unasked"


def test_a_or_start_opens_the_page():
    for button in ("a", "start"):
        with finished(5) as t:
            open_stats(t, button)
            assert is_stats(t), f"{button}: {page(t)}"
            assert t.state == GS_LEVEL_ENDED, f"{button}: left for ${t.state:02X}"


def test_the_page_stays_until_the_next_press():
    with finished(5) as t:
        open_stats(t)
        before = page(t)
        t.tick(300)
        assert page(t) == before and t.state == GS_LEVEL_ENDED


def test_the_next_press_goes_to_the_name_entry_when_the_score_placed():
    with finished(5, plays=(4,)) as t:
        open_stats(t)
        t.press("a")
        t.run_until_state(GS_NAME_ENTRY)
        t.tick(30)
        assert not is_stats(t), "the stats are still on screen under the name"


def test_and_to_the_level_select_when_it_did_not():
    with finished(5) as t:                       # nothing scored, nothing to file
        game.set_score(t, 0)
        open_stats(t)
        t.press("start")
        t.run_until_state(GS_A_TYPE_SELECTION_MAIN)


def test_a_press_while_the_game_over_box_is_still_arriving_does_not_spoil_it():
    """The box is sent a row a frame, and the page is opened on top of it."""
    with finished(5) as t:
        t.press("a", hold=2, release=0)
        t.tick(4)
        assert is_stats(t), page(t)
        before = page(t)
        t.tick(60)
        assert page(t) == before, "the game over box drew over the page"


def test_the_restart_combination_still_restarts_from_the_page():
    with finished(5) as t:
        open_stats(t)
        t.hold("a", "b", "select", "start")
        t.tick(6)
        t.release("a", "b", "select", "start")
        t.run_until_state(GS_IN_GAME_MAIN)
        t.tick(30)
        assert not is_stats(t), "the page is still up in the new game"
        game.empty_board(t)
        game.lock(t)                             # and it plays
        assert game.word(t, game.PIECES) == 2, game.word(t, game.PIECES)


def test_the_next_game_gets_a_page_of_its_own():
    with finished(5, plays=(4,)) as t:
        open_stats(t)
        t.hold("a", "b", "select", "start")
        t.tick(6)
        t.release("a", "b", "select", "start")
        t.run_until_state(GS_IN_GAME_MAIN)
        t.tick(10)
        game.top_out(t)
        t.tick(100)
        assert not is_stats(t), "the second game skipped its game over screen"
        open_stats(t)
        assert ["TETRISES", "0"] in lines(t), page(t)


# --- what it says ------------------------------------------------------------

def test_the_page_says_what_the_game_was():
    """Level 9 with hearts, to level 11 on 117 lines: 12 of 21 lines in fours."""
    with game.started(9, hearts=True) as t:
        game.set_score(t, 50000)
        game.set_lines(t, 96)
        game.complete_rows(t, 4)
        game.lock(t, push=False)
        for n in (1, 2, 2, 3, 4, 4, 1):
            game.complete_rows(t, n)
            game.lock(t)
        dealt = [t[game.ACTIVE] & 0xFC]
        for piece in (T, O, S, Z, I):
            game.deal(t, piece)
            dealt.append(piece)
        game.top_out(t)
        final = game.score(t)
        drought = game.word(t, game.DROUGHT)
        assert drought >= 4, f"harness: drought {drought} from {dealt}"
        open_stats(t)

        assert lines(t) == [
            ["GAME", "STATS"],
            ["START", "9", "END", "11"],
            ["HEARTS"],
            ["SCORE", "LINES"],
            ["END", str(final), "117"],
            ["L10", "62000", "100"],
            ["SINGLES", "2"],
            ["DOUBLES", "2"],
            ["TRIPLES", "1"],
            ["TETRISES", "3"],
            ["TETRIS", "RATE", "57"],
            ["MAX", "DROUGHT", str(drought)],
        ], "\n".join(page(t))


def test_numbers_end_on_the_same_column():
    with finished(9, plays=(4, 4, 1)) as t:
        open_stats(t)
        ends = {len(row) for row in page(t)
                if row and row.split()[-1].isdigit() and not row.startswith(" START")}
        assert ends == {19}, f"right edges at {sorted(ends)}:\n" + "\n".join(page(t))


def test_a_level_that_was_not_reached_has_no_row():
    with finished(5, plays=(4,)) as t:
        open_stats(t)
        names = [row[0] for row in lines(t)]
        assert "L10" not in names and "L20" not in names, page(t)
        assert "END" in names


def test_level_20_alone_closes_up_under_the_final_row():
    with game.started(19) as t:
        game.set_score(t, 300000)
        game.set_lines(t, 197)
        game.complete_rows(t, 3)
        game.lock(t, push=False)
        game.top_out(t)
        open_stats(t)
        rows = page(t)
        end = next(i for i, row in enumerate(rows) if row.startswith(" END "))
        assert rows[end + 1].split() == ["L20", "306000", "200"], "\n".join(rows)


def test_both_levels_get_a_row_each():
    with game.started(9) as t:
        game.set_score(t, 50000)
        game.set_lines(t, 96)
        game.complete_rows(t, 4)
        game.lock(t, push=False)                 # level 10 on 100
        game.set_score(t, 300000)
        game.set_lines(t, 197)
        for level in range(11, 20):              # one level a clear, as it must be
            t.pb.memory[game.hLevel] = level
        game.complete_rows(t, 3)
        game.lock(t, push=False)                 # level 20 on 200
        assert t[game.hLevel] == 20, f"harness: level {t[game.hLevel]}"
        game.top_out(t)
        open_stats(t)
        rows = lines(t)
        assert ["L10", "62000", "100"] in rows, page(t)
        assert ["L20", "306000", "200"] in rows, page(t)
        assert rows.index(["L20", "306000", "200"]) == rows.index(["L10", "62000", "100"]) + 1


def test_a_score_past_a_million_shows_all_of_it():
    with game.started(19) as t:
        game.set_score(t, 995000)
        game.set_lines(t, 196)
        game.complete_rows(t, 4)
        game.lock(t, push=False)
        game.top_out(t)
        open_stats(t)
        assert ["L20", "1019000", "200"] in lines(t), page(t)
        assert ["END", str(game.checkpoint(t, game.FINAL)[0]), "200"] in lines(t), page(t)


def test_a_game_with_no_lines_is_nought_everywhere_and_not_a_divide_by_it():
    with finished(5) as t:
        open_stats(t)
        rows = lines(t)
        for name in ("SINGLES", "DOUBLES", "TRIPLES", "TETRISES"):
            assert [name, "0"] in rows, page(t)
        assert ["TETRIS", "RATE", "0"] in rows, page(t)


def test_the_tetris_rate_is_the_share_of_lines_that_came_in_fours():
    for plays, rate in (((4, 4, 4), 100), ((4, 1, 1, 1, 1), 50), ((4, 2), 66),
                        ((1, 2, 3), 0), ((4, 3, 3, 3, 3), 25)):
        with finished(0, plays=plays) as t:
            open_stats(t)
            assert ["TETRIS", "RATE", str(rate)] in lines(t), (
                f"{plays} should be {rate}:\n" + "\n".join(page(t))
            )


def test_hearts_and_a_seed_are_named_only_when_they_were_on():
    with finished(5) as t:
        open_stats(t)
        words = sum(lines(t), [])
        assert "HEARTS" not in words and "SEEDED" not in words, page(t)

    with Tetris(ROM) as t:
        t.to_level_select(hearts=True)
        t.pb.memory[wLabSeedLo] = 0x5A
        t.pb.memory[hATypeLevel] = 5
        t.press("start")
        t.run_until_state(GS_IN_GAME_MAIN)
        t.tick(4)
        game.top_out(t)
        open_stats(t)
        assert ["HEARTS", "SEEDED"] in lines(t), page(t)


def test_nothing_on_the_page_is_outside_the_font():
    with finished(9, hearts=True, plays=(4, 3, 2, 1)) as t:
        open_stats(t)
        assert not any("#" in row for row in page(t)), "\n".join(page(t))


# --- which games get one -----------------------------------------------------

def test_trainers_and_b_type_go_straight_on():
    """They keep no record, so there is nothing to show."""
    for mode, name in ((1, "B-TYPE"), (2, "TRANSITION"), (3, "CRUNCH"), (4, "OBSTACLE")):
        with Tetris(ROM) as t:
            t.to_mode(mode)
            t.press("start")
            t.tick(60)
            t.press("start")
            t.run_until_state(GS_IN_GAME_MAIN)
            t.tick(30)
            t.pb.memory[0xFFE1] = 0x0D
            t.run_until_state(GS_LEVEL_ENDED)
            t.tick(40)
            t.press("a")
            t.tick(4)
            assert t.state != GS_LEVEL_ENDED, f"{name}: still on the game over screen"
            assert not is_stats(t), f"{name}: got a stats page"


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
