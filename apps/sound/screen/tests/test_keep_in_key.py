"""Keep notes in the key (spec workflow 6): with it on from the In key ▾ chip, a real Draw click on an out-of-key row
adds the note on the nearest in-key row; with it off the note lands where it was clicked. Real input on the real
window's QML (offscreen): the real chip, menu row and roll, the real mouse; the bridge is only read. The engine is a
stand-in."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Who  # noqa: E402
from screensound import playback  # noqa: E402
from test_amounts_popover import click, shown  # noqa: E402
from test_screen import FakeEngine  # noqa: E402
from test_song_swap import rolls, song  # noqa: E402


def draw_on(screen, key, fx):
    """A real Draw click on the roll's row of `key` (a MIDI number); the new note's pitch."""
    b, win = screen.bridge, screen.win
    [roll] = rolls(win)
    grid = roll.property("grid")
    top = grid.mapToScene(QPoint(0, 0))
    r = roll.mapRectToScene(roll.boundingRect())
    at = QPoint(round(r.x() + r.width() * fx), round(top.y() + (grid.property("roll")["hi"] - key + 0.5) * grid.property("rowH")))
    QTest.mouseMove(win, at)
    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at)
    QTest.qWait(200)
    return b.doc.item(b.selectedIds[0])["pitch"]


def test_keep_in_key_puts_a_drawn_note_on_the_nearest_key_row(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(playback, "open_engine", FakeEngine)
    import main as soundmain
    screen = soundmain.Screen((1646, 900))
    try:
        assert screen.files.openPath(str(song(tmp_path / "A")))
        b, win = screen.bridge, screen.win
        b.doc.apply([{"op": "key.add", "target": [], "args": {"at": 0, "key": "D minor"}}], Who.person())
        b.select("lead")
        b.workspace.setDock("editor")
        b.setTool("draw")
        QTest.qWait(300)
        click(win, shown(win, "inKeyChip"))
        click(win, shown(win, "menu:keep"))                 # the chip's first row: Keep notes in the key
        assert b.keepInKey and b.inKeyChip["label"] == "In key"
        drawn = draw_on(screen, 61, 0.3)                    # C#4: a half step from C4 and D4, a tie goes down
        assert drawn in ("C4", 60), drawn
        click(win, shown(win, "inKeyChip"))
        click(win, shown(win, "menu:keep"))                 # off again: the note lands where it was clicked
        assert not b.keepInKey and b.inKeyChip["label"] == "Key: D minor"
        assert draw_on(screen, 61, 0.6) in ("C#4", 61)
    finally:
        screen.close()
        QTest.qWait(50)
