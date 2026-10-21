"""Motion events (read.py) -> designed sounds that follow them, as a starting point an agent or a person then edits
(every value is a field of a `sound` item). How each event is read:

  move   a whoosh over exactly the move: its speed curve is the sound's speed curve, its pan follows the layer
         across the frame, faster moves are louder and brighter with more air and doppler, bigger layers sound
         bigger. A layer leaving the frame at speed rings on past the edge. Arriving hard (a snap stop, an
         overshoot) adds a click where it first reaches its place, harder for a harder landing.
  snap   a bright click at its most sudden moment, a short air lead-in before it, and a small thump under it
  press  a soft press click at the deepest point and a lighter, higher release click when it comes back
  step   a tight tick, each a little different (another take, a hair of pitch), never a copy-paste

Plus `glue_ops`: the "ui" bus every one of these tracks plays into: a short shared room and a light compressor,
so the layers sit as one piece.

With source="library" the same events get recordings from the user's own sound library instead (score_library.py).
"""
from __future__ import annotations

import math

BUS = "ui"
TRACKS = {"move": "ui_whoosh", "land": "ui_clicks", "snap": "ui_clicks", "press": "ui_clicks", "step": "ui_ticks",
          "thump": "ui_low"}


def _norm_speed(px_s: float) -> float:
    """0 at 800 px/s (a gentle drift) … 1 at 32000 px/s (a flick across the frame in a few frames)."""
    return max(0.0, min(1.0, math.log10(max(px_s, 1.0) / 800.0) / math.log10(40.0)))


def _pan(x: float, width: float) -> float:
    return round(max(-0.9, min(0.9, (x - width / 2) / (width / 2))), 3)


def _size(area: float, frame: float) -> float:
    return round(max(0.15, min(0.9, math.sqrt(area / frame) * 1.6)), 3) if area else 0.5


def _whoosh(e: dict, W: float, H: float) -> dict:
    n = _norm_speed(e["peak_speed"])
    dur, speed = e["end"] - e["at"], [list(p) for p in e["speed"]]
    pans = e["x"]
    path = [[round(k / (len(pans) - 1), 3), _pan(x, W)] for k, x in enumerate(pans)]
    if not e["on_screen"][1] and speed[-2][1] > 0.5:
        # Off the edge at speed: it keeps going, so the sound does too (a third longer, dying away).
        ring = dur * 0.35
        scale = dur / (dur + ring)
        last = speed[-2][1]
        speed = [[round(u * scale, 4), v] for u, v in speed[:-1]] + [[round(scale + (1 - scale) * 0.4, 4), last * 0.35], [1.0, 0.0]]
        path = [[round(u * scale, 4), p] for u, p in path] + [[1.0, path[-1][1]]]
        dur += ring
    return {"design": "whoosh", "at": e["at"], "dur": round(max(dur, 0.05), 4), "speed": speed, "panPath": path,
            "volume": round(0.4 + 0.6 * n, 3), "brightness": round(0.3 + 0.55 * n, 3), "size": _size(e["area"], W * H),
            "doppler": round(0.15 + 0.35 * n, 3), "air": round(0.2 + 0.5 * n, 3), "tone": 0.15,
            "texture": round(0.1 + 0.2 * _size(e["area"], W * H), 3), "width": 0.6}


def _landing(e: dict, W: float, H: float) -> dict | None:
    land = e["lands"]
    if not land or land["hardness"] < 0.15:
        return None
    size = _size(e["area"], W * H)
    hard = land["hardness"]
    return {"design": "click", "at": land["at"], "pitch": round(2600 - 1500 * size), "material": 0.3, "tight": 0.7,
            "transient": round(0.5 + 0.4 * hard, 3), "body": 0.55, "air": 0.25, "bend": 0.15,
            "volume": round(0.35 + 0.5 * hard, 3), "pan": _pan(e["to"][0], W), "width": 0.2}


