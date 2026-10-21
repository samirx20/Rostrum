"""Guards the fact sync rests on: a cut starts 5 ms before its transient (door_redo starts it 5 ms
early), within a few milliseconds (a frame is 40 ms), and the rules in pick.py keep or drop cuts by their facts."""
import numpy as np

from redo import pool
from redo.pick import Picker


def test_hit_cuts_start_5ms_before_each_click():
    sr = pool.SR
    x = np.random.default_rng(0).normal(0, 1e-4, sr * 3).astype(np.float32)
    clicks = [0.5, 1.3, 2.2]
    for t in clicks:
        n = int(t * sr)
        x[n:n + 2400] += np.exp(-np.arange(2400) / 300) * np.sin(np.arange(2400) * 0.6) * 0.5
    cuts = pool.hits(x, {"max_s": 0.4})
    starts = sorted(c["offset"] + 0.005 for c in cuts if c["snr_db"] > 30)
    assert len(starts) == 3
    for got, want in zip(starts, clicks):
        assert abs(got - want) < 0.006, (got, want)  # onset step is 128 samples = 2.7 ms


def test_picker_respects_facts_and_does_not_repeat_back_to_back():
    base = {"kind": "padlock", "length": 0.3, "attack_ms": 5, "cosine": 0.3}
    pool_ = [dict(base, path="a", offset=0.0, centroid_hz=12000, prob=0.99),   # too bright: dropped
             dict(base, path="a", offset=1.0, centroid_hz=5000, prob=0.9),
             dict(base, path="b", offset=0.0, centroid_hz=4000, prob=0.8)]
    p = Picker(pool_)
    first, second = p.pick("padlock", 0.05, 1.0), p.pick("padlock", 0.05, 1.2)
    assert (first["path"], first["offset"]) == ("a", 1.0)
    assert second["path"] == "b"
