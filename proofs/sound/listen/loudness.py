"""loudness: LUFS, true peak, LRA, short-term curve, peak/RMS, clipping."""
import numpy as np
import pyloudnorm as pyln
from scipy.signal import resample_poly

from .core import db, duration, load, num

CLIP_LEVEL = 0.999


def _lufs(meter, seg):
    # pyloudnorm needs at least one 400 ms block
    if seg.shape[0] < int(0.4 * meter.rate):
        return float("-inf")
    return float(meter.integrated_loudness(seg))


def short_term(y, sr, step=1.0, window=3.0):
    """Short-term LUFS (3 s window ending at each step) -> (times, values)."""
    meter = pyln.Meter(sr)
    n = y.shape[0]
    ends = np.arange(step, duration(y, sr) + step - 1e-9, step)
    ends = np.minimum(ends, n / sr)
    vals = []
    for e in ends:
        a = max(0, int((e - window) * sr))
        vals.append(_lufs(meter, y[a:int(e * sr)]))
    return ends, np.array(vals)


def loudness_range(st_vals):
    """EBU R128 LRA from short-term values: abs gate -70, rel gate -20, 10-95 %."""
    v = st_vals[st_vals > -70]
    if v.size == 0:
        return float("nan")
    rel = 10 * np.log10(np.mean(10 ** (v / 10))) - 20
    v = v[v > rel]
    return float(np.percentile(v, 95) - np.percentile(v, 10)) if v.size else float("nan")


def true_peak_db(y):
    up = resample_poly(y, 4, 1, axis=0)
    return db(np.max(np.abs(up)) ** 2)


def analyse(path_or_data, sr=None):
    y, sr = load(path_or_data) if isinstance(path_or_data, str) else (path_or_data, sr)
    meter = pyln.Meter(sr)
    t, st = short_term(y, sr)
    peak = float(np.max(np.abs(y)))
    return {
        "duration_s": num(duration(y, sr), 3),
        "integrated_lufs": num(_lufs(meter, y)),
        "true_peak_dbtp": num(true_peak_db(y)),
        "lra_lu": num(loudness_range(st)),
        "sample_peak_dbfs": num(db(peak ** 2)),
        "rms_dbfs": num(db(np.mean(y.astype(np.float64) ** 2))),
        "clipping_samples": int(np.sum(np.abs(y) >= CLIP_LEVEL)),
        "short_term_lufs_per_s": [num(v, 1) for v in st],
        "short_term_note": "3 s window ending at t=1,2,3...s; null = silence or <0.4 s of audio",
    }
