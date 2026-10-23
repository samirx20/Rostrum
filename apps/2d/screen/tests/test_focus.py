"""The keyboard must come back to the workspace when an in-place editor closes, whichever way it closes (Esc after
typing or a rename, Ctrl+Enter): the shortcuts (Ctrl+Z, P, the arrows) went dead once, with the focus left on a hidden
editor. Real key presses into the real window; needs the engine (ROSTRUM2D_ENGINE) like any scripted run."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
pytestmark = pytest.mark.skipif(not os.environ.get("ROSTRUM2D_ENGINE"), reason="needs the built engine (ROSTRUM2D_ENGINE)")


@pytest.fixture
def screen(tmp_path):
    from rostrum_core import Document
    from rostrum2d import KIND, run_source
    from rostrum_gui.app import qt_app
    from screen2d.sample import SOURCE
    from screen2d.session import Session
    app = qt_app()
    session = Session((1646, 900), None)
    doc = Document.new(KIND, folder=str(tmp_path), item="proj")
    doc.run_script("a.py", run_source(SOURCE, "a.py"))
    session.files.put(doc)
    from PySide6.QtTest import QTest
    QTest.qWait(800)                                      # the window lays itself out first, as a person waits
    yield session.bridge, session.win
    app.processEvents()


def _steps(b, win, *steps):
    from screen2d.steps import do_step
    for s in steps:
        do_step(b, win, s)


def test_keys_work_after_typing_and_renaming_end_with_esc_or_ctrl_enter(screen):
    b, win = screen
    layers = lambda: len(b.comp()["layers"])
    n = layers()
    _steps(b, win, "keytap t", "mouseclick 300 200", "typekeys Hi_there", "keytap escape")
    assert not win.property("typing") and layers() == n + 1
    _steps(b, win, "keytap z ctrl")                       # the whole text is one step
    assert layers() == n
    _steps(b, win, "keytap t", "mouseclick 700 300", "typekeys A", "keytap return ctrl", "keytap p")
    assert b.tool == "pen"
    _steps(b, win, "keytap escape", "keytap v", "select title")
    x = b.comp()["layers"][1]["x"]
    _steps(b, win, "keytap f2", "keytap escape", "keytap right", "keytap right")
    assert b.comp()["layers"][1]["x"] == x + 2
    _steps(b, win, "keytap z ctrl")                       # each press is its own step
    assert b.comp()["layers"][1]["x"] == x + 1
