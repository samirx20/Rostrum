"""The writing helpers' answers agents build on without hearing them: numerals in a key, voice leading, approach notes,
and the line landing on the beats it says (the same notes, so the same ids, on a re-run)."""
import pytest

from rostrum_core import RostrumError
from rostrum_sound import run_source
from rostrum_sound.writing import bass_line, roman, voice


@pytest.mark.parametrize("numeral, key, chord", [
    ("VII", "A minor", "G"), ("III", "A minor", "C"), ("bVII", "C major", "Bb"), ("V7/V", "C major", "D7"),
    ("ii7", "C major", "Dm7"), ("#vii°7", "A minor", "G#dim7"), ("vii°7", "A minor", "Gdim7"), ("VI", "D minor", "Bb"), ("iv", "C minor", "Fm")])
def test_numerals_are_the_degree_of_the_keys_own_scale(numeral, key, chord):
    assert roman(numeral, key) == chord


def test_led_voicing_holds_common_tones_and_moves_the_rest_by_step():
    c, am, f, g7 = voice(["C", "Am", "F", "G7"], key="C major")
    assert {"C4", "E4"} <= set(c) & set(am)              # C to Am: C and E stay, G steps to A
    assert "A4" in am and "A4" in f                     # Am to F: A held
    assert len(g7) == 4 and "B3" in g7                  # C's E falls a half step to B on G7


def test_approach_note_is_a_half_step_into_the_next_root():
    ln = bass_line(["C", "F"], style="walking", approach=True, key="C major")
    last_of_bar1 = [n for n in ln if n["at"] < 4][-1]
    assert last_of_bar1["pitch"] in ("E2", "F#2", "E1", "F#1")
    assert [n for n in ln if n["at"] == 4][0]["pitch"].startswith("F")


def test_a_written_line_lands_on_its_beats_and_reruns_the_same():
    src = ('tempo(100); key("D minor"); length(bar(5)); p = track("p", builtIn="grandPiano")\n'
           'write(p, comp(["i", "VI"], rhythm="half"), bar(2))\n')
    one, two = run_source(src, "w.py"), run_source(src, "w.py")
    notes = one["tracks"][0]["notes"]
    assert [n["at"] for n in notes] == [{"beat": 4.0}, {"beat": 6.0}, {"beat": 8.0}, {"beat": 10.0}]
    assert notes[0]["pitch"] == ["D4", "F4", "A4"] and notes[2]["pitch"][-1] in ("Bb4", "A4", "D5")
    assert [n["id"] for n in notes] == [n["id"] for n in two["tracks"][0]["notes"]]


def test_a_numeral_without_a_key_is_a_loud_error_naming_the_fix():
    with pytest.raises(RostrumError, match="key"):
        run_source('p = track("p", builtIn="grandPiano"); write(p, comp(["ii", "V"]))', "w.py")
