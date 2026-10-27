"""A reopened song shows the view it was closed with: the stretch of time (zoom, scroll) and each track's piano-roll
keys (critic r12 must-fix 2: the roll came back at bars 1-10 and another height, so the next click made a wrong note
at a wrong bar). The Editor's working zoom leaves a view the song was closed with in the Editor."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtGui import QGuiApplication  # noqa: E402
from rostrum_core import Document  # noqa: E402
from rostrum_sound import KIND, run_source  # noqa: E402
from screensound import playback  # noqa: E402
from screensound.bridge import SoundBridge  # noqa: E402
from screensound.files_sound import ITEM  # noqa: E402
from test_screen import FakeEngine  # noqa: E402

SRC = '''
a = track("bass", builtIn="feltPiano")
b = track("lead", builtIn="feltPiano")
for i in range(40):
    a.note(36 + i % 12, at=beat(i * 2), dur=beats(1))
    b.note(67 + i % 5, at=beat(i * 2), dur=beats(1))
'''


def _open(folder):
    b = SoundBridge(Document.open(folder, ITEM, KIND))
    return b


def test_view_and_each_tracks_keys_come_back_after_a_reopen(tmp_path, monkeypatch):
    QGuiApplication.instance() or QGuiApplication([])
    monkeypatch.setattr(playback, "open_engine", FakeEngine)
    doc = Document.new(KIND, folder=tmp_path / "S", item=ITEM)
    doc.run_script("song.py", run_source(SRC, "song.py"))
    doc.save()
    b = _open(tmp_path / "S")
    b.workspace.setDock("editor")
    bars = b.song["bars"]
    b._tv.fitTo(bars[0], bars[15])                     # zoomed out to ~bars 1-15 in the Editor, then scrolled a bit
    b.setViewStart(bars[1])
    start, span = b.viewStart, b.viewSpan
    b.keepRollPlace("bass/notes", 38, 5.0)             # PianoRoll's `kept`: the key at the view's middle, into its row
    b.keepRollPlace("lead/notes", 70, 2.5)
    b._close_view()
    b.close()

    again = _open(tmp_path / "S")                      # reopened: the same view before anything is shown
    assert (again.viewStart, again.viewSpan) == (pytest.approx(start, abs=1e-3), pytest.approx(span, abs=1e-3))
    assert again.rollPlaces == {"bass/notes": [38, 5.0], "lead/notes": [70, 2.5]}
    again.workspace.setDock("editor")                  # a click on the track opens the Editor: its working zoom keeps it
    assert (again.viewStart, again.viewSpan) == (pytest.approx(start, abs=1e-3), pytest.approx(span, abs=1e-3))
    again.close()


def test_a_reopened_song_shows_the_roll_where_it_was_left(tmp_path, monkeypatch):
    """The same, through the real window: wheel on the roll, Ctrl+wheel to zoom, then the song closed and reopened."""
    from PySide6.QtCore import QPoint
    from PySide6.QtTest import QTest
    from test_amounts_popover import click
    from test_plugin_items import header
    from test_roll_keeps_rows import _grid, _middle, _wheel
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(playback, "open_engine", FakeEngine)
    for name in ("S", "T"):
        doc = Document.new(KIND, folder=tmp_path / name, item=ITEM)
        doc.run_script("song.py", run_source(SRC, "song.py"))
        doc.save()
    import main as soundmain
    screen = soundmain.Screen((1646, 900))

    def roll_open():
        assert screen.files.openPath(str(tmp_path / "S"))
        QTest.qWait(400)
        click(screen.win, header(screen.win, "bass"))
        screen.bridge.workspace.setDock("editor")
        QTest.qWait(400)
        g = _grid(screen.win)
        return g.mapRectToScene(g.boundingRect())
    try:
        r = roll_open()
        b = screen.bridge
        fresh = (_middle(screen.win), round(b.viewStart, 3), round(b.viewSpan, 3))
        _wheel(screen.win, QPoint(round(r.x() + r.width() / 2), 700), 4)       # the roll scrolled up and down
        screen.bridge.zoomAt(0.6, 0.5)                                          # and zoomed out
        QTest.qWait(300)
        b = screen.bridge
        left = (_middle(screen.win), round(b.viewStart, 3), round(b.viewSpan, 3))
        assert left[0] != fresh[0] and left[2] > fresh[2]                       # the person did move it
        assert screen.files.openPath(str(tmp_path / "T"))                      # another song, then this one again
        QTest.qWait(400)
        roll_open()
        b = screen.bridge
        assert (_middle(screen.win), round(b.viewStart, 3), round(b.viewSpan, 3)) == left
    finally:
        screen.close()
