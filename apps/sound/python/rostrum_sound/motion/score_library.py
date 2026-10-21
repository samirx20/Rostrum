"""Motion events (read.py) -> recordings from the user's own sound library, placed as `clip`s the way a careful sound
designer would (the P7 listening page's placement, proofs/p7-sfx-sources):

  move   a whoosh whose loudest moment sits on the move's fastest moment, panned with the layer across the frame,
         louder for faster moves, trimmed with a fade a little after the move ends; a click where it lands hard
  snap   a bright click on its most sudden moment
  press  a press click at the deepest point, and the same click higher and softer on the release
  step   a tick, each a little different: another of the nearest takes, a little pitch, a little level

Each sound is chosen by searching the index (userlib.search.closest) for the kind and shape the event asks for: a
fast short move gets a short bright whoosh, a slow big one a longer, darker one; a take already used is pushed back
so a scene doesn't repeat one recording. Deterministic: the same events and library give the same picks. Levels
are evened out by each sound's measured loudness, so a quiet recording isn't lost and a hot one doesn't jump out.
"""
from __future__ import annotations

import math
from collections import Counter

from rostrum_core import RostrumError, codes

from ..userlib.search import closest, sound_id
from .score import TRACKS, _norm_speed, _pan, _size

REF_LUFS = -18.0                   # every pick is brought to this loudness before its own volume
CLICKS = ["click", "ui", "hit"]
TICKS = ["click", "ui"]


def _level(s: dict, volume: float) -> float:
    return round(max(0.02, min(4.0, volume * 10 ** ((REF_LUFS - s["lufs"]) / 20))), 3)


def _pick(lib, kinds, target, used, role, nth=0) -> dict:
    s = closest(lib, kinds, target, used, nth)
    if s is None:
        raise RostrumError(codes.NOT_FOUND, "edit_sounds_from_motion", f"a {role} ({' / '.join(kinds)})",
                           "is not in your sound library",
                           hint="Add a folder with that kind of sound: inspect_library folder=<path>.")
    used[sound_id(s)] += 1
    return s


def _clip(s: dict, moment: float, align: str, tail: float | None = None, **f) -> dict:
    """A clip of sound `s` with its peak (align="peak") or onset ("onset") on `moment`, inside its own cut."""
    lead = s["peak_s"] if align == "peak" else s["onset_s"]
    start, at = s["start"], moment - lead
    if at < 0:                       # the build-up is longer than the time before the moment: start later in it
        start, lead, at = start - at, moment, 0.0
    room = s["end"] - start
    length = room if tail is None else min(room, lead + tail)
    out = {"media": s["path"], "at": round(at, 4), "in_": round(start, 4), "length": round(max(length, 0.01), 4)}
    if tail is not None and length > lead:
        out["fadeOut"] = round(min(0.25, (length - lead) * 0.6), 3)
    return {**out, **f}


def clips(events: list[dict], width: float, height: float, lib: list[dict]) -> list[tuple[str, dict]]:
    """(track id, clip fields) for every event, picked from `lib` (userlib.search.library())."""
    if not lib:
        raise RostrumError(codes.NOT_FOUND, "edit_sounds_from_motion", "your sound library", "has no sounds yet",
                           hint="Add a sound folder first: inspect_library folder=<path>.")
    used: Counter = Counter()
    out: list[tuple[str, dict]] = []
    steps = 0
    for e in events:
        k = e["kind"]
        if k == "move":
            n, dur = _norm_speed(e["peak_speed"]), e["end"] - e["at"]
            size = _size(e["area"], width * height)
            target = {"seconds": dur + 0.35 + 0.6 * size * (1 - n), "brightness": 0.35 + 0.55 * n,
                      "attack_ms": max(20.0, 600 * dur * (1 - n))}
            s = _pick(lib, ["whoosh"], target, used, "whoosh")
            loud = min(1.0, 0.45 + 0.55 * math.log10(max(e["peak_speed"], 800) / 800) / math.log10(40))
            out.append((TRACKS["move"], _clip(s, e["peak_at"], "peak", tail=e["end"] - e["peak_at"] + 0.35,
                                              volume=_level(s, loud), pan=_pan(e["x"][0], width),
                                              panTo=_pan(e["x"][-1], width))))
            land = e.get("lands")
            if land and land["hardness"] >= 0.15:
                c = _pick(lib, CLICKS, {"seconds": 0.15, "brightness": 0.85 - 0.3 * size, "attack_ms": 4}, used, "click")
                out.append((TRACKS["land"], _clip(c, land["at"], "onset", volume=_level(c, 0.4 + 0.6 * land["hardness"]),
                                                  pan=_pan(e["x"][-1], width))))
        elif k == "snap":
            c = _pick(lib, CLICKS, {"seconds": 0.12, "brightness": 0.9, "attack_ms": 3}, used, "click")
            out.append((TRACKS["snap"], _clip(c, e["at"], "onset", volume=_level(c, 0.8))))
        elif k == "step":
            steps += 1
            c = _pick(lib, TICKS, {"seconds": 0.06, "brightness": 0.9, "attack_ms": 3}, Counter(), "tick", nth=steps % 3)
            out.append((TRACKS["step"], _clip(c, e["at"], "onset", volume=_level(c, 0.55 + 0.08 * (steps % 3)),
                                              pitch=round(((steps * 7) % 5 - 2) * 0.15, 2))))
        elif k == "press":
            c = _pick(lib, TICKS, {"seconds": 0.2, "brightness": 0.8, "attack_ms": 8}, used, "press click")
            out.append((TRACKS["press"], _clip(c, e["at"], "onset", volume=_level(c, 0.7))))
            out.append((TRACKS["press"], _clip(c, e["release"], "onset", volume=_level(c, 0.45), pitch=2.0)))
    return out
