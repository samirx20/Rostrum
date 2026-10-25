"""A song marker's right-click menu by real input (sound-pro-workflows SPEC § 3.7): right-click the real tag, the kit's
marker menu opens with Sound's rows; Move to playhead is absent when the playhead is already on the marker; Delete
clicked in the real menu removes it as one step. Offscreen window, real mouse; the bridge is only read (the markers are
written into the song as set-up). The engine is a stand-in."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QObject, QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Who  # noqa: E402
from screensound import playback  # noqa: E402
from test_amounts_popover import items, shown  # noqa: E402
from test_screen import FakeEngine  # noqa: E402
from test_song_swap import song  # noqa: E402


def _rows(menu):
    return [e["value"] for e in menu.property("entries")]


def _right_click_tag(win, band, t):
    r = band.mapRectToScene(band.boundingRect())
    ruler = band.property("ruler")
    at = QPoint(round(r.x() + (t - ruler.property("start")) * ruler.property("perSec")) + 6, round(r.y() + r.height() / 2))
    QTest.mouseMove(win, at)
    QTest.mouseClick(win, Qt.RightButton, Qt.NoModifier, at)
    QTest.qWait(150)
    return at


def test_right_click_a_marker_then_delete_and_move_absent_when_there(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(playback, "open_engine", FakeEngine)
    import main as soundmain
    screen = soundmain.Screen((1646, 900))
    try:
        assert screen.files.openPath(str(song(tmp_path / "A")))
        QTest.qWait(300)
        win, b = screen.win, screen.bridge
        bars = b.song["bars"]
        b.doc.apply([{"op": "marker.add", "args": {"name": "drop", "at": round(bars[1], 4)}},
                     {"op": "marker.add", "args": {"name": "end", "at": round(bars[3], 4)}}], Who.person())
        QTest.qWait(200)
        band = shown(win, "markerBand")
        _right_click_tag(win, band, bars[1])
        menu = band.findChild(QObject, "markerMenu")
        assert menu.property("opened")
        rows = _rows(menu)
        assert rows[0] == "marker.rename" and "marker.move" in rows and "loop_next" in rows, rows
        assert rows[-1] == "marker.remove" and any(v.startswith("colour:") for r in menu.property("entries")
                                                   for v in [r["value"], *[s["value"] for s in r.get("sub") or []]])
        QTest.keyClick(win, Qt.Key_Escape)
        QTest.qWait(100)
        assert not menu.property("opened")
        at = _right_click_tag(win, band, bars[1])
        QTest.keyClick(win, Qt.Key_Escape)
        QTest.qWait(100)
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at)          # a click on the tag: the playhead on it
        QTest.qWait(100)
        assert abs(b.time - bars[1]) < 1e-3
        _right_click_tag(win, band, bars[1])
        assert "marker.move" not in _rows(menu)
        steps = len(b.doc.history.changes)
        row = next(it for it in items(win) if it.isVisible() and it.property("text") == "Delete marker")
        r = row.mapRectToScene(row.boundingRect())
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, QPoint(round(r.center().x()), round(r.center().y())))
        QTest.qWait(150)
        assert [m["name"] for m in b.doc.data["markers"]] == ["end"]
        assert len(b.doc.history.changes) == steps + 1
    finally:
        screen.close()
        QTest.qWait(50)
