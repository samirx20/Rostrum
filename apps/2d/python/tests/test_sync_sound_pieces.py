"""A video layer's own sound as Sound plays it (sync_sound._pieces): a looped layer starts again where its picture does,
a held one goes quiet when the file ends. Wrong here is heard only as sound out of step, so it is guarded."""
from rostrum2d.sync_sound import _pieces

FPS = 30.0


def test_loop_starts_again_where_the_picture_does():
    layer = {"id": "v", "start": 0.5, "offset": 0.5, "loop": True}
    got = _pieces(layer, 0.5, 9.0, 1.0, 3.0, FPS)
    assert got == [{"after": 0.0, "in": 0.5, "length": 2.5}, {"after": 2.5, "in": 0.0, "length": 3.0},
                   {"after": 5.5, "in": 0.0, "length": 3.0}]


def test_cut_to_a_group_and_quiet_after_the_file_ends():
    layer = {"id": "v", "start": 0.5, "offset": 0.5}
    assert _pieces(layer, 1.0, 2.5, 1.0, 3.0, FPS) == [{"after": 0.0, "in": 1.0, "length": 1.5}]   # group 1.0-2.5 s
    assert _pieces(layer, 0.5, 9.0, 1.0, 3.0, FPS) == [{"after": 0.0, "in": 0.5, "length": 2.5}]   # held: no sound


def test_loop_at_double_speed_counts_file_seconds():
    layer = {"id": "v", "start": 0.0, "loop": True}
    got = _pieces(layer, 0.0, 2.0, 2.0, 1.5, FPS)          # 4 file seconds over 2 s: 1.5 + 1.5 + 1.0
    assert [(p["after"], p["in"], p["length"]) for p in got] == [(0.0, 0.0, 1.5), (0.75, 0.0, 1.5), (1.5, 0.0, 1.0)]
