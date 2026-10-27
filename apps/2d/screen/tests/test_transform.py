"""A resize drag and a rotate drag are each exactly one undo step, and on an animated field they add a key at the
playhead (never change the hidden still value)."""
from math import cos, radians, sin

from rostrum_core.keys import keys_of
from test_screen import bridge  # noqa: F401  (the shared fixture: a small document, the engine stood in)


def test_resize_and_rotate_are_one_undo_step_each_and_key_animated_fields(bridge):  # noqa: F811
    doc = bridge.doc
    bridge.select("box")                                              # 40 x 40 at 200, 90
    bridge.setTime(0.3)
    bridge.toggleAnimate("w")                                         # Size (w and h) is keyed from here on
    n = len(doc.history.changes)
    assert bridge.beginResize(1, 1)                                   # bottom-right corner
    for d in (5, 10, 20):
        bridge.resizeBy(d, d, False, False)
    bridge.endDrag()
    box = doc.item("box")
    assert len(doc.history.changes) == n + 1
    assert [(k["t"], k["v"]) for k in keys_of(box, "w")] == [(0.3, 60)] and box["w"] == 40     # a key, not the still value
    assert [(k["t"], k["v"]) for k in keys_of(box, "h")] == [(0.3, 60)] and (box["x"], box["y"]) == (210, 100)   # top-left stayed
    bridge.undo()
    assert [k["v"] for k in keys_of(doc.item("box"), "h")] == [40]

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


def test_resize_knobs_point_their_arrow_along_their_screen_direction():
    from screen2d.transform import resize_cursor as c
    assert [c(*k, 0) for k in ((1, 0), (0, 1), (1, 1), (1, -1))] == [0, 90, 45, 135]
    assert [c(*k, 20) for k in ((1, 0), (0, 1), (1, 1), (1, -1))] == [20, 110, 65, 155]   # leans with a turned layer
    assert c(-1, -1, 90) == 135 and c(1, 0, 180) == 0 and c(1, 0, 33) == 35                # a line: 180° round is the same; 5° steps


def test_group_resize_and_turn_are_one_undo_step_and_leave_unselected_layers_alone(bridge):  # noqa: F811
    doc = bridge.doc
    bridge.selectMany(["box", "title"])
    before = {i: dict(doc.item(i)) for i in ("box", "title", "ra")}
    n = len(doc.history.changes)
    assert bridge.beginGroupResize(1, 1)
    for d in (5, 10, 20):
        bridge.groupResizeBy(d, d, False, False)
    bridge.endDrag()
    assert len(doc.history.changes) == n + 1                            # two layers, three moves: one step
    assert doc.item("box")["w"] > before["box"]["w"] and doc.item("ra") == before["ra"]
    assert bridge.beginGroupRotate()
    b = bridge._multi.groupBox
    c = (b["x"] + b["w"] / 2, b["y"] + b["h"] / 2)
    for a in (0, 10, 20):
        bridge.groupRotateTo(c[0] + 50 * cos(radians(a)), c[1] + 50 * sin(radians(a)), False)
    bridge.endDrag()
    assert len(doc.history.changes) == n + 2 and round(doc.item("box")["rotation"], 1) == 20.0
    bridge.undo()
    bridge.undo()
    assert {i: dict(doc.item(i)) for i in before} == before             # both gone, nothing else touched


def test_dragging_a_line_end_moves_that_end_only_and_alt_keeps_the_middle():
    from math import hypot
    from screen2d.line_ends import drag_end
    g = {"x": 500, "y": 300, "w": 200, "h": 4, "ax": 0.5, "ay": 0.5, "rot": 0}      # a flat line from (400, 300) to (600, 300)
    r = drag_end(g, 1, 30, 40)                                                     # the right end goes to (630, 340)
    start = (r["x"] - r["w"] / 2 * cos(radians(r["rot"])), r["y"] - r["w"] / 2 * sin(radians(r["rot"])))
    assert hypot(start[0] - 400, start[1] - 300) < 1e-6 and round(r["w"], 3) == round(hypot(230, 40), 3)
    m = drag_end(g, -1, -30, 10, alt=True)                                         # Alt: the middle stays at (500, 300)
    assert (round(m["x"], 6), round(m["y"], 6)) == (500, 300) and round(m["w"], 3) == round(hypot(260, 20), 3)


def test_a_corner_dragged_past_the_opposite_corner_flips_in_one_step(bridge):  # noqa: F811
    doc = bridge.doc
    bridge.select("box")                                              # 40 x 40 about its centre 200, 90: top-left 180, 70
    n = len(doc.history.changes)
    assert bridge.beginResize(1, 1)
    for d in (-20, -40, -60):                                         # through zero and 20 px out the other side
        bridge.resizeBy(d, d, False, False)
    bridge.endDrag()
    box = doc.item("box")
    assert len(doc.history.changes) == n + 1
    assert box["scaleX"] < 0 and box["scaleY"] < 0 and (box["w"], box["h"]) == (20, 20)   # the sign only in Stretch
    assert (box["x"], box["y"]) == (170, 60)                          # the top-left corner stayed: the box is 160..180
