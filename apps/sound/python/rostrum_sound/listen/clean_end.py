"""clean_end: a song asked to end cleanly must not end in the delivery's fade.

Canary 3E r8 task 3 ("ends cleanly on a marker, a real ending, not a soft fade-out"): the last chord was held to an
"end" marker at the song's length, its ring ran past it, and deliver.py faded that ring over the file's last second.
The reply only warned, and a soft fade-out shipped. So when the brief asks for a clean ending (brief.asks
"clean_ending") or the song has a marker naming its end (ENDS), the delivery's fade is a fault, `faded_end`.

    fault(doc, faded, wav) -> [shared fault] ; faded = deliver's {"faded_s", "rang_s", "from_s"} (None: nothing faded)

Re-run of the same canary: both models then held the last chord to the marker and switched Ring out off, so the file
stopped while still loud (-7 and -15 dBFS): chopped, not an ending, and the engine's warning even advised fading. So a
song asked to end cleanly whose file stops within CHOP_DB of its loudest is a fault too, `chopped_end`: a clean ending
is the music stopping itself (a short last chord or hit on the marker, its tail dying away in the room after it).
"""
from __future__ import annotations

import numpy as np

from rostrum_core.mcp import faults as shared

from .core import db, load, mono

ENDS = ("end", "ending", "the end", "clean end", "hard end", "final", "final hit", "button")   # marker names that mean "the song ends here"

FIX = ("end on the marker with the music itself, not the delivery's fade: " + "{chop}")


CHOP_DB = 12.0       # a file whose last 0.25 s is within this of its loudest 0.5 s stops while still playing: chopped
CHOP_FIX = ("end on the marker with the music itself: a short last chord or hit ON the marker (a staccato chord, a kick "
            "and a choked cymbal, notes no longer than a beat) and the song's length 1–2 s after it, Ring out on, so the "
            "tail dies away in the room (no fade, nothing cut); held notes stop on the marker (end=\"#end\"), not at the "
            "file's end")


def _chopped(wav) -> tuple[float, float] | None:
    """(last 0.25 s dBFS, loudest 0.5 s dBFS) when the file stops within CHOP_DB of its loudest, else None."""
    y, sr = load(wav)
    m = mono(y).astype(np.float64)
    n = int(0.5 * sr)
    if len(m) < 2 * n:
        return None
    last = db(np.mean(m[-n // 2:] ** 2))
    k = len(m) // n
    loud = max(db(np.mean(m[i * n:(i + 1) * n] ** 2)) for i in range(k))
    return (last, loud) if last > loud - CHOP_DB else None


def _why(doc) -> str | None:
    """The brief's phrase that asks for a clean ending, else the end marker's name, else None."""
    data = getattr(doc, "data", None) or {}
    try:
        from .. import brief
        said = brief.asks(data, "clean_ending")
        if said:
            return f'the brief asks for it ("{said}")'
    except ImportError:          # brief.py (member A) not there yet
        pass
    try:
        from ..doc import markers
        with markers.project(getattr(doc, "folder", None)):
            name = next((n for n, _ in markers.all(data) if n.strip().lower() in ENDS), None)
    except Exception:  # noqa: BLE001  a marker that does not resolve is the document checks' business
        name = None
    return f"the song marks its end (marker '{name}')" if name else None


def fault(doc, faded: dict | None, wav=None) -> list[dict]:
    why = _why(doc)
    if not why:
        return []
    if not faded:
        chop = _chopped(wav) if wav else None
        return [shared.fault("chopped_end", f"the ending is chopped, not a clean end, and {why}: the file stops while still "
                             f"playing (its last 0.25 s at {chop[0]:.0f} dBFS, only {chop[1] - chop[0]:.0f} dB under its "
                             f"loudest)", CHOP_FIX, "the end")] if chop else []
    return [shared.fault("faded_end", f"the ending is a fade, not a clean end, and {why}: what still rang at the length "
                         f"({faded['rang_s']:.1f} s of it) was faded out over the file's last {faded['faded_s']:.1f} s",
                         FIX.format(chop=CHOP_FIX), f"{faded['from_s']:.2f} s on")]
