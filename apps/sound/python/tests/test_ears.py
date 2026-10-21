"""Guard: the clash finder says two stems clash when they are loud in the same band at the same time, and not when
they sit in different bands or take turns."""
import numpy as np
import soundfile as sf

from rostrum_sound.ears import clash

SR = 44100


def _sine(path, f, start=0.0, end=2.0, amp=0.3):
    t = np.arange(int(2.0 * SR)) / SR
    y = amp * np.sin(2 * np.pi * f * t) * ((t >= start) & (t < end))
    sf.write(path, y.astype("float32"), SR)
    return str(path)


def _spans(tmp_path, a, b):
    levels, hop = clash.stem_levels({"a": _sine(tmp_path / "a.wav", **a), "b": _sine(tmp_path / "b.wav", **b)})
    return clash.find_clashes(levels, hop_s=hop)[0]


def test_clash_same_band_yes_other_band_and_turns_no(tmp_path):
    same = _spans(tmp_path, dict(f=440), dict(f=450))
    assert len(same) == 1 and same[0]["band_hz"][0] <= 440 <= same[0]["band_hz"][1] and same[0]["end_s"] - same[0]["start_s"] > 1.5
    assert _spans(tmp_path, dict(f=440), dict(f=2000)) == []
    assert _spans(tmp_path, dict(f=440, end=0.9), dict(f=450, start=1.1)) == []
