"""A click on a setting's key mark (its diamond) adds a key at the playhead, or deletes only the key at the playhead,
and never stops the whole animation: round 7's critic lost a camera move to one click. Stop animating is the mark's
right-click. Real mouse into the real window."""
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


def test_the_key_mark_adds_or_deletes_one_key_and_stops_only_from_its_menu(screen):
    from rostrum_core.keys import keys_of
    from screen2d.steps import do_step
    b, win = screen
    times = lambda: [round(k["t"], 2) for k in keys_of(b.doc.item("title"), "opacity")]  # noqa: E731
    b.select("title")
    b.setTime(2.0)
    assert times() == [0.2, 0.9]
    do_step(b, win, "clickobj keymark:opacity")            # outlined: a key at a new moment, the others stay
    assert times() == [0.2, 0.9, 2.0]
    do_step(b, win, "clickobj keymark:opacity")            # filled: only this key goes, and the top bar says so
    assert times() == [0.2, 0.9] and "2.00 s" in b.status
    b.setTime(0.9)
    do_step(b, win, "clickobj keymark:opacity")
    assert times() == [0.2]
    do_step(b, win, "clickobj keymark:opacity right")      # the named step that stops it all
    do_step(b, win, "clickobj menu:stop")
    assert times() == [] and "Stop animating" in b.status
