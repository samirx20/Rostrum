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
from rostrum_gui.pointer import hover, wait_until  # noqa: E402
from rostrum_gui.settle import grab_settled  # noqa: E402
from screensound import playback  # noqa: E402
from test_amounts_popover import items, shown  # noqa: E402
from test_screen import FakeEngine  # noqa: E402
from test_song_swap import song  # noqa: E402


def _rows(menu):
    return [e["value"] for e in menu.property("entries")]


def _drawn(win, ready=None):
    """The window drawn until it holds still (and `ready()` is true): a click lands where the picture is."""
    grab_settled(win, ready=ready)


def _opened(menu, want=True):
    wait_until(lambda: bool(menu.property("opened")) == want, f"the marker menu to be {'open' if want else 'closed'}")
    if not want:       # closed means gone from the screen: a click during its fade-out is taken by the menu, not the tag
        wait_until(lambda: not menu.property("visible"), "the marker menu to finish fading out")


def _tag_point(band, t):
    r = band.mapRectToScene(band.boundingRect())
    ruler = band.property("ruler")
    return QPoint(round(r.x() + (t - ruler.property("start")) * ruler.property("perSec")) + 6, round(r.y() + r.height() / 2))


def _right_click_tag(win, band, t):
    at = _tag_point(band, t)
    QTest.mouseMove(win, at)
    QTest.mouseClick(win, Qt.RightButton, Qt.NoModifier, at)
    return at


def test_right_click_a_marker_then_delete_and_move_absent_when_there(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(playback, "open_engine", FakeEngine)
    import main as soundmain
    screen = soundmain.Screen((1646, 900))
    try:
        assert screen.files.openPath(str(song(tmp_path / "A")))
        win, b = screen.win, screen.bridge
        wait_until(lambda: b.song and b.song.get("bars") and len(b.song["bars"]) > 3, "the song to open with its bars")
        bars = b.song["bars"]
        b.doc.apply([{"op": "marker.add", "args": {"name": "drop", "at": round(bars[1], 4)}},
                     {"op": "marker.add", "args": {"name": "end", "at": round(bars[3], 4)}}], Who.person())
        _drawn(win, lambda: len(b._view["markers"]) == 2)
        band = shown(win, "markerBand")
        _right_click_tag(win, band, bars[1])
        menu = band.findChild(QObject, "markerMenu")
        _opened(menu)
        rows = _rows(menu)
        assert rows[0] == "marker.rename" and "marker.move" in rows and "loop_next" in rows, rows
        assert rows[-1] == "marker.remove" and any(v.startswith("colour:") for r in menu.property("entries")
                                                   for v in [r["value"], *[s["value"] for s in r.get("sub") or []]])
        QTest.keyClick(win, Qt.Key_Escape)
        _opened(menu, False)
        at = _tag_point(band, bars[1])
        hover(win, at)                                                   # arrive by moving, as a hand does
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at)          # a click on the tag: the playhead on it
        wait_until(lambda: abs(b.time - bars[1]) < 1e-3, f"the playhead to reach the marker at {bars[1]} (is {b.time})")
        _right_click_tag(win, band, bars[1])
        _opened(menu)
        assert "marker.move" not in _rows(menu)
        steps = len(b.doc.history.changes)
        _drawn(win)
        row = next(it for it in items(win) if it.isVisible() and it.property("text") == "Delete marker")
        r = row.mapRectToScene(row.boundingRect())
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, QPoint(round(r.center().x()), round(r.center().y())))
        wait_until(lambda: [m["name"] for m in b.doc.data["markers"]] == ["end"],
                   f"Delete marker to remove it (markers now {[m['name'] for m in b.doc.data['markers']]})")
        assert [m["name"] for m in b.doc.data["markers"]] == ["end"]
        assert len(b.doc.history.changes) == steps + 1
    finally:
        screen.close()
