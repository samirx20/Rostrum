"""What would break silently: Play right after an edit starts at once (the last good render), says the sound is being
updated, and the edit's render, when it lands, is loaded into the playing transport (the person hears the edit, never
the old song for good). fake_play.py stands in for the engine's player; a slow stand-in engine keeps a render on its way."""
import sys
import time
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from PySide6.QtGui import QGuiApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document  # noqa: E402
from rostrum_sound import KIND, run_source  # noqa: E402
from screensound import playback  # noqa: E402
from screensound.bridge import SoundBridge  # noqa: E402
from screensound.transport import UPDATING  # noqa: E402
from test_recording import FAKE, pump  # noqa: E402


class SlowEngine:
    def request(self, do, schedule=None, out=None, **kw):
        time.sleep(0.8)                                  # a long song's re-render, shortened
        sf.write(out, np.zeros((48000 * 6, 2), "float32"), 48000)
        return {"file": out, "lufs": -20.0, "tracks": []}

    def take_restarted(self):
        return ""

    def close(self):
        pass

    def abort(self):
        pass


@pytest.fixture
def bridge(monkeypatch, tmp_path):
    QGuiApplication.instance() or QGuiApplication([])
    monkeypatch.setattr(playback, "open_engine", SlowEngine)
    monkeypatch.chdir(tmp_path)
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source('tempo(120)\nkeys = track("keys", synth="saw")\nkeys.note("C4", at=beat(0), dur=beats(1))\n', "s.py"))
    b = SoundBridge(doc)
    b.transport.player.program = FAKE
    pump(10, lambda: not b.transport.busy())
    yield b
    b.close()


def test_play_after_an_edit_starts_at_once_and_the_edit_joins_the_playing_sound(bridge):
    tr = bridge.transport
    first = tr.last["file"]
    bridge._apply([{"op": "doc.set", "target": ["root"], "args": {"tempo": 100}}], "Tempo")   # an edit: a render is on its way
    assert tr.busy()
    bridge.togglePlay()
    assert tr.playing and tr.player.file == first and tr.state == UPDATING      # no wait, and it says why
    pump(10, lambda: not tr.busy() and tr.player.file != first)
    assert tr.playing and tr.player.file == tr.last["file"] != first and tr.state == ""
