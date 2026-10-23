"""A hover preview (action_preview.py) draws an action's would-be result from a scratch copy and never touches the
document or its history; an action that can't be previewed shows nothing."""
import copy
import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QGuiApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document, Who  # noqa: E402
from rostrum2d import KIND, textsize  # noqa: E402
from screen2d import frames  # noqa: E402
from screen2d.action_preview import PREVIEW_TAG  # noqa: E402
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
               *[{"op": "layer.add", "target": "film", "args": {"type": "shape", "id": i}} for i in ("a", "b")],
               {"op": "shape.set", "target": ["b"], "args": {"x": 60, "y": 30}}], Who.person("sam"))
    b = Bridge2D(doc)
    yield b
    b.close()


def test_a_hover_preview_never_changes_the_document_or_its_history(bridge, monkeypatch):
    asked = []
    monkeypatch.setattr(bridge.frames, "request", lambda scene, t, *a, **k: asked.append((scene, a)))
    bridge.selectMany(["a", "b"])
    data, seq = copy.deepcopy(bridge.doc.data), bridge.doc.seq
    for action in ("layer:subtract", "layer:align_left"):
        asked.clear()
        bridge._hub.previewStart(action)
        assert len(asked) == 1 and asked[0][1][-1] == PREVIEW_TAG        # one frame, tagged as a preview
        bridge._hub.previewEnd()
        assert len(asked) == 2 and asked[1][1][-1] != PREVIEW_TAG        # the document's own frame is asked again
        assert bridge.doc.data == data and bridge.doc.seq == seq
    asked.clear()
    bridge._hub.previewStart("layer:delete")                                   # not a previewable action: nothing drawn
    bridge._hub.previewEnd()
    assert asked == [] and bridge.doc.data == data and bridge.doc.seq == seq
