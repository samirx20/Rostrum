"""Guards: onset sync check is accurate; the cut pool is analysed once and re-analysed on change."""
import importlib

import numpy as np
import soundfile as sf

from rostrum_sound.listen import onsets
pool_mod = importlib.import_module("rostrum_sound.sfx.pool")   # the package re-exports a function named pool

SR = 48000
rng = np.random.default_rng(1)


def _clicks(path, times, dur=3.0):
    x = np.zeros(int(dur * SR), np.float32)
    for t in times:
        i = int(t * SR)
        n = int(0.15 * SR)                       # a 150 ms decaying burst, sharp start
        x[i:i + n] = 0.8 * np.exp(-np.arange(n) / (0.03 * SR)) * rng.uniform(-1, 1, n)
    sf.write(path, x, SR)


def test_onsets_expect_within_5ms(tmp_path):
    f = tmp_path / "clicks.wav"
    _clicks(f, [0.5, 1.2, 2.0])
    r = onsets(f, expect=[0.5, 1.2, 2.0])
    assert all(abs(row["offset_ms"]) <= 5 for row in r["expected"]), r["expected"]
    assert r["all_pass"]


def test_pool_cache_reads_then_reanalyses_on_change(tmp_path, monkeypatch):
    f, store = tmp_path / "rec.wav", tmp_path / "cache"
    _clicks(f, [0.5, 1.2, 2.0])
    calls = []
    real = pool_mod._analyse
    monkeypatch.setattr(pool_mod, "_analyse", lambda p, o: calls.append(p) or real(p, o))
    a = pool_mod.cut(f, cache_dir=store)
    b = pool_mod.cut(f, cache_dir=store)
    assert (a["cached"], b["cached"], len(calls)) == (False, True, 1)
    assert a["cuts"] == b["cuts"] and a["cuts"]
    _clicks(f, [0.5, 1.2])                       # the file changed
    c = pool_mod.cut(f, cache_dir=store)
    assert not c["cached"] and len(calls) == 2
