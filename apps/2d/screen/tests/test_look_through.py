"""Look through the frame (Shift+C) is screen state: turning it off brings back the person's own view exactly (pan and
view %), and it is never an undo step. A wrong restore would silently move someone's view. Needs the built engine."""
import sys
from pathlib import Path

import pytest
from rostrum2d import settings

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
pytestmark = pytest.mark.skipif(settings.engine_missing_reason() is not None, reason=settings.engine_missing_reason() or "")


def test_look_through_keeps_the_view_and_the_history(tmp_path):
    from PySide6.QtCore import QObject
    from PySide6.QtTest import QTest
    from rostrum_core import Document
    from rostrum2d import KIND, run_source
    from rostrum_gui.app import qt_app
    from screen2d.sample import SOURCE
    from screen2d.session import Session
    from screen2d.steps import do_step
    app = qt_app()
    session = Session((1646, 900), None)
    doc = Document.new(KIND, folder=str(tmp_path), item="proj")
    doc.run_script("a.py", run_source(SOURCE, "a.py"))
    session.files.put(doc)
    QTest.qWait(800)
    b, win = session.bridge, session.win
    stage = win.findChild(QObject, "stage")
    view = lambda: (round(stage.property("compScale"), 6), stage.property("compOrigin").toTuple())   # noqa: E731
    try:
        for s in ("zoom 200", "pan 140 -60"):
            do_step(b, win, s)
        mine, steps = view(), len(b.doc.history.changes)
        do_step(b, win, "keytap c shift")
        assert stage.property("lookThrough") and view() != mine
        do_step(b, win, "keytap c shift")
        assert not stage.property("lookThrough") and view() == mine
        assert len(b.doc.history.changes) == steps
    finally:
        app.processEvents()
        session.close()
