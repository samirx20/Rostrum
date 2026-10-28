"""Moments read as a listener hears them (sound-script-first blind judging, 2026-10-28): drums only 6 dB down in a
drop's gap are still heard, a really silent gap is not a fault; after a stop, a band that keeps its pulse is named."""
import numpy as np

from rostrum_sound.listen import drop_gap, stop_fall

SR = 22050


def _chords(length):
    t = np.arange(int(length * SR)) / SR
    return 0.1 * sum(np.sin(2 * np.pi * f * t) for f in (220.0, 277.2, 329.6))


def _drums(length, every=0.25, gain=lambda t0: 1.0, seed=1):
    """A hat (bright noise burst) every `every` s and a kick (60 Hz thump) every 4th, scaled by gain(time)."""
    y, rng = np.zeros(int(length * SR)), np.random.default_rng(seed)
    hat_t, kick_t = np.arange(int(0.08 * SR)) / SR, np.arange(int(0.2 * SR)) / SR
    for k, t0 in enumerate(np.arange(0, length - 0.3, every)):
        a, g = int(t0 * SR), gain(t0)
        y[a:a + hat_t.size] += g * 0.3 * rng.normal(0, 1, hat_t.size) * np.exp(-hat_t * 60)
        if k % 4 == 0:
            y[a:a + kick_t.size] += g * 0.6 * np.sin(2 * np.pi * 60 * kick_t) * np.exp(-kick_t * 15)
    return y


def test_drums_in_gap_six_db_down_is_a_fault_silent_gap_is_not():
    for gap_gain, faulted in ((10 ** (-6 / 20), True), (0.0, False)):
        y = _chords(9.0) + _drums(9.0, gain=lambda t0: gap_gain if 4.0 <= t0 < 6.0 else 1.0)
        found = drop_gap.faults(y, SR, 4.0, 6.0)
        assert bool(found) == faulted, (gap_gain, found)
    assert 5 < found_db(_chords(9.0) + _drums(9.0, gain=lambda t0: 0.5 if 4.0 <= t0 < 6.0 else 1.0)) < 8


def found_db(y):
    return drop_gap.measure(y, SR, 4.0, 6.0)["down_db"]


def test_drop_return_from_entry_and_default_gap():
    assert drop_gap.return_of([{"at": 4.0, "kind": "drop"}, {"at": 6.0, "kind": "entry"}], 4.0) == 6.0
    assert drop_gap.return_of([{"at": 4.0, "kind": "drop"}], 4.0) is None
    y = _chords(9.0) + _drums(9.0, gain=lambda t0: 0.5 if t0 >= 4.0 else 1.0)
    (f,) = drop_gap.faults(y, SR, 4.0, None)
    assert f["measured"]["gap_assumed"] and f["measured"]["to_s"] == 5.5 and "no return given" in drop_gap.words(f)


def test_stop_names_a_band_that_keeps_its_pulse():
    going = _chords(8.0) + _drums(8.0)
    stopped = _chords(8.0) * (np.arange(int(8.0 * SR)) / SR < 4.3) + _drums(8.0, gain=lambda t0: 1.0 if t0 <= 4.0 else 0.0)
    kept, cut = stop_fall.measure(going, SR, 4.0), stop_fall.measure(stopped, SR, 4.0)
    assert kept["low_pulse_kept"] >= 0.7 and any("pulse" in w for w in stop_fall.why(kept))
    assert cut["low_pulse_kept"] < 0.2 and cut["under_before_db"] > 20 and stop_fall.why(cut) == []
