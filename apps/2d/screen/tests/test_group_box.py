"""Ctrl+G on animated layers fits the group's box (its turning point) to them as they are at the playhead, not at 0 s
(round 7: a card scaling in from nothing was left out of its group's box). Real keys into the real window."""
import sys
from pathlib import Path

import pytest
from rostrum2d import settings

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
pytestmark = pytest.mark.skipif(settings.engine_missing_reason() is not None, reason=settings.engine_missing_reason() or "")

SRC = '''
comp("c", width=1920, height=1080, fps=10, duration=4)
card = shape("card", w=800, h=400, x=960, y=540, fill="#eeddcc")
card.key("scale", {0.0: 0, 0.8: 1})
shape("dot", w=40, h=40, x=960, y=540, fill="#334455")
'''


@pytest.fixture
def screen(tmp_path):
    from rostrum_core import Document
    from rostrum2d import KIND, run_source
    from rostrum_gui.app import qt_app
    from screen2d.session import Session
    app = qt_app()
    session = Session((1646, 900), None)
    doc = Document.new(KIND, folder=str(tmp_path), item="proj")
    doc.run_script("a.py", run_source(SRC, "a.py"))
    session.files.put(doc)
    from PySide6.QtTest import QTest
    QTest.qWait(800)
    yield session.bridge, session.win
    app.processEvents()
    session.close()


def test_ctrl_g_measures_the_group_at_the_playhead(screen):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    b, win = screen
    b.setTime(2.0)
    b.selectMany(["card", "dot"])
    QTest.qWait(50)
    QTest.keyClick(win, Qt.Key_G, Qt.ControlModifier)
    QTest.qWait(50)
    g = b.doc.item(b.multi.ids[0])
    assert g["type"] == "group" and (round(g["w"]), round(g["h"]), round(g["x"]), round(g["y"])) == (800, 400, 960, 540)
