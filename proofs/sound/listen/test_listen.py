"""Two facts agents rely on: LUFS is calibrated, and onset offsets are honest.
Run from proofs/sound/:  python -m pytest listen -q"""
import numpy as np
import soundfile as sf

from listen import loudness, onsets

SR = 44100


def test_sine_minus20_dbfs_reads_minus23_lufs(tmp_path):
    t = np.arange(SR * 5) / SR
    y = (10 ** (-20 / 20) * np.sin(2 * np.pi * 1000 * t)).astype(np.float32)
    p = str(tmp_path / "sine.wav")
    sf.write(p, y, SR, subtype="FLOAT")
    r = loudness.analyse(p)
    assert abs(r["integrated_lufs"] - (-23.0)) < 0.3, r["integrated_lufs"]
    assert abs(r["sample_peak_dbfs"] - (-20.0)) < 0.1


def test_clicks_over_sweep_report_near_zero_offset(tmp_path):
    t = np.arange(SR * 6) / SR
    f = 200 + 1800 * t / 6
    y = 0.1 * np.sin(2 * np.pi * np.cumsum(f) / SR)
    times = [1.2, 2.45, 3.4, 4.8]
    for c in times:
        i = int(c * SR)
        y[i:i + 40] += 0.8 * np.hanning(40)
    p = str(tmp_path / "clicks.wav")
    sf.write(p, y.astype(np.float32), SR, subtype="FLOAT")
    r = onsets.analyse(p, expect=times)
    for row in r["expected"]:
        assert row["offset_ms"] is not None and abs(row["offset_ms"]) < 10, row
