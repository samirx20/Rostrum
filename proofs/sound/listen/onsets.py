"""onsets: hit times, tempo/beats, energy curve, and offsets from expected events."""
import librosa
import numpy as np

from .core import db, duration, load, mono, num

HOP = 256


def _refine(m, sr, t, span=0.04):
    """Move a detected onset to the first sample that rises above 50 % of the
    local peak (the detector's frame grid is coarser than a click)."""
    a, b = max(0, int((t - span) * sr)), min(len(m), int((t + span) * sr))
    seg = np.abs(np.diff(m[a:b], prepend=m[a]))
    if seg.size == 0 or seg.max() <= 0:
        return t
    return (a + int(np.argmax(seg > 0.5 * seg.max()))) / sr


def energy_curve(m, sr, step=0.5):
    n = int(step * sr)
    return [num(db(np.mean(m[i:i + n] ** 2)), 1) for i in range(0, len(m), n) if len(m[i:i + n]) > 0]


def analyse(path, expect=()):
    y, sr = load(path)
    m = mono(y)
    env = librosa.onset.onset_strength(y=m, sr=sr, hop_length=HOP)
    frames = librosa.onset.onset_detect(onset_envelope=env, sr=sr, hop_length=HOP, backtrack=False)
    ons = [_refine(m, sr, t) for t in librosa.frames_to_time(frames, sr=sr, hop_length=HOP)]
    tempo, beats = librosa.beat.beat_track(onset_envelope=env, sr=sr, hop_length=HOP)
    out = {
        "duration_s": num(duration(y, sr), 3),
        "onsets_s": [num(t, 3) for t in ons],
        "tempo_bpm": num(float(np.atleast_1d(tempo)[0]), 1),
        "beats_s": [num(t, 3) for t in librosa.frames_to_time(beats, sr=sr, hop_length=HOP)],
        "energy_db_per_0.5s": energy_curve(m, sr),
    }
    if len(expect):
        rows = []
        for e in expect:
            if ons:
                near = min(ons, key=lambda t: abs(t - e))
                rows.append({"expected_s": e, "nearest_onset_s": num(near, 3),
                             "offset_ms": num((near - e) * 1000, 1)})
            else:
                rows.append({"expected_s": e, "nearest_onset_s": None, "offset_ms": None})
        out["expected"] = rows
        out["note"] = "offset_ms > 0: sound lands late; < 0: early"
    return out
