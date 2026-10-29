"""Canary 3E r8: the app's own fix advice must hold on the render (dull_top's shelf), a riser that dies before its
peak is a fault, and a fault that comes back says what
the change did."""
from types import SimpleNamespace

import numpy as np
import soundfile as sf

from rostrum_sound.listen import applied, faults, rise_gap, shelf_try

SR = 48000


def _tones(path, parts, seconds=6.0):
    t = np.arange(int(seconds * SR)) / SR
    y = sum(a * np.sin(2 * np.pi * f * t) for f, a in parts) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.5 * t) ** 2)
    sf.write(path, np.stack([y, y], axis=1) * 0.3, SR, subtype="PCM_24")
    return str(path)


def test_the_shelf_advice_never_claims_to_clear_what_it_does_not(tmp_path):
    dark = _tones(tmp_path / "dark.wav", [(300, 1.0), (600, 0.5), (5000, 0.002)])      # far too dark for any shelf
    f = [x for x in faults.check(dark)["faults"] if x["kind"] == "dull_top"][0]
    s = f["measured"]["shelf"]
    assert not s["clears"] and s["reaches_db"] < faults.DULL_DB
    assert "does not clear it" in f["words"] and "short" in f["words"] and "passes at" not in f["words"]
    near = _tones(tmp_path / "near.wav", [(500, 1.0), (6000, 0.06)])                    # a few dB short: a shelf does it
    f = [x for x in faults.check(near)["faults"] if x["kind"] == "dull_top"][0]
    s = f["measured"]["shelf"]
    assert s["clears"] and s["gain"] <= faults.SHELF_MOST_DB
    assert shelf_try.reach(near, s["gain"]) >= faults.DULL_DB + faults.SHELF_MARGIN       # the promise holds when re-measured
    assert f"\"gain\": {s['gain']:g}," in f["words"] and "measured on this render" in f["words"]


def _build(gap_from=None, seconds=7.0, at=6.0):
    """A rising noise roll up to `at`, silent from `gap_from` to `at`, then a hit."""
    rng = np.random.default_rng(1)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    y = rng.standard_normal(n) * 0.02 * (0.2 + t / at) * (t < at)
    if gap_from is not None:
        y[int(gap_from * SR):int(at * SR)] = 0.0
    y[int(at * SR):int((at + 0.3) * SR)] += 0.5 * rng.standard_normal(int(0.3 * SR))
    return np.stack([y, y], axis=1), SR


def test_a_riser_that_dies_before_its_peak_is_a_fault():
    f = rise_gap.faults(*_build(gap_from=3.5), 6.0)
    assert f and f[0]["kind"] == "gap_before" and abs(f[0]["measured"]["gap_s"] - 2.5) < 0.1
    assert not rise_gap.faults(*_build(), 6.0)                      # a build all the way in
    assert not rise_gap.faults(*_build(gap_from=5.6), 6.0)          # a 0.4 s breath before the peak


def _doc(brief=None):
    return SimpleNamespace(data={"brief": brief} if brief else {}, folder=None)


def test_a_fault_that_comes_back_says_what_the_change_did():
    raw = [{"kind": "dull_top", "at_s": 0.0, "measured": {"brightest_db": -29.1}}]
    shaped = [{"id": "dull_top", "what": "dull top end", "fix": "brighten"}]
    applied.tell(raw, shaped, {"dull_top": {"brightest_db": -33.8}})
    assert "was -33.8 dB, now -29.1 dB, passes at -20 dB or more" in shaped[0]["what"] and "not enough" in shaped[0]["what"]
    assert applied.record(raw, shaped) == {"dull_top": {"brightest_db": -29.1}}


def test_a_climax_at_the_files_end_is_read_not_a_crash(tmp_path):
    """Canary re-run (Haiku task 8): a climax 0.6 s before the file's end (its next seconds past the end, or silent) made the
    listening check crash (an empty stretch, then a -inf number in the fault words). It is read: the hold falls to silence."""
    sr = 48000
    t = np.arange(int(8.6 * sr)) / sr
    y = 0.05 * np.sin(2 * np.pi * 220 * t) * (t / 8.0)
    y[int(8.0 * sr):] = 0.6 * np.sin(2 * np.pi * 110 * t[int(8.0 * sr):])
    path = tmp_path / "end.wav"
    sf.write(path, np.stack([y, y], axis=1), sr)
    found = faults.check(str(path), [{"at": 8.0, "kind": "climax"}])["faults"]
    assert all(isinstance(faults._words(f), str) for f in found)


