"""The song's Length, as the settings panel's Length picker shows and takes it (no Qt): "Until the last sound", a
number of bars, or a typed length ("23 bars", "23", "bar 23", "1:02.5", "62.5 s", "#end").

What is typed is written as the song's `length` in the form it means, through the same `doc.set` an agent calls:
bars stay bars (a beat, so the end follows a tempo change), seconds stay seconds, a marker stays on its marker. Export,
the end-of-song checks and the ruler all read `length` through times.seconds, whatever its form.
"""
from __future__ import annotations

import re

from rostrum_sound.doc import markers, meter, musical, tempo, times

PRESETS = (4, 8, 16, 32, 64, 128)                 # the bars the picker offers, after "Until the last sound"
OWN = "own"                                       # the picker's value for a length typed some other way
UNTIL = ("", "until the last sound", "auto", "none")
_BAR = re.compile(r"^(?:end\s+at\s+|at\s+)?bar\s+(\d+)$", re.I)
_SECONDS = re.compile(r"^\d+(?:[.,]\d+)?\s*(?:s|sec|secs|seconds?)$|^\d+:\d", re.I)
WORDS = 'Type bars ("23 bars"), the bar it ends on ("bar 24"), seconds ("62.5 s") or a clock ("1:02.5")'


def parse(text: str, root: dict):
    """The `length` value typed words mean: None (until the last sound), {"beat": n}, seconds, or a marker reference.
    Raises ValueError, in words, when they are none of those or the song would end at or before its start."""
    s = str(text).strip()
    if s.lower() in UNTIL:
        return None
    if markers.ref(s):
        times.seconds(s, root, "length")                # an unknown marker: its own loud error, now
        return s
    bar = _BAR.match(s)
    if bar:
        if int(bar.group(1)) < 2:
            raise ValueError("The song can't end where bar 1 starts: pick a later bar")
        return {"beat": meter.bar_start(root, int(bar.group(1)))}
    try:
        sec = musical.parse(s, root, True, 0.0)
    except ValueError:
        raise ValueError(f'"{text}" is not a length. {WORDS}') from None
    if sec <= 1e-6:
        raise ValueError(f'"{text}" is no length: the song would end at its start. {WORDS}.')
    if _SECONDS.match(s):
        return round(sec, 4)
    return {"beat": round(tempo.beat_at(root, sec), 6)}


def current(root: dict) -> tuple[str, str] | None:
    """(value, label) of the song's own length as the picker lists it, None when it is until the last sound. Whole bars
    read "23 bars" (the value types back the same); seconds read as a clock, a marker by its name, else where it ends
    in bars.beats (value OWN: picking it again changes nothing)."""
    v = root.get("length")
    if v is None:
        return None
    if isinstance(v, str):
        return OWN, f"At {v}"
    sec = times.seconds(v, root, "length")
    if isinstance(v, (int, float)):
        return OWN, musical.clock(sec)
    n = meter.bars_long(root, sec)
    if abs(n - round(n)) < 1e-6:
        return f"{round(n)} bars", f"{round(n)} bar" + ("" if round(n) == 1 else "s")
    return OWN, f"Ends at {musical.position(sec, root)}"


def choices(root: dict) -> list[dict]:
    """[{value, label}]: until the last sound, the preset bars and the song's own length where it is none of them."""
    own = current(root)
    out = [{"value": "", "label": "Until the last sound"},
           *({"value": f"{n} bars", "label": f"{n} bars"} for n in PRESETS)]
    if own and all(o["value"] != own[0] for o in out):
        out.append({"value": own[0], "label": own[1]})
    return out
