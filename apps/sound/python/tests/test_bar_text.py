"""look_arrangement's bar-by-bar text (ears/bar_text.py): chord symbols as musicians write them, read from the
written notes, and each one-line part's notes as name+octave@beat; the picture keeps a lane per track."""
import pytest
from PIL import Image
from rostrum_core import Document

from rostrum_sound import KIND, run_source
from rostrum_sound.ears import arrangement as A
from rostrum_sound.ears import bar_text as BT
from rostrum_sound.ears.draw_arrangement import arrangement_picture
from rostrum_sound.ears.theory import name_chord
from rostrum_sound.ears.written import written_notes
from rostrum_sound.doc.keys import midi


def _m(*names):
    return [midi(n) for n in names]


@pytest.mark.parametrize("notes, name", [
    (("C4", "E4", "G4"), "C"), (("E3", "G3", "C4"), "C/E"), (("G3", "C4", "E4"), "C/G"),
    (("B2", "D3", "G3"), "G/B"), (("A3", "C4", "E4"), "Am"),
    (("C4", "E4", "G4", "B4"), "Cmaj7"), (("D3", "F3", "A3", "C4"), "Dm7"), (("G2", "B2", "D3", "F3"), "G7"),
    (("F#3", "A3", "C4", "E4"), "F#m7b5"), (("B2", "D3", "F3", "Ab3"), "Bdim7"),
    (("B2", "F3", "G3", "D4"), "G7/B"), (("G2", "A3", "C4", "E4"), "Am7/G"), (("E3", "B3", "C4", "G4"), "Cmaj7/E"),
    (("C3", "E3", "G3", "A3"), "C6"), (("D3", "G3", "A3", "C4"), "D7sus4"), (("C3", "E3", "G3", "Bb3", "D4"), "C9"),
])
def test_chord_names_on_known_voicings(notes, name):
    assert name_chord(_m(*notes)) == name


def test_chord_label_over_a_bass_and_alone():
    assert BT.chord_label(_m("E4", "G4", "B4"), midi("C2"), None) == "Cmaj7"   # the bass names the root
    assert BT.chord_label(_m("C4", "E4", "G4"), midi("E2"), None) == "C/E"      # … or the inversion
    assert BT.chord_label([], None, None) == "N.C."
    assert BT.chord_label(_m("D4"), None, None) == "(D)"
    assert BT.chord_label(_m("C4", "C#4", "D4"), None, None) == "(C C# D)"


SONG = """tempo(120); beats_per_bar(4); key("C major"); length(bar(5))
p = track("pad", builtIn="piano")
p.chord(["C4","E4","G4","B4"], at=bar(1), dur=beats(4))
p.chord(["F#3","A3","C4","E4"], at=bar(2), dur=beats(2)); p.chord(["B2","D3","G3"], at=bar(2)+beats(2), dur=beats(2))
l = track("lead", builtIn="piano")
l.note("E5", at=bar(1), dur=beats(1.5)); l.note("G5", at=bar(1)+beats(1.5), dur=beats(3.5)); l.note("A5", at=bar(2)+beats(1), dur=beats(1))
l.note("C6", at=bar(3)+beats(0.98), dur=beats(0.5))
d = track("drums", kit="drums"); d.hit("kick", at=bar(1))
"""


def _doc(src=SONG):
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(src, "s.py"))
    return doc


def test_bar_by_bar_chords_and_note_names():
    doc = _doc()
    arr = A.read(doc.data)
    bt = BT.read(doc.data, written_notes(doc.data), arr["end"])
    assert (bt["from"], bt["to"], bt["of"]) == (1, 4, 4)
    rows = {r["bar"]: r for r in bt["rows"]}
    assert rows[1]["chord"] == "Cmaj7" and rows[1]["parts"]["lead"] == "E5@1 G5@2.5"
    assert rows[2]["chord"] == "F#m7b5@1 G/B@3" and rows[2]["parts"]["lead"] == "~G5 A5@2"
    assert rows[3]["chord"] == "N.C." and rows[3]["parts"]["lead"] == "C6@2"          # played 10 ms early, read on 2
    assert rows[4]["parts"]["lead"] == "—"
    assert bt["line_tracks"] == ["lead"] and bt["chord_tracks"] == ["pad"]
    lines = BT.lines(bt)
    assert len(lines) == 4 and len({ln.index("| lead") for ln in lines}) == 1         # aligned per bar
    head = BT.header(bt, ["drums"], [])
    assert "bars 1–4 of 4" in head and "drums (drums)" in head and "pad" in head