def test_a_solo_the_limiter_squashes_is_a_fault_and_a_gentle_master_is_not(tmp_path):
    """Canary task 7: a solo piano at -14 LUFS took 9.6 dB of limiting and shipped; a transparent master stays quiet."""
    from rostrum_sound.listen import passing, squash
    wav = _tones(tmp_path / "solo.wav", [(220, 1.0), (440, 0.4)])
    tracks = [{"id": "piano", "lufs": -13.3, "peak": 1.63, "rms": 0.124}, {"id": "bells", "lufs": -22.1, "peak": 0.67, "rms": 0.04}]
    song = {"tracks": tracks, "data": {"brief": "Export a -14 LUFS stereo mix.", "master": [{"normalize": True, "loudness": -14}]}}

    def lim(top):
        curve = np.zeros(60)
        curve[5:25] = top
        return {"max_db": top, "worst": [{"time_s": 0.5, "reduced_db": top, "drivers": []}], "_curve": curve, "curve_step_s": 0.1}
    f = [x for x in faults.check(wav, limiter=lim(9.6), song=song)["faults"] if x["kind"] == "squashed_mix"]
    assert f and f[0]["measured"]["lead"] == "piano" and f[0]["measured"]["exposed"]
    w = f[0]["words"]
    assert "9.6 dB" in w and "0.5–2.5 s" in w and "piano" in w and "brief fixes -14 LUFS" in w
    assert w.index("(1) raise the quiet parts") < w.index("(2) thicken")
    assert not passing.near(f[0]) and "Limiter: up to 9.6 dB" in squash.line(lim(9.6), tracks)
    for gentle in (2.5, 3.0):
        assert not [x for x in faults.check(wav, limiter=lim(gentle), song=song)["faults"] if x["kind"].startswith("squashed")]
        assert squash.line(lim(gentle), tracks) == ""
    swell = {**song, "data": {**song["data"], "brief": "A piano piece that starts quietly and builds to a climax."}}
    w = squash.words(squash.fault(wav, lim(9.6), swell)[0])
    assert "(1) thicken" in w and "not lifting the quiet parts" in w      # the brief's arc: no lift offered first
    dense = [{"id": k, "lufs": -20.0, "peak": 0.5, "rms": 0.1} for k in ("bass", "keys", "pad", "drums")]
    assert squash.fault(wav, lim(5.0), {**song, "tracks": dense}) == []    # a dense mix shares the gain under 6 dB
    from rostrum_sound.listen import fault_shape
    from rostrum_sound.mcp import asked_keep, brief_keep
    raw = [x for x in faults.check(wav, limiter=lim(9.6), song=song)["faults"] if x["kind"] == "squashed_mix"]
    shaped = fault_shape.shape(raw, None)
    assert shaped[0]["id"] == "squashed_mix"
    near = asked_keep.mark(raw, shaped, [])
    keep = asked_keep.screen(shaped, {"squashed_mix": "the brief says \"slammed\""}, {"squashed_mix"}, near)
    assert keep == {} and "keep refused" in shaped[0]["fix"]                 # 9.6 dB: too far from passing to keep
    assert brief_keep.why_not("squashed_mix", "\"Export a -14 LUFS stereo mix\"", song["data"])  # the brief never asks for it


def test_three_tracks_of_one_piano_are_one_exposed_piano(tmp_path):
    """Canary re-run: keys, lead and bell all on the piano (36 % each) passed 5.5 dB of limiting as a dense mix."""
    from rostrum_sound.listen import squash
    wav = _tones(tmp_path / "pianos.wav", [(220, 1.0)])
    tracks = [{"id": k, "lufs": -21.6, "peak": 0.6, "rms": 0.06} for k in ("keys", "lead", "bell")]
    curve = np.zeros(60)
    curve[5:25] = 5.5
    lim = {"max_db": 5.5, "worst": [{"time_s": 0.5, "reduced_db": 5.5, "drivers": []}], "_curve": curve, "curve_step_s": 0.1}
    data = {"brief": "A calm piano piece at -14 LUFS.", "master": [{"normalize": True, "loudness": -14}],
            "tracks": [{"id": k, "instrument": "builtIn", "builtIn": "piano"} for k in ("keys", "lead", "bell")]}
    f = squash.fault(wav, lim, {"tracks": tracks, "data": data})
    assert f and f[0]["measured"]["exposed"] and f[0]["measured"]["lead"] == "piano (keys, lead, bell)"
    assert squash.fault(wav, lim, {"tracks": tracks, "data": {**data, "tracks": []}}) == []   # three different sounds: dense
