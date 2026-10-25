"""The drum step tool (spec § 3.8): a real mouse drag with the Draw tool along the Hat row paints one hit per grid step
it passes, and one undo takes them all away; a click on a hit removes it. Real input on the real window's QML
(offscreen): press, move and release on the real roll; the bridge is only read (the history's undo is the check).
The engine is a stand-in."""
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
from test_song_swap import rolls  # noqa: E402

SRC = '''
tempo(120); beats_per_bar(4)
kit = track("kit", kit="drums")
kit.hit("kick", at=beat(0))
kit.hit("snare", at=beat(1))
'''


def test_a_drag_along_the_hat_row_paints_one_hit_per_step_and_one_undo_removes_them(tmp_path, monkeypatch):
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
        b.setGrid("beat")
        QTest.qWait(300)
        [roll] = rolls(win)
        r = roll.mapRectToScene(roll.boundingRect())
        ruler = next(it for it in items(win) if it.objectName() == "barRuler" and it.isVisible()
                     and abs(it.mapRectToScene(it.boundingRect()).x() - r.x()) < 2)
        per, start = ruler.property("perSec"), ruler.property("start")
        drums = list(b.roll["drums"])
        row_h = r.height() / len(drums)
        y = round(r.y() + (drums.index("hat") + 0.5) * row_h)
        x = lambda beat: round(r.x() + (beat * 0.5 - start) * per) + 4          # 120 bpm: half a second a beat  # noqa: E731
        d = b.doc
        before, hits = len(d.history.changes), len(d.item("kit")["hits"])
        QTest.mouseMove(win, QPoint(x(4), y))
        QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, QPoint(x(4), y))
        for beat in (4.4, 5, 5.5, 6, 6.5, 7):
            QTest.mouseMove(win, QPoint(x(beat), y))
            QTest.qWait(10)
        QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, QPoint(x(7), y))
        QTest.qWait(100)
        new = [h for h in d.item("kit")["hits"] if h["drum"] == "hat"]
        assert sorted(h["at"]["beat"] if isinstance(h["at"], dict) else h["at"] * 2 for h in new) == [4, 5, 6, 7], new
        assert len(d.history.changes) == before + 1                              # one stroke, one step
        b.undo()
        assert len(d.item("kit")["hits"]) == hits
        # a click on a step adds one; a click on that hit removes it again
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, QPoint(x(9), y))
        QTest.qWait(100)
        assert len(d.item("kit")["hits"]) == hits + 1
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, QPoint(x(9), y))
        QTest.qWait(100)
        assert len(d.item("kit")["hits"]) == hits
    finally:
        screen.close()
        QTest.qWait(50)


def test_fill_row_counts_grid_steps_and_hit_fill_gets_beats():
    from screensound import amount_actions as A
    from types import SimpleNamespace as NS
    f = NS(doc=NS(data={"tempo": 120, "beatsPerBar": 4}), fill={"track": "kit", "drum": "hat", "from": 0.0, "to": 2.0, "step": 0.5})
    args = A.fill_calls(f, {"every": 2, "offset": 2, "vel": 0.8, "accentEvery": 4})[0]["args"]
    assert (args["every"], args["offset"], args["accentEvery"]) == (1.0, 0.5, 2.0), args       # 1/8 grid: a step is half a beat
