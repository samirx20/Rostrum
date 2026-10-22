"""Trying a sound from the Library on the selected track (DESIGN.md §3.2b): trying writes nothing (no history entry),
Revert puts the original back exactly, Keep is one undo step. The audition itself (engine + player) is replaced by a
stand-in: sound is checked by listening."""
import copy
import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QGuiApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document  # noqa: E402
from rostrum_sound import KIND, run_source, userlib  # noqa: E402
from screensound import playback  # noqa: E402
from screensound.bridge import SoundBridge  # noqa: E402
from screensound.library_panel import LibraryPanel  # noqa: E402

SRC = '''
tempo(120); beats_per_bar(4)
lead = track("lead", builtIn="feltPiano")
lead.note("C4", at=beat(4), dur=beats(1))
pad = track("pad", builtIn="warmPad")
'''


class FakeEngine:
    def close(self):
        pass


@pytest.fixture
def panel(monkeypatch):
    QGuiApplication.instance() or QGuiApplication([])
    monkeypatch.setattr(playback, "open_engine", FakeEngine)
    monkeypatch.setattr(userlib, "list_folders", lambda: [])
    doc = Document.new(KIND)
    doc.run_script("song.py", run_source(SRC, "song.py"))
    b = SoundBridge(doc)
    p = LibraryPanel(b)
    p._heard.start = lambda *a, **k: None            # the audition's render and player are not under test
    b.select("lead")
    yield p
    b.close()


def test_trying_writes_nothing_and_revert_restores_the_original(panel):
    doc, before = panel.bridge.doc, copy.deepcopy(panel.bridge.doc.data)
    n = len(doc.history.changes)
    panel.auditionEntry("builtIn:grandPiano")
    assert panel.trying["track"] == "lead" and len(doc.history.changes) == n and doc.data == before
    panel.revert()
    assert panel.trying == {} and len(doc.history.changes) == n and doc.data == before


def test_keep_is_one_undo_step(panel):
    doc, n = panel.bridge.doc, len(panel.bridge.doc.history.changes)
    panel.auditionEntry("builtIn:grandPiano")
    assert panel.keep() and panel.trying == {}
    assert doc.item("lead")["builtIn"] == "grandPiano" and len(doc.history.changes) == n + 1
    panel.bridge.undo()
    assert doc.item("lead")["builtIn"] == "feltPiano"


def test_cancelled_cleanup_leaves_the_original_playing(panel, tmp_path, monkeypatch):
    """Cancel keeps no take: the clip it was cleaning plays its original (useCleaned off, one undo step), never
    "take not made yet"."""
    import wave
    from rostrum_core.cache import Cache
    from screensound.clean_process import CleanProcess
    from screensound.cleaning import CleanedTake
    monkeypatch.setenv("ROSTRUM_CACHE_DIR", str(tmp_path / "cache"))
    wav = tmp_path / "take.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(48000), w.writeframes(b"\0\0" * 4800)
    b = panel.bridge
    b._apply([{"op": "clip.add", "target": ["lead"], "args": {"media": str(wav), "at": 0, "length": 0.1}}], "Add clip")
    clip = b.doc.data["tracks"][0]["clips"][0]["id"]
    b._apply([{"op": "clip.set", "target": [clip], "args": {"denoise": 0.5}}], "Clean")
    take = CleanedTake(b)
    n = len(b.doc.history.changes)
    take._busy, take._steps, take._job = True, {clip: [0, 2]}, CleanProcess(b.doc.data, [clip], lambda _t: None)
    take._job.cancelled = True
    take._finish("")
    item = b.doc.item(clip)
    assert item["useCleaned"] is False and item["denoise"] == 0.5 and len(b.doc.history.changes) == n + 1
    assert "Cancelled" in take.status and Cache().get("cleanup", "x") is None
    b.undo()
    assert b.doc.item(clip).get("useCleaned", True) is True


def test_picking_another_track_ends_the_try(panel):
    panel.auditionEntry("builtIn:grandPiano")
    panel.bridge.select("pad")
    assert panel.trying == {} and panel.bridge.doc.item("lead")["builtIn"] == "feltPiano"
