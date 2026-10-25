"""The amounts popover (the kit's base A, Sound's Humanise ▾): what would break silently. Moving its slider changes the
notes live, and Enter keeps the whole session as ONE history step that Undo takes back exactly; Esc after live changes
leaves the song as it was (the history count unchanged). Real input on the real window's QML (offscreen): the real ▾,
the real slider, the real Enter / Esc / Ctrl+Z keys; the bridge is only read. The engine is a stand-in."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from screensound import playback  # noqa: E402
from test_screen import FakeEngine  # noqa: E402
from test_song_swap import song  # noqa: E402

NOTES = ["lead.n0", "lead.n16000"]


def items(win):
    """Every item in the window, popups' overlay included."""
    root = win.contentItem()
    while root.parentItem() is not None:
        root = root.parentItem()
    out, todo = [], [root]
    while todo:
        it = todo.pop()
        out.append(it)
        todo += it.childItems()
    return out


def shown(win, name):
    for it in items(win):
        if it.objectName() == name and it.isVisible() and it.width() > 0:
            return it
    raise AssertionError(f"{name} is not on screen")


def centre(it, fx=0.5):
    r = it.mapRectToScene(it.boundingRect())
    return QPoint(round(r.x() + r.width() * fx), round(r.y() + r.height() / 2))


def click(win, it):
    at = centre(it)
    QTest.mouseMove(win, at)
    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at)
    QTest.qWait(150)


def drag_slider(win, row):
    """Press on the row's slider, move along it, let go (the real slider, by the pointer)."""
    slider = next(it for it in items(win) if "Slider" in type(it).__name__ + it.metaObject().className()
                  and _inside(it, row) and it.isVisible())
    a, b = centre(slider, 0.2), centre(slider, 0.8)
    QTest.mouseMove(win, a)
    QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, a)
    for f in (0.35, 0.5, 0.65, 0.8):
        QTest.mouseMove(win, centre(slider, f))
        QTest.qWait(20)
    QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, b)
    QTest.qWait(100)


def _inside(it, row):
    while it is not None:
        if it is row:
            return True
        it = it.parentItem()
    return False


def opened(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(playback, "open_engine", FakeEngine)
    import main as soundmain
    screen = soundmain.Screen((1646, 900))
    assert screen.files.openPath(str(song(tmp_path / "A")))
    QTest.qWait(300)
    b = screen.bridge
    b.pickMany(NOTES)                                       # set-up: the notes selected
    QTest.qWait(400)
    return screen, b


def humanise_live(screen, b):
    """Click Humanise's ▾, drag the Velocity slider: the notes change live, nothing is recorded yet."""
    win, doc = screen.win, b.doc
    before, n = [dict(doc.item(i)) for i in NOTES], len(doc.history.changes)
    click(win, shown(win, "actionAmounts:humanize"))
    shown(win, "amount_timing")                             # the popover is open (its rows)
    drag_slider(win, shown(win, "amount_velocity"))
    assert [doc.item(i) for i in NOTES] != before          # live
    assert len(doc.history.changes) == n                    # nothing kept yet
    return before, n


def test_live_then_enter_is_one_step_and_undo_restores_exactly(tmp_path, monkeypatch):
    screen, b = opened(tmp_path, monkeypatch)
    try:
        doc = b.doc
        before, n = humanise_live(screen, b)
        QTest.keyClick(screen.win, Qt.Key_Return)
        QTest.qWait(150)
        assert len(doc.history.changes) == n + 1
        assert doc.history.changes[-1].label.startswith("Humanise · 2 notes · ")
        QTest.keyClick(screen.win, Qt.Key_Z, Qt.ControlModifier)
        QTest.qWait(150)
        assert [doc.item(i) for i in NOTES] == before
    finally:
        screen.close()
        QTest.qWait(50)


def test_esc_after_live_changes_leaves_the_song_unchanged(tmp_path, monkeypatch):
    screen, b = opened(tmp_path, monkeypatch)
    try:
        doc = b.doc
        before, n = humanise_live(screen, b)
        QTest.keyClick(screen.win, Qt.Key_Escape)
        QTest.qWait(150)
        assert len(doc.history.changes) == n
        assert [doc.item(i) for i in NOTES] == before
    finally:
        screen.close()
        QTest.qWait(50)
