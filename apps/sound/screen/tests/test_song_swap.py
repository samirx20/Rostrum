"""Opening another song keeps the window and swaps the song's parts under it (main.py Screen._swap). Afterwards the
Editor must work on the new song: a click there with the Draw tool adds a note to it, and no binding read the old
song (critic r6 M1: after ≡ › Open the roll raised "Cannot call method 'tOf' of undefined" and took no edits).
The real window's QML, offscreen; the engine is a stand-in (sound is checked by listening)."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Document  # noqa: E402
from rostrum_gui import qt_faults  # noqa: E402
from rostrum_sound import KIND, run_source  # noqa: E402
from screensound import playback  # noqa: E402
from screensound.files_sound import ITEM  # noqa: E402
from test_screen import FakeEngine  # noqa: E402

SRC = '''
tempo(120); beats_per_bar(4)
lead = track("lead", builtIn="feltPiano")
lead.note("C4", at=beat(0), dur=beats(1))
lead.note("G4", at=beat(32), dur=beats(1))
'''


def song(folder: Path) -> Path:
    doc = Document.new(KIND, folder=folder, item=ITEM)
    doc.run_script("song.py", run_source(SRC, "song.py"))
    doc.save()
    return folder


def rolls(win):
    found = []

    def walk(it):
        for c in it.childItems():
            if "RollInput" in c.metaObject().className() and c.isVisible():
                found.append(c)
            walk(c)
    walk(win.contentItem())
    return found


def click_draw(screen, fx):
    """Select the lead track, show the Editor with the Draw tool (setup), then click empty space in the visible roll
    with the real mouse; returns the new note's id (the bridge's selection after the click)."""
    b = screen.bridge
    b.select("lead")
    b.workspace.setDock("editor")
    b.setTool("draw")
    QTest.qWait(300)
    [roll] = rolls(screen.win)
    r = roll.mapRectToScene(roll.boundingRect())
    q = roll.parentItem()
    while q is not None:                     # the part shown: inside every clipping parent
        if q.clip():
            r = r.intersected(q.mapRectToScene(q.boundingRect()))
        q = q.parentItem()
    at = QPoint(round(r.x() + r.width() * fx), round(r.y() + r.height() * 0.5))
    count = len(b.doc.history.changes)
    QTest.mouseMove(screen.win, at)
    QTest.mouseClick(screen.win, Qt.LeftButton, Qt.NoModifier, at)
    QTest.qWait(200)
    assert len(b.doc.history.changes) == count + 1, b.status
    assert b.doc.history.changes[-1].label == "Draw note"
    return b.doc


def test_the_editor_edits_the_song_opened_from_the_menu(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(playback, "open_engine", FakeEngine)
    import main as soundmain
    a, b = song(tmp_path / "A"), song(tmp_path / "B")
    faults = len(qt_faults.found())
    screen = soundmain.Screen((1646, 900))
    try:
        assert screen.files.openPath(str(a))
        QTest.qWait(300)
        doc_a = click_draw(screen, 0.3)                         # the Editor made and used on the first song
        assert screen.files.openPath(str(b))               # ≡ › Open (the dialog hands the menu this path)
        QTest.qWait(300)
        doc_b = click_draw(screen, 0.3)
        assert doc_b is not doc_a and Path(doc_b.folder) == b
        assert screen.files.openRecent(0)                  # ≡ › Open recent (its first row: the song before)
        QTest.qWait(300)
        assert Path(click_draw(screen, 0.6).folder) == a
        assert qt_faults.found()[faults:] == []
    finally:
        screen.close()
        QTest.qWait(50)
