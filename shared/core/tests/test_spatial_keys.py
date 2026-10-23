"""Spatial handles (keys/spatial.py): a key's `out` / `in` bend the way between two number keys; without them the value
is the straight line, exactly as before (the engine's scene tests check the same numbers)."""
from rostrum_core.keys import track_value


def test_handles_bend_the_midpoint_and_none_stays_straight():
    keys = [{"t": 0.0, "v": 0.0, "ease": "linear"}, {"t": 1.0, "v": 90.0, "ease": "linear"}]
    assert track_value(keys, 0.5) == 45.0
    keys[0]["out"] = 60.0                       # Bézier 0, 60, 60, 90 at p = 0.5
    assert track_value(keys, 0.5) == 56.25
    keys[1]["in"] = -60.0                       # 0, 60, 30, 90
    assert abs(track_value(keys, 0.5) - 45.0) < 1e-12 and abs(track_value(keys, 0.25) - 30.9375) < 1e-12
    assert track_value(keys, 0.0) == 0.0 and track_value(keys, 1.0) == 90.0
