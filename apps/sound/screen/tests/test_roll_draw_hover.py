"""Draw in the roll shows what a click will do, and a click does what it showed (PLAN S1; critic: a click on the empty
step beside a hit deleted the hit, and lost hats and a tom). Real pointer moves and clicks on the real window (offscreen):
- a drum hit is caught only on its diamond: a click on the step beside it adds there, the hit stays;
- a click on a grid line lands in the step after it;
- hovering an empty step shows the hit a click makes, hovering a hit lights it red with the erase pointer;
- on the notes, the faint note sits on the key under the pointer and that key is lit on the keyboard; Draw+Alt click
  erases the note under it."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Document  # noqa: E402
from rostrum_sound import KIND, run_source  # noqa: E402
from screensound import playback  # noqa: E402
from screensound.files_sound import ITEM  # noqa: E402
from test_amounts_popover import items  # noqa: E402
from test_screen import FakeEngine  # noqa: E402

SRC = '''
tempo(120); beats_per_bar(4)
kit = track("kit", kit="drums")
kit.hit("kick", at=beat(0))
kit.hit("hat", at=beat(4))
p = track("piano", builtIn="feltPiano")
p.note(60, at=beat(2), dur=beats(1))
'''


def _input(win):
    return next(i for i in items(win) if i.isVisible() and i.property("drawTool") is not None)


def _beats(h):
    return h["at"]["beat"] if isinstance(h["at"], dict) else h["at"] * 2


def test_draw_shows_what_a_click_does_and_a_hit_is_caught_only_on_its_diamond(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(playback, "open_engine", FakeEngine)
    import main as soundmain
    doc = Document.new(KIND, folder=tmp_path / "A", item=ITEM)
    doc.run_script("song.py", run_source(SRC, "song.py"))
    doc.save()
    screen = soundmain.Screen((1646, 900))
    try:
        assert screen.files.openPath(str(tmp_path / "A"))
        QTest.qWait(300)
        win, b = screen.win, screen.bridge
        b.select("kit")
        b.workspace.setDock("editor")
        b.setTool("draw")
        b.setGrid("1/8")
        b._tv.fitTo(0.0, 4.0)                      # bars 1-2: an 1/8 step is ~40 px
        QTest.qWait(300)
        m = _input(win)
        r = m.mapRectToScene(m.boundingRect())
        start, per = b.viewStart, m.width() / b.viewSpan
        drums = list(b.roll["drums"])
        grid = m.property("grid")
        row_h = grid.property("rowH")
        y = round(r.y() + (drums.index("hat") + 0.5) * row_h)
        x = lambda beat: round(r.x() + (beat * 0.5 - start) * per)            # 120 bpm: half a second a beat  # noqa: E731
        hats = lambda: sorted(_beats(h) for h in b.doc.item("kit")["hits"] if h["drum"] == "hat")  # noqa: E731

        QTest.mouseMove(win, QPoint(x(5) + 10, y))             # an empty step: the hit a click makes, faint
        QTest.qWait(50)
        g = m.property("ghost")
        assert g is not None and abs(g["t"] - 2.5) < 1e-3, g          # beat 5's step (0.5 s a beat)
        assert m.property("pointer") == "draw"
        QTest.mouseMove(win, QPoint(x(4) + 2, y))              # on the hat's diamond: lit red, the erase pointer
        QTest.qWait(50)
        assert m.property("lit") and m.property("pointer") == "erase"

        # beside the hat, on the step before it and off its diamond (the old catch was ~9 px either side, any height)
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, QPoint(x(4) - 7, y + round(row_h * 0.3)))
        QTest.qWait(100)
        assert hats() == [3.5, 4], hats()
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, QPoint(x(6), y))     # exactly on a grid line: the step after
        QTest.qWait(100)
        assert hats() == [3.5, 4, 6], hats()
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, QPoint(x(4) - 3, y))  # the hat's own diamond, left half
        QTest.qWait(100)
        assert hats() == [3.5, 6], hats()                       # only that hit, never the step before's

        b.select("piano")                                       # the notes: the ghost on the key, the key lit
        QTest.qWait(300)
        m = _input(win)
        grid = m.property("grid")
        row_h, hi = grid.property("rowH"), grid.property("roll")["hi"]
        view = grid.parentItem().parentItem()
        top = r.y() - view.property("contentY")
        yk = lambda key: round(top + (hi - key + 0.5) * row_h)  # noqa: E731
        start, per = b.viewStart, m.width() / b.viewSpan
        QTest.mouseMove(win, QPoint(x(6) + 5, yk(64)))
        QTest.qWait(50)
        assert m.property("ghost") is not None and grid.property("litKey") == 64
        QTest.mouseMove(win, QPoint(x(2) + 15, yk(60)))         # on the note's body: the pick pointer
        QTest.qWait(50)
        assert m.property("pointer") == "pick" and m.property("ghost") is None
        QTest.mouseClick(win, Qt.LeftButton, Qt.AltModifier, QPoint(x(2) + 16, yk(60)))   # Draw+Alt: erase it
        QTest.qWait(100)
        assert b.doc.item("piano").get("notes", []) == []
    finally:
        screen.close()
        QTest.qWait(50)
