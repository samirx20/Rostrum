"""lead_in: how long the file is silent before its first audible sound.

Round 2's orchestral piece opened on 1.8 s of silence, left so a beat would land on a sync time; judges heard a dead
start. The first 20 ms window over -45 dBFS (RMS) is where the music is heard to begin; later than 0.25 s is a fault,
named with the ways to land a sync moment without the gap."""
from __future__ import annotations

import numpy as np

from .core import mono, num

AUDIBLE_DBFS = -45.0
LATE_S = 0.25
_WIN_S = 0.02


def first_sound_s(y, sr) -> float | None:
    """Seconds to the first 20 ms window whose RMS is over AUDIBLE_DBFS; None when nothing is."""
    m = mono(y).astype(np.float64)
    w = max(1, int(_WIN_S * sr))
    n = len(m) // w
    if n == 0:
        return None
    rms = np.sqrt(np.mean(m[:n * w].reshape(n, w) ** 2, axis=1))
    loud = np.flatnonzero(rms > 10 ** (AUDIBLE_DBFS / 20))
    return float(loud[0] * w / sr) if loud.size else None


def faults(y, sr) -> list[dict]:
    t = first_sound_s(y, sr)
    if t is None or t <= LATE_S:
        return []
    return [{"kind": "leading_silence", "at_s": 0.0, "measured": {"first_sound_s": num(t, 2), "audible_dbfs": AUDIBLE_DBFS}}]


def words(f) -> str:
    t = f["measured"]["first_sound_s"]
    return (f"silent start: nothing is heard for {t:g} s (the first sound over {AUDIBLE_DBFS:g} dBFS); a listener hears a "
            "dead start. Start the music at once; to land a beat on a sync time, play a pickup before bar 1 with "
            "downbeat(bar(1), at=<seconds>) or place the sync moment in seconds instead of moving the music")
