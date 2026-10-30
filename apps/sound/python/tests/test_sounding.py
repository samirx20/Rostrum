"""sounding.at / sounding.over: what is written to sound at a second, through the app's own tempo map."""
from rostrum_core import Document

from rostrum_sound import KIND, run_source, sounding

SCRIPT = """tempo(120); beats_per_bar(4); key("D minor"); length(bar(5))
tempo_change(bar(2), 60)
p = track("keys", builtIn="piano")
p.note(["D3", "F3", "A3", "C4"], at=bar(1), dur=beats(3), vel=0.7)
d = track("drums", kit="drums"); d.hit("kick", at=bar(1), vel=0.9); d.hit("snare", at=bar(2), vel=0.8)
"""


def _doc():
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(SCRIPT, "s.py"))
    return doc.data


def test_chord_hit_and_tempo_change():
    data = _doc()
    now = sounding.at(data, 1.0)                    # bar 1 at 120 bpm: beat 2, inside the held chord
    assert now["chord"] == "Dm7" and now["pitches"] == ["D", "F", "A", "C"]
    assert [t["track"] for t in now["tracks"]] == ["keys"]
    assert [h["drum"] for h in sounding.at(data, 0.03)["tracks"][1]["hits"]] == ["kick"]
    # the tempo halves at bar 2 (2.0 s): the snare there is at 2.0 s, and a beat after it lasts 1 s
    assert sounding.over(data, 1.9, 2.1)[0]["first_s"] == 2.0
    assert sounding.at(data, 1.9)["chord"] is None   # chord (3 beats = 1.5 s) has ended
    row = {r["track"]: r for r in sounding.over(data, 0, 5)}
    assert row["keys"]["low"] == "D3" and row["keys"]["high"] == "C4" and row["drums"]["hits"] == 2


def test_a_hits_vel_is_as_written_not_times_the_fader():
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source('tempo(120); length(bar(2)); c = track("cym", kit="drums", volume=2.0)\n'
                                      'c.hit("crash", at=bar(1), vel=0.95)\nc.volume = 1.5', "s.py"))
    assert sounding.over(doc.data, 0, 4)[0]["vel_mean"] == 0.95 and doc.data["tracks"][0]["volume"] == 1.5
