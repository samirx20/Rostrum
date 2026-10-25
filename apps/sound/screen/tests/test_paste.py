"""Paste guards what people rely on: a copied audio clip pastes (its default Cleanup fields are not re-added), and what
one song copied pastes into another song (one clipboard for the app), the clip's sound copied into that song."""
import sys
import wave
from pathlib import Path

import pytest
from PySide6.QtGui import QGuiApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document  # noqa: E402
from rostrum_sound import KIND, run_source  # noqa: E402
from screensound import playback  # noqa: E402
from screensound.bridge import SoundBridge  # noqa: E402
from test_select import FakeEngine  # noqa: E402


def song(tmp_path, name, wav):
    folder = tmp_path / name
    folder.mkdir()
    doc = Document.new(KIND, folder=str(folder), item="song")
    doc.run_script("a.py", run_source(f'tempo(120); beats_per_bar(4)\nd = track("door")\nd.clip(r"{wav}", at=1.0)\n', "a.py"))
    doc.save()
    return doc


def test_a_copied_clip_pastes_into_another_song(tmp_path, monkeypatch):
    QGuiApplication.instance() or QGuiApplication([])
    monkeypatch.setattr(playback, "open_engine", FakeEngine)
    wav = tmp_path / "door.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000); w.writeframes(b"\0\0" * 800)
    a, b = SoundBridge(song(tmp_path, "one", wav)), None
    try:
        clip = a.doc.item("door")["clips"][0]["id"]
        a.select(clip)
        assert a.run("copy")
        b = SoundBridge(song(tmp_path, "two", wav))
        b.select("door")
        assert b.run("paste"), b.status                     # the clip's default Cleanup fields did not refuse it
        made = b.doc.item("door")["clips"]
        assert len(made) == 2 and (tmp_path / "two" / made[-1]["media"]).is_file()
    finally:
        a.close()
        b and b.close()
