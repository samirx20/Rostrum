"""Paste and Duplicate show what they made (critic r12 should-fix 6, PLAN S5): the pasted notes far out of view, the
view slides just enough to show them; already in view, it doesn't move. A copy outlives the app: the next run pastes it
(Ctrl+V after a restart did nothing and said nothing)."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Document  # noqa: E402
from rostrum_sound import KIND, run_source  # noqa: E402
from screensound import clipboard, playback  # noqa: E402
from screensound.files_sound import ITEM  # noqa: E402
from test_screen import FakeEngine  # noqa: E402

SRC = '''
tempo(120); beats_per_bar(4)
p = track("piano", builtIn="feltPiano")
for i in range(4):
    p.note(60 + i, at=beat(i), dur=beats(1))
p.note(40, at=beat(120), dur=beats(1))
'''


def test_a_copy_outlives_the_app(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(clipboard, "_KEPT", [])
    board = {"items": [{"kind": "note", "track": "piano", "offset": 0.0, "fields": {"pitch": "C4", "at": {"beat": 0}}}],
             "tracks": ["piano"]}
    clipboard.keep(board)
    monkeypatch.setattr(clipboard, "_KEPT", [])                # the next run: nothing in memory
    assert clipboard.kept() == board


def test_paste_and_duplicate_slide_just_enough_to_show_what_they_made(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(playback, "open_engine", FakeEngine)
    monkeypatch.setattr(clipboard, "_KEPT", [])
    import main as soundmain
    doc = Document.new(KIND, folder=tmp_path / "A", item=ITEM)
    doc.run_script("song.py", run_source(SRC, "song.py"))
    doc.save()
    screen = soundmain.Screen((1646, 900))
    try:
        assert screen.files.openPath(str(tmp_path / "A"))
        QTest.qWait(300)
        win, b = screen.win, screen.bridge
        b.select("piano")
        b.workspace.setDock("editor")
        b._tv.fitTo(0.0, 8.0)                                  # bars 1-4
        QTest.qWait(300)
        first = [n["id"] for n in b.doc.item("piano")["notes"] if n["pitch"] not in (40, "E2")]
        b.pickMany(first)
        QTest.qWait(100)
        assert b.run("copy"), b.status                         # (the actions Ctrl+C / V / D run)
        b.setTime(40.0)                                        # bar 21: far out of view
        QTest.qWait(50)
        b._tv.fitTo(0.0, 8.0)
        QTest.qWait(50)
        assert b.run("paste"), b.status
        QTest.qWait(300)
        start, span = b.viewStart, b.viewSpan
        assert start <= 40.0 and 42.0 <= start + span, (start, span)       # the four pasted notes are in view
        assert b.run("duplicate"), b.status                   # its copy runs past the right edge: shown too
        QTest.qWait(300)
        assert b.viewStart + b.viewSpan >= 44.0 and b.viewStart <= 42.0, (b.viewStart, b.viewSpan)
        b._tv.fitTo(30.0, 60.0)                                 # a wide view: the next copy (44-46 s) is in it
        QTest.qWait(50)
        start, span = b.viewStart, b.viewSpan
        assert b.run("duplicate"), b.status
        QTest.qWait(300)
        assert (b.viewStart, b.viewSpan) == (start, span)       # in view already: nothing moves
    finally:
        screen.close()
        QTest.qWait(50)
