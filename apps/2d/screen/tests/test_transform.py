"""A resize drag and a rotate drag are each exactly one undo step, and on an animated field they add a key at the
playhead (never change the hidden still value)."""
from math import cos, radians, sin

from rostrum_core.keys import keys_of
from test_screen import bridge  # noqa: F401  (the shared fixture: a small document, the engine stood in)


def test_resize_and_rotate_are_one_undo_step_each_and_key_animated_fields(bridge):  # noqa: F811
    doc = bridge.doc
    bridge.select("box")                                              # 40 x 40 at 200, 90
    bridge.setTime(0.3)
    bridge.toggleAnimate("w")                                         # w is keyed from here on
    n = len(doc.history.changes)
    assert bridge.beginResize(1, 1)                                   # bottom-right corner
    for d in (5, 10, 20):
        bridge.resizeBy(d, d, False, False)
    bridge.endDrag()
    box = doc.item("box")
    assert len(doc.history.changes) == n + 1
    assert [(k["t"], k["v"]) for k in keys_of(box, "w")] == [(0.3, 60)] and box["w"] == 40     # a key, not the still value
    assert (box["h"], box["x"], box["y"]) == (60, 210, 100)           # top-left corner stayed put
    bridge.undo()
    assert doc.item("box")["h"] == 40

    bridge.toggleAnimate("rotation")
    n = len(doc.history.changes)
    assert bridge.beginRotate()
    for a in (10, 20, 30):                                            # the pointer circles the anchor (200, 90)
        bridge.rotateTo(200 + 50 * cos(radians(a)), 90 + 50 * sin(radians(a)), False)
    bridge.endDrag()
    box = doc.item("box")
    assert len(doc.history.changes) == n + 1 and box["rotation"] == 0
    assert round(keys_of(box, "rotation")[0]["v"], 1) == 20.0         # swept 20 degrees from the first move
