"""onsets: hit times, and offsets from the times a picture expects them."""
import numpy as np

from .core import duration, load, mono, name_of, num
from .dsp_events import onset_times

HOP = 256


def _refine(m, sr, t, span=0.04):
    """Move a detected onset to the first sample that rises above 50 % of the local peak
    (the detector's frame grid is coarser than a click)."""
    a, b = max(0, int((t - span) * sr)), min(len(m), int((t + span) * sr))
    seg = np.abs(np.diff(m[a:b], prepend=m[a]))
    if seg.size == 0 or seg.max() <= 0:
        return t
    return (a + int(np.argmax(seg > 0.5 * seg.max()))) / sr


def detect(m, sr):
    return [_refine(m, sr, t) for t in onset_times(m, sr, HOP)]


def _nearest(ons, e):
    near = min(ons, key=lambda t: abs(t - e)) if ons else None
    return near, (None if near is None else num((near - e) * 1000, 1))


def which_stem(mix, stems, expect, tolerance=0.04):
    """For each expected time: the stem whose onset is nearest (and how far off, ms; > 0 = late), the next two
    stems, and the mix's own nearest onset: one answer per time instead of one look per stem. Same detector as `onsets`."""
    def of(p):
        y, sr = load(p)
        return detect(mono(y), sr)
    found = {k: of(p) for k, p in stems.items()}
    mix_ons = of(mix)
    rows = []
    for e in expect:
        near = {k: _nearest(o, e) for k, o in found.items()}
        ranked = sorted((k for k, (t, _) in near.items() if t is not None), key=lambda k: abs(near[k][1]))
        mt, mo = _nearest(mix_ons, e)
        best = ranked[0] if ranked else None
        rows.append({"expected_s": e, "stem": best, "stem_onset_s": num(near[best][0], 4) if best else None,
                     "offset_ms": near[best][1] if best else None,
                     "pass": best is not None and abs(near[best][1]) <= tolerance * 1000,
                     "next_stems": [{"stem": k, "offset_ms": near[k][1]} for k in ranked[1:3]],
                     "mix_onset_s": None if mt is None else num(mt, 4), "mix_offset_ms": mo})
    return {"expected": rows, "tolerance_ms": num(tolerance * 1000, 1), "all_pass": all(r["pass"] for r in rows),
            "note": "stem = the track whose onset is nearest the time; mix_* = the mix's nearest onset (a louder sound "
                    "nearby can win there). Stems are the last render's."}


def onsets(wav, expect=None, tolerance=0.04):
    """Onset times in seconds. With `expect` (times a picture says a sound must start), each gets
    its nearest onset, the offset in ms (> 0 = sound lands late) and pass/fail against `tolerance`
    seconds (one video frame = 1 / fps)."""
    y, sr = load(wav)
    ons = detect(mono(y), sr)
    out = {"file": name_of(wav), "duration_s": num(duration(y, sr), 3),
           "onsets_s": [num(t, 4) for t in ons]}
    if expect is not None:
        rows = []
        for e in expect:
            near = min(ons, key=lambda t: abs(t - e)) if ons else None
            off = None if near is None else (near - e) * 1000
            rows.append({"expected_s": e, "nearest_onset_s": None if near is None else num(near, 4),
                         "offset_ms": None if off is None else num(off, 1),
                         "pass": off is not None and abs(off) <= tolerance * 1000})
        out["expected"] = rows
        out["tolerance_ms"] = num(tolerance * 1000, 1)
        out["all_pass"] = all(r["pass"] for r in rows)
    return out
