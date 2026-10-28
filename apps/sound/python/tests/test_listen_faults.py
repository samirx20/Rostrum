"""The fault check names what a listener would hear: a hit that is barely there, drums dropping early, one flat held tone
(sound-fair benchmark, 2026-10-28: the old check passed all three) and stays quiet on a clear hit."""
import numpy as np
import soundfile as sf

from rostrum_sound.listen.faults import check

SR = 48000
NOTES = [261.6, 329.6, 392.0, 440.0, 293.7, 349.2, 493.9, 523.3]


def _note(f, amp, dur=0.45):
    t = np.arange(int(dur * SR)) / SR
    click = np.random.default_rng(int(f)).normal(0, 1, t.size) * np.exp(-t * 200)
    return amp * (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(4 * np.pi * f * t) + 0.3 * click) * np.exp(-t * 6)


def _piece(path, hit_at=10.0, hit_amp=0.2, gap_before=0.0, stop_at=20.0, length=20.0):
    """A note every 0.5 s on a moving line; at `hit_at` a note `hit_amp` loud, with `gap_before` s of silence first."""
    y = np.zeros(int(length * SR))
    for k, t0 in enumerate(np.arange(0, stop_at, 0.5)):
        if hit_at - gap_before <= t0 < hit_at:
            continue
        loud = t0 == hit_at
        n = _note(NOTES[k % len(NOTES)] * (0.5 if loud else 1), hit_amp if loud else 0.2)
        if loud and hit_amp > 0.5:                      # a big hit: a chord, bright, from several instruments
            n = n + sum(_note(f, hit_amp / 2) for f in (130.8, 196.0, 659.3, 1046.5))
        a = int(t0 * SR)
        y[a:a + n.size] += n[:y.size - a]
    y = 0.8 * y / np.abs(y).max()
    sf.write(path, np.stack([y, np.roll(y, 240)], axis=1), SR, subtype="PCM_24")
    return str(path)


def kinds(r):
    return {f["kind"] for f in r["faults"]}


def test_weak_hit_named_with_time_and_fix(tmp_path):
    r = check(_piece(tmp_path / "weak.wav", hit_amp=0.26), [{"at": 10.0, "kind": "hit"}], whole=False)
    assert "weak_hit" in kinds(r)
    assert "10.0" in r["words"] and "a normal note" in r["words"] and "silence just before" in r["words"]


def test_clear_hit_passes(tmp_path):
    r = check(_piece(tmp_path / "clear.wav", hit_amp=1.5, gap_before=0.5), [{"at": 10.0, "kind": "hit"}], whole=False)
    assert r["faults"] == [], r["words"]


def test_drums_dropping_early(tmp_path):
    r = check(_piece(tmp_path / "drop.wav", stop_at=13.3), [{"at": 14.0, "kind": "drop"}], whole=False)
    f = [f for f in r["faults"] if f["kind"] == "early_drop"]
    assert f and 0.4 < f[0]["measured"]["early_s"] < 1.0


def test_flat_held_tone(tmp_path):
    t = np.arange(20 * SR) / SR
    y = 0.2 * sum(np.sin(2 * np.pi * f * t) for f in (146.8, 220.0, 293.7))
    sf.write(tmp_path / "flat.wav", np.stack([y, y], axis=1), SR, subtype="PCM_24")
    r = check(str(tmp_path / "flat.wav"))
    assert "held_tone" in kinds(r) and "one flat tone" in r["words"]
    assert "near_mono" in kinds(r)
