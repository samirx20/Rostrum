"""Every voicing `voice` knows lands inside the range it was given (agents cannot hear a note an octave under it), or
refuses loudly; `bass=True` stays under the voicing and never under E1. Loops over the registry, not a hand list."""
import itertools

import pytest

from rostrum_core import RostrumError
from rostrum_sound.doc import keys as K
from rostrum_sound.writing.voicing import BASS_FLOOR, VOICINGS, voice

CHORDS = ["C", "Am", "F#m7", "Bbmaj7", "G7", "Dm9", "Esus4", "C/E", "Bm7b5", "Cdim7", "C13", "Ebm11", "A7#9"]
RANGES = [("G3", "D5"), ("C3", "C4"), ("A3", "E5"), ("E2", "B3"), ("C4", "C6"), ("F2", "F4")]


@pytest.mark.parametrize("voicing", VOICINGS)
def test_every_voicing_stays_inside_its_range(voicing):
    fitted = 0
    for (lo, hi), inversion, voices in itertools.product(RANGES, (0, 1, 2), (None, 3, 4, 5)):
        try:
            out = voice(CHORDS, "C major", voicing=voicing, inversion=inversion, voices=voices, range=(lo, hi), bass=True)
        except RostrumError as e:
            assert any(w in str(e) for w in ("spans", "does not fit", "same note")), str(e)
            continue
        fitted += 1
        for chord in out:
            ms = [K.midi(n) for n in chord]
            b, notes = ms[0], ms[1:]
            assert all(K.midi(lo) <= m <= K.midi(hi) for m in notes), (voicing, lo, hi, chord)
            assert len(set(notes)) == len(notes), (voicing, chord)
            assert b < notes[0] and (b >= BASS_FLOOR or b + 12 >= notes[0]), (voicing, chord)  # floor unless it would cross
    assert fitted, f"{voicing} fitted no range at all"


def test_a_shape_wider_than_the_range_says_so():
    with pytest.raises(RostrumError, match="spans"):
        voice(["Cmaj7"], voicing="spread", voices=4, range=("C4", "C5"))
