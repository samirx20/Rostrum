"""A click in the Editor lands where the person aims (critic r8 M5: the flash hit came out a beat late; the end-card
chord landed early; Snap ignored the markers). Real input on the real window's QML (offscreen): the real E and B
keys, real Draw clicks on the roll, a real click on Snap; the bridge is read to verify (and selects the track first).
- the Editor opens at a working zoom (about 8 bars), not the whole song;
- at three zooms a Draw click on the drawn bar line writes on it (Snap on), and with Snap off within 1 px of the
  pointer;
- with Snap on, a click a few px beside a marker writes on the marker, off the grid."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Document  # noqa: E402
from rostrum_sound import KIND, run_source  # noqa: E402
from screensound import playback, timing  # noqa: E402
from screensound.files_sound import ITEM  # noqa: E402
from test_amounts_popover import click, shown  # noqa: E402
from test_screen import FakeEngine  # noqa: E402
from test_song_swap import rolls  # noqa: E402

FLASH = 52.31                      # off every grid line (120 bpm: a 1/16 is 0.125 s), well clear of bar 27 (52.0)
SRC = f'''
tempo(120); beats_per_bar(4)
lead = track("lead", builtIn="feltPiano")
lead.note("C4", at=beat(0), dur=beats(1))
lead.note("G4", at=beat(120), dur=beats(1))
marker("flash", at={FLASH})
'''


def song(folder: Path) -> Path:
    doc = Document.new(KIND, folder=folder, item=ITEM)
    doc.run_script("song.py", run_source(SRC, "song.py"))
    doc.save()
    return folder


def draw(win, b, x, key_row_y):
    """A real Draw click at window x; the new note's start (seconds), then Ctrl+Z takes it away."""
    before = {n["id"] for n in b.doc.item("lead")["notes"]}
    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, QPoint(x, key_row_y))
    QTest.qWait(60)
    new = [n for n in b.doc.item("lead")["notes"] if n["id"] not in before]
    assert len(new) == 1, new
    QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier)
    QTest.qWait(60)
    return timing.sec(new[0]["at"], b.doc.data, new[0]["id"])


def test_a_click_lands_where_the_person_aims(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(playback, "open_engine", FakeEngine)
    import main as soundmain
    screen = soundmain.Screen((1646, 900))
    try:
        assert screen.files.openPath(str(song(tmp_path / "A")))
        b, win = screen.bridge, screen.win
        QTest.qWait(300)
        bars = b.song["bars"]
        b.select("lead")
        b.setTime(bars[26] + 0.3)                                     # the playhead in bar 27
        QTest.qWait(100)
        assert b.viewSpan > bars[16] - bars[0]                         # the whole song shows
        QTest.keyClick(win, Qt.Key_E)                                  # the Editor opens ...
        QTest.qWait(300)
        assert b.viewSpan <= (bars[8] - bars[0]) * 1.3 + 1e-6, b.viewSpan     # ... on about 8 bars (and 15 % each side)
        assert b.viewStart <= b.time <= b.viewStart + b.viewSpan
        QTest.keyClick(win, Qt.Key_B)                                  # Draw
        QTest.qWait(50)
        [roll] = rolls(win)
        ruler = roll.property("bars")
        rr = ruler.mapRectToScene(ruler.boundingRect())
        y = round(rr.bottom() + 40)                                    # a key row near the roll's top
        ox = rr.x()                                                    # the roll's x 0 is its ruler's x 0

        def x_of(t):                                                   # where the roll draws time t (whole pixel)
            return round(ox + (t - ruler.property("start")) * ruler.property("perSec"))

        for zoom in range(3):
            if zoom:
                b.zoomAt(1.6, 0.5)
                b.setViewStart(bars[26] - 1.0)
                QTest.qWait(80)
            per = ruler.property("perSec")
            line = bars[26]                                            # bar 27's line, as drawn
            got = draw(win, b, x_of(line), y)
            assert abs(got - line) < 1e-6, (zoom, per, got, line)
            got = draw(win, b, x_of(FLASH) + 4, y)                     # 4 px past the marker: caught by it
            assert abs(got - FLASH) < 1e-6, (zoom, per, got)
        click(win, shown(win, "snapButton"))                           # Snap off: exactly under the pointer
        assert not b.snapOn
        for dx in (3, 17, 40):
            x = x_of(bars[26]) + dx
            got = draw(win, b, x, y)
            assert abs((got - ruler.property("start")) * ruler.property("perSec") + ox - x) <= 1.0, (dx, got)
    finally:
        screen.close()
        QTest.qWait(50)
