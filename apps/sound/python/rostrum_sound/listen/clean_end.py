"""clean_end: a song asked to end cleanly must not end in the delivery's fade.

Canary 3E r8 task 3 ("ends cleanly on a marker, a real ending, not a soft fade-out"): the last chord was held to an
"end" marker at the song's length, its ring ran past it, and deliver.py faded that ring over the file's last second.
The reply only warned, and a soft fade-out shipped. So when the brief asks for a clean ending (brief.asks
"clean_ending") or the song has a marker naming its end (ENDS), the delivery's fade is a fault, `faded_end`.

    fault(doc, faded) -> [shared fault] ; faded = deliver's {"faded_s", "rang_s", "from_s"} (None: nothing faded)
"""
from __future__ import annotations

from rostrum_core.mcp import faults as shared

ENDS = ("end", "ending", "the end", "clean end", "hard end", "final", "final hit", "button")   # marker names that mean "the song ends here"

FIX = ("end on the marker with a hard stop instead: end the last notes on it (end=\"#end\") and switch Ring out off "
       "(ring_out(False) in a script) so the song stops at its length, its last 0.1 s smoothed so it does not click "
       "(ring_out(False, soft_end=False): a dead stop); a short, dry last hit (a staccato chord, a kick and a choked "
       "cymbal) stops cleanest. Or let the ring finish inside the song: end the last notes 1–2 s before the length")


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


def fault(doc, faded: dict | None) -> list[dict]:
    if not faded:
        return []
    why = _why(doc)
    if not why:
        return []
    return [shared.fault("faded_end", f"the ending is a fade, not a clean end, and {why}: what still rang at the length "
                         f"({faded['rang_s']:.1f} s of it) was faded out over the file's last {faded['faded_s']:.1f} s",
                         FIX, f"{faded['from_s']:.2f} s on")]
