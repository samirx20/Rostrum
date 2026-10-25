"""loudness: LUFS, true peak, LRA, short-term curve, clipped moments, optional picture."""
import numpy as np

from . import bs1770
from .core import db, duration, load, name_of, num, peak_db
from .memo import remembered

CLIP_LEVEL = 0.999           # full scale: the sample is clipped
NEAR_CLIP_DB = -1.0          # within 1 dB of full scale: "near clip"
MERGE_S = 0.05               # hits closer than this are one moment


def short_term(y, sr, step=1.0, window=3.0):
    """Short-term LUFS (`window`-second window ending at each `step`, gated like the integrated value) -> (times,
    values). The K-weighting runs once over the whole file, as a running meter's would."""
    kw = bs1770.k_weight(y, sr)
    dur = duration(y, sr)
    ends = np.minimum(np.arange(step, dur + step - 1e-9, step), dur)
    return ends, np.array([bs1770.gated_lufs(kw[max(0, int((e - window) * sr)):int(e * sr)], sr) for e in ends])


def loudness_range(st):
    """EBU R128 LRA from short-term values: absolute gate -70, relative gate -20, 10-95 %."""
    v = st[st > -70]
    if v.size == 0:
        return float("nan")
    v = v[v > 10 * np.log10(np.mean(10 ** (v / 10))) - 20]
    return float(np.percentile(v, 95) - np.percentile(v, 10)) if v.size else float("nan")


def true_peak_db(y):
    return db(bs1770.true_peak(y) ** 2)


def clip_moments(y, sr):
    """Moments at or near full scale -> [{time_s, peak_dbfs, samples, clipped}]."""
    a = np.abs(y).max(axis=1)
    runs, start, last = [], None, None
    for i in np.nonzero(a >= 10 ** (NEAR_CLIP_DB / 20))[0]:
        if start is not None and i - last > MERGE_S * sr:
            runs.append((start, last))
            start = None
        start = i if start is None else start
        last = i
    if start is not None:
        runs.append((start, last))
    return [{"time_s": num(s / sr, 3), "peak_dbfs": num(db(float(a[s:e + 1].max()) ** 2)),
             "samples": int(e - s + 1), "clipped": bool((a[s:e + 1] >= CLIP_LEVEL).any())}
            for s, e in runs]


@remembered
def loudness(wav, out_png=None, step=1.0, series=None, limiter=None):
    """Facts about how loud `wav` is. `series` = the engine's own short-term values
    [(time_s, lufs)] (e.g. its 100 ms series), used for the curve instead of computing one.
    `out_png` writes the loudness + band-energy picture and returns its path under "png".
    `limiter` = {"stems": {track: wav}, "reduction": [dB per 100 ms], "caveat": str}: adds where the master limiter worked and which tracks
    drove it (listen/limiter.py) to the facts and a third panel to the picture."""
    y, sr = load(wav)
    if series is not None:
        t = np.array([p[0] for p in series], float)
        st = np.array([-200.0 if p[1] is None else p[1] for p in series], float)
    else:
        t, st = short_term(y, sr, step)
    out = {"file": name_of(wav), "duration_s": num(duration(y, sr), 3),
           "integrated_lufs": num(bs1770.integrated(y, sr)), "true_peak_dbtp": num(true_peak_db(y)),
           "lra_lu": num(loudness_range(st)), "sample_peak_dbfs": num(peak_db(y)),
           "rms_dbfs": num(db(np.mean(y.astype(np.float64) ** 2))),
           "clipped_samples": int(np.sum(np.abs(y) >= CLIP_LEVEL)),
           "clip_moments": clip_moments(y, sr),
           "short_term_step_s": num(float(t[1] - t[0]) if t.size > 1 else step, 3),
           "short_term_lufs": [num(v, 1) if v > -70 else None for v in st],
           "note": "short-term = 3 s window ending at each step; null = silence or under 0.4 s of audio; "
                   f"clip_moments are samples within {abs(NEAR_CLIP_DB):g} dB of full scale"}
    panel = None
    if limiter:
        from .limiter import HOP_S, limiter as measure
        lim = measure(limiter["stems"], limiter["reduction"], limiter.get("caveat", ""), engine_max_db=limiter.get("engine_max_db"))
        curve = lim.pop("_curve")
        out["limiter"] = lim
        panel = (HOP_S, curve.tolist(), lim["worst"])
    if out_png:
        from .curves import draw_loudness
        out["png"] = draw_loudness(y, sr, t, st, out_png, name_of(wav), limiter=panel)
    return out
