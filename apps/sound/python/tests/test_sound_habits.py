"""Agents' common habits from MIDI and DAWs are read, not refused, and the reply says once what was read."""
import pytest

from rostrum_core import RostrumError
from rostrum_sound import run_source
from rostrum_sound.script_scope import printed

HEAD = "tempo(120); length(bar(5))\n"


def run(src):
    return run_source(HEAD + src, "t.py")


def test_a_midi_velocity_is_read_on_0_to_127_and_said_once():
    tree = run("t = track('a', builtIn='piano')\nfor i in range(3):\n    t.note('C4', at=beat(i), dur=1, vel=40 + i * 5)\n"
               "t.note('D4', at=beat(3), dur=1, vel=0.5); t.note('E4', at=beat(4), dur=1, vel=1)")
    assert [round(n["vel"], 4) for n in tree["tracks"][0]["notes"]] == [round(40 / 127, 4), round(45 / 127, 4), round(50 / 127, 4), 0.5, 1]
    said = [line for line in printed() if "0 to 127" in line]
    assert said == ["vel=40 was read on MIDI's 0 to 127 scale as 0.31; every whole-number vel from 2 to 127 is read that way "
                    "(Rostrum's own scale is 0 to 1)."]


def test_velocity_is_the_name_vel_on_notes_chords_and_hits():
    tree = run("t = track('a', builtIn='piano'); t.note('C4', at=0, dur=1, velocity=0.5); t.chord(['C4', 'E4'], at=1, dur=1, velocity=0.4)\n"
               "d = track('d', kit='drums'); d.hit('kick', at=0, velocity=127)")
    assert [n["vel"] for n in tree["tracks"][0]["notes"]] == [0.5, 0.4]
    assert tree["tracks"][1]["hits"][0]["vel"] == 1
    assert printed().count("velocity= was read as vel= (the same thing).") == 1


@pytest.mark.parametrize("src", ["vel=1.5", "vel=128", "vel=0.5, velocity=0.5"])
def test_what_is_not_a_plain_midi_velocity_is_still_refused(src):
    with pytest.raises(RostrumError):
        run(f"t = track('a', builtIn='piano'); t.note('C4', at=0, dur=1, {src})")


def test_a_send_to_a_bus_not_made_makes_it_by_its_name():
    tree = run("t = track('a', builtIn='piano'); t.note('C4', at=0, dur=1)\n"
               "t.send('reverb', 0.3); t.send('room', 0.2); t.send('echo', 0.2); t.send('fx'); t.send('own')\n"
               "bus('own')")
    buses = {b["id"]: b for b in tree["buses"]}
    assert [(e["effect"], e.get("space"), e["mix"]) for e in buses["reverb"]["effects"]] == [("reverb", "hall", 1.0)]
    assert buses["room"]["effects"][0]["space"] == "room"
    assert buses["echo"]["effects"][0]["effect"] == "delay" and buses["fx"]["effects"] == [] and buses["own"]["effects"] == []
    assert [s["bus"] for s in tree["tracks"][0]["sends"]] == ["reverb", "room", "echo", "fx", "own"]
    assert ('track "a" sends to "reverb", which the script never made: made a bus "reverb" with a hall reverb on it, '
            "playing to the master.") in printed()
    assert not any('"own"' in line for line in printed())         # a bus the script made is not mentioned


def test_a_section_without_end_runs_to_the_next_one_or_the_song_end():
    tree = run("section('chorus', at=bar(3))\nsection('verse', at=bar(1))\nsection('outro', at=bar(4))\nsection('bridge', at=bar(2), end=bar(3))")
    ends = {s["name"]: s["end"] for s in tree["sections"]}
    assert ends == {"verse": {"beat": 4.0}, "chorus": {"beat": 12.0}, "outro": {"beat": 16.0}, "bridge": {"beat": 8.0}}
    assert printed() == ['A section without end= runs on: "chorus" to where "outro" starts, "verse" to where "bridge" starts, '
                         '"outro" to the end of the song.']


def test_a_last_section_with_no_end_and_no_length_says_what_to_write():
    with pytest.raises(RostrumError) as e:
        run_source("tempo(120)\nsection('intro', at=bar(1))", "t.py")
    assert "end=bar(17)" in str(e.value)


def test_a_common_instrument_name_plays_the_nearest_built_in_said():
    tree = run("t = track('bells', builtIn='celesta'); u = track('h', builtIn='French Horn'); v = track('p', builtIn='piano')")
    assert [t["builtIn"] for t in tree["tracks"]] == ["glockenspiel", "horn", "piano"]
    assert "celesta isn't a built-in sound; track \"bells\" uses glockenspiel, the nearest." in printed()
    assert len(printed()) == 2
    with pytest.raises(RostrumError):
        run("track('x', builtIn='harpsichord')")           # no honest near sound: still refused with the close names
