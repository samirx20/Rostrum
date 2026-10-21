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


def test_chords_and_keys_are_spelled_in_the_key():
    from rostrum_sound.ears.theory import key_name, name_chord
    assert name_chord([58, 62, 65], key="D minor") == "Bb"
    assert name_chord([62, 65, 70], key="F major") == "Bb/D"
    assert name_chord([61, 65, 68]) == "C#"
    assert key_name(3, "major") == "Eb major"


def test_over_full_scale_clips_only_in_a_fixed_point_file(tmp_path):
    """Guard: a stem above 0 dBFS is held by a float file and cut flat by a fixed-point one; the flag must say which."""
    from rostrum_sound import listen
    y = (1.5 * np.sin(2 * np.pi * 440 * np.arange(SR) / SR)).astype("float32")
    sf.write(tmp_path / "f.wav", y, SR, subtype="FLOAT")
    sf.write(tmp_path / "i.wav", y, SR, subtype="PCM_16")     # written clipped: reaches full scale
    flags = {f["stem"]: f for f in listen.levels({"f": str(tmp_path / "f.wav"), "i": str(tmp_path / "i.wav")})["flags"]}
    assert flags["f"]["flag"] == "over full scale" and flags["f"]["clips"] is False
    assert flags["i"]["flag"] == "clips" and flags["i"]["clips"] is True
