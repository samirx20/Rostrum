"""The rubber band lights the layers it would pick while it grows (screen2d/band.py), by the same rule letting go uses
(Shift adds), without changing the selection until the release."""
from test_screen import bridge  # noqa: F401  (the shared fixture: a small document, the engine stood in)


def test_the_growing_band_lights_what_letting_go_picks(bridge):  # noqa: F811
    multi = bridge.multi
    bridge.select("title")
    multi.bandTo(185, 75, 195, 85, "")                 # over the box only
    assert multi._band[0] == ("box",) and multi.bandPath.startswith("M") and multi.layers() == ["title"]
    multi.bandTo(185, 75, 195, 85, "shift ")           # Shift: added to the pick
    assert set(multi._band[0]) == {"title", "box"}
    assert multi.boxSelect(185, 75, 195, 85, "shift ") == 2 and set(multi.layers()) == {"title", "box"}
    assert multi.bandPath == ""
