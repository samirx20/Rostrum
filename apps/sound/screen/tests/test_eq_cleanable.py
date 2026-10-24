"""EQ bands as plain rows (one bands list underneath) and which clips show their Cleanup rows."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from screensound import cleanable, eq_rows


def test_an_eq_band_edit_rewrites_the_list_keeping_the_other_bands_and_a_new_band_starts_flat():
    eq = {"type": "effect", "effect": "eq", "id": "e", "bands": [{"shape": "peak", "freq": 1000, "gain": 3, "q": 1}]}
    more = eq_rows.edit_args(eq, "Bands", 2)["bands"]
    assert more[0] == eq["bands"][0] and more[1]["gain"] == 0 and len(more) == 2
    assert eq_rows.edit_args(eq, "Band 1 gain", -4)["bands"][0] == {"shape": "peak", "freq": 1000, "gain": -4.0, "q": 1}
    assert eq["bands"][0]["gain"] == 3                       # the document's own list is never changed in place
    assert eq_rows.edit_args(eq, "Band 1 type", "highpass")["bands"][0]["shape"] == "highpass"
    assert eq_rows.edit_args({"type": "effect", "effect": "delay"}, "Bands", 2) is None


def test_cleanup_rows_are_left_out_of_a_tone_and_kept_for_a_take_a_set_step_or_when_asked():
    asked = cleanable.Asked()
    tone = {"type": "clip", "id": "c1", "media": "media/tone.wav", "denoise": 0, "dereverb": 0, "isolate": False, "stem": "none"}
    assert asked.left_out(tone) == set(cleanable.FIELDS)
    assert asked.left_out({**tone, "media": "media/Recording-take-1.wav"}) == set()
    assert asked.left_out({**tone, "denoise": 0.6}) == set()
    asked.ids.add("c1")
    assert asked.left_out(tone) == set()
    assert asked.left_out({"type": "track", "id": "t"}) == set()
