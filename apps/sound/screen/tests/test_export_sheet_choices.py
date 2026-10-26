"""The Export sheet never sends out the wrong file (critic r8): a choice keeps its value when another one changes
(Stems stays "Mix and stems" after the target is changed), and a list never opens with an entry under the press that
opened it (a release there once picked Apple Music for Streaming). Real mouse input on the visible controls; the bridge
is only read. The engine is a stand-in."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from screensound import playback  # noqa: E402
from test_amounts_popover import centre, click, items, shown  # noqa: E402
from test_screen import FakeEngine  # noqa: E402
from test_song_swap import song  # noqa: E402


def sheet(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(playback, "open_engine", FakeEngine)
    import main as soundmain
    screen = soundmain.Screen((1646, 900))
    assert screen.files.openPath(str(song(tmp_path / "A")))
    QTest.qWait(300)
    screen.parts["mixer"].export.setDialogOpen(True)
    QTest.qWait(300)
    return screen, screen.parts["mixer"].export


def entries(win):
    """The open list's entries as (label, scene rect), read from the visible rows."""
    lst = shown(win, "choiceList")
    out = []
    for it in items(win):
        if it.isVisible() and it.width() > 0 and lst.isAncestorOf(it) and hasattr(it, "property") and it.property("option") is not None:
            out.append((it.property("option"), it.mapRectToScene(it.boundingRect())))
    return out


def pick(win, field, index):
    """Open a field by a click and click its `index`th entry."""
    click(win, shown(win, field))
    rows = sorted(entries(win), key=lambda e: e[1].y())
    at = QPoint(round(rows[index][1].center().x()), round(rows[index][1].center().y()))
    QTest.mouseMove(win, at)
    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at)
    QTest.qWait(250)


def test_stems_stay_chosen_when_the_target_changes(tmp_path, monkeypatch):
    screen, job = sheet(tmp_path, monkeypatch)
    try:
        win = screen.win
        pick(win, "exportStems", 1)
        assert job.stemsMode == "all"
        for k in (1, 2, 0):
            pick(win, "exportTarget", k)
            assert job.stemsMode == "all", f"stems fell back after picking target entry {k}"
    finally:
        screen.close()
        QTest.qWait(50)


def test_a_press_and_release_on_the_target_field_picks_nothing(tmp_path, monkeypatch):
    screen, job = sheet(tmp_path, monkeypatch)
    try:
        win = screen.win
        before = (job.choice, job.stemsMode)
        field = shown(win, "exportTarget")
        at = centre(field)
        QTest.mouseMove(win, at)
        QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, at)
        QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, at)      # the click that opens the list
        QTest.qWait(250)
        rows = entries(win)
        assert rows and not any(r.contains(at.x(), at.y()) for _, r in rows), "an entry lies under the press point"
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at)        # a second click on the same spot picks nothing
        QTest.qWait(250)
        assert (job.choice, job.stemsMode) == before
    finally:
        screen.close()
        QTest.qWait(50)


def test_a_new_window_starts_from_what_the_last_export_chose(tmp_path, monkeypatch):
    """Critic r8 M6: each window's sheet started at "Only the mix", so the export after reopening went out without stems.
    The sheet starts from the newest export's manifest (the run's first version; an extra version carries no stems)."""
    import json
    folder = song(tmp_path / "A")
    base = folder / "renders" / "song"
    for v, stems in ((1, {"lead": {"file": "lead.wav"}}), (2, {})):          # one Export run: the first with stems
        (base / f"v{v:03d}").mkdir(parents=True)
        (base / f"v{v:03d}" / "manifest.json").write_text(json.dumps(
            {"version": v, "source": {"document": "song", "history_entry": 1}, "format": {"id": "wav24"},
             "trimmed_silence": False, **({"stems": stems} if stems else {})}), encoding="utf-8")
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(playback, "open_engine", FakeEngine)
    import main as soundmain
    screen = soundmain.Screen((1646, 900))
    try:
        assert screen.files.openPath(str(folder))
        QTest.qWait(300)
        QTest.keyClick(screen.win, Qt.Key_E, Qt.ControlModifier)            # the sheet, by its key
        QTest.qWait(300)
        job = screen.parts["mixer"].export
        assert (job.stemsMode, job.format, job.trim) == ("all", "wav24", False)
    finally:
        screen.close()
        QTest.qWait(50)
