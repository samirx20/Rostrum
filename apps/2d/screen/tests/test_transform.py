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


def test_layer_in_a_turned_group_is_boxed_and_picked_where_it_shows_and_stepped_time_is_followed():
    from rostrum2d import KIND, run_source
    from rostrum_core import Document
    from screen2d import bounds
    src = '''
comp("c", width=400, height=300, fps=10, duration=2)
with group("g", w=100, h=100, x=200, y=150, rotation=90, anchorX=0.5, anchorY=0.5):
    shape("kid", w=20, h=10, x=80, y=50, anchorX=0, anchorY=0)
m = shape("m", w=10, h=10, x=0, y=0, timing="2")
m.key("x", {0.0: 0, 1.0: 100})
'''
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(src, "s.py"))
    comp = doc.item("c")
    kid = next(b for b in bounds.boxes(comp, 0) if b["id"] == "kid")
    # the group turns a quarter about its centre (200, 150): the child's point (80, 50) in the group lands at (200, 180)
    assert (round(kid["x"]), round(kid["y"]), kid["rot"]) == (200, 180, 90)
    assert bounds.pick(comp, 0, 195, 190) == "kid" and bounds.pick(comp, 0, 205, 190) != "kid"    # turned 90: covers x 190..200, y 180..200
    ds = bounds.parent_delta(kid, 5, 0)                    # screen right is the group's own "up"
    assert (round(ds[0]), round(ds[1])) == (0, -5)
    on_twos = lambda t: next(b for b in bounds.boxes(comp, t) if b["id"] == "m")["x"]   # noqa: E731
    assert on_twos(0.3) == on_twos(0.2) != on_twos(0.4)    # between steps the outline sits on the drawn picture


def test_resize_knobs_show_the_arrow_that_matches_their_screen_direction():
    from screen2d.transform import resize_cursor as c
    assert [c(*k, 0) for k in ((1, 0), (0, 1), (1, 1), (1, -1))] == ["hor", "ver", "fdiag", "bdiag"]
    assert [c(*k, 45) for k in ((1, 0), (0, 1), (1, 1), (1, -1))] == ["fdiag", "bdiag", "ver", "hor"]
    assert c(-1, -1, 90) == "bdiag" and c(1, 0, 180) == "hor"
