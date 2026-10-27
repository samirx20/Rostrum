"""A section follows its bars through a tempo change (critic r12 should-fix 1): one made from a time range on the
ruler (seconds) is kept on the beat it falls on, so 100 -> 132 bpm moves it with its hits instead of leaving it at
the old moment, overlapping its neighbours. A marker reference still follows its marker."""
from rostrum_core import Document, Who

from rostrum_sound import KIND
from rostrum_sound.doc import tempo, times

P = Who.person()


def _op(op, target, **args):
    return {"op": op, "target": target, "args": args}


def _beat(d, sid, key="at"):
    s = d.item(sid)
    return tempo.beat_at(d.data, times.seconds(s[key], d.data, sid))


def test_a_time_range_section_stays_on_its_bars_when_the_tempo_changes():
    d = Document.new(KIND)
    # 100 bpm: a beat = 0.6 s; bar 9 starts at beat 32 = 19.2 s; the range ends at bar 13 (beat 48 = 28.8 s)
    d.apply([_op("doc.set", ["root"], tempo=100), _op("track.add", [], id="p", instrument="kit", kit="drums"),
             _op("hit.add", ["p"], id="n", drum="hat", at={"beat": 32}),
             _op("section.add", [], name="verse", at=19.2, end=28.8)], P)
    d.apply(_op("doc.set", ["root"], tempo=132), P)
    assert abs(_beat(d, "section.verse") - 32) < 1e-6
    assert abs(_beat(d, "section.verse", "end") - 48) < 1e-6
    assert abs(times.seconds(d.item("section.verse")["at"], d.data, "v")
               - times.seconds(d.item("n")["at"], d.data, "n")) < 1e-6        # still starts with its hit


def test_a_section_moved_in_seconds_is_kept_on_its_beat_too():
    d = Document.new(KIND)
    d.apply([_op("doc.set", ["root"], tempo=120),
             _op("section.add", [], name="verse", at={"beat": 0}, end={"beat": 8})], P)
    d.apply(_op("section.set", ["section.verse"], at=2.0), P)                  # 2 s at 120 bpm = beat 4
    d.apply(_op("doc.set", ["root"], tempo=60), P)
    assert abs(_beat(d, "section.verse") - 4) < 1e-6


def test_a_section_on_a_marker_keeps_following_the_marker():
    d = Document.new(KIND)
    d.apply([_op("doc.set", ["root"], tempo=120), _op("marker.add", [], name="cut", at=10.0),
             _op("section.add", [], name="reveal", at="#cut", end={"beat": 40})], P)
    assert d.item("section.reveal")["at"] == "#cut"


def test_a_song_saved_with_sections_in_seconds_opens_with_them_on_their_bars():
    data, _ = KIND.migrate({"id": "root", "type": "doc", "tempo": 100, "tracks": [], "master": [], "sections": [
        {"id": "section.verse", "type": "section", "name": "verse", "at": 19.2, "end": 28.8},
        {"id": "section.drop", "type": "section", "name": "drop", "at": "#drop", "end": {"beat": 64}}]}, 7)
    verse, drop = data["sections"]
    assert verse["at"] == {"beat": 32.0} and verse["end"] == {"beat": 48.0}      # same place at 100 bpm, now on bars
    assert drop["at"] == "#drop" and drop["end"] == {"beat": 64}                 # a marker reference stays
