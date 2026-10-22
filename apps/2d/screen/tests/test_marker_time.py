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
    engine = resolve(timed(bridge.comp(), bridge.times(), 10)["layers"][0], 12.3)["opacity"]
    assert shown == pytest.approx(engine) and 0 < shown < 1
