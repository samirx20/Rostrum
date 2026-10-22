"""The top bar's "N changes" counts what is in effect (Undo takes it down, Redo brings it back), and Undo / Redo are
offered only while they have something to do, across the document and the shared markers (one history)."""
import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QGuiApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document, Who  # noqa: E402
from rostrum2d import KIND, textsize  # noqa: E402
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
    doc = Document.new(KIND, folder=tmp_path)
    doc.apply([{"op": "comp.add", "args": {"id": "film", "fps": 10, "duration": 5}},
               {"op": "layer.add", "target": "film", "args": {"type": "shape", "id": "dot"}}], Who.person("sam"))
    b = Bridge2D(doc)
    yield b
    b.close()

def test_count_follows_what_is_in_effect_and_buttons_follow_what_can_be_done(bridge):
    start = bridge.historyCount
    bridge.markerEdit.add(1.0)                                  # a marker edit joins the same history
    assert bridge.historyCount == start + 1 and bridge.undoLabel == "Add marker" and bridge.redoLabel == ""
    bridge.undo()
    assert bridge.historyCount == start and bridge.redoLabel == "Add marker"
    bridge.redo()
    assert bridge.historyCount == start + 1 and bridge.redoLabel == ""
