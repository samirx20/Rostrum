"""limiter: where the master limiter worked, and which tracks drove it.

Not a second limiter. The stems leave through the master's linear gain only (handoff.stems_rule), so the
tracks added together are the signal that went INTO the glue and limiter; the mix is what came out. The
gain reduction over time is the mix against that sum, measured. It is exact where the glue and the master
effects did not act (`caveat` says when they did); the engine itself reports only the largest number."""
import numpy as np

from .core import db, load, num

HOP_S = 0.01          # one point of the curve per 10 ms
MIN_DB = 0.05         # a reduction under this is under the files' own rounding (handoff.LIMITER_SLACK_DB)
SEPARATE_S = 0.5      # worst moments at least this far apart
WINDOW_S = 0.01       # who drives a moment: the stems' share over ±10 ms around its loudest sample
MIN_SHARE = 1.0       # a stem under 1 % of the signal (or silent there) is not listed
TOP_DRIVERS = 6
FLOOR = 1e-4          # blocks quieter than this (−80 dBFS) hold no meaningful ratio


def _blocks(y, hop):
    n = y.shape[0] // hop
    return (y[:n * hop].astype(np.float64) ** 2).reshape(n, hop, -1).sum(axis=(1, 2)) / (hop * y.shape[1])


def reduction_curve(mix, pre, sr):
    """dB reduced per 10 ms block (>= 0): the mix's level against the sum of the stems' (before the limiter)."""
    hop = int(sr * HOP_S)
    n = min(mix.shape[0], pre.shape[0])
    m, p = _blocks(mix[:n], hop), _blocks(pre[:n], hop)
    live = p > FLOOR ** 2
    red = np.zeros_like(p)
    red[live] = 10 * np.log10(np.maximum(p[live], 1e-30) / np.maximum(m[live], 1e-30))
    return np.clip(red, 0.0, None)


def drivers(stems, pre, at, sr):
    """Each stem's share of the signal going into the limiter around sample `at`, loudest first.
    Shares are the stems' projections on the sum: they add to 100 % (a stem that cancels reads negative)."""
    a, b = max(0, at - int(WINDOW_S * sr)), min(pre.shape[0], at + int(WINDOW_S * sr))
    total = float(np.sum(pre[a:b].astype(np.float64) ** 2)) or 1.0
    rows = [{"track": k, "share_pct": num(100 * float(np.sum(y[a:b].astype(np.float64) * pre[a:b])) / total, 1),
             "level_dbfs": num(db(np.mean(y[a:b].astype(np.float64) ** 2)))} for k, y in stems.items()]
    rows = [r for r in rows if abs(r["share_pct"] or 0) >= MIN_SHARE and r["level_dbfs"] > -60]
    return sorted(rows, key=lambda r: -(r["share_pct"] or 0))[:TOP_DRIVERS]


def limiter(mix, stems, caveat="", top=5, engine_max_db=None):
    """mix: wav; stems: {track: wav} (the ones that add up to the mix). -> curve, worst moments, drivers."""
    my, sr = load(mix)
    data = {k: load(p)[0] for k, p in stems.items()}
    n = min([my.shape[0]] + [y.shape[0] for y in data.values()])
    data = {k: y[:n] for k, y in data.items()}
    pre = sum(data.values())
    red = reduction_curve(my[:n], pre, sr)
    order = np.argsort(-red)
    worst, taken = [], []
    for i in order:
        if red[i] < MIN_DB or len(worst) >= top:
            break
        if all(abs(i - j) * HOP_S >= SEPARATE_S for j in taken):
            taken.append(i)
            a = int(i * HOP_S * sr)
            hop = int(sr * HOP_S)
            at = a + int(np.argmax(np.abs(pre[a:a + hop]).max(axis=1)))
            worst.append({"time_s": num(i * HOP_S + HOP_S / 2, 2), "reduced_db": num(red[i], 2),
                          "drivers": drivers(data, pre, at, sr)})
    tenth = int(round(0.1 / HOP_S))
    coarse = [num(red[i:i + tenth].max(), 2) for i in range(0, red.size, tenth)]     # the deepest of each 100 ms
    return {"curve_step_s": 0.1, "reduction_db": coarse, "max_db": num(red.max() if red.size else 0.0, 2), "engine_max_db": engine_max_db,
            "seconds_working": num(float((red >= MIN_DB).sum() * HOP_S), 2), "worst": worst,
            "how": "measured as the mix against the sum of the tracks' stems (the signal going into the limiter), "
                   "per 10 ms, so it is a close estimate of the engine's own gain, not its exact curve" + (f"; {caveat}" if caveat else ""),
            "_curve": red}
