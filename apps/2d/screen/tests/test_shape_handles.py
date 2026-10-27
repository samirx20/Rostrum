"""A shape's orange setting handles on the canvas (corner radius dots, star / polygon / triangle / arc / spiral handles,
ellipse to arc) and a text's wrap-width sides: each drag is exactly one undo step and leaves the shape as the same
value.set calls an agent makes would. The engine is the stand-in of test_screen."""
import copy

import pytest
from PySide6.QtGui import QGuiApplication
from test_screen import FakeEngine

from rostrum_core import Document
from rostrum2d import KIND, run_source, textsize
from screen2d import frames, route
from screen2d.bridge2d import Bridge2D
from screen2d.handle_steps import shape_handle
from screen2d.shape_handle_geom import HANDLES
from screen2d.shape_handle_slots import placed

SRC = '''
comp("c", width=1200, height=800, fps=10, duration=2)
shape("card", w=200, h=100, x=200, y=150, radius=10)
shape("star", shape="star", w=200, h=200, x=500, y=200)
shape("poly", shape="polygon", w=200, h=200, x=800, y=200)
shape("tri", shape="triangle", w=200, h=200, x=200, y=500)
shape("pie", shape="arc", w=200, h=200, x=500, y=500, startAngle=0, sweep=270, hole=0.2)
shape("egg", shape="ellipse", w=200, h=200, x=800, y=500)
shape("curl", shape="spiral", w=200, h=200, x=1050, y=500)
text("note", body="Hello world", size=40, x=200, y=700)
'''


@pytest.fixture
def bridge(monkeypatch):
    QGuiApplication.instance() or QGuiApplication([])
    monkeypatch.setattr(frames, "open_engine", FakeEngine)
    monkeypatch.setattr(textsize, "open_engine", FakeEngine)
    monkeypatch.setattr(textsize, "_own", None)
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(SRC, "s.py"))
    b = Bridge2D(doc)
    yield b
    b.close()


def by_hand_and_by_agent(bridge, layer, handle, dx, dy, shift=False, alt=False) -> dict:
    """Drag `handle` as a hand would; check it is one undo step and that an agent's value.set calls of the same
    fields leave the same shape. Returns what the drag set."""
    doc = bridge.doc
    before, n = copy.deepcopy(doc.item(layer)), len(doc.history.changes)
    bridge.select(layer)
    shape_handle(bridge, "test", handle, dx, dy, shift, alt)
    after = copy.deepcopy(doc.item(layer))
    assert len(doc.history.changes) == n + 1, "one drag, one undo step"
    sets = {k: v for k, v in after.items() if before.get(k) != v and k in HANDLES[handle].fields}   # (shape.set names an arc "Arc")
    bridge.undo()
    assert doc.item(layer) == before
    order = sorted(sets, key=lambda k: k not in ("shape", "eachCorner"))   # an ellipse turns into an arc first, corners split first
    doc.apply([route.edit_call(doc, layer, k, sets[k], 0.0) for k in order], bridge.who)    # value.set, or shape.set on a still field
    assert doc.item(layer) == after
    return sets


@pytest.mark.parametrize("layer, handle, dx, dy, shift, want", [
    ("card", "radius:se", -20, -20, False, {"radius": 30}),              # along the diagonal, inward: every corner
    ("card", "radius:nw", 200, 200, False, {"radius": 50}),              # never past half the short side
    ("star", "points", 24, 0, False, {"points": 7}),                     # sideways: 12 screen px a point
    ("star", "inner", 0, -40, False, {"innerRadius": 0.824}),       # out along the first inner corner (36°)
    ("poly", "sides", -24, 0, False, {"sides": 4}),
    ("tri", "tip", 40, 0, False, {"tip": 0.7}),                          # along the top edge
    ("tri", "radius", 0, 20, False, {"radius": 20}),
    ("pie", "hole", 20, 20, False, None),                              # out, on the half-way line (135°)
    ("pie", "start", 100, 100, True, {"startAngle": 90, "sweep": 180}),  # round the middle, Shift = 15° steps
    ("curl", "turns", 100, 100, False, None),
])
def test_each_handle_is_one_undo_step_and_the_same_as_value_set(bridge, layer, handle, dx, dy, shift, want):
    sets = by_hand_and_by_agent(bridge, layer, handle, dx, dy, shift)
    if want is None:
        assert sets
    else:
        assert {k: pytest.approx(v, abs=0.02) for k, v in want.items()} == sets


def test_alt_on_a_radius_dot_turns_each_corner_on_and_sets_only_that_corner(bridge):
    sets = by_hand_and_by_agent(bridge, "card", "radius:nw", 10, 10, alt=True)
    assert sets["eachCorner"] is True and sets["radiusTL"] == 20
    assert (sets["radiusTR"], sets["radiusBR"], sets["radiusBL"]) == (10, 10, 10)    # the others stay as they showed
    bridge.doc.apply([route.edit_call(bridge.doc, "card", k, v, 0.0) for k, v in sets.items()], bridge.who)
    sets = by_hand_and_by_agent(bridge, "card", "radius:ne", -5, 5)                     # no Alt: one radius again
    assert sets == {"eachCorner": False, "radius": 15}


def test_dragging_an_ellipse_dot_makes_an_arc_with_the_same_box_in_one_step(bridge):
    sets = by_hand_and_by_agent(bridge, "egg", "start", 100, 38, shift=True)     # the start swept on to 60°
    assert sets == {"shape": "arc", "startAngle": 60, "sweep": 300}                 # the end stays at the top
    assert bridge.doc.item("egg")["w"] == 200


def test_a_text_side_sets_its_wrap_width_from_the_width_it_shows(bridge):
    doc = bridge.doc
    bridge.select("note")
    w0 = bridge.selBox["w"]
    n = len(doc.history.changes)
    assert bridge.beginResize(1, 0)
    bridge.snap.keys(True, False)
    for d in (10, 30):
        bridge.resizeBy(d, 0, False, False)
    bridge.endDrag()
    note = doc.item("note")
    assert len(doc.history.changes) == n + 1
    assert note["boxWidth"] == pytest.approx(w0 + 30) and note["size"] == 40 and note.get("scaleX", 1) == 1


def test_where_the_handles_sit(bridge):
    def at(layer, zoom=1.0):
        b = next(iter(bridge.shown_boxes([layer])))
        hs = placed(b, route.shown_values(bridge.doc.item(layer), 0), zoom)
        return {h["name"]: (round(h["u"], 3), round(h["v"], 3)) for h in hs}
    assert at("card")["radius:nw"] == (0.05, 0.1)          # inset by the radius, 10 px
    assert at("card")["radius:se"] == (0.95, 0.9)
    assert at("card", 0.5) == {}                           # 100 x 50 on screen: under 60 px, no dots
    star = at("star")
    assert star["points"] == (0.5, -0.06)                  # just above the first tip
    assert star["inner"][1] < 0.5                          # the first inner corner, up and right of the middle
    assert at("pie")["start"] == (0.5, 0.06)               # the arc's start, 12 px in from the edge
    assert set(at("egg")) == {"start", "end"}
