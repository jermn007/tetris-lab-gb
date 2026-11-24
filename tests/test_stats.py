#!/usr/bin/env python3
"""What a finished game looked like.

    .venv/bin/python tests/test_stats.py

The Lab keeps a record of every TETRIS game as it is played: the score and
lines on reaching level 10 and level 20, how the lines were cleared, and the
longest run of pieces with no I (ADR 0016). Nothing is drawn yet, so these
assert on the record.

The games here are real ones. Rows are completed by writing the playfield and
letting a piece lock on top - the original checks every row on every lock - and
the pieces are chosen by writing the preview, which is what gets dealt next. So
each expectation comes from what the test set up, not from watching the same
variables the Lab watches.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.emu import (Tetris, sym, hATypeLevel, hGameState,      # noqa: E402
                       hPieceFallingState, GS_IN_GAME_MAIN,
                       GS_A_TYPE_SELECTION_MAIN)

ROM = "build/tetrislab.gb"

BUF, W = 0xC800, 32
BLOCK, EMPTY = 0x87, 0x2F
ROWS, COLS = 18, 10

wScoreBCD = 0xC0A0
hLines = sym("hNumLinesCompletedBCD")
hLevel = sym("hATypeLinesThresholdToPassForNextLevel")
hShifting = sym("hRowsShiftingDownState")
wSpriteSpecs = sym("wSpriteSpecs")
ACTIVE = wSpriteSpecs + 3               # the falling piece's spec index
PREVIEW = wSpriteSpecs + 0x10 + 3       # and the one dealt after it
wLabSeedLo = sym("wLabSeedLo")

FLAGS = sym("wLabStatsFlags")
START_LEVEL = sym("wLabStatsStartLevel")
LEVEL = sym("wLabStatsLevel")
FINAL = sym("wLabStatsFinal")
L10 = sym("wLabStatsL10")
L20 = sym("wLabStatsL20")
CLEARS = sym("wLabStatsClears")
DROUGHT = sym("wLabStatsDrought")
PIECES = sym("wLabStatsPieces")

TRACKING, DONE, HEARTS, SEEDED, AT_10, AT_20 = (1 << i for i in range(6))

L, J, I, O, Z, S, T = 0x00, 0x04, 0x08, 0x0C, 0x10, 0x14, 0x18

GS_LEVEL_ENDED = 0x04


def bcd(n, size):
    d = f"{n:0{size * 2}d}"
    return [int(d[i - 2:i], 16) for i in range(len(d), 0, -2)]


def unbcd(data):
    return int("".join(f"{b:02x}" for b in reversed(data)))


def word(t, addr):
    return t[addr] | (t[addr + 1] << 8)


def checkpoint(t, addr):
    """(score, lines) as a checkpoint holds them."""
    return (unbcd([t[addr + i] for i in range(4)]),
            unbcd([t[addr + 4], t[addr + 5]]))


def score(t):
    return unbcd([t[wScoreBCD + i] for i in range(3)])


def set_score(t, n):
    for i, b in enumerate(bcd(n, 3)):
        t.pb.memory[wScoreBCD + i] = b


def set_lines(t, n):
    for i, b in enumerate(bcd(n, 2)):
        t.pb.memory[hLines + i] = b


def clears(t):
    return [word(t, CLEARS + 2 * i) for i in range(4)]


def started(level, hearts=False):
    t = Tetris(ROM)
    t.start_game_at(level, hearts=hearts)
    t.tick(4)
    return t


def empty_board(t):
    for r in range(ROWS):
        for c in range(COLS):
            t.pb.memory[BUF + r * W + 2 + c] = EMPTY


def complete_rows(t, n):
    """The bottom `n` rows full, under an otherwise empty board."""
    empty_board(t)
    for r in range(ROWS - n, ROWS):
        for c in range(COLS):
            t.pb.memory[BUF + r * W + 2 + c] = BLOCK


def settled(t):
    return t[hPieceFallingState] == 0 and t[hShifting] == 0


def lock(t, push=True):
    """Let the falling piece land, and come back with the next one out."""
    if push:
        t.hold("down")
    t.run_until(lambda: t[hPieceFallingState] != 0 or t.state != GS_IN_GAME_MAIN,
                limit=3000, what="the piece to land")
    t.release("down")
    t.run_until(lambda: settled(t) or t.state != GS_IN_GAME_MAIN,
                limit=600, what="the next piece")
    t.tick(3)


def deal(t, piece):
    """Make `piece` the next one dealt, and deal it."""
    t.pb.memory[PREVIEW] = piece
    empty_board(t)
    lock(t)
    assert t[ACTIVE] & 0xFC == piece, f"harness: wanted ${piece:02X}, got ${t[ACTIVE]:02X}"


def top_out(t):
    """End the game the way games end: nowhere for the next piece to go."""
    for r in range(2, ROWS):
        for c in range(COLS - 1):
            t.pb.memory[BUF + r * W + 2 + c] = BLOCK
    t.run_until(lambda: t.state == GS_LEVEL_ENDED, limit=4000,
                what="the game over screen")
    t.tick(3)


def longest_drought(dealt):
    best = now = 0
    for p in dealt:
        now = 0 if p == I else now + 1
        best = max(best, now)
    return best


# --- the level 10 and level 20 checkpoints ---------------------------------

def test_reaching_level_10_keeps_the_score_and_lines_the_clear_left():
    """A tetris at level 9 on 96 lines: 1200 x 10 points, 100 lines, level 10."""
    with started(9) as t:
        set_score(t, 50000)
        set_lines(t, 96)
        complete_rows(t, 4)
        lock(t, push=False)                      # no drop points to account for

        assert t[hLevel] == 10, f"harness: level {t[hLevel]}"
        assert t[FLAGS] & AT_10, "no level 10 checkpoint"
        assert checkpoint(t, L10) == (62000, 100), checkpoint(t, L10)
        assert not t[FLAGS] & AT_20, "a level 20 checkpoint at level 10"


def test_a_checkpoint_does_not_move_once_it_is_taken():
    with started(9) as t:
        set_score(t, 50000)
        set_lines(t, 96)
        complete_rows(t, 4)
        lock(t, push=False)
        for _ in range(3):
            complete_rows(t, 2)
            lock(t)
        assert score(t) > 62000, "harness: the game did not go on"
        assert checkpoint(t, L10) == (62000, 100), checkpoint(t, L10)


def test_reaching_level_20_is_its_own_checkpoint():
    with started(19) as t:
        set_score(t, 300000)
        set_lines(t, 197)
        complete_rows(t, 3)                      # a triple: 300 x 20
        lock(t, push=False)

        assert t[hLevel] == 20, f"harness: level {t[hLevel]}"
        assert t[FLAGS] & AT_20, "no level 20 checkpoint"
        assert checkpoint(t, L20) == (306000, 200), checkpoint(t, L20)
        assert not t[FLAGS] & AT_10, "this game started past level 10"


def test_a_checkpoint_carries_the_seventh_digit():
    with started(19) as t:
        set_score(t, 995000)
        set_lines(t, 196)
        complete_rows(t, 4)                      # 1200 x 20 carries past a million
        lock(t, push=False)
        assert checkpoint(t, L20) == (1019000, 200), checkpoint(t, L20)


def test_a_level_that_was_not_reached_has_no_checkpoint():
    """Starting on 10 is not reaching it, and neither is passing 11."""
    with started(10) as t:
        set_lines(t, 106)
        complete_rows(t, 4)
        lock(t)
        assert t[hLevel] == 11, f"harness: level {t[hLevel]}"
        assert not t[FLAGS] & (AT_10 | AT_20), f"flags ${t[FLAGS]:02X}"


def test_hearts_reach_the_same_levels():
    """Hearts change how fast a level falls, not which level it is."""
    with started(9, hearts=True) as t:
        set_score(t, 50000)
        set_lines(t, 96)
        complete_rows(t, 4)
        lock(t, push=False)
        assert t[FLAGS] & HEARTS, "the record does not say it was a heart game"
        assert checkpoint(t, L10) == (62000, 100), checkpoint(t, L10)


# --- how the lines were cleared --------------------------------------------

def test_every_clear_is_counted_by_its_size():
    with started(5) as t:
        for n in (1, 2, 2, 3, 4, 4, 4, 1):
            complete_rows(t, n)
            lock(t)
        assert clears(t) == [2, 2, 1, 3], clears(t)


def test_a_piece_that_clears_nothing_counts_nothing():
    with started(5) as t:
        for _ in range(4):
            empty_board(t)
            lock(t)
        assert clears(t) == [0, 0, 0, 0], clears(t)
        assert word(t, PIECES) == 5, word(t, PIECES)


# --- droughts ---------------------------------------------------------------

def test_the_longest_drought_is_counted_in_pieces_dealt():
    with started(5) as t:
        dealt = [t[ACTIVE] & 0xFC]               # the first piece is the game's
        for piece in (T, I, O, O, S, I, Z, L, I):
            deal(t, piece)
            dealt.append(piece)
        assert word(t, PIECES) == len(dealt), (word(t, PIECES), len(dealt))
        assert word(t, DROUGHT) == longest_drought(dealt), (
            f"{word(t, DROUGHT)} from {dealt}"
        )


def test_a_drought_still_running_counts():
    """The longest run is the one the game ends in, I never having come."""
    with started(5) as t:
        dealt = [t[ACTIVE] & 0xFC]
        for piece in (I, O, I, T, Z, S, L, J):
            deal(t, piece)
            dealt.append(piece)
        assert longest_drought(dealt) == 5, "harness: the script changed"
        assert word(t, DROUGHT) == 5, word(t, DROUGHT)


def test_pausing_deals_nothing():
    with started(5) as t:
        deal(t, T)
        before = (word(t, PIECES), word(t, DROUGHT))
        t.press("start")
        t.tick(120)
        t.press("start")
        t.tick(10)
        assert (word(t, PIECES), word(t, DROUGHT)) == before


# --- the end of the game ----------------------------------------------------

def test_a_finished_game_keeps_how_it_ended():
    with started(7, hearts=True) as t:
        set_lines(t, 76)
        complete_rows(t, 4)                      # 80 lines: level 8
        lock(t)
        assert not t[FLAGS] & DONE, "done before it ended"
        top_out(t)

        assert t[FLAGS] & DONE, f"not marked finished: ${t[FLAGS]:02X}"
        assert t[START_LEVEL] == 7 and t[LEVEL] == 8, (t[START_LEVEL], t[LEVEL])
        assert checkpoint(t, FINAL) == (score(t), 80), checkpoint(t, FINAL)
        assert clears(t) == [0, 0, 0, 1], clears(t)


def test_the_final_score_is_the_one_on_the_game_over_screen():
    with started(0) as t:
        set_score(t, 1000)
        deal(t, T)                               # pushed down: drop points
        top_out(t)
        assert score(t) > 1000, "harness: no drop points were scored"
        assert checkpoint(t, FINAL)[0] == score(t), (checkpoint(t, FINAL), score(t))


def test_a_game_walked_out_of_is_not_a_finished_game():
    with started(5) as t:
        deal(t, T)
        t.press("start")                         # pause
        t.tick(10)
        t.press("b")                             # and leave
        t.run_until_state(GS_A_TYPE_SELECTION_MAIN)
        assert not t[FLAGS] & DONE, f"${t[FLAGS]:02X}"


def test_a_restart_starts_the_record_again():
    with started(5) as t:
        for n in (4, 2):
            complete_rows(t, n)
            lock(t)
        t.hold("a", "b", "select", "start")
        t.tick(6)
        t.release("a", "b", "select", "start")
        t.tick(4)
        t.run_until_state(GS_IN_GAME_MAIN)
        t.tick(4)
        assert clears(t) == [0, 0, 0, 0], clears(t)
        assert word(t, PIECES) == 1, word(t, PIECES)
        assert t[FLAGS] & TRACKING and not t[FLAGS] & DONE, f"${t[FLAGS]:02X}"


# --- which games are counted ------------------------------------------------

def test_a_seeded_game_says_so():
    with Tetris(ROM) as t:
        t.to_level_select()
        t.pb.memory[wLabSeedLo] = 0x5A
        t.pb.memory[hATypeLevel] = 5
        t.press("start")
        t.run_until_state(GS_IN_GAME_MAIN)
        t.tick(4)
        assert t[FLAGS] & SEEDED, f"${t[FLAGS]:02X}"

    with started(5) as t:
        assert t[FLAGS] & TRACKING and not t[FLAGS] & SEEDED, f"${t[FLAGS]:02X}"


def test_trainers_and_b_type_are_not_counted():
    """A trainer starts from a state nobody played their way to."""
    for mode, name in ((1, "B-TYPE"), (2, "TRANSITION"), (3, "CRUNCH"), (4, "OBSTACLE")):
        with Tetris(ROM) as t:
            t.to_mode(mode)
            t.press("start")
            t.tick(60)
            t.press("start")
            t.run_until_state(GS_IN_GAME_MAIN)
            t.tick(30)
            complete_rows(t, 4)
            lock(t)
            assert t[FLAGS] == 0, f"{name}: flags ${t[FLAGS]:02X}"
            assert clears(t) == [0, 0, 0, 0], f"{name}: {clears(t)}"


def test_a_trainer_after_a_game_does_not_inherit_its_record():
    with started(5) as t:
        complete_rows(t, 4)
        lock(t)
        t.press("start")
        t.tick(10)
        t.press("b")                             # to the level select
        t.run_until_state(GS_A_TYPE_SELECTION_MAIN)
        t.tick(20)
        t.press("b")                             # to the menu
        t.tick(60)
        t.to_mode(2)
        t.press("start")
        t.tick(60)
        t.press("start")
        t.run_until_state(GS_IN_GAME_MAIN)
        t.tick(10)
        assert t[FLAGS] == 0 and clears(t) == [0, 0, 0, 0], (t[FLAGS], clears(t))


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
