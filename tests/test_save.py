#!/usr/bin/env python3
"""High scores survive a power cycle.

    .venv/bin/python tests/test_save.py

WRAM is still where scores are filed, named and drawn; cartridge RAM mirrors
it (ADR 0015). So every test here switches the machine off and on again, and
asserts on what the *next* session shows - the battery RAM is carried between
them in memory, as bytes, and nothing is written beside the ROM.
"""

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.emu import Tetris, sym, hATypeLevel, hIsHardMode  # noqa: E402

ROM = "build/tetrislab.gb"

wScoreBCD = 0xC0A0
hGameState = 0xFFE1
wBTypeHighScores = sym("wBTypeHighScores")
wATypeHighScores = sym("wATypeHighScores")
wLabHiScoreMillions = sym("wLabHiScoreMillions")
wLabScoreMillions = sym("wLabScoreMillions")

HISCORE_SIZEOF = 27
GS_A_TYPE_SELECTION_INIT = 0x10
GS_A_TYPE_SELECTION_MAIN = 0x11
GS_ENTERING_HIGH_SCORE = 0x15
LEVEL = 9

# Where things sit on the cartridge, as offsets into the 8 KB (save.asm).
HEADER = 0x0000
PLAIN = 0x0040
HEART = 0x0340
BTYPE = 0x0640
A_SLOT = HISCORE_SIZEOF + 3 + 1       # entries, seventh digits, checksum
B_SLOT = HISCORE_SIZEOF + 1
B_TABLE = HISCORE_SIZEOF * 60
MAGIC = b"TLAB\x01"

ROW_VRAM = 0x9800 + 13 * 32 + 4


def bcd(n):
    d = f"{n % 1000000:06d}"
    return [int(d[4:6], 16), int(d[2:4], 16), int(d[0:2], 16)]


def top(t, level=LEVEL):
    """The best score in the live table's slot for `level`."""
    b = wATypeHighScores + level * HISCORE_SIZEOF
    m = t[wLabHiScoreMillions + level * 3]
    return int(f"{m:02x}{t[b + 2]:02x}{t[b + 1]:02x}{t[b]:02x}")


def shown(t):
    """The best score as the level select draws it, seventh digits included."""
    cells = [t[ROW_VRAM + 6 + i] for i in range(8)]
    digits = "".join(str(c) for c in cells if c <= 9)
    return int(digits) if digits else 0


def end_game(t, score):
    """End the running game worth `score`, leaving it on the name entry."""
    for j, byte in enumerate(bcd(score)):
        t.pb.memory[wScoreBCD + j] = byte
    t.pb.memory[wLabScoreMillions] = int(f"{score // 1000000:02d}", 16)
    t.pb.memory[hGameState] = GS_A_TYPE_SELECTION_INIT
    t.tick(120)
    assert t.state == GS_ENTERING_HIGH_SCORE, f"did not place: ${t.state:02X}"


def accept_name(t):
    t.press("start")
    t.tick(30)
    assert t.state == GS_A_TYPE_SELECTION_MAIN, f"${t.state:02X}"


def played(score, hearts=False, ram=None):
    t = Tetris(ROM, ram=ram)
    t.start_game_at(LEVEL, hearts=hearts)
    t.tick(120)
    end_game(t, score)
    accept_name(t)
    return t


def switched_on(ram, hearts=False):
    """A new session on a saved cartridge, at the level select on LEVEL."""
    t = Tetris(ROM, ram=ram)
    t.to_level_select(hearts=hearts)
    while t[hATypeLevel] != LEVEL:
        t.press("right" if t[hATypeLevel] < LEVEL else "left")
    t.tick(40)
    return t


def test_a_score_survives_a_power_cycle():
    ram = played(123400).power_off()
    with switched_on(ram) as t:
        assert top(t) == 123400, f"filed score did not come back: {top(t)}"
        assert shown(t) == 123400, f"and is not on screen: {shown(t)}"


def test_the_name_survives_with_it():
    t = played(123400)
    name = wATypeHighScores + LEVEL * HISCORE_SIZEOF + 9
    typed = [t[name + i] for i in range(6)]
    ram = t.power_off()
    with switched_on(ram) as t:
        assert [t[name + i] for i in range(6)] == typed


def test_a_score_past_a_million_survives_whole():
    ram = played(12000350).power_off()
    with switched_on(ram) as t:
        assert top(t) == 12000350, top(t)
        assert shown(t) == 12000350, shown(t)


def test_plain_and_heart_tables_are_saved_apart():
    t = played(111100, hearts=False)
    t.press("select")                            # hearts on
    t.tick(40)
    t.pb.memory[hATypeLevel] = LEVEL
    t.press("start")
    t.run_until_state(0x00)
    t.tick(120)
    end_game(t, 222200)
    accept_name(t)
    ram = t.power_off()

    with switched_on(ram) as t:
        assert not t[hIsHardMode]
        assert shown(t) == 111100, f"plain table: {shown(t)}"
        t.press("select")
        t.tick(40)
        assert shown(t) == 222200, f"heart table: {shown(t)}"