def sounds(events: list[dict], width: float, height: float) -> list[tuple[str, dict]]:
    """(track id, sound fields) for every event."""
    out: list[tuple[str, dict]] = []
    steps = 0
    for e in events:
        k = e["kind"]
        if k == "move":
            out.append((TRACKS["move"], _whoosh(e, width, height)))
            land = _landing(e, width, height)
            if land:
                out.append((TRACKS["land"], land))
        elif k == "snap":
            lead = max(0.06, min(0.18, e["at"] - e.get("start", e["at"]) + 0.12))
            out.append((TRACKS["move"], {"design": "whoosh", "at": round(max(0.0, e["at"] - lead), 4), "dur": lead,
                                         "speed": [[0, 0], [0.8, 0.7], [1, 1]], "brightness": 0.8, "size": 0.2,
                                         "air": 0.7, "doppler": 0.0, "volume": 0.25}))
            out.append((TRACKS["snap"], {"design": "click", "at": e["at"], "pitch": 3000, "material": 0.45,
                                         "tight": 0.75, "transient": 0.9, "body": 0.5, "air": 0.5, "volume": 0.9}))
            out.append((TRACKS["thump"], {"design": "hit", "at": e["at"], "size": 0.15, "pitch": 70, "tail": 0.25,
                                          "brightness": 0.2, "drive": 0.2, "volume": 0.2}))
        elif k == "press":
            out.append((TRACKS["press"], {"design": "click", "at": e["at"], "pitch": 1100, "material": 0.1,
                                          "tight": 0.75, "transient": 0.6, "body": 0.7, "bend": 0.3, "volume": 0.7}))
            out.append((TRACKS["press"], {"design": "click", "at": e["release"], "pitch": 1700, "material": 0.15,
                                          "tight": 0.85, "transient": 0.4, "body": 0.5, "volume": 0.35, "seed": 2}))
        elif k == "step":
            steps += 1
            out.append((TRACKS["step"], {"design": "click", "at": e["at"], "pitch": round(4200 * (1 + 0.012 * ((steps % 3) - 1))),
                                         "material": 0.55, "tight": 0.9, "transient": 0.6, "body": 0.4, "air": 0.2,
                                         "volume": 0.45, "seed": steps}))
    return out


LEVELS = {"ui_whoosh": 0.8, "ui_clicks": 0.9, "ui_ticks": 0.7, "ui_low": 0.8}


def script(events: list[dict], width: float, height: float, source: str = "designed",
           library: list[dict] | None = None) -> tuple[str, list[str]]:
    """The sounds as a Sound script (run with run_script, so a re-run keeps what a person changed) and its track ids.
    source "designed": designed `sound`s (above); "library": recordings from the user's own sound library
    (`library` = userlib.search.library()), placed as `clip`s by score_library.py."""
    if source == "library":
        from .score_library import clips
        placed = clips(events, width, height, library or [])
    elif source == "designed":
        placed = sounds(events, width, height)
    else:
        raise ValueError(f"source must be 'designed' or 'library', not {source!r}")
    tracks = list(dict.fromkeys(t for t, _ in placed))
    lines = [f"{t} = track({t!r}, volume={LEVELS.get(t, 0.8)})" for t in tracks]
    for t, f in placed:
        if "media" in f:
            args = ", ".join(f"{k}={v!r}" for k, v in f.items() if k != "media")
            lines.append(f"{t}.clip({f['media']!r}, {args})")
            continue
        args = ", ".join(f"{k}={v!r}" for k, v in f.items() if k != "design")
        lines.append(f"{t}.sound({f['design']!r}, {args})")
    return "\n".join(lines), tracks


def glue_ops(doc: dict, tracks: list[str]) -> list[dict]:
    """The "ui" bus (short shared room, light compressor) when the document has none yet, and every UI track routed
    into it. Nothing for what is already there, so running it again changes nothing a person set."""
    ops = []
    if not any(b["id"] == BUS for b in doc.get("buses", [])):
        ops = [{"op": "bus.add", "args": {"id": BUS}},
               {"op": "effect.add", "target": [BUS], "args": {"effect": "eq", "bands": [{"shape": "highpass", "freq": 45}]}},
               {"op": "effect.add", "target": [BUS], "args": {"effect": "reverb", "space": "room", "mix": 0.12}},
               {"op": "effect.add", "target": [BUS], "args": {"effect": "compressor", "threshold": -20, "ratio": 2.5,
                                                             "attack": 0.008, "release": 0.12, "makeup": 2}}]
    # Only tracks still on the master (as a script makes them): one a person routed elsewhere stays where it is.
    have = {t["id"]: t.get("output") for t in doc.get("tracks", [])}
    return ops + [{"op": "track.set", "target": [t], "args": {"output": BUS}} for t in tracks if have.get(t) == "master"]
