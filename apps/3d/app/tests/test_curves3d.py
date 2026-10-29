"""What would break silently in 3D's curve view (curves3d.py on the kit's curve_view.py): a key drag and a handle drag
are ONE undo step each, a handle drag makes the ease custom from the named ease's numbers, and the curves shown are the
picked item's, or every animated item's with nothing picked or All curves chosen. (Pictures are checked by looking.)"""
import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QGuiApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document, Who  # noqa: E402
from rostrum_core.keys import BEZIERS, keys_of  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from screen3d.bridge3d import Bridge3D  # noqa: E402
from screen3d.steps import do_step  # noqa: E402

SRC = '''
cam = camera("cam", z=3)
mesh("box", shape="box")
mesh("ball", shape="sphere", x=1)
shot("s", camera=cam, fps=10, start=0, end=20)
'''


@pytest.fixture
def bridge():
    QGuiApplication.instance() or QGuiApplication([])
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(SRC, "s.py"))
    doc.apply([{"op": "key.add", "target": ["box"], "args": {"prop": "x", "t": 0, "v": 0}},
               {"op": "key.add", "target": ["box"], "args": {"prop": "x", "t": 1, "v": 2}},
               {"op": "key.add", "target": ["ball"], "args": {"prop": "y", "t": 0.5, "v": 1}},
               {"op": "key.add", "target": ["ball"], "args": {"prop": "y", "t": 1.5, "v": 3}}], Who.person())
    b = Bridge3D(doc, viewport=None)
    yield b
    b.close()


def test_picked_item_or_all_curves(bridge):
    cv = bridge.curves
    assert cv.offered and not cv.on
    do_step(bridge, None, "curves on")
    assert {f["group"] for f in cv.fields} == {"box", "ball"} and cv.all          # nothing picked: every item's
    bridge.select("box")
    assert [f["id"] for f in cv.fields] == ["box.x"] and cv.canAll and not cv.all
    do_step(bridge, None, "curves all")
    assert [f["id"] for f in cv.fields] == ["box.x", "ball.y"]


def test_key_drag_is_one_undo_step(bridge):
    bridge.select("box")
    do_step(bridge, None, "curves on")
    k1 = keys_of(bridge.doc.item("box"), "x")[1]["id"]
    n = len(bridge.doc.history.changes)
    do_step(bridge, None, f"curvedrag {k1} 0.5 1.5")
    k = bridge.doc.item(k1)
    assert (k["t"], k["v"]) == (pytest.approx(1.5), pytest.approx(3.5))
    assert len(bridge.doc.history.changes) == n + 1
    bridge.undo()
    assert (bridge.doc.item(k1)["t"], bridge.doc.item(k1)["v"]) == (1, 2)


def test_handle_drag_is_one_undo_step_and_makes_the_ease_custom(bridge):
    k0 = keys_of(bridge.doc.item("box"), "x")[0]["id"]
    n = len(bridge.doc.history.changes)
    do_step(bridge, None, f"handledrag {k0} 1 0.1 0.3")
    k = bridge.doc.item(k0)
    x1, y1, x2, y2 = BEZIERS["smooth"]
    assert (k["ease"], k["x1"], k["y1"], k["x2"], k["y2"]) == ("custom", pytest.approx(x1 + 0.1), pytest.approx(y1 + 0.3), x2, y2)
    assert len(bridge.doc.history.changes) == n + 1
    bridge.undo()
    assert bridge.doc.item(k0)["ease"] == "smooth"
