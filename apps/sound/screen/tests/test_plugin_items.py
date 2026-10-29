"""A plugin's item in a song ("wiggle:generator": a kind this Rostrum doesn't have, kept in the file byte for byte, never
played) is a plain row in the arrangement that a person can lock, mute, move and delete with the real mouse and keys, each
step undone to exactly what it was; after a save and reopen every field the plugin wrote is as it was. Real input on the
real window's QML (offscreen): the real header, its M button, Ctrl+Shift+L, Delete, Ctrl+Z; the bridge is only read.
The engine is a stand-in."""
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core.storage import canonical, paths  # noqa: E402
from rostrum_sound import KIND  # noqa: E402
from screensound import playback  # noqa: E402
from screensound.files_sound import ITEM  # noqa: E402
from test_amounts_popover import centre, items  # noqa: E402
from test_screen import FakeEngine  # noqa: E402
from test_song_swap import song  # noqa: E402

PLUGIN = {"id": "wig1", "type": "wiggle:generator", "name": "Wobble", "wiggle:cfg": {"a": [1, {"b": None}], "c": 1.5e300},
          "odd": [True, None, "é", 0.1], "deep": {"x": {"y": []}}}
CHILD = {"id": "wc", "type": "wiggle:clip", "at": 2, "x": {"y": []}}
# Two budgets (Sam, 2026-10-27): only direct manipulation (the drag's move steps) owes a frame; a discrete action (click, M,
# Ctrl+Shift+L, Delete, Ctrl+Z, the drop) only has to feel instant: visible reaction at once, nothing stalls over ~0.2 s.
# Measured in real ms: the first click on a cold window (builds the selection's look) 44-125 ms, the rest 1-35 ms.
DISCRETE_MS = 200
DRAG_STEP_MS = 50        # a frame is ~16 ms; headroom for a loaded laptop


def timed(fn):
    start = time.perf_counter()
    fn()
    return (time.perf_counter() - start) * 1000


def header(win, track_id):
    return next(h for h in items(win) if h.objectName() == "trackHeader" and h.isVisible()
                and h.property("track")["id"] == track_id)


def inside(win, outer, name):
    box = outer.mapRectToScene(outer.boundingRect())
    return next(i for i in items(win) if i.objectName() == name and i.isVisible()
                and box.contains(i.mapRectToScene(i.boundingRect()).center()))


def click(win, it):
    at = centre(it)
    QTest.mouseMove(win, at)
    return timed(lambda: QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at))


def key(win, k, mods=Qt.NoModifier):
    ms = timed(lambda: QTest.keyClick(win, k, mods))
    QTest.qWait(150)
    return ms


def test_a_plugin_item_can_be_locked_muted_moved_and_deleted(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(playback, "open_engine", FakeEngine)
    folder = song(tmp_path / "S")
    p = paths(folder, ITEM, KIND.ext)
    f = json.loads(p["doc"].read_text(encoding="utf-8"))
    f["doc"]["tracks"].append(json.loads(json.dumps(PLUGIN)))
    f["doc"]["tracks"][0]["clips"] = [json.loads(json.dumps(CHILD))]
    p["doc"].write_text(json.dumps(f), encoding="utf-8")
    import main as soundmain
    screen = soundmain.Screen((1646, 900))
    slowest = drag_slowest = 0.0
    try:
        assert screen.files.openPath(str(folder))
        QTest.qWait(400)
        b, win = screen.bridge, screen.win
        order = lambda: [t["id"] for t in b.doc.data["tracks"]]  # noqa: E731
        assert order() == ["lead", "wig1"]

        slowest = max(slowest, click(win, header(win, "wig1")))              # select it: the real header row
        QTest.qWait(150)
        assert b.selectedIds == ["wig1"], b.status

        slowest = max(slowest, key(win, Qt.Key_L, Qt.ControlModifier | Qt.ShiftModifier))      # Lock
        assert b.doc.item("wig1")["locked"] is True, b.status
        key(win, Qt.Key_Z, Qt.ControlModifier)
        assert b.doc.item("wig1") == PLUGIN                                  # undone: exactly as it was

        slowest = max(slowest, click(win, inside(win, header(win, "wig1"), "trackMute")))      # Mute (hide from play)
        QTest.qWait(150)
        assert b.doc.item("wig1")["mute"] is True, b.status
        key(win, Qt.Key_Z, Qt.ControlModifier)
        assert b.doc.item("wig1") == PLUGIN

        up, mid = header(win, "lead"), header(win, "wig1")                   # Move: drag its header above the first row
        r_up, r_mid = up.mapRectToScene(up.boundingRect()), mid.mapRectToScene(mid.boundingRect())
        top = QPoint(round(r_up.x() + r_up.width() * 0.8), round(r_up.y() + 3))      # upper edge of the first row
        a = QPoint(round(r_mid.x() + r_mid.width() * 0.8), round(r_mid.y() + 8))     # the name line, clear of the buttons
        QTest.mouseMove(win, a)
        QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, a)
        for step in range(1, 7):
            drag_slowest = max(drag_slowest, timed(lambda: QTest.mouseMove(
                win, QPoint(a.x(), round(a.y() + (top.y() - a.y()) * step / 6)))))
            QTest.qWait(20)
        slowest = max(slowest, timed(lambda: QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, top)))
        QTest.qWait(200)
        assert order() == ["wig1", "lead"], (order(), b.status)
        key(win, Qt.Key_Z, Qt.ControlModifier)
        assert order() == ["lead", "wig1"] and b.doc.item("wig1") == PLUGIN

        click(win, header(win, "wig1"))
        QTest.qWait(150)
        slowest = max(slowest, key(win, Qt.Key_Delete))                      # Delete
        assert "wig1" not in order(), b.status
        key(win, Qt.Key_Z, Qt.ControlModifier)
        assert order() == ["lead", "wig1"] and b.doc.item("wig1") == PLUGIN

        click(win, inside(win, header(win, "wig1"), "trackMute"))            # left muted and locked for the save
        QTest.qWait(150)
        click(win, header(win, "wig1"))
        QTest.qWait(150)
        key(win, Qt.Key_L, Qt.ControlModifier | Qt.ShiftModifier)
        assert {k: v for k, v in b.doc.item("wig1").items() if k not in ("mute", "locked")} == PLUGIN
        assert b.doc.item("wig1")["mute"] is True and b.doc.item("wig1")["locked"] is True
        assert b.doc.item("wc")["type"] == "wiggle:clip"                     # the lane's plugin item is kept too

        assert screen.files.openPath(str(folder))                            # reopened from what was saved
        QTest.qWait(300)
        again = screen.bridge.doc.item("wig1")
        assert {k: v for k, v in again.items() if k not in ("mute", "locked")} == PLUGIN
        assert canonical({k: v for k, v in again.items() if k not in ("mute", "locked")}) == canonical(PLUGIN)
        assert again["mute"] is True and again["locked"] is True
        assert canonical(screen.bridge.doc.item("wc")) == canonical(CHILD)
    finally:
        screen.close()
    print(f"slowest discrete input {slowest:.1f} ms, slowest drag step {drag_slowest:.1f} ms")
    assert slowest < DISCRETE_MS
    assert drag_slowest < DRAG_STEP_MS
