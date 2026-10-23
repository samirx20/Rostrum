"""What would break silently: a take lands where the engine's live transport says it was played (ONE undoable clip at
the take's `start`, a start before 0 trimmed with the in-point; a punch take only the range; keyboard notes on the
beats of their mix times), and a player that cannot open is loud while the playhead still runs.
fake_play.py stands in for the engine's player, the microphone and the keyboard."""
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

FAKE = [sys.executable, "-I", str(Path(__file__).resolve().parents[1] / "screensound" / "fake_play.py")]


class FakeEngine:
    def request(self, do, schedule=None, out=None, **kw):
        sf.write(out, np.zeros((48000 * 6, 2), "float32"), 48000)
        return {"file": out, "lufs": -20.0, "tracks": [], "stems": {}}

    def take_restarted(self):
        return ""

    def close(self):
        pass

    def abort(self):
        pass


def pump(s, until=lambda: False):
    """Run the screen's events until `until()` is true (a generous limit, never a fixed wait) or `s` seconds pass."""
    end = time.monotonic() + s
    while time.monotonic() < end and not until():
        QCoreApplication.processEvents()
        time.sleep(0.02)


@pytest.fixture
def bridge(monkeypatch, tmp_path):
    QGuiApplication.instance() or QGuiApplication([])
    monkeypatch.setattr(playback, "open_engine", FakeEngine)
    monkeypatch.chdir(tmp_path)
    sf.write(tmp_path / "src.wav", (np.sin(np.arange(96000) / 20) * 0.3).astype("float32"), 48000)
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source('tempo(120)\nkeys = track("keys", synth="saw")\nvox = track("vox")\n', "s.py"))
    b = SoundBridge(doc)
    pump(5, lambda: not b.transport.busy())
    yield b
    b.close()


def armed(bridge, track, *fake):
    bridge.transport.player.program = FAKE + list(fake)
    r = Recording(bridge)
    r.arm(track)
    pump(5, lambda: r.level is not None)
    return r


@pytest.mark.parametrize("at, delay, clip_at, clip_in", [(1.0, 0.03, 0.97, None), (0.0, 0.05, 0.0, 0.05)])
def test_mic_take_is_one_undoable_clip_at_the_engines_start(bridge, tmp_path, at, delay, clip_at, clip_in):
    r = armed(bridge, "vox", "--fake-source", str(tmp_path / "src.wav"), "--fake-delay", str(delay))
    bridge.setTime(at)
    before = bridge.historyCount
    r.toggleRecord()
    pump(0.5)
    r.toggleRecord()
    pump(3, lambda: bridge.doc.item("vox").get("clips"))
    clips = bridge.doc.item("vox")["clips"]
    assert len(clips) == 1 and clips[0]["at"] == pytest.approx(clip_at, abs=0.02)
    assert clips[0].get("in", 0) == pytest.approx(clip_in or 0, abs=1e-3)
    assert Path(clips[0]["media"]).name == "vox-take-1.wav" and Path(clips[0]["media"]).is_file()
    assert bridge.historyCount == before + 1
    bridge.undo()
    assert not bridge.doc.item("vox").get("clips")
    r.close()


def test_punch_take_covers_only_the_range_and_ends_by_itself(bridge, tmp_path):
    r = armed(bridge, "vox", "--fake-source", str(tmp_path / "src.wav"))
    bridge.setTime(0.5)
    r.setup.setPunch(0.7, 1.0, True)
    r.toggleRecord()
    pump(3, lambda: bridge.doc.item("vox").get("clips"))
    assert not r.recording                                  # stopped by itself past the punch-out
    (c,) = bridge.doc.item("vox")["clips"]
    assert c["at"] == pytest.approx(0.7, abs=0.02)
    assert sf.info(c["media"]).duration == pytest.approx(0.3, abs=0.02)
    r.close()


def test_keyboard_take_is_one_step_on_the_beats_of_its_mix_times(bridge):
    r = armed(bridge, "keys", "--fake-notes", "60@0.2:0.45,64@0.7:1.2")
    k = KeysRecording(bridge, r)
    k.list_devices = lambda: ["Fake keyboard"]
    k.look_for_keyboards()
    pump(5, lambda: k.usable and bridge.transport.player.opts.get("midi") == 0)
    bridge.setTime(1.0)
    before = bridge.historyCount
    k.toggleRecord()
    pump(30, lambda: k.notes == 2)                          # both notes reported by the player, however busy the machine
    assert k.notes == 2, f"the fake keyboard reported {k.notes} of 2 notes within 30 s"
    k.toggleRecord()
    pump(30, lambda: bridge.doc.item("keys").get("notes"))
    notes = sorted(bridge.doc.item("keys")["notes"], key=lambda n: n["at"]["beat"])
    assert [n["pitch"] for n in notes] == [60, 64]
    assert notes[0]["at"]["beat"] == pytest.approx(tempo.beat_at(bridge.doc.data, 1.2), abs=0.05)
    assert notes[1]["at"]["beat"] - notes[0]["at"]["beat"] == pytest.approx(1.0, abs=1e-3)    # 0.5 s at 120 bpm
    assert bridge.historyCount == before + 1
    k.close()
    r.close()


def test_a_player_that_cannot_open_is_loud_and_the_playhead_runs_on(bridge):
    bridge.transport.player.program = [sys.executable, "-c", "import sys; sys.stderr.write('no output device'); sys.exit(3)"]
    bridge.setTime(1.0)
    bridge.togglePlay()
    pump(1.0, lambda: not bridge.transport.player.alive)
    pump(0.3)
    assert "no output device" in bridge.status and bridge.soundState.startswith("No sound output")
    assert bridge.playing and bridge.time > 1.1
