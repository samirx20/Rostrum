"""A press that picks a layer and drags it moves it on the first move; the new pick's settings panel waits for the
release (panel_hold.py), so the drag's first frames never build it."""
import sys
from pathlib import Path

import pytest
from rostrum2d import settings

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
pytestmark = pytest.mark.skipif(settings.engine_missing_reason() is not None, reason=settings.engine_missing_reason() or "")

SOURCE = '''
comp("c", name="Scene", width=1920, height=1080, fps=30, duration=4)
shape("a", w=100, h=100, x=300, y=300)
shape("b", w=100, h=100, x=700, y=300)
'''


@pytest.fixture
def b(tmp_path, monkeypatch):
    from rostrum_core import Document
    from rostrum2d import KIND, run_source
    from rostrum_gui import pointer_quiet
    from rostrum_gui.app import qt_app
    from screen2d.session import Session
    app = qt_app()
    session = Session((1646, 900), None)
    doc = Document.new(KIND, folder=str(tmp_path), item="proj")
    doc.run_script("a.py", run_source(SOURCE, "a.py"))
    session.files.put(doc)
    hand = {"on": True}                                   # a person's pointer is busy (pressing, moving)
    monkeypatch.setattr(pointer_quiet, "busy", lambda: hand["on"])
    session.bridge.hand = hand
    yield session.bridge
    app.processEvents()
    session.close()


def turns(ms):
    from PySide6.QtCore import QEventLoop, QTimer
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def test_grab_moves_first_and_the_panel_follows_the_release(b):
    b.select("a")
    turns(50)
    shown = []
    b.panelShown.connect(lambda: shown.append(b._sel))
    n = len(b.doc.history.changes)
    b.multi.pick(750, 350, "click")                        # press on "b", not picked yet
    assert b.beginMove()
    b.snap.keys(True, False)                               # (Ctrl: no snapping)
    b.moveBy(20, 0)
    assert b.doc.item("b")["x"] == 720                     # moved on the first move
    for dx in (30, 40):
        turns(20)
        b.moveBy(dx, 0)
    assert shown == [] and b._kit.panel_held               # the panel waits while the hand drags
    b.endDrag()
    b.hand["on"] = False
    turns(120)
    assert shown and shown[-1] == "b" and not b._kit.panel_held
    assert b.doc.item("b")["x"] == 740 and len(b.doc.history.changes) == n + 1
