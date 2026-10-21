"""What would break silently in the curve editor: a handle drag on a named ease is ONE undo step and turns the key into
`custom` from that ease's numbers; key.handles sets the custom ease. (Pictures are checked by looking.)"""
import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QGuiApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from rostrum2d.easing import BEZIERS  # noqa: E402
from rostrum2d.evaluate import keys_of  # noqa: E402
from screen2d.bridge2d import Bridge2D  # noqa: E402
from screen2d.steps import do_step  # noqa: E402
from test_screen import FakeEngine, frames, Document, KIND, run_source, SRC  # noqa: E402,F401


@pytest.fixture
def bridge(monkeypatch):
    QGuiApplication.instance() or QGuiApplication([])
    monkeypatch.setattr(frames, "open_engine", FakeEngine)
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(SRC, "s.py"))
    b = Bridge2D(doc)
    yield b
    b.close()


def test_handle_drag_is_one_undo_step_and_makes_the_ease_custom(bridge):
    key = keys_of(bridge.doc.item("title"), "opacity")[0]
    bridge.select("title")
    assert key["ease"] == "smooth"
    do_step(bridge, None, f"handledrag {key['id']} 1 0.1 0.3")
    k = keys_of(bridge.doc.item("title"), "opacity")[0]
    x1, y1, x2, y2 = BEZIERS["smooth"]
    assert (k["ease"], k["x1"], k["y1"], k["x2"], k["y2"]) == ("custom", pytest.approx(x1 + 0.1), pytest.approx(y1 + 0.3), x2, y2)
    bridge.undo()                                         # one step brings back the whole ease
    assert keys_of(bridge.doc.item("title"), "opacity")[0]["ease"] == "smooth"


def test_key_handles_op_sets_custom_ease(bridge):
    key = keys_of(bridge.doc.item("title"), "opacity")[0]["id"]
    bridge.doc.apply([{"op": "key.handles", "target": [key], "args": {"x1": 0.1, "y1": -0.5, "x2": 0.9, "y2": 1.4}}], bridge.who)
    k = keys_of(bridge.doc.item("title"), "opacity")[0]
    assert (k["ease"], k["y1"], k["y2"]) == ("custom", -0.5, 1.4)
