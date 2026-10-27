"""Repeat's box (the kit's amounts popover): a choice picked from its Until list with the mouse, then Return, keeps the
session (ONE "Repeat" step in the history, the box closes) -- critic r9: the picked field kept the keys and its own
Return opened the list again, so nothing was kept. A preview that fails ends the whole gesture (nothing half-open).
Real input on the real window (offscreen): Ctrl+R, a click on the list's entry, the Return key; the bridge only read."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Document  # noqa: E402
from rostrum_gui.pointer import wait_until  # noqa: E402
from rostrum_sound import KIND, run_source  # noqa: E402
from screensound import playback  # noqa: E402
from rostrum_gui.meta import class_name  # noqa: E402
from screensound.files_sound import ITEM  # noqa: E402
from test_amounts_popover import click, items, shown  # noqa: E402
from test_screen import FakeEngine  # noqa: E402

SRC = '''
tempo(120); beats_per_bar(4)
lead = track("lead", builtIn="feltPiano")
for i in range(%d):
    lead.note("C4", at=beat(i), dur=beats(1))
marker("Reveal", at=bar(6))
'''


def opened(tmp_path, monkeypatch, count):
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(playback, "open_engine", FakeEngine)
    folder = tmp_path / "A"
    doc = Document.new(KIND, folder=folder, item=ITEM)
    doc.run_script("song.py", run_source(SRC % count, "song.py"))
    doc.save()
    import main as soundmain
    screen = soundmain.Screen((1646, 900))
    assert screen.files.openPath(str(folder))
    QTest.qWait(300)
    b = screen.bridge
    b.pickMany([f"lead.n{500 * i}" for i in range(count)])   # set-up: the notes selected
    QTest.qWait(400)
    return screen, b


def repeats(doc):
    return [c.label for c in doc.history.changes if c.label.startswith("Repeat")]


def open_box(screen, entry_text=None):
    """Ctrl+R, then (when asked) the real Until field and a click on one entry of its list."""
    win = screen.win
    QTest.keyClick(win, Qt.Key_R, Qt.ControlModifier)
    QTest.qWait(300)
    if entry_text:
        click(win, shown(win, "amount_until"))
        click(win, next(it for it in items(win) if it.isVisible() and class_name(it).startswith("QQuickText")
                        and str(it.property("text")).startswith(entry_text)))


def closed_clean(b):
    return b.doc._gesture is None


def test_pick_then_return_keeps_one_repeat(tmp_path, monkeypatch):
    for count, entry in ((12, "Next marker"), (4, "Next marker")):
        screen, b = opened(tmp_path / f"{count}{entry}".replace(" ", ""), monkeypatch, count)
        try:
            open_box(screen, entry)
            QTest.keyClick(screen.win, Qt.Key_Return)
            wait_until(lambda: len(repeats(b.doc)) == 1, f"Return keeps Repeat once ({count} notes, {entry})")
            QTest.qWait(300)
            assert len(repeats(b.doc)) == 1 and closed_clean(b) and not b.actions.amounts.live
        finally:
            screen.close()
            QTest.qWait(50)


def test_esc_after_a_pick_and_a_second_ctrl_r_keeps_nothing(tmp_path, monkeypatch):
    screen, b = opened(tmp_path, monkeypatch, 12)
    try:
        open_box(screen, "Next marker")
        open_box(screen)                       # Ctrl+R again with the box open: starts again on the original notes
        assert not b.actions.amounts.live or "n8000" not in screen.bridge.status
        QTest.keyClick(screen.win, Qt.Key_Escape)
        QTest.qWait(300)
        assert repeats(b.doc) == [] and closed_clean(b)
    finally:
        screen.close()
        QTest.qWait(50)
