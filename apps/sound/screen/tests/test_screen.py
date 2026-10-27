"""What would break silently on the Sound screen: a note drag is one undo step (and undo puts it back), it keeps
the time's form (beats stay beats), and re-running the song's script keeps what a person moved.
The engine is replaced by a stand-in that writes a real short silent WAV (sound is checked by listening)."""
import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QGuiApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document  # noqa: E402
from rostrum_sound import KIND, run_source  # noqa: E402
from screensound import playback  # noqa: E402
from screensound.bridge import SoundBridge  # noqa: E402
from screensound.steps import drag  # noqa: E402
from stand_in import FakeEngine  # noqa: E402,F401  (other tests import it from here)

SRC = '''
tempo(120); beats_per_bar(4)
lead = track("lead", builtIn="feltPiano")
lead.note("C4", at=beat(4), dur=beats(1))
lead.note("E4", at=beat(6), dur=beats(1))
'''


@pytest.fixture
def bridge(monkeypatch):
    QGuiApplication.instance() or QGuiApplication([])
    monkeypatch.setattr(playback, "open_engine", FakeEngine)
    doc = Document.new(KIND)
    doc.run_script("song.py", run_source(SRC, "song.py"))
    b = SoundBridge(doc)
    yield b
    b.close()


def test_note_drag_is_one_undo_step_and_keeps_beats(bridge):
    doc, before = bridge.doc, len(bridge.doc.history.changes)
    drag(bridge, "lead.n2000", 0.5, 2)                   # +1 beat (0.5 s at 120 bpm), +2 semitones
    note = doc.item("lead.n2000")
    assert (note["at"], note["pitch"]) == ({"beat": 5.0}, "D4")
    assert len(doc.history.changes) == before + 1
    bridge.undo()
    note = doc.item("lead.n2000")
    assert (note["at"], note["pitch"]) == ({"beat": 4}, "C4")


def test_script_rerun_keeps_a_persons_note_move(bridge):
    drag(bridge, "lead.n2000", 0.25, 0)                  # half a beat later
    bridge.doc.run_script("song.py", run_source(SRC, "song.py"))
    assert bridge.doc.item("lead.n2000")["at"] == {"beat": 4.5}
    assert bridge.doc.item("lead.n3000")["at"] == {"beat": 6}


def test_a_preset_name_that_does_not_exist_is_refused_naming_the_real_ones(bridge, capsys):
    from rostrum_sound import presets
    from screensound.export import RenderExport
    sheet = RenderExport(bridge)
    before = sheet.preset
    sheet.usePreset("For")
    err = capsys.readouterr().err
    assert 'no preset named "For"' in err and all(k in err for k in presets.PRESETS) and sheet.preset == before


def test_plus_effect_adds_one_step_on_a_track_and_the_master(bridge):
    """The Mixer's "+ Effect" is the effect.add operation on that strip (it once called a command id that no longer
    existed and failed on every strip): one change each, the new effect selected."""
    from screensound.mixer import MixPage
    doc, mix = bridge.doc, MixPage(bridge)
    for owner in ("lead", "master"):
        before = len(doc.history.changes)
        assert mix.addEffect(owner, "delay"), bridge.status
        assert len(doc.history.changes) == before + 1
        assert doc.item(owner)["effects"][-1]["effect"] == "delay"
        assert bridge.selected == doc.item(owner)["effects"][-1]["id"]


def test_song_length_picker_sets_bars_typed_lengths_and_goes_back_to_the_last_sound(bridge):
    """The Length picker: N bars is written in beats (it follows the tempo), a typed time in seconds, a typed bar where it
    starts; words it can't read change nothing; "" puts it back to left out."""
    from screensound.song_panel import SongPanel
    panel, doc = SongPanel(bridge), bridge.doc
    assert panel.lengthChoice == "" and panel.lengthChoices[0]["label"] == "Until the last sound"
    panel.setLength("8 bars")
    assert doc.data["length"] == {"beat": 32.0} and panel.lengthChoice == "8 bars"
    assert panel.setLength("1:02.5") and doc.data["length"] == 62.5 and panel.lengthChoices[-1]["label"] == "1:02.50"
    assert panel.setLength("bar 24") and panel.lengthChoice == "23 bars"
    assert not panel.setLength("soon") and panel.lengthChoice == "23 bars"
    panel.setLength("")
    assert doc.data["length"] is None and panel.lengthChoice == ""
