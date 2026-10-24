"""A layer timed from a shared marker: the screen shows its keys where they play (composition seconds, like the
playhead) and writes the document back in the layer's own seconds. Guards: timeline row, key drag, inspector value."""
import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QGuiApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document, Who, markers  # noqa: E402
from rostrum_core.keys import keys_of  # noqa: E402
from rostrum2d import KIND, textsize  # noqa: E402
from rostrum2d.evaluate import resolve  # noqa: E402
from rostrum2d.retime import timed  # noqa: E402
from screen2d import frames  # noqa: E402
from screen2d.bridge2d import Bridge2D  # noqa: E402
from test_screen import FakeEngine  # noqa: E402


@pytest.fixture
def bridge(monkeypatch, tmp_path):
    QGuiApplication.instance() or QGuiApplication([])
    monkeypatch.setattr(frames, "open_engine", FakeEngine)
    monkeypatch.setattr(textsize, "open_engine", FakeEngine)
    monkeypatch.setattr(textsize, "_own", None)
    (tmp_path / "docs").mkdir()
    markers.edit(tmp_path, [{"op": "marker.add", "args": {"name": "reveal", "at": 11.6}}], Who.person("sam"))
    doc = Document.new(KIND, folder=tmp_path)
    doc.apply([{"op": "comp.add", "args": {"id": "film", "fps": 10, "duration": 20}},
               {"op": "layer.add", "target": "film", "args": {"type": "shape", "id": "dot"}},
               {"op": "shape.set", "target": "dot", "args": {"marker": "reveal"}},
               {"op": "key.add", "target": "dot", "args": {"prop": "opacity", "t": 0.0, "v": 0}},
               {"op": "key.add", "target": "dot", "args": {"prop": "opacity", "t": 1.0, "v": 1}}], Who.person("sam"))
    b = Bridge2D(doc)
    yield b
    b.close()


def test_keys_show_at_play_time_and_write_in_own_seconds(bridge):
    row = next(r for r in bridge.layers if r["row"] == "layer" and r["id"] == "dot")
    assert [k["t"] for k in row["keys"]] == [pytest.approx(11.6), pytest.approx(12.6)]      # marker + written t
    first = row["keys"][0]["id"]
    bridge.select(first)
    assert bridge.beginKeyDrag(first)
    bridge.keyDragTo(12.1)
    bridge.endDrag()
    assert [k["t"] for k in keys_of(bridge.doc.item("dot"), "opacity")] == [pytest.approx(0.5), 1.0]   # written: 12.1 - 11.6
    bridge.select("dot")
    bridge.setTime(12.3)
    shown = bridge.shown_values(bridge.doc.item("dot"))["opacity"]
    engine = resolve(next(l for l in timed(bridge.comp(), bridge.times(), 10)["layers"] if l["id"] == "dot"), 12.3)["opacity"]
    assert shown == pytest.approx(engine) and 0 < shown < 1


def test_a_cut_on_a_marker_stays_tied_when_the_next_shot_is_dragged(bridge):
    """Cut here with the playhead on a marker ties the cut to it; dragging the frame to the next shot there changes
    that key (no second key beside it), so moving the marker moves the cut (camera spec § 5 #20)."""
    fd = bridge.frameDrag
    fd.pick()
    bridge.setTime(11.6)
    assert bridge.run("layer:cut_here"), bridge.status
    x0 = bridge.doc.item(fd.id).get("x", 960.0)
    assert fd.begin("move", x0, 540.0, 0)
    bridge.snap.keys(True, False)                  # Ctrl: free
    fd.moveBy(500, 0)
    fd.end()
    assert {k["t"]: k["v"] for k in keys_of(bridge.doc.item(fd.id), "x")} == {"#reveal-0.1": x0, "#reveal": x0 + 500}


def test_an_edit_on_a_marker_key_changes_that_key(bridge):
    """A key on a marker under the playhead is THE key there: moving the layer changes it and it stays on the marker
    (route.value_call), never a second key at the playhead's seconds beside it."""
    bridge.doc.apply([{"op": "key.add", "target": "dot", "args": {"prop": "x", "t": "#reveal", "v": 100}},
                      {"op": "key.add", "target": "dot", "args": {"prop": "x", "t": 3.0, "v": 200}}], Who.person("sam"))
    bridge.select("dot")
    bridge.setTime(11.6)
    assert bridge.beginMove()
    bridge.moveBy(50, 0)
    bridge.endDrag()
    assert {k["t"]: k["v"] for k in keys_of(bridge.doc.item("dot"), "x")} == {"#reveal": 150, 3.0: 200}