def test_a_range_and_the_default_window_say_what_is_shown():
    long = "tempo(120); length(bar(41))\nl = track('lead', builtIn='piano')\nfor b in range(1, 41):\n    l.note('A4', at=bar(b), dur=beats(1))\n"
    doc = _doc(long)
    arr = A.read(doc.data)
    bt = BT.read(doc.data, written_notes(doc.data), arr["end"])
    assert (bt["from"], bt["to"], bt["of"]) == (1, 16, 40)
    assert "bars 1–16 of 40 (ask bars" in BT.header(bt, [], [])
    bt = BT.read(doc.data, written_notes(doc.data), arr["end"], 38, 60)
    assert [r["bar"] for r in bt["rows"]] == [38, 39, 40] and bt["rows"][0]["parts"]["lead"] == "A4@1"
    assert bt["rows"][0]["chord"] == "(A)"


def test_a_short_rest_keeps_the_chord_a_long_one_is_no_chord():
    src = """tempo(120); beats_per_bar(4); length(bar(4))
p = track("pad", builtIn="piano")
p.chord(["C4","E4","G4"], at=bar(1), dur=beats(1)); p.chord(["C4","E4","G4"], at=bar(1)+beats(3), dur=beats(1))
p.chord(["D4","F4","A4"], at=bar(2), dur=beats(1))
p.chord(["D4","F4","A4"], at=bar(3)+beats(3), dur=beats(1))
"""
    doc = _doc(src)
    arr = A.read(doc.data)
    rows = BT.read(doc.data, written_notes(doc.data), arr["end"])["rows"]
    assert [r["chord"] for r in rows] == ["C", "Dm@1 N.C.@2", "N.C.@1 Dm@4"]   # a 2-beat rest holds C; 6 beats do not hold Dm


def test_the_picture_keeps_a_lane_per_track_and_a_chord_row(tmp_path):
    doc = _doc()
    arr = A.read(doc.data)
    bt = BT.read(doc.data, written_notes(doc.data), arr["end"])
    with Image.open(arrangement_picture(str(tmp_path / "a.png"), arr, title="t")) as im:
        plain = im.height
    with Image.open(arrangement_picture(str(tmp_path / "b.png"), arr, title="t", chords=bt["chords"])) as im:
        assert im.height == plain + 16                     # the chord row; one 84 px lane per track either way
    one = _doc(SONG.replace('d = track("drums", kit="drums"); d.hit("kick", at=bar(1))', ""))
    with Image.open(arrangement_picture(str(tmp_path / "c.png"), A.read(one.data), title="t")) as im:
        assert plain - im.height == 84


def test_a_range_reads_each_bar_as_the_whole_song_does():
    src = (SONG.replace('at=bar(2)+beats(2), dur=beats(2))', 'at=bar(2)+beats(2), dur=beats(1))')   # a rest on bar 2's last beat
           + 'p.chord(["D4","F4","A4"], at=bar(3), dur=beats(1))\n')
    doc = _doc(src)
    arr = A.read(doc.data)
    whole = {r["bar"]: r for r in BT.read(doc.data, written_notes(doc.data), arr["end"])["rows"]}
    assert whole[2]["chord"] == "F#m7b5@1 G/B@3"           # the rest is held: the chord part plays on after it
    for bar in (2, 3, 4):
        assert BT.read(doc.data, written_notes(doc.data), arr["end"], bar, bar)["rows"] == [whole[bar]]
