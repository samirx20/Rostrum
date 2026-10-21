"""What would break silently: a recorded take is ONE undoable clip at the time recording started, and a take that
fails (the engine dies, no `done`) is loud and leaves the document alone. A WAV stands in for the microphone."""
import sys
import time
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QGuiApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document  # noqa: E402
from rostrum_sound import KIND, run_source  # noqa: E402
from screensound import playback  # noqa: E402
from screensound.bridge import SoundBridge  # noqa: E402
from screensound.recording import Recording  # noqa: E402

FAKE = Path(__file__).resolve().parents[1] / "screensound" / "fake_mic.py"


class FakeEngine:
    def request(self, do, schedule=None, out=None, **kw):
        Path(out).write_bytes(b"")
        return {"file": out, "lufs": -20.0, "tracks": [], "stems": {}}

    def close(self):
        pass


@pytest.fixture
def rig(monkeypatch, tmp_path):
    QGuiApplication.instance() or QGuiApplication([])
    monkeypatch.setattr(playback, "open_engine", FakeEngine)
    monkeypatch.chdir(tmp_path)
    sf.write(tmp_path / "src.wav", (np.sin(np.arange(24000) / 20) * 0.3).astype("float32"), 48000)
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source('lead = track("voice")\n', "s.py"))
    b = SoundBridge(doc)
    yield b, Recording(b, [sys.executable, "-I", str(FAKE), "{out}", str(tmp_path / "src.wav")]), tmp_path
    b.close()


def pump(s):
    end = time.monotonic() + s
    while time.monotonic() < end:
        QCoreApplication.processEvents()
        time.sleep(0.02)


def test_take_is_one_undoable_clip_at_the_start_time(rig):
    b, r, tmp = rig
    b.setTime(2.0)
    r.arm("voice")
    r.toggleRecord()
    pump(0.5)
    r.toggleRecord()
    clips = b.doc.item("voice")["clips"]
    assert len(clips) == 1 and clips[0]["at"] == 2.0 and Path(clips[0]["media"]).name == "voice-take-1.wav"
    assert Path(clips[0]["media"]).is_file()
    b.undo()
    assert not b.doc.item("voice").get("clips")


def test_a_failed_take_is_loud_and_adds_nothing(rig):
    b, r, tmp = rig
    r.command = [sys.executable, "-c", "import sys; sys.exit(3)"]
    r.arm("voice")
    r.toggleRecord()
    assert not r.recording and b.status.startswith("Error") and not b.doc.item("voice").get("clips")
