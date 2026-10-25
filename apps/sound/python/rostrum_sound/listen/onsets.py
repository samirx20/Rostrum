"""onsets: hit times, and offsets from the times a picture expects them."""
import numpy as np

from .core import duration, load, mono, name_of, num
from .dsp_events import onset_times
from .memo import remembered

HOP = 256


def _refine(m, sr, t, span=0.04):
    """Move a detected onset to the first sample that rises above 50 % of the local peak
    (the detector's frame grid is coarser than a click)."""
    a, b = max(0, int((t - span) * sr)), min(len(m), int((t + span) * sr))
    seg = np.abs(np.diff(m[a:b], prepend=m[a]))
    if seg.size == 0 or seg.max() <= 0:
        return t
    return (a + int(np.argmax(seg > 0.5 * seg.max()))) / sr


START_S, START_SHARE = 0.01, 0.05     # a sound already at full strength in the first 10 ms (of the file's peak or 5 %)


def _starts_at_zero(m, sr):
    """The detector measures a rise between frames, so a sound that is already there at sample 0 has nothing to rise
    from. It is an onset all the same: the first 10 ms hold at least 5 % of the file's peak."""
    top = float(np.max(np.abs(m))) if m.size else 0.0
    return top > 1e-4 and float(np.max(np.abs(m[:max(1, int(START_S * sr))]))) >= START_SHARE * top


def detect(m, sr):
    ons = [_refine(m, sr, t) for t in onset_times(m, sr, HOP)]
    return [0.0] + ons if _starts_at_zero(m, sr) and not (ons and ons[0] < 0.03) else ons


@remembered
def file_onsets(wav):
    """The onset times of one file (remembered until the file changes)."""
    y, sr = load(wav)
    return detect(mono(y), sr)


REACH_S = 0.25           # a stem's onset counts for a time only within this far of it (another sound's start is not this one's)
SOFT_RISE_DB = 6.0       # a soft or masked start: the level rises this far over the quietest it was just before
SOFT_FLOOR_DBFS = -70.0
ENV_S = 0.01


def soft_onset(m, sr, e, reach=REACH_S, rise_db=SOFT_RISE_DB):
    """The start of a soft or masked sound near `e` that the hit detector (which wants a sharp jump) misses: a swell,
    a bow, a brass entry over a held chord. Reads the 10 ms level around `e` and returns the first time (within `reach`)
    where it stands `rise_db` over the quietest it has been since `reach` before `e`, else None."""
    h = max(1, int(ENV_S * sr))
    a, b = max(0, int((e - reach) * sr)), min(len(m), int((e + reach) * sr))
    n = (b - a) // h
    if n < 3:
        return None
    seg = m[a:a + n * h].astype(np.float64).reshape(n, h)
    env = 10 * np.log10(np.mean(seg ** 2, axis=1) + 1e-12)
    low = np.minimum.accumulate(env)
    hit = np.nonzero((env - low >= rise_db) & (env > SOFT_FLOOR_DBFS))[0]
    return None if not len(hit) else (a + int(hit[0]) * h) / sr


def with_soft(m, sr, ons, expect, reach=REACH_S):
    """`ons` plus, for each expected time with no onset within `reach`, the soft onset there (when there is one)."""
    out = list(ons)
    for e in expect:
        if not any(abs(t - e) <= reach for t in ons):
            t = soft_onset(m, sr, e, reach)
            if t is not None:
                out.append(t)
    return sorted(out)


def _nearest(ons, e, reach=None):
    """(the nearest onset, its offset in ms), None when there is none (within `reach` seconds, when given)."""
    near = min(ons, key=lambda t: abs(t - e)) if ons else None
    if near is not None and reach is not None and abs(near - e) > reach:
        near = None
    return near, (None if near is None else num((near - e) * 1000, 1))


def which_stem(mix, stems, expect, tolerance=0.04):
    """For each expected time: the stem whose onset is nearest (and how far off, ms; > 0 = late), the next two
    stems, and the mix's own nearest onset: one answer per time instead of one look per stem. Same detector as `onsets`."""
    def of(p):
        y, sr = load(p)
        return with_soft(mono(y), sr, file_onsets(p), expect)
    found = {k: of(p) for k, p in stems.items()}
    mix_ons = file_onsets(mix)
    rows = []
    for e in expect:
        near = {k: _nearest(o, e, REACH_S) for k, o in found.items()}
        ranked = sorted((k for k, (t, _) in near.items() if t is not None), key=lambda k: abs(near[k][1]))
        mt, mo = _nearest(mix_ons, e)
        best = ranked[0] if ranked else None
        rows.append({"expected_s": e, "stem": best, "stem_onset_s": num(near[best][0], 4) if best else None,
                     "offset_ms": near[best][1] if best else None,
                     "pass": best is not None and abs(near[best][1]) <= tolerance * 1000,
                     "next_stems": [{"stem": k, "offset_ms": near[k][1]} for k in ranked[1:3]],
                     "mix_onset_s": None if mt is None else num(mt, 4), "mix_offset_ms": mo})
    return {"expected": rows, "tolerance_ms": num(tolerance * 1000, 1), "all_pass": all(r["pass"] for r in rows),
            "note": "stem = the track whose onset is nearest the time, within 250 ms (a stem with none that close is not listed: "
                    "another sound's start is never quoted as its own); a soft or masked start (a swell, a bow, an entry over a held "
                    "chord) is found as the level rising 6 dB over its quietest just before; mix_* = the mix's nearest onset (a louder "
                    "sound nearby can win there). Stems are the last render's."}


def onsets(wav, expect=None, tolerance=0.04):
    """Onset times in seconds. With `expect` (times a picture says a sound must start), each gets
    its nearest onset, the offset in ms (> 0 = sound lands late) and pass/fail against `tolerance`
    seconds (one video frame = 1 / fps)."""
    y, sr = load(wav)
    ons = file_onsets(wav)
    if expect:
        ons = with_soft(mono(y), sr, ons, expect)
    out = {"file": name_of(wav), "duration_s": num(duration(y, sr), 3),
           "onsets_s": [num(t, 4) for t in ons]}
    if expect is not None:
        rows = []
        for e in expect:
            near = _nearest(ons, e, REACH_S)[0]
            off = None if near is None else (near - e) * 1000
            rows.append({"expected_s": e, "nearest_onset_s": None if near is None else num(near, 4),
                         "offset_ms": None if off is None else num(off, 1),
                         "pass": off is not None and abs(off) <= tolerance * 1000})
        out["expected"] = rows
        out["tolerance_ms"] = num(tolerance * 1000, 1)
        out["all_pass"] = all(r["pass"] for r in rows)
    return out
