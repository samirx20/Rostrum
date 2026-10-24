"""The Depth group's switch and field, and ⋯ Pin to frame, keep a layer where it shows at the playhead (2d-camera SPEC
§4.9, §4.10): a plain field write would make it jump with nothing said. Through the screen's own routing (pin_depth.py,
as hooks.edit_call and the action list use it) and the boxes the canvas draws (bounds.boxes)."""
import sys
from pathlib import Path

import pytest
from rostrum_core import Document, Who

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum2d import KIND, run_source  # noqa: E402
from screen2d import bounds, pin_depth  # noqa: E402
from screen2d.actions import LIST, Facts  # noqa: E402

SRC = '''
comp("c", width=1920, height=1080, fps=10, duration=4)
f = frame()
f.key("x", {0: 960, 4: 2400})
f.key("zoom", {0: 1, 4: 1.5})
shape("card", w=200, h=100, x=1200, y=500)
with group("g", w=100, h=100):
    shape("inner", w=10, h=10)
'''
T = 3.0


@pytest.fixture
def doc():
    d = Document.new(KIND)
    d.run_script("s.py", run_source(SRC, "s.py"))
    return d


def box(doc):
    b = next(b for b in bounds.boxes(doc.item("c"), T) if b["id"] == "card")
    return [b[k] for k in ("x", "y", "w", "h")]


@pytest.mark.parametrize("param, value", [("screenLock", True), ("depth", 3.0)])
def test_the_depth_group_keeps_it_where_it_shows(doc, param, value):
    before = box(doc)
    doc.apply([pin_depth.edit_call(doc, "card", param, value, T)], Who.person(), "edit")
    assert doc.item("card")[param] == value
    assert box(doc) == pytest.approx(before, abs=0.01)


def test_pin_and_unpin_offered_only_where_they_apply(doc):
    def offered(ids):
        return {e["id"] for e in LIST.available(Facts(doc, ids, {"now": T}))} & {"layer:pin", "layer:unpin"}
    assert offered(["card"]) == {"layer:pin"}
    assert offered(["inner"]) == set() and offered(["frame"]) == set()
    doc.apply([pin_depth.calls(Facts(doc, ["card"], {"now": T}), True)[0]], Who.person(), "pin")
    assert offered(["card"]) == {"layer:unpin"}


def test_set_depth_far_leaves_a_covering_drawing_s_canvas_alone(doc):
    """Set depth ▾ Far on a painted background: it stays where it shows, and its canvas (which still covers the move)
    is not resized, so its picture is not made again (it showed the old or a blank picture meanwhile)."""
    doc.apply({"op": "background.add", "target": "c", "args": {"depths": [0.0], "names": ["Hills"]}}, Who.person())
    hills = next(l for l in doc.item("c")["layers"] if l["type"] == "drawing")
    paint = hills["frames"][0]["paints"][0]["id"]
    doc.apply({"op": "stroke.add", "target": paint, "args": {"points": [[300, 300], [900, 600]], "size": 40}}, Who.person())
    before = doc.item(hills["id"])
    f = Facts(doc, [hills["id"]], {"now": T})
    calls = pin_depth.depth_calls(f, 3.0)
    assert [c["op"] for c in calls] == ["layer.set_depth", "background.fit"]
    doc.apply(calls, Who.person(), "Set depth")
    after = doc.item(hills["id"])
    assert (after["w"], after["h"], after["depth"]) == (before["w"], before["h"], 3.0)
    assert after["frames"][0]["paints"][0]["strokes"] == before["frames"][0]["paints"][0]["strokes"]
