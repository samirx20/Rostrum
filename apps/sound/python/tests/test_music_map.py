"""What the music workflow must never get wrong silently: times through a tempo map (the screen, ids and engine all
read it), a section move that moves everything inside it as one undo step, a MIDI file that comes back with its
notes and tempo, and a keyboard take that lands where it was played."""
from rostrum_core import Document, Who

from rostrum_sound import KIND, compile, midi, run_source
from rostrum_sound.doc import keys, tempo, times
from rostrum_sound.midi import keyboard

SONG = """
tempo(120); beats_per_bar(4)
tempo_change(bar(3), 60); key("D minor"); section("verse", bar(1), bar(3)); section("drop", bar(3), bar(5))
marker("hit", at=bar(2)); marker("late", at=bar(4))
p = track("lead", builtIn="feltPiano")
p.note("D4", at=beat(0), dur=beats(1), vel=0.5); p.note("F4", at=bar(2), dur=beats(2)); p.note("A4", at=bar(4), dur=1.0)
p.note("C5", at="#hit+0.25", dur=0.5)
p.automate("volume", [(0, 0.5), (bar(2), 0.8), (bar(4), 1.0)])
d = track("drums", kit="synth"); d.hit("kick", at=beat(0)); d.hit("snare", at=bar(4))
"""


def _doc():
    doc = Document.new(KIND)
    doc.run_script("song.py", run_source(SONG, "song.py"), Who.script("song.py"))
    return doc


def test_times_follow_the_tempo_map():
    root = _doc().data
    assert times.seconds({"beat": 8}, root, "t") == 4.0                  # 8 beats at 120
    assert times.seconds({"beat": 12}, root, "t") == 8.0                 # + 4 beats at 60
    assert times.length_seconds({"beats": 2}, root, start=3.5) == 1.5    # beat 7: 1 beat at 120, then 1 at 60
    assert tempo.beat_at(root, 6.0) == 10.0
    assert compile(root)["tempo"] == [{"beat": 0.0, "bpm": 120.0}, {"beat": 8.0, "bpm": 60.0}]
    assert root["tracks"][0]["notes"][2]["id"] == "lead.n8000"           # ids read the map too (bar 4 = 8 s)


def test_section_move_moves_everything_inside_as_one_step():
    doc = _doc()
    before = doc.seq
    doc.apply({"op": "section.move", "target": ["section.verse"], "args": {"by": {"beats": 1}}}, Who.person())
    assert doc.seq == before + 1
    notes = {n["pitch"]: n["at"] for n in doc.item("lead")["notes"]}
    assert notes["D4"] == {"beat": 1.0} and notes["F4"] == {"beat": 5.0}    # inside: moved, still in beats
    assert notes["A4"] == {"beat": 12}                                      # in the drop: untouched
    assert notes["C5"] == "#hit+0.25"                                      # on a marker that moved: follows it
    assert doc.item("marker.hit")["at"] == {"beat": 5.0}
    assert doc.item("drums.kick0")["at"] == {"beat": 1.0}
    assert doc.item("section.verse")["at"] == {"beat": 1.0} and doc.item("section.verse")["end"] == {"beat": 9.0}
    assert doc.item("section.drop")["at"] == {"beat": 8}
    assert [p[0] for p in doc.item("lead.auto_volume")["points"]] == [0.5, {"beat": 5.0}, {"beat": 12}]
    doc.undo(Who.person())
    assert doc.data == _doc().data                                         # one undo puts it all back


def test_midi_round_trip_keeps_notes_and_tempo(tmp_path):
    src = _doc().data
    out = tmp_path / "song.mid"
    assert midi.export(src, out) == []
    doc = Document.new(KIND)
    calls, skipped = midi.import_calls(doc.data, out)
    doc.apply(calls, Who.agent("t"), label="Import MIDI")
    assert skipped == [] and doc.seq == 1
    root = doc.data
    assert compile(root)["tempo"] == compile(src)["tempo"]
    assert [k["key"] for k in root["keys"]] == ["D minor"] and len(root["sections"]) == 2

    def heard(r, tid):          # (seconds, MIDI key, seconds long) of every note on a track
        return sorted((round(times.seconds(n["at"], r, "t"), 3), keys.midi(n["pitch"]),
                       round(times.length_seconds(n["dur"], r, times.seconds(n["at"], r, "t")), 3))
                      for n in next(t for t in r["tracks"] if t["id"] == tid)["notes"])
    assert heard(root, "lead") == heard(src, "lead")
    assert [(h["drum"], h["at"]) for h in next(t for t in root["tracks"] if t["id"] == "drums")["hits"]] == \
        [("kick", {"beat": 0.0}), ("snare", {"beat": 12.0})]


def test_keyboard_take_lands_where_it_was_played():
    lines = ['{"ready": {"mode": "shared", "rate": 48000}}', "not json",
             '{"heard": {"key": 62, "latencyMs": 9}}', '{"note": {"key": 62, "velocity": 0.8, "start": 0.5, "end": 1.0}}',
             '{"note": {"key": 36, "velocity": 1.2, "start": 1.0, "end": 1.1}}', '{"latency": {}}']
    ready, notes, errors = keyboard.parse(lines)
    assert ready["rate"] == 48000 and len(notes) == 2 and errors == []
    root = _doc().data
    call = keyboard.take_call({"id": "lead", "instrument": "builtIn"}, notes, 3.5, root)
    assert call["args"]["notes"][0] == {"pitch": 62, "at": {"beat": 8.0}, "dur": {"beats": 0.5}, "vel": 0.8}
    drums = keyboard.take_call({"id": "drums", "instrument": "kit"}, notes, 0.0, root)
    assert drums == {"op": "hit.add_many", "target": ["drums"],
                     "args": {"hits": [{"drum": "kick", "at": {"beat": 2.0}, "vel": 1.0}]}}
