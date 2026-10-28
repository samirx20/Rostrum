"""Canary 3E r8: the app's own fix advice must hold on the render (dull_top's shelf), a riser that dies before its
peak is a fault, a faded ending is a fault when the song asks for a clean one, and a fault that comes back says what
the change did."""
from types import SimpleNamespace

import numpy as np
import soundfile as sf

from rostrum_sound.listen import applied, clean_end, faults, rise_gap, shelf_try

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


FADED = {"faded_s": 1.0, "rang_s": 2.4, "from_s": 19.0}


def test_a_faded_end_is_a_fault_only_when_a_clean_ending_is_asked():
    got = clean_end.fault(_doc("A cue that ends cleanly on a marker, a real ending, not a soft fade-out"), FADED)
    assert got and got[0]["id"] == "faded_end" and "ring_out(False)" in got[0]["fix"]
    assert not clean_end.fault(_doc("A 4-bar piano chord progression at 90 bpm"), FADED)
    assert not clean_end.fault(_doc("ends cleanly"), None)          # nothing was faded


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
