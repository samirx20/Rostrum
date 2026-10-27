"""Pedal each chord writes the sustain lane as steps on the chord changes and keeps the lane's points outside the
chords: a pedal lifting at the wrong time, or a person's own pedalling wiped, would only be heard."""
from rostrum_core import Document, Who

from rostrum_sound import KIND, run_source

SONG = """
tempo(60)
p = track("p", synth="saw")
for b, chord in enumerate((("C4", "E4", "G4"), ("F4", "A4", "C5"), ("G4", "B4", "D5"))):
    for tone in chord:
        p.note(tone, at=beat(4 + 4 * b), dur=beats(4), vel=0.6)
p.sustain([(0, 1), (2, 1), (2, 0)])
"""


def test_pedal_each_chord_steps_on_the_changes_and_keeps_the_rest():
    doc = Document.new(KIND)
    doc.run_script("song.py", run_source(SONG, "song.py"))
    ids = [n["id"] for n in doc.item("p")["notes"]]
    doc.apply({"op": "note.pedal", "target": ids, "args": {"catch": 0.25}}, Who.person())
    lane = next(a for a in doc.item("p")["automation"] if a["lane"] == "sustain")
    pts = [(p[0]["beat"] if isinstance(p[0], dict) else p[0], p[1]) for p in lane["points"]]
    assert pts[:3] == [(0, 1), (2, 1), (2, 0)]                       # the person's own pedalling before stays
    assert pts[3:] == [(4.0, 0), (4.25, 0), (4.25, 1), (8.0, 1), (8.0, 0), (8.25, 0), (8.25, 1),
                       (12.0, 1), (12.0, 0), (12.25, 0), (12.25, 1), (16.0, 1), (16.0, 0)]   # steps: never a ramp
