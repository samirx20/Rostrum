"""A played track's sustain pedal, expression and pitch bend survive a MIDI file both ways (CC 64, CC 11, the pitch
wheel and its range), as the same automation lanes a person draws."""
from rostrum_core import Document, Who

from rostrum_sound import KIND, midi, run_source
from rostrum_sound.expression import curve_at

CUE = """
tempo(90)
p = track("keys", builtIn="feltPiano")
p.note("C4", at=beat(0), dur=beats(1))
p.note("E4", at=beat(2), dur=beats(1))
p.sustain([(beat(0), 0), (beat(1), 0), (beat(1), 1), (beat(3), 1), (beat(3), 0)])
p.dynamics([(beat(0), 0.4), (beat(4), 1.0)])
p.bend([(beat(0), 0), (beat(2), 0), (beat(2), 0.5), (beat(4), 0.5)], range=3)
"""


def _beats(track, lane):
    return [(p[0]["beat"], p[1]) for p in next(a["points"] for a in track["automation"] if a["lane"] == lane)]


def test_sustain_expression_and_bend_round_trip(tmp_path):
    src = Document.new(KIND)
    src.run_script("cue.py", run_source(CUE, "cue.py"), Who.script("cue.py"))
    path = tmp_path / "cue.mid"
    assert midi.export(src.data, path) == []

    doc = Document.new(KIND)
    calls, skipped = midi.import_calls(doc.data, path)
    doc.apply(calls, Who.person(), label="Import MIDI")
    assert skipped == []
    t = next(t for t in doc.data["tracks"] if t.get("notes"))
    assert t["bendRange"] == 3
    assert _beats(t, "sustain") == [(0, 0), (1, 0), (1, 1), (3, 1), (3, 0)]     # steps: down at 1, up at 3
    swell = _beats(t, "dynamics")
    for b in (0, 1, 2.5, 4):                                     # a line, within one MIDI step
        assert abs(curve_at(swell, b) - (0.4 + 0.15 * b)) < 0.02
    bend = _beats(t, "bend")
    assert abs(curve_at(bend, 1) - 0) < 1e-3 and abs(curve_at(bend, 3) - 0.5) < 1e-3
