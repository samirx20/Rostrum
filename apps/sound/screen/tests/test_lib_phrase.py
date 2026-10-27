"""What would break silently: hearing a Library sound before adding it (interaction plan S3). The phrase is in the
song's key (every note a note of it) and at its tempo, and a click on the row that plays stops it."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_sound.doc import keys  # noqa: E402
from screensound import auditioner  # noqa: E402
from screensound.auditioner import Auditioner, phrase_track  # noqa: E402


def test_the_phrase_is_in_the_songs_key_and_a_few_seconds_at_any_tempo():
    for key, tempo in (("D minor", 120), ("F# major", 60), ("Bb dorian", 180)):
        doc = {"tempo": tempo, "keys": [{"id": "k1", "at": 0, "key": key}], "tracks": []}
        notes = phrase_track(doc)["notes"]
        assert all(keys.in_key(m, key) for n in notes for m in keys.midis(n["pitch"]))
        end = max(n["at"]["beat"] + n["dur"]["beats"] for n in notes)
        assert 2 <= end * 60 / tempo <= 5                       # never a minute of waiting, never a blip
    assert keys.midis(phrase_track({"tempo": 120})["notes"][0]["pitch"]) == [48]   # no key: C major


def test_the_row_that_plays_stops_on_a_second_click_and_another_replaces_it(monkeypatch):
    a = Auditioner(type("B", (), {"doc": type("D", (), {"data": {"tracks": []}})()})())
    monkeypatch.setattr(auditioner.threading, "Thread", lambda **kw: type("T", (), {"start": lambda s: None})())
    entry = {"instrument": "builtIn", "builtIn": "piano"}
    a.toggle(entry, "Piano", phrase=True)
    assert a.busy == "Piano"                                    # answered at once, before any sound is made
    a.toggle(entry, "Piano", phrase=True)
    assert a.busy == ""                                         # the same row again: stopped
    a.toggle(entry, "Piano", phrase=True)
    a.toggle(entry, "Harp", phrase=True)
    assert a.busy == "Harp"
