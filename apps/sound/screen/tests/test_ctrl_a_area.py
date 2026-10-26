"""Ctrl+A takes everything of where the person last pressed, and the Editor stays on its track (critic r10 must-fix 1:
the track's name clicked, the Editor's Select clicked, then after a panel edit Ctrl+A selected every note of the song,
the Editor jumped to the first track, and the next Repeat copied every track). A pick in a popup's list belongs to
the area that opened it (critic r11 must-fix 1: "Next marker" picked in Repeat's Until list, over the arrangement,
and the next Ctrl+A took every track). Real clicks and keys on the window."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Document  # noqa: E402
from rostrum_sound import KIND, run_source  # noqa: E402
from screensound import playback  # noqa: E402
from screensound.files_sound import ITEM  # noqa: E402
from test_amounts_popover import click, items, shown  # noqa: E402
from test_plugin_items import header  # noqa: E402
from test_screen import FakeEngine  # noqa: E402

SRC = '''
a = track("strings", builtIn="feltPiano")
b = track("piano", builtIn="feltPiano")
for i in range(8):
    a.note("D4", at=beat(i * 2), dur=beats(2))
    b.note("A4", at=beat(i), dur=beats(1))
marker("cut", at=bar(6))
'''


def _opened(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(playback, "open_engine", FakeEngine)
    doc = Document.new(KIND, folder=tmp_path / "S", item=ITEM)
    doc.run_script("song.py", run_source(SRC, "song.py"))
    doc.save()
    import main as soundmain
    screen = soundmain.Screen((1646, 900))
    assert screen.files.openPath(str(tmp_path / "S"))
    QTest.qWait(400)
    b, win = screen.bridge, screen.win
    click(win, header(win, "piano"))                      # the track's name: selected, the Editor shows it
    b.workspace.setDock("editor")
    QTest.qWait(300)
    select = next(i for i in items(win) if i.isVisible() and i.property("text") == "Select")
    click(win, select)                                    # the Editor's own button: the keys are the Editor's now
    return screen, b, win


def _on(b, tid):
    return [i for i in b.selectedIds if b.doc.parent_of(i)[0] == tid]


def test_ctrl_a_in_the_editor_takes_its_track_and_the_editor_stays(tmp_path, monkeypatch):
    screen, b, win = _opened(tmp_path, monkeypatch)
    on = lambda tid: _on(b, tid)  # noqa: E731
    try:
        QTest.keyClick(win, Qt.Key_A, Qt.ControlModifier)
        QTest.qWait(300)
        assert len(b.selectedIds) == 8 and len(on("piano")) == 8, b.status
        QTest.keyClick(win, Qt.Key_A, Qt.ControlModifier)  # again (as after a panel edit: the notes are the selection)
        QTest.qWait(300)
        assert len(b.selectedIds) == 8 and len(on("piano")) == 8, "Ctrl+A in the Editor took other tracks' notes"
        assert b.roll["id"] == "piano", "the Editor left its track"
    finally:
        screen.close()


def test_a_pick_in_repeats_until_list_keeps_ctrl_a_in_the_editor(tmp_path, monkeypatch):
    screen, b, win = _opened(tmp_path, monkeypatch)
    try:
        QTest.keyClick(win, Qt.Key_A, Qt.ControlModifier)
        QTest.qWait(300)
        QTest.keyClick(win, Qt.Key_R, Qt.ControlModifier)
        QTest.qWait(300)
        click(win, shown(win, "amount_until"))            # the Until list, then its entry, with the mouse
        click(win, next(it for it in items(win) if it.isVisible() and it.metaObject().className().startswith("QQuickText")
                        and str(it.property("text")).startswith("Next marker")))
        QTest.keyClick(win, Qt.Key_Return)
        QTest.qWait(400)
        QTest.keyClick(win, Qt.Key_A, Qt.ControlModifier)
        QTest.qWait(300)
        assert b.selectedIds and len(_on(b, "piano")) == len(b.selectedIds), "Ctrl+A after a pick in a list took other tracks"
        assert b.roll["id"] == "piano", "the Editor left its track"
    finally:
        screen.close()
