"""Dragging a key square on the motion path moves only that key's x and y, as one undo step."""
from rostrum_core.keys import keys_of
from test_screen import bridge  # noqa: F401  (the shared fixture: a small document, the engine stood in)
from rostrum2d import run_source


def test_key_square_drag_moves_only_that_key_in_one_step(bridge):  # noqa: F811
    doc = bridge.doc
    bridge.select("box")
    for t, x, y in ((0.0, 200, 90), (0.5, 300, 90), (1.0, 400, 150)):
        bridge.setTime(t)
        if t == 0.0:
            bridge.toggleAnimate("x")              # Position's key mark: X and Y together
        bridge.setValue("x", x)
        bridge.setValue("y", y)
    before = {p: [(k["t"], k["v"]) for k in keys_of(doc.item("box"), p)] for p in ("x", "y")}
    path = next(p for p in bridge.motionPath.paths if p["id"] == "box")
    assert [k["t"] for k in path["keys"]] == [0.0, 0.5, 1.0] and len(path["ticks"]) > 3
    n = len(doc.history.changes)
    assert bridge.motionPath.beginKey("box", 0.5)
    bridge.snap.keys(True, False)                  # Ctrl: free (the drag is about which keys move, not where it lands)
    for d in (5, 10, 20):
        bridge.motionPath.drag(d, -d, False)
    bridge.endDrag()
    box = doc.item("box")
    assert len(doc.history.changes) == n + 1
    after = {p: [(k["t"], k["v"]) for k in keys_of(box, p)] for p in ("x", "y")}
    assert after["x"] == [before["x"][0], (0.5, 320), before["x"][2]]
    assert after["y"] == [before["y"][0], (0.5, 70), before["y"][2]]


def _path_with_three_keys(bridge):  # noqa: F811
    bridge.select("box")
    for t, x, y in ((0.0, 200, 40), (0.5, 300, 40), (1.0, 400, 150)):
        bridge.setTime(t)
        if t == 0.0:
            bridge.toggleAnimate("x")              # Position's key mark: X and Y together
        bridge.setValue("x", x)
        bridge.setValue("y", y)
    bridge.setTime(0.0)


def test_key_square_snaps_to_the_frame_centre_unless_free(bridge):  # noqa: F811
    _path_with_three_keys(bridge)
    mp, doc = bridge.motionPath, bridge.doc
    xs = lambda: next(k["v"] for k in keys_of(doc.item("box"), "x") if k["t"] == 0.5)   # noqa: E731
    ys = lambda: next(k["v"] for k in keys_of(doc.item("box"), "y") if k["t"] == 0.5)   # noqa: E731
    assert mp.beginKey("box", 0.5)
    mp.drag(-137, 52, False)                       # 3 and 2 px off the centre (160, 90), the frame's lines catch it
    bridge.endDrag()
    assert (xs(), ys()) == (160, 90)
    assert mp.beginKey("box", 0.5)
    bridge.snap.keys(True, False)                  # Ctrl: place freely
    mp.drag(3, 2, False)
    bridge.endDrag()
    assert (xs(), ys()) == (163, 92)


def test_frame_key_lands_under_the_pointer_with_the_playhead_between_keys(bridge):  # noqa: F811
    """The canvas is the world, so a frame key's square follows the pointer exactly while the frame it moves changes."""
    bridge.doc.run_script("cam.py", run_source(CAM, "cam.py"))
    bridge.select("frame")
    bridge.setTime(1.0)                            # between the camera's keys at 0 s and 2 s
    mp = bridge.motionPath
    square = lambda: next(k for p in mp.paths if p["id"] == "frame" for k in p["keys"] if k["t"] == 2.0)["pos"]   # noqa: E731
    x0, y0 = square()
    assert mp.beginKey("frame", 2.0)
    bridge.snap.keys(True, False)                  # Ctrl: free
    for dx, dy in ((20, -10), (60, -40), (95, -41)):
        mp.drag(dx, dy, False)
        x, y = square()
        assert abs(x - (x0 + dx)) < 0.5 and abs(y - (y0 + dy)) < 0.5
    bridge.endDrag()


CAM = '''
comp("c", width=320, height=180, fps=10, duration=2)
cam = frame()
cam.key("x", {0.0: 160, 2.0: 220})
cam.key("y", {0.0: 90, 2.0: 70})
cam.key("zoom", {0.0: 1, 2.0: 1.4})
'''
