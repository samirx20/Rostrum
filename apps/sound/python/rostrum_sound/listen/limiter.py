"""limiter: where the master's glue and limiter turned the mix down, and which tracks drove it.

Not a second limiter, and not a guess: the engine records the gain its mastering stage gave every frame and answers
the deepest reduction of each 100 ms (the render's `series.reductionDb`, the gain to the loudness target taken out).
The stems carry that same gain (handoff.stems_rule), so at any moment each stem's share of their sum is its share of
the signal the limiter was holding: that names the tracks that drove it."""
import numpy as np

from .core import db, load, num

HOP_S = 0.1           # the engine's curve: one point per 100 ms
MIN_DB = 0.05         # a reduction under this is under the files' own rounding (handoff.LIMITER_SLACK_DB)
SEPARATE_S = 0.5      # worst moments at least this far apart
WINDOW_S = 0.01       # who drives a moment: the stems' share over ±10 ms around its loudest sample
MIN_SHARE = 1.0       # a stem under 1 % of the signal (or silent there) is not listed
TOP_DRIVERS = 6
DEFAULT_MAX_LIMIT_DB = 2.0   # the master's `maxLimit` default (Most limiting)
TOP_SPANS = 8
WORTH_SAYING_DB = 0.5        # a lead track is named only when the limiter works this far over the allowance


def drivers(stems, pre, at, sr):
    """Each stem's share of the signal around sample `at`, loudest first. Shares are the stems' projections on their
    sum: they add to 100 % (a stem that cancels reads negative)."""
    a, b = max(0, at - int(WINDOW_S * sr)), min(pre.shape[0], at + int(WINDOW_S * sr))
    total = float(np.sum(pre[a:b].astype(np.float64) ** 2)) or 1.0
    rows = [{"track": k, "share_pct": num(100 * float(np.sum(y[a:b].astype(np.float64) * pre[a:b])) / total, 1),
             "level_dbfs": num(db(np.mean(y[a:b].astype(np.float64) ** 2)))} for k, y in stems.items()]
    rows = [r for r in rows if abs(r["share_pct"] or 0) >= MIN_SHARE and r["level_dbfs"] > -60]
    return sorted(rows, key=lambda r: -(r["share_pct"] or 0))[:TOP_DRIVERS]


def working_spans(red, top=TOP_SPANS):
    """The curve as the stretches where the limiter worked: [{from_s, to_s, max_db}], the `top` deepest, in time order.
    (Never the raw curve: a quiet piece is a few hundred zeros.)"""
    on = np.concatenate([[False], red >= MIN_DB, [False]])
    edges = np.flatnonzero(on[1:] != on[:-1])
    spans = [{"from_s": num(a * HOP_S, 2), "to_s": num(b * HOP_S, 2), "max_db": num(red[a:b].max(), 2)} for a, b in zip(edges[::2], edges[1::2])]
    return sorted(sorted(spans, key=lambda x: -x["max_db"])[:top], key=lambda x: x["from_s"])


def advice(worst, max_db, allowed_db):
    """Which track sets the limiter and by how many dB to lower it so the limiter stays within `allowed_db` (the master's
    Most limiting). The driver is the one that leads the most of the worst moments (the deepest decides a tie)."""
    led: dict = {}
    for w in worst:
        if w["drivers"]:
            led.setdefault(w["drivers"][0]["track"], []).append(w["reduced_db"])
    if not led or max_db is None:
        return None
    track = max(led, key=lambda k: (len(led[k]), max(led[k])))
    over = max(0.0, max_db - allowed_db)
    lower = round(over + 0.1, 1) if over >= WORTH_SAYING_DB else 0.0
    words = (f"{track} sets the limiter ({len(led[track])} of the {len(worst)} worst moments): lower {track} by {lower:g} dB (its volume, "
             f"track.set volume) to keep the limiter within Most limiting {allowed_db:g} dB." if lower else
             f"{track} sets the limiter, which works at most {max_db:g} dB: within Most limiting {allowed_db:g} dB, nothing to lower.")
    return {"track": track, "lower_db": lower, "keep_within_db": allowed_db, "moments_led": len(led[track]), "words": words}


def limiter(stems, reduction, caveat="", top=5, engine_max_db=None, max_limit_db=None):
    """stems: {track: wav} (the ones that add up to the mix); reduction: the engine's dB reduced per 100 ms.
    -> curve, worst moments, drivers."""
    red = np.asarray(reduction, dtype=np.float64)
    data = {k: load(p) for k, p in stems.items()}
    sr = next(iter(data.values()))[1] if data else 48000
    n = min((y.shape[0] for y, _ in data.values()), default=0)
    pre = sum(y[:n] for y, _ in data.values()) if data else None
    hop = int(sr * HOP_S)
    order = np.argsort(-red)
    worst, taken = [], []
    for i in order:
        if red[i] < MIN_DB or len(worst) >= top:
            break
        if all(abs(i - j) * HOP_S >= SEPARATE_S for j in taken):
            taken.append(i)
            row = {"time_s": num(i * HOP_S + HOP_S / 2, 2), "reduced_db": num(red[i], 2), "drivers": []}
            a = int(i * hop)
            if pre is not None and a < n:
                at = a + int(np.argmax(np.abs(pre[a:a + hop]).max(axis=1)))
                row["drivers"] = drivers({k: y[:n] for k, (y, _) in data.items()}, pre, at, sr)
            worst.append(row)
    max_db = num(red.max() if red.size else 0.0, 2)
    allowed = DEFAULT_MAX_LIMIT_DB if max_limit_db is None else max_limit_db
    return {"curve_step_s": HOP_S, "max_db": max_db, "working": working_spans(red), "advice": advice(worst, max_db, allowed),
            "engine_max_db": engine_max_db, "seconds_working": num(float((red >= MIN_DB).sum() * HOP_S), 2), "worst": worst,
            "how": "`working`: the deepest stretches where the limiter worked (the whole curve is in the picture); the engine's own gain on the mix (glue and limiter, the loudness target's gain taken out), the deepest of "
                   "each 100 ms; the drivers are each track's share of the signal at that moment" + (f"; {caveat}" if caveat else ""),
            "_curve": red}
