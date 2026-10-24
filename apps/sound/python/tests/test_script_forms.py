"""The script forms agents write first: beat arithmetic, drum names, plain Python, and the before-render checks."""
import pytest

from rostrum_core import RostrumError
from rostrum_sound import run_source
from rostrum_sound.doc import KIND
from rostrum_sound.script_scope import printed


def notes(src):
    return run_source("tempo(120); length(bar(9)); s = track('k', builtIn='grandPiano')\n" + src, "t.py")["tracks"][0]["notes"]


def test_beat_arithmetic_gives_document_values():
    n = notes("for i in range(2):\n    s.note('C4', at=bar(2) + i * beats(1), dur=beats(1) * 2)")
    assert [x["at"] for x in n] == [{"beat": 4}, {"beat": 5}] and n[0]["dur"] == {"beats": 2}


@pytest.mark.parametrize("src", ["s.note('C4', at=bar(2) + 0.5, dur=1)", "x = bar(2) < 3.0", "s.note('C4', at='#a' + beats(1), dur=1)"])
def test_beats_mixed_with_seconds_are_refused_naming_the_form(src):
    with pytest.raises(RostrumError) as e:
        notes(src)
    assert "beats(" in str(e.value)


def test_drum_names_agents_reach_for():
    t = run_source("d = track('d', kit='synth'); d.hit('Hi-Hat', at=0); d.hit('bd', at=1)", "t.py")
    assert [h["drum"] for h in t["tracks"][0]["hits"]] == ["hat", "kick"]
    with pytest.raises(RostrumError, match='write "cymbal"'):
        run_source("d = track('d', kit='synth'); d.hit('crash', at=0)", "t.py")


def test_random_is_the_same_every_run_and_print_comes_back():
    src = "import random\ns.note(random.choice(['C4', 'D4', 'E4', 'F4', 'G4']), at=0, dur=1)\nprint('hi')"
    assert notes(src) == notes(src) and printed() == ["hi"]


def test_timing_slips_are_said_when_the_script_runs():
    with pytest.raises(RostrumError, match="not after its start"):
        notes("s.note('C2', at=10.1, dur={'to': 9.5})")
    t = run_source("length(10); s = track('k', builtIn='grandPiano'); s.note('C4', at=10.5, dur=1)", "t.py")
    assert any("never heard" in w for w in KIND.warn(t))
