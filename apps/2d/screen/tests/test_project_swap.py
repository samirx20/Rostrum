"""Every way the window opens another project from a click or a key leaves no Qt fault: a Recent card, Continue, the
sample and renaming the project all swap the window, and once they did it inside their own click handler, so Qt
deleted the card under it and the app ended (2D sweep r3). QML reaches those actions only through files.pickLater.
Real mouse clicks and keys on the real window, offscreen; needs the built engine like any scripted run."""
import shutil
import sys
from pathlib import Path

import pytest
from rostrum2d import settings

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
pytestmark = pytest.mark.skipif(settings.engine_missing_reason() is not None, reason=settings.engine_missing_reason() or "")


def _items(win):
    todo = [win.contentItem()]
    while todo:
        it = todo.pop()
        if it.isVisible() and it.opacity() > 0:
            yield it
            todo.extend(it.childItems())


def _click(win, found):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtTest import QTest
    it = next((i for i in _items(win) if found(i)), None)
    assert it is not None
    p = it.mapToScene(QPointF(it.width() / 2, it.height() / 2)).toPoint()
    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, p)
    QTest.qWait(1200)                                     # the swap runs after the click's handler, then the new window settles


def _click_text(win, words):
    _click(win, lambda i: isinstance(i.property("text"), str) and i.property("text").startswith(words))


def test_recent_card_rename_continue_and_sample_swap_without_a_fault(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path / "home"))
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from rostrum_gui import qt_faults
    from rostrum_gui.app import qt_app
    from screen2d.session import Session
    app = qt_app()
    s = Session((1646, 900), None)
    files = s.files
    try:
        files.put(files.kind.blank(tmp_path / "First"))
        files.newProject("Second")                        # setup: two projects, First in Open recent
        second = Path(files.doc.folder)
        files.setStart(True)
        QTest.qWait(800)
        before = len(qt_faults.found())

        _click_text(s.win, "First")                       # a Recent card
        assert Path(files.doc.folder).name == "First" and not files.startShown

        _click(s.win, lambda i: i.objectName() == "projectName")          # rename: click the name, type, Enter
        QTest.keyClick(s.win, Qt.Key_A, Qt.ControlModifier)
        for ch in "Renamed":
            QTest.keyClick(s.win, ch)
        QTest.keyClick(s.win, Qt.Key_Return)
        QTest.qWait(1200)
        assert Path(files.doc.folder).name == "Renamed"

        files.put(files.kind.blank(None)); files.setStart(True)               # setup: as at launch
        QTest.qWait(800)
        _click_text(s.win, "Continue ")
        assert Path(files.doc.folder).name == "Renamed"

        files.put(files.kind.blank(None))                                  # setup: no project left, so the sample shows
        for folder in (tmp_path / "Renamed", second):
            shutil.rmtree(folder, ignore_errors=True)
        files.setStart(True)
        QTest.qWait(800)
        _click_text(s.win, "Open the sample")
        assert files.has_project() and not files.startShown
        assert qt_faults.found()[before:] == []
    finally:
        app.processEvents()
        s.close()
