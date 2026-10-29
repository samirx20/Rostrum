"""Guards: onset sync check is accurate; the cut pool is analysed once and re-analysed on change; a held note is not called hum."""
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
    _clicks(f, [0.0, 1.0])                       # a hit at the very start is an onset too
    assert onsets(f)["onsets_s"][0] == 0.0


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


def test_a_held_note_is_a_tone_and_mains_hum_is_hum():
    from rostrum_sound.listen.dsp import stft
    from rostrum_sound.listen.tones import N_FFT, steady_tones
    t = np.arange(8 * SR) / SR
    swell = np.interp(t, [0, 3, 6, 8], [0.05, 1.0, 0.3, 0.02])            # a held D3 that swells and fades
    drone = 0.3 * swell * sum(a * np.sin(2 * np.pi * 146.83 * h * t) for h, a in [(1, 1), (2, 0.5), (3, 0.3)])
    hum = 0.03 * (np.sin(2 * np.pi * 60 * t) + np.sin(2 * np.pi * 240 * t) + np.sin(2 * np.pi * 360 * t))   # a mains series

    def tones(y):
        y = (y + 0.001 * rng.standard_normal(len(t))).astype(np.float32)
        return steady_tones(np.abs(stft(y, N_FFT, 1024)) ** 2, SR)
    held = tones(drone)
    assert any(x["note"] == "D3" for x in held) and not any(x["is_hum"] for x in held)
    found = tones(drone + hum)
    assert [round(x["freq_hz"]) for x in found if x["is_hum"]][:2] == [60, 360]
    assert not any(x["is_hum"] for x in found if x["note"] == "D3")
    lone = tones(0.3 * np.sin(2 * np.pi * 65.4 * t) + 0 * drone)          # a lone flat steady low note is not hum
    assert lone and not any(x["is_hum"] for x in lone)


def test_each_start_says_how_strong_it_is_in_its_own_file(tmp_path):
    # Re-bench member note: a part's starts were given without their strength (only the mix's hits had one).
    import numpy as np
    import soundfile as sf
    from rostrum_sound.listen.onsets import onsets
    sr, x = 48000, np.zeros(48000 * 2)
    for t, a in ((0.5, 0.5), (1.2, 0.05)):        # a loud hit, then one 20 dB softer
        i = int(t * sr)
        x[i:i + 2400] = a * np.exp(-np.arange(2400) / 400) * np.sin(np.arange(2400) * 0.3)
    sf.write(str(tmp_path / "part.wav"), x, sr)
    r = onsets(tmp_path / "part.wav")
    assert len(r["peaks_dbfs"]) == len(r["onsets_s"]) == 2
    assert r["peaks_dbfs"][0] > -7 and 16 < r["peaks_dbfs"][0] - r["peaks_dbfs"][1] < 24
