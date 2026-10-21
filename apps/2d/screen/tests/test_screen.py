"""What would break silently on the 2D screen: an inspector edit on an animated field must key it at the playhead
(never change the hidden still value); a canvas drag or key drag is one undo step; the key mark toggles keys.
The engine is replaced by a stand-in that writes a blank frame (pictures are checked by looking)."""
import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QGuiApplication, QImage

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document  # noqa: E402
from rostrum2d import KIND, run_source  # noqa: E402
from rostrum_core.keys import keys_of  # noqa: E402
from screen2d import frames  # noqa: E402
from screen2d.bridge2d import Bridge2D  # noqa: E402

SRC = '''
comp("c", width=320, height=180, fps=10, duration=2)
t = text("title", body="Hi", size=40, x=100, y=90)
t.key("opacity", {0.0: 0, 1.0: 1})
shape("box", w=40, h=40, x=200, y=90)
'''


class FakeEngine:
    def load(self, scene):
        pass

    def still(self, t, png):
        QImage(4, 4, QImage.Format.Format_RGB32).save(str(png))

    def pixels(self, t):
        return memoryview(bytearray(4 * 4 * 4)), 4, 4, 16

    def close(self):
        pass


@pytest.fixture
def bridge(monkeypatch):
    QGuiApplication.instance() or QGuiApplication([])
    monkeypatch.setattr(frames, "open_engine", FakeEngine)
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(SRC, "s.py"))
    b = Bridge2D(doc)
    yield b
    b.close()


def test_edit_on_animated_field_keys_it_at_the_playhead(bridge):
    bridge.select("title")
    bridge.setTime(0.5)
    still = bridge.doc.item("title")["opacity"]
    assert bridge.setValue("opacity", 0.25)
    title = bridge.doc.item("title")
    assert [(k["t"], k["v"]) for k in keys_of(title, "opacity")] == [(0.0, 0), (0.5, 0.25), (1.0, 1)]
    assert title["opacity"] == still
    assert bridge.setValue("size", 50) and bridge.doc.item("title")["size"] == 50     # not animatable: still


def test_canvas_drag_is_one_undo_step_and_keys_an_animated_field(bridge):
    bridge.select("box")
    bridge.setTime(0.3)
    assert bridge.toggleAnimate("x") is None and keys_of(bridge.doc.item("box"), "x")   # key mark: first key
    n = len(bridge.doc.history.changes)
    assert bridge.beginMove()
    for dx in (5, 10, 20):
        bridge.moveBy(dx, 4)
    bridge.endDrag()
    box = bridge.doc.item("box")
    assert len(bridge.doc.history.changes) == n + 1
    assert [(k["t"], k["v"]) for k in keys_of(box, "x")] == [(0.3, 220)] and box["y"] == 94
    bridge.undo()
    box = bridge.doc.item("box")
    assert [(k["t"], k["v"]) for k in keys_of(box, "x")] == [(0.3, 200)] and box["y"] == 90
    bridge.toggleAnimate("x")                                                         # key mark: stop animating
    assert not keys_of(bridge.doc.item("box"), "x") and bridge.doc.item("box")["x"] == 200


def test_key_drag_is_one_step_and_keeps_the_key(bridge):
    key = keys_of(bridge.doc.item("title"), "opacity")[1]["id"]
    n = len(bridge.doc.history.changes)
    assert bridge.beginKeyDrag(key)
    for t in (1.1, 1.26, 1.5):
        bridge.keyDragTo(t)
    bridge.endDrag()
    assert len(bridge.doc.history.changes) == n + 1
    assert bridge.doc.item(key)["t"] == 1.5 and bridge.selected == key


def test_pen_stroke_is_one_undo_step_and_one_change(bridge):
    doc = bridge.doc
    doc.apply([{"op": "layer.add", "target": ["c"], "args": {"type": "drawing", "id": "pad"}},
               {"op": "drawing.set", "target": ["pad"], "args": {"w": 320, "h": 180}}],
              bridge.who)
    bridge.select("pad")
    bridge.setTime(0.5)
    n = len(doc.history.changes)
    assert bridge.painter.beginStroke(20, 20, 1.0)
    for x in (40, 80, 120):
        bridge.painter.strokeTo(x, 60, 0.6)
    bridge.painter.endStroke()

    def strokes():
        return [s for f in doc.item("pad")["frames"] for p in f["paints"] for s in p["strokes"]]
    assert len(doc.history.changes) == n + 1 and len(strokes()) == 1
    assert len(strokes()[0]["points"]) == 4 and strokes()[0]["points"][-1][2] == 0.6
    bridge.undo()
    assert not strokes() and not any(f["at"] == 5 for f in doc.item("pad")["frames"])   # the frame it added went too
