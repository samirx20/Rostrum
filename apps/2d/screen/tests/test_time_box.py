"""The time in the timeline's header is a box: click it, type 36f + Enter, the playhead is on frame 36; while the box has
the keyboard every key is its own, so "." never jumps to the next key. Real mouse and keys into the real window."""
import sys
from pathlib import Path

import pytest
from rostrum2d import settings

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
pytestmark = pytest.mark.skipif(settings.engine_missing_reason() is not None, reason=settings.engine_missing_reason() or "")


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
    QTest.qWait(800)
    yield session.bridge, session.win
    app.processEvents()
    session.close()


def test_typing_a_time_goes_there_and_keys_stay_in_the_box(screen):
    from screen2d.steps import do_step
    b, win = screen
    for s in ("clickobj timeBox", "typekeys 36f", "keytap return"):
        do_step(b, win, s)
    assert round(b.time * 30) == 36
    for s in ("clickobj timeBox", "typekeys .", "keytap escape"):      # "." jumps to the next key anywhere else
        do_step(b, win, s)
    assert round(b.time * 30) == 36
    for s in ("clickobj timeBox", "typekeys 99", "keytap return"):      # past the end (4 s): refused, not clamped
        do_step(b, win, s)
    assert round(b.time * 30) == 36
