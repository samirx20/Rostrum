"""Whether each written note of a part that plays several notes at once (chords, a melody over its own chords) is
in the sound: a pitch finder follows one line, so on a chord it names one note and every other note of the chord
would read as a wrong note or octave. Here each written pitch is looked for on its own, in the spectrum just after
the note starts: a peak at its fundamental standing over the spectrum around it.

A note is there when its fundamental is, or (a low note's fundamental is often faint) its second and third
harmonics both are. A written note that is not there but the octave above is (and was not written) is
`wrong_octave`; else `missing`. What it can't tell: a written note that is also an overtone of a lower note
sounding at the time (an octave, a twelfth above it) reads as there even if it was not played, so a note played an
octave low reads as there. Timing and tuning of single notes in a chord
are not judged (the line's pitch says those for a one-voice part)."""
from __future__ import annotations

import numpy as np

from ..doc.keys import pitch_name
from ..listen.core import load, mono, num

N_FFT = 16384                 # ~3 Hz bins at 48 kHz: a semitone apart down to about C2
LOOK = (0.03, 0.35)           # seconds after the start the note is looked for (past the attack noise, before it fades)
STANDS_DB = 8.0               # a peak this far over the median of the spectrum around it
UNDER_LOUDEST_DB = 45.0       # and no further than this under the loudest peak at that moment


def polyphonic(written: list[dict], overlap_s: float = 0.05) -> bool:
    """True when the part ever sounds two notes at once (a chord in one note, or notes overlapping)."""
    ends = []
    for w in sorted(written, key=lambda w: w["start"]):
        if len(w["midis"]) > 1 or any(e - w["start"] > overlap_s for e in ends):
            return True
        ends.append(w["end"])
    return False


def _spectrum_db(x: np.ndarray, sr: float, start: float, end: float) -> np.ndarray:
    """The mean power spectrum (dB) of a few frames from `start` to `end` seconds."""
    a, b = int(start * sr), max(int(start * sr) + 1, int(end * sr) - N_FFT)
    win = np.hanning(N_FFT)
    acc = np.zeros(N_FFT // 2 + 1)
    starts = np.linspace(a, max(a, b), 3).astype(int)
    for s in starts:
        seg = x[s:s + N_FFT]
        seg = np.pad(seg, (0, N_FFT - len(seg)))
        acc += np.abs(np.fft.rfft(seg * win)) ** 2
    return 10 * np.log10(acc / len(starts) + 1e-20)


def _peak(spec: np.ndarray, sr: float, hz: float) -> bool:
    """A peak within a third of a semitone of `hz` standing over the spectrum around it (two semitones, and at least
    40 Hz, each side: low notes' bins are few and their neighbours' peaks wide)."""
    k = lambda f: int(round(f * N_FFT / sr))  # noqa: E731
    near = spec[k(hz * 2 ** (-0.35 / 12)):k(hz * 2 ** (0.35 / 12)) + 1]
    around = spec[k(min(hz * 2 ** (-2 / 12), hz - 40)):k(max(hz * 2 ** (2 / 12), hz + 40)) + 1]
    if not len(near) or not len(around):
        return False
    return near.max() - np.median(around) >= STANDS_DB and near.max() >= spec.max() - UNDER_LOUDEST_DB


def _there(spec: np.ndarray, sr: float, midi: int) -> bool:
    """The note's fundamental, or (a low note's fundamental is often faint) its second and third harmonics together:
    a note an octave up has the second but never the third."""
    hz = 440.0 * 2 ** ((midi - 69) / 12)
    return _peak(spec, sr, hz) or (_peak(spec, sr, 2 * hz) and _peak(spec, sr, 3 * hz))


def _overtone(midi: int, sounding: set) -> bool:
    """`midi` is a written note sounding, or one of its overtones (2nd … 6th harmonic, within a third of a semitone)."""
    return any(abs(midi - (s + 12 * np.log2(h))) < 0.35 for s in sounding for h in range(1, 7))


def check(wav, written: list[dict]) -> dict:
    """Each written pitch: ok (there), wrong_octave (not there, its unwritten octave is) or missing. Rows as
    pitch.compare's (id, written, start_s, target, status) so the picture and counts read the same."""
    y, sr = load(wav)
    x = mono(y).astype(float)
    rows = []
    for w in written:
        spec = _spectrum_db(x, sr, w["start"] + LOOK[0], min(w["end"], w["start"] + LOOK[1]))
        sounding = {m for v in written if v["start"] <= w["start"] + LOOK[0] < v["end"] for m in v["midis"]}
        for m in w["midis"]:
            row = {"id": w["id"], "written": pitch_name(m), "start_s": num(w["start"], 3), "target": m}
            if _there(spec, sr, m):
                rows.append({**row, "status": "ok"})
                continue
            octave = m + 12 if not _overtone(m + 12, sounding - {m}) and _there(spec, sr, m + 12) else None
            rows.append({**row, "status": "wrong_octave", "heard": pitch_name(octave)} if octave is not None else {**row, "status": "missing"})
    counts = {s: sum(r["status"] == s for r in rows) for s in sorted({r["status"] for r in rows})}
    return {"rows": rows, "counts": counts, "mode": "chords: each written note looked for in the sound",
            "not_judged": "timing and tuning of notes in a chord; a written note that is also an overtone of a lower note sounding reads as there"}
