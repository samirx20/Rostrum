"""onsets: hit times, and offsets from the times a picture expects them."""
import librosa
import numpy as np

from .core import duration, load, mono, name_of, num

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
    env = librosa.onset.onset_strength(y=m, sr=sr, hop_length=HOP)
    frames = librosa.onset.onset_detect(onset_envelope=env, sr=sr, hop_length=HOP, backtrack=False)
    return [_refine(m, sr, t) for t in librosa.frames_to_time(frames, sr=sr, hop_length=HOP)]


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