def test_a_heart_score_saved_last_is_not_read_back_as_plain():
    """The live table is the heart one when this save is made, and the plain
    one when it is read. The cartridge must not care which was live."""
    ram = played(222200, hearts=True).power_off()
    with switched_on(ram) as t:
        assert shown(t) == 0, f"heart score read back as plain: {shown(t)}"
        t.press("select")
        t.tick(40)
        assert shown(t) == 222200, shown(t)


def test_b_type_scores_are_saved():
    t = Tetris(ROM)
    t.start_game_at(LEVEL)
    t.tick(120)
    rng = random.Random(1989)
    table = [rng.randrange(0x9A) for _ in range(B_TABLE)]
    for i, byte in enumerate(table):
        t.pb.memory[wBTypeHighScores + i] = byte
    end_game(t, 500)
    accept_name(t)
    ram = t.power_off()

    with Tetris(ROM, ram=ram) as t:
        t.to_title()
        t.tick(10)
        back = [t[wBTypeHighScores + i] for i in range(B_TABLE)]
        assert back == table, "the B-type table did not come back as it was saved"


def test_switching_off_while_typing_the_name_keeps_the_score():
    """The entry goes into the table before the name is asked for, and that is
    a screen people switch off on."""
    t = Tetris(ROM)
    t.start_game_at(LEVEL)
    t.tick(120)
    end_game(t, 123400)
    ram = t.power_off()                          # no Start: the name is unfinished
    with switched_on(ram) as t:
        assert top(t) == 123400, f"lost with the unfinished name: {top(t)}"


def test_a_cartridge_never_written_starts_empty():
    """Unwritten RAM holds anything. None of it may be read as scores."""
    rng = random.Random(7)
    for label, blank in (("$FF", bytes([0xFF]) * 0x2000),
                         ("$00", bytes(0x2000)),
                         ("noise", bytes(rng.randrange(256) for _ in range(0x2000)))):
        t = Tetris(ROM, ram=blank)
        t.to_title()
        t.tick(10)
        a = [t[wATypeHighScores + i] for i in range(HISCORE_SIZEOF * 23)]
        b = [t[wBTypeHighScores + i] for i in range(B_TABLE)]
        assert not any(a) and not any(b), f"{label}: scores out of nowhere"
        ram = t.power_off()
        assert ram[HEADER:HEADER + 5] == MAGIC, f"{label}: no save was started"

        with Tetris(ROM, ram=ram) as t:          # and the save it started is sound
            t.to_title()
            t.tick(10)
            a = [t[wATypeHighScores + i] for i in range(HISCORE_SIZEOF * 23)]
            assert not any(a), f"{label}: its own new save read back as scores"


def test_a_damaged_slot_costs_only_that_slot():
    """A power cut mid-write can leave one slot half written. Its checksum
    catches it; every other level keeps its scores."""
    t = played(123400)
    t.pb.memory[hATypeLevel] = 5
    t.press("start")
    t.run_until_state(0x00)
    t.tick(120)
    end_game(t, 55500)
    accept_name(t)
    ram = bytearray(t.power_off())

    ram[PLAIN + LEVEL * A_SLOT + 1] ^= 0x10      # one digit of level 9's best
    with switched_on(bytes(ram)) as t:
        assert top(t, LEVEL) == 0, f"a damaged slot was trusted: {top(t, LEVEL)}"
        assert top(t, 5) == 55500, f"and took level 5 with it: {top(t, 5)}"


def test_a_save_from_another_version_is_not_read():
    ram = bytearray(played(123400).power_off())
    ram[HEADER + 4] = 0x7F
    t = switched_on(bytes(ram))
    assert top(t) == 0, f"read a save it does not understand: {top(t)}"
    assert t.power_off()[HEADER:HEADER + 5] == MAGIC, "and did not start its own"


def test_a_soft_reset_does_not_read_the_cartridge_back():
    """WRAM survives the soft reset and is the newer copy. Reading the
    cartridge over it would undo anything not yet written."""
    with played(123400) as t:
        t.pb.memory[wATypeHighScores + 3 * HISCORE_SIZEOF + 2] = 0x42   # unsaved
        t.hold("a", "b", "select", "start")
        t.tick(6)
        t.release("a", "b", "select", "start")
        t.run_until_state(0x07, limit=600)
        t.tick(30)
        assert t[wATypeHighScores + 3 * HISCORE_SIZEOF + 2] == 0x42


def test_cartridge_ram_is_closed_whenever_the_game_is_running():
    """Open RAM is what a reset or a flat battery corrupts. It is opened for a
    slot and closed again - never left open across a screen, a game or a save.
    PyBoy reads $FF from closed RAM, and the header's first byte is not $FF."""
    def closed(t, where):
        assert t[0xA000] == 0xFF, f"cartridge RAM is open {where}"

    t = Tetris(ROM)
    t.to_title()
    closed(t, "on the title screen")
    t.start_game_at(LEVEL)
    for _ in range(60):
        t.tick()
        closed(t, "during play")
    end_game(t, 123400)
    closed(t, "on the name entry")
    accept_name(t)
    closed(t, "after the name is in")
    ram = t.power_off()
    assert ram[HEADER] == MAGIC[0]

    # Reading a save back ends on a slot, not on the header - a different last
    # step from writing one, and the one that was left open when this was tried.
    with Tetris(ROM, ram=ram) as t:
        t.to_title()
        closed(t, "after loading a save")


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
