"""What would break silently: Play right after an edit starts at once (the last good render), says the sound is being
updated, and the edit's render, when it lands, is loaded into the playing transport (the person hears the edit, never
the old song for good). fake_play.py stands in for the engine's player; a slow stand-in engine keeps a render on its way."""
import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QGuiApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document  # noqa: E402
from rostrum_sound import KIND, run_source  # noqa: E402
from screensound import playback  # noqa: E402
from screensound.bridge import SoundBridge  # noqa: E402
from screensound.transport import UPDATING  # noqa: E402
from stand_in import FakeEngine  # noqa: E402
from test_recording import FAKE, pump  # noqa: E402


def SlowEngine():
    return FakeEngine(seconds=6, delay=0.8)              # a long song's re-render, shortened


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


def test_a_refused_render_never_claims_ready_and_names_the_track(bridge, monkeypatch):
    """While the newest render is refused (a note out of its sound's range) the screen says so (soundRefused: the loudness
    chip's words, the Problems row with the track to jump to); the next render that works takes it away."""
    from screensound import problems
    tr = bridge.transport
    line = (r"Error: render: the mix C:\sounds\vsco2-strings\ViolinEnsSusVib.sfz: no sample for C7 (key 96) at "
            "velocity 100; the instrument plays G3–D6.")
    bridge.doc.run_script("v.py", run_source('vl = track("Violins", builtIn="violins")\nvl.note("C7", at=beat(0), dur=beats(1))\n', "v.py"))
    tr._failed(line)
    r = bridge.soundRefused
    assert r["kind"] == "out-of-range" and r["short"] == "Can't play: fix the notes"
    assert bridge.doc.item(r["item"])["name"] == "Violins"
    assert problems.refused_rows(r)[0]["item"] == r["item"]
    tr._rendered({"file": tr.last["file"], "lufs": -20.0, "tracks": []})
    assert bridge.soundRefused == {}
