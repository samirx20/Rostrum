"""Dragging the frame on the canvas (frame_drag.py): still, it moves for the whole piece; keyed, it gets a key at the
playhead and keeps its other keys; each drag is one undo step; a locked frame refuses and nothing changes."""
from rostrum_core.keys import keys_of
from test_screen import bridge  # noqa: F401  (the shared fixture: a small document, the engine stood in)


def _frame(bridge):  # noqa: F811
    return bridge.doc.item(bridge.frameDrag.id)


def _drag(bridge, dx, dy):  # noqa: F811
    fd = bridge.frameDrag
    f = _frame(bridge)
    assert fd.begin("move", f.get("x", 0), f.get("y", 0), 0)
    bridge.snap.keys(True, False)                  # Ctrl: free (this is about what is written, not where it snaps)
    for k in (0.25, 0.5, 1.0):
        fd.moveBy(dx * k, dy * k)
    fd.end()


def test_frame_drag_writes_still_or_a_key_in_one_step(bridge):  # noqa: F811
    doc, fd = bridge.doc, bridge.frameDrag
    fd.pick()
    assert fd.picked
    x0 = _frame(bridge).get("x", 0)
    n = len(doc.history.changes)
    _drag(bridge, 100, 0)
    assert len(doc.history.changes) == n + 1 and _frame(bridge)["x"] == x0 + 100 and not keys_of(_frame(bridge), "x")
    assert bridge.status == "Moved the frame (whole piece)"
    bridge.toggleAnimate("x")                      # a key at 0 s
    bridge.setTime(1.0)
    n = len(doc.history.changes)
    _drag(bridge, -40, 0)
    assert len(doc.history.changes) == n + 1
    assert [(k["t"], k["v"]) for k in keys_of(_frame(bridge), "x")] == [(0.0, x0 + 100), (1.0, x0 + 60)]
    assert bridge.status == "Moved the frame at 1.00 s"


def test_locked_frame_refuses(bridge):  # noqa: F811
    bridge.frameDrag.pick()
    bridge.setValue("locked", True)
    n = len(bridge.doc.history.changes)
    assert not bridge.frameDrag.begin("move", 0, 0, 0)
    assert "locked" in bridge.status and len(bridge.doc.history.changes) == n
