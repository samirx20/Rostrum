"""What would break silently: a keyboard take is ONE undo step with its notes on the beats they were played at
(relative to playback), and a punch take keeps only the punch range. Fakes stand in for the keyboard and microphone."""
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
from rostrum_sound.doc import tempo  # noqa: E402
from screensound import playback  # noqa: E402
from screensound.bridge import SoundBridge  # noqa: E402
from screensound.keys_record import KeysRecording  # noqa: E402
from screensound.recording import Recording  # noqa: E402

HERE = Path(__file__).resolve().parents[1] / "screensound"


class FakeEngine:
    def request(self, do, schedule=None, out=None, **kw):
        Path(out).write_bytes(b"")
        return {"file": out, "lufs": -20.0, "tracks": [], "stems": {}}

    def close(self):
        pass


def pump(s, until=lambda: False):
    end = time.monotonic() + s
    while time.monotonic() < end and not until():
        QCoreApplication.processEvents()
        time.sleep(0.02)


@pytest.fixture
def bridge(monkeypatch, tmp_path):
    QGuiApplication.instance() or QGuiApplication([])
    monkeypatch.setattr(playback, "open_engine", FakeEngine)
    monkeypatch.chdir(tmp_path)
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source('tempo(120)\nkeys = track("keys", synth="saw")\nvox = track("vox")\n', "s.py"))
    b = SoundBridge(doc)
    yield b
    b.close()


def test_keyboard_take_is_one_step_on_the_played_beats(bridge):
    r = Recording(bridge)
    k = KeysRecording(bridge, r)
    k.list_devices = lambda: ["Fake keyboard"]
    k.command = [sys.executable, "-I", str(HERE / "fake_midi.py"), "60@0.2:0.45,64@0.7:1.2"]
    bridge.setTime(1.0)
    r.arm("keys")
    pump(5, lambda: k.usable)
    before = bridge.historyCount
    k.toggleRecord()
    pump(1.6)
    k.toggleRecord()
    notes = sorted(bridge.doc.item("keys")["notes"], key=lambda n: n["at"]["beat"])
    zero = k.clock.at - k.clock.lead                   # the timeline time of the keyboard's stream start
    assert [n["pitch"] for n in notes] == [60, 64]
    assert notes[0]["at"]["beat"] == pytest.approx(tempo.beat_at(bridge.doc.data, zero + 0.2), abs=1e-3)
    assert notes[1]["at"]["beat"] - notes[0]["at"]["beat"] == pytest.approx(1.0, abs=1e-3)    # 0.5 s at 120 bpm
    assert k.clock.at == 1.0 and 0 <= k.clock.lead < 1.0
    assert bridge.historyCount == before + 1
    bridge.undo()
    assert not bridge.doc.item("keys").get("notes")
    k.close()
    r.close()


def test_punch_take_covers_only_the_range(bridge, tmp_path):
    sf.write(tmp_path / "src.wav", (np.sin(np.arange(96000) / 20) * 0.3).astype("float32"), 48000)
    r = Recording(bridge, [sys.executable, "-I", str(HERE / "fake_mic.py"), "{out}", str(tmp_path / "src.wav")])
    bridge.setTime(2.0)
    r.arm("vox")
    r.setup.set("punch", True)
    r.setup.set("punchIn", 2.2)
    r.setup.set("punchOut", 2.5)
    r.toggleRecord()
    pump(1.2)
    r.stop()
    clips = bridge.doc.item("vox")["clips"]
    assert len(clips) == 1
    c = clips[0]
    assert c["at"] == 2.2 and c["length"]["seconds" if isinstance(c["length"], dict) else 0] == pytest.approx(0.3) \
        if isinstance(c["length"], dict) else c["length"] == pytest.approx(0.3)
    assert c["in"] == pytest.approx(0.2 + r.clock.lead, abs=1e-3)     # the file's first 0.2 s + its lead are cut
    r.close()
