"""Sync without bending the music: a grid start (gridStart) moves bar 1 later and every reader agrees, downbeat lands a
bar on a time with a pickup, land glides the tempo so a bar lands, and a song without it is unchanged."""
import pytest

from rostrum_core import RostrumError

from rostrum_sound import run_source
from rostrum_sound.doc import tempo, times
from rostrum_sound.script_scope import printed

RAMPED = {"tempo": 120, "gridStart": 1.5,
          "tempos": [{"at": {"beat": 8}, "bpm": 120, "ramp": True}, {"at": {"beat": 16}, "bpm": 140}, {"at": 20.0, "bpm": 90}]}


def test_grid_start_moves_beat_zero_and_round_trips_through_ramps():
    assert tempo.seconds_at(RAMPED, 0) == 1.5 and tempo.seconds_at(RAMPED, 8) == 5.5
    assert tempo.seconds_at(RAMPED, -2) == pytest.approx(0.5)               # a pickup beat reads back at the first tempo
    for b in (-1.0, 3.0, 11.5, 18.0, 40.0):
        assert tempo.beat_at(RAMPED, tempo.seconds_at(RAMPED, b)) == pytest.approx(b, abs=1e-9)
    assert tempo.bpm_at(RAMPED, 19.99) != 90 and tempo.bpm_at(RAMPED, 20.01) == 90     # a change in seconds stays at its moment
    assert tempo.beats(RAMPED, 2.0)[:3] == [0.0, 0.5, 1.0]                  # the ruler draws the pickup's beats (-3, -2, -1)
    assert tempo.contract(RAMPED)[0] == {"beat": 0.0, "bpm": 120.0, "seconds": 1.5}


def test_old_songs_are_unchanged():
    assert tempo.seconds_at({"tempo": 96}, 8) == 5.0 and tempo.contract({"tempo": 96}) == 96.0
    assert tempo.contract({"tempo": 96, "gridStart": 0}) == 96.0


def test_downbeat_lands_with_a_pickup_and_says_so():
    tree = run_source("tempo(132); downbeat(bar(21), at=37.0)\n"
                      "t = track('keys', builtIn='piano'); t.note('G4', at=seconds_of(bar(1) - beats(1)), dur=beats(1))\n"
                      "t.note('C5', at=bar(21), dur=beats(1))", "sync.py")
    assert abs(times.seconds({"beat": 80}, tree, "t") - 37.0) < 1e-6
    assert tree["gridStart"] == pytest.approx(37.0 - 80 * 60 / 132)
    assert any("pickup" in line for line in printed())
    assert tempo.contract(tree) == [{"beat": 0.0, "bpm": 132.0, "seconds": tree["gridStart"]}]     # what compile sends


def test_downbeat_refuses_a_grid_before_zero_naming_bars_that_work():
    with pytest.raises(RostrumError) as e:
        run_source("tempo(132); downbeat(bar(21), at=36.0)", "sync.py")
    said = str(e.value.to_dict())
    assert "bar 20 lands at 36 s with a 1.45 s pickup" in said and "land(bar(21), at=36" in said


def test_land_glides_the_tempo_and_resumes_it():
    tree = run_source("tempo(132); land(bar(21), at=36.0, ramp_from=bar(15))", "sync.py")     # the ramp named below
    assert abs(tempo.seconds_at(tree, 80) - 36.0) < 1e-6
    assert tempo.bpm_at(tree, 36.5) == pytest.approx(132) and "gridStart" not in tree
    assert any("bpm over bar 15 - bar 21" in line for line in printed())
    with pytest.raises(RostrumError, match=r"ramp_from=bar\(15\)"):         # 4 bars is too short: refused, a longer ramp named
        run_source("tempo(132); land(bar(21), at=36.0, ramp_from=bar(17))", "sync.py")


def test_a_later_tempo_change_that_moves_a_landing_is_refused():
    with pytest.raises(RostrumError, match="now lands"):
        run_source("tempo(132); downbeat(bar(21), at=37.0); tempo_change(bar(9), 140)", "sync.py")


def test_a_negative_beat_is_refused_with_the_pickup_form():
    with pytest.raises(RostrumError) as e:
        run_source("tempo(120); t = track('k', builtIn='piano'); t.note('C4', at=bar(1) - beats(1), dur=beats(1))", "sync.py")
    assert "seconds_of" in str(e.value.to_dict())


def test_humanize_never_moves_a_bar_1_note_before_bar_1_with_a_pickup():
    src = ("tempo(132); downbeat(bar(21), at=37.0)\n"
           "t = track('keys', builtIn='piano').humanize(seed=s, timing=0.05)\n"
           "for b in range(1, 3): t.note('C4', at=bar(b), dur=beats(1))\n")
    for s in range(12):                                  # some seeds draw a move earlier: none may fail the run
        tree = run_source(f"s = {s}\n" + src, "pickup.py")
        notes = next(x for x in tree["tracks"] if x["id"] == "keys")["notes"]
        assert min(n["at"]["beat"] for n in notes) >= 0
