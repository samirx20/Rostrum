"""The harmony check judges each note against the key in force at its time (the document's key list), never the first
key for the whole song (critic r11: a song in G, A, G had its A-major G#s called out of key)."""
from rostrum_sound.ears import voicing as V

ROOT = {"tempo": 120, "tempos": [], "beatsPerBar": 4,      # a bar is 2 s
        "keys": [{"type": "key", "id": "key_1", "at": 0, "key": "G major"},
                 {"type": "key", "id": "key_2", "at": {"beat": 16}, "key": "A major"},
                 {"type": "key", "id": "key_3", "at": {"beat": 32}, "key": "G major"}]}


def note(at, pitch):
    return {"track": "piano", "start": at, "end": at + 1, "midis": [pitch]}


def test_each_note_is_judged_in_its_own_key():
    G_SHARP, C_NATURAL = 68, 60
    found = V.out_of_key([note(9.0, G_SHARP),        # bar 5, A major: in key
                          note(1.0, G_SHARP),        # bar 1, G major, no change near: out of key
                          note(17.0, G_SHARP),       # bar 9, back in G major: out of key
                          note(9.0, C_NATURAL),      # bar 5, A major: C natural is out of key
                          note(7.0, G_SHARP)],       # bar 4, the bar before A major: leads into it
                         ROOT, "G major")
    out = {(e["notes"][0], e["at_s"]) for e in found if e["kind"] == "out_of_key"}
    assert out == {("G#4", 1.0), ("C4", 9.0)}, found
    lead = [e for e in found if e["kind"] == "leads_into_key"]
    assert [(e["at_s"], e["into"]) for e in lead] == [(7.0, "A major")], found
    assert V.key_changes(ROOT) == [(0.0, "G major"), (8.0, "A major"), (16.0, "G major")]
