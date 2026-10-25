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


def test_clash_one_buries_the_other_yes_same_level_other_band_and_turns_no(tmp_path):
    assert _spans(tmp_path, dict(f=440), dict(f=430)) == []                    # same level: no real problem
    same = _spans(tmp_path, dict(f=440), dict(f=430, amp=0.15))               # 6 dB under
    assert len(same) == 1 and same[0]["buried_track"] == "b" and 5 < same[0]["buried_by_db"] < 7 and same[0]["band_hz"][0] <= 440 <= same[0]["band_hz"][1] and same[0]["end_s"] - same[0]["start_s"] > 1.5
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


def test_a_chord_is_checked_note_by_note_never_a_false_wrong_octave(tmp_path):
    """Guard: on a part playing chords each written note is looked for on its own: a right chord reads all ok (the
    pitch line named one note and called the rest wrong octaves), a note not played reads missing, one played an
    octave up reads wrong_octave."""
    from rostrum_sound.ears import chords_heard
    t = np.arange(int(2.0 * SR)) / SR
    tone = lambda m: sum(0.1 / h * np.sin(2 * np.pi * h * 440 * 2 ** ((m - 69) / 12) * t) for h in (1, 2, 3))  # noqa: E731
    sf.write(tmp_path / "c.wav", (tone(60) + tone(64) + tone(82)).astype("float32"), SR)   # C4 E4 and Bb5 (Bb4 an octave up)
    row = lambda midis: {"id": "n", "start": 0.0, "end": 2.0, "midis": midis}  # noqa: E731
    assert chords_heard.polyphonic([row([60, 64])])
    got = {r["written"]: r["status"] for r in chords_heard.check(tmp_path / "c.wav", [row([60, 64, 70, 69])])["rows"]}
    assert got == {"C4": "ok", "E4": "ok", "A#4": "wrong_octave", "A4": "missing"}, got


def test_ending_check_flags_a_cut_tail_and_passes_a_finished_one():
    """Guards the ending line of look_sound loudness: a tail still at -33 dBFS that falls off a cliff is a cut; a fade to silence is not."""
    import numpy as np
    from rostrum_sound.listen.ending import ending
    sr = 8000
    t = np.arange(int(3 * sr)) / sr
    tone = 0.03 * np.sin(2 * np.pi * 220 * t)
    cut = tone.copy()
    cut[-int(0.05 * sr):] *= 0.05                        # the last 50 ms fall 26 dB: a cut
    assert ending(cut[:, None], sr)["cut"] and not ending(cut[:, None], sr)["finished"]
    faded = tone * np.clip((3.0 - t) / 1.5, 0, 1) ** 4   # a long fade to silence
    e = ending(faded[:, None], sr)
    assert e["finished"] and not e["cut"]
