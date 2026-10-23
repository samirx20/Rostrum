"""Dragging a key square on the motion path moves only that key's x and y, as one undo step."""
from rostrum_core.keys import keys_of
from test_screen import bridge  # noqa: F401  (the shared fixture: a small document, the engine stood in)


def test_key_square_drag_moves_only_that_key_in_one_step(bridge):  # noqa: F811
    doc = bridge.doc
    bridge.select("box")
    for t, x, y in ((0.0, 200, 90), (0.5, 300, 90), (1.0, 400, 150)):
        bridge.setTime(t)
        if t == 0.0:
            bridge.toggleAnimate("x")
            bridge.toggleAnimate("y")
        bridge.setValue("x", x)
        bridge.setValue("y", y)
    before = {p: [(k["t"], k["v"]) for k in keys_of(doc.item("box"), p)] for p in ("x", "y")}
    path = next(p for p in bridge.motionPath.paths if p["id"] == "box")
    assert [k["t"] for k in path["keys"]] == [0.0, 0.5, 1.0] and len(path["ticks"]) > 3
    n = len(doc.history.changes)
    assert bridge.motionPath.beginKey("box", 0.5)
    for d in (5, 10, 20):
        bridge.motionPath.drag(d, -d, False)
    bridge.endDrag()
    box = doc.item("box")
    assert len(doc.history.changes) == n + 1
    after = {p: [(k["t"], k["v"]) for k in keys_of(box, p)] for p in ("x", "y")}
    assert after["x"] == [before["x"][0], (0.5, 320), before["x"][2]]
    assert after["y"] == [before["y"][0], (0.5, 70), before["y"][2]]
