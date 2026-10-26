"""Room for speech: how far a voice at the mix's own loudness would stand over the music where speech is understood.

A voice is scaled to the same K-weighted loudness as the mix (what LUFS measures), then the two are compared band by
band in the 1/3-octave bands 1–4 kHz (where consonants, and so intelligibility, live). Each band's gap is in dB, and the
gaps are averaged in dB with the bands' speech-importance weights. Why not the old reading (sound-agent-pieces-r4 finding 7: a
pad's low-pass moved from 2.5 to 1.4 kHz and levels' 1–4 kHz hardly moved): that was a stem's share of the mix's own 1–4
kHz energy, so a pad that is most of that region reads near 0 dB whatever its filter, and a single power sum over the
region is ruled by its loudest edge (a pad's strong harmonics just above 1 kHz). Measured against a voice, per band in dB,
the bands at 2–4 kHz, where a voice needs room, show the change.

Data (ANSI S3.5-1997, Speech Intelligibility Index, Table 3): the standard speech spectrum level for normal vocal effort
(dB per Hz, per 1/3-octave band centre) and the average-speech band-importance function. The levels' absolute value
cancels out (the voice is scaled to the mix); only the spectrum's shape matters.
"""
from __future__ import annotations

import numpy as np

from .bs1770 import k_response
from .core import mono, num

# centre Hz: (speech spectrum level dB/Hz, normal effort; band importance)
SII = {160: (32.41, 0.0083), 200: (34.48, 0.0095), 250: (34.75, 0.0150), 315: (33.98, 0.0289), 400: (34.59, 0.0440),
       500: (34.27, 0.0578), 630: (32.06, 0.0653), 800: (28.30, 0.0711), 1000: (25.01, 0.0818), 1250: (23.00, 0.0844),
       1600: (20.15, 0.0882), 2000: (17.32, 0.0898), 2500: (13.18, 0.0868), 3150: (11.55, 0.0844), 4000: (9.33, 0.0771),
       5000: (5.31, 0.0527), 6300: (2.59, 0.0364), 8000: (1.13, 0.0185)}
SPEECH_BANDS = [f for f in SII if 1000 <= f <= 4000]
THIRD = 2 ** (1 / 6)                       # a 1/3-octave band runs fc / 2^(1/6) … fc · 2^(1/6)
TARGET_DB = 6.0                            # a voice-over bed: the voice this far over the music in 1–4 kHz


def _speech_levels(sr) -> dict:
    """Band level (dB) of the standard speech spectrum, each band minus the voice's K-weighted total."""
    fc = np.array(list(SII), float)
    band = np.array([SII[f][0] for f in SII]) + 10 * np.log10(fc * (THIRD - 1 / THIRD))
    k = np.abs(k_response(fc, sr)) ** 2
    total = 10 * np.log10(np.sum(10 ** (band / 10) * k))
    return {f: b - total for f, b in zip(SII, band)}


def room(y, sr) -> dict:
    """{"db": the importance-weighted gap (+ = a voice at the mix's loudness stands over it), "bands": {Hz: dB}, "words"}."""
    m = mono(y).astype(np.float64)
    spec = np.abs(np.fft.rfft(m)) ** 2
    f = np.fft.rfftfreq(m.size, 1 / sr)
    total = float(np.sum(spec * np.abs(k_response(f, sr)) ** 2))
    if total <= 0:
        return {"db": None, "bands": {}, "words": "Room for speech: the mix is silent"}
    speech = _speech_levels(sr)
    gaps = {}
    for fc in SPEECH_BANDS:
        p = float(spec[(f >= fc / THIRD) & (f < fc * THIRD)].sum())
        gaps[fc] = min(60.0, speech[fc] - 10 * np.log10(max(p / total, 1e-12)))   # an empty band: 60 dB of room
    w = np.array([SII[fc][1] for fc in SPEECH_BANDS])
    db = float(np.dot(w, list(gaps.values())) / w.sum())
    return {"db": num(db, 1), "bands": {fc: num(g, 1) for fc, g in gaps.items()}, "target_db": TARGET_DB,
            "words": words(db)}


def words(db: float) -> str:
    side = "over" if db >= 0 else "under"
    return (f"Room for speech {db:+.1f} dB: a voice at the same loudness stands {abs(db):.1f} dB {side} the music in 1–4 kHz"
            + ("" if db >= TARGET_DB else f" (a voice-over bed wants +{TARGET_DB:g} dB or more)"))
