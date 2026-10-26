"""What a mixer strip shows, from the document and the last render's answer (no Qt).

A strip is a plain dict: id, name, volume, pan, mute, solo, the insert chain in order, and a meter that is
`{}` (absent) until a render has measured the track. The master is one more strip, the one with id "master".
The master's delivery settings (Normalize, the loudness target) are in the Deliver dialog and the inspector.
"""
from __future__ import annotations

import math

from rostrum_sound.doc import effects

from . import plugin_rows

MASTER = "master"
EFFECT_NAMES = effects.WORDS


def effect_name(kind: str) -> str:
    return EFFECT_NAMES.get(kind) or kind[:1].upper() + kind[1:]


def db(linear: float) -> float | None:
    return round(20 * math.log10(linear), 1) if linear and linear > 0 else None


def chip_label(e: dict, vendor_of=None) -> str:
    """The chip's short text: a plug-in by its own name without the vendor in front, a built-in by its type."""
    spec = e.get("plugin") or {}
    if not spec.get("name"):
        return effect_name(e.get("effect", ""))
    return plugin_rows.short_name(spec["name"], vendor_of(spec) if vendor_of else "")


def chain(item: dict, vendor_of=None) -> list[dict]:
    """The inserts left to right in insert order; a bypassed one is dim (state), not a disabled control."""
    return [{"id": e["id"], "label": chip_label(e, vendor_of), "bypass": bool(e.get("bypass"))}
            for e in item.get("effects", [])]


def meter_of(render: dict, track_id: str) -> dict:
    """{peak (dBFS), lufs} of a track or a group (the engine answers groups apart, as `buses`), or {} when no render
    has measured it."""
    for t in [*(render.get("tracks") or []), *(render.get("buses") or [])]:
        if t.get("id") == track_id:
            return {"peak": db(t.get("peak")), "lufs": _num(t.get("lufs"))}
    return {}


def held_peaks(held: dict, now: dict, fresh: bool) -> dict:
    """The one peak number of every strip (tracks, groups, Master): the highest engine peak (dBFS) since play started.
    `held` is what was held so far, `now` the engine's latest {id: [peak, rms]}, `fresh` True on the first line of a play
    (the old numbers are dropped). The stop leaves `held` alone: the numbers stay until the next play."""
    out = {} if fresh else dict(held)
    for sid, v in now.items():
        if v:                                  # a strip that has made no sound yet holds the floor (shown "−∞")
            out[sid] = max(out.get(sid, -120.0), round(float(v[0]), 1))
    return out


def master_meter(render: dict) -> dict:
    if "lufs" not in render:
        return {}
    tp = _num(render.get("truePeak"))       # the master's meter reads true peak: the same number as the loudness panel's
    return {"peak": tp if tp is not None else db(render.get("peak")), "lufs": _num(render.get("lufs")), "truePeak": _num(render.get("truePeak")),
            "lra": _num(render.get("lra"))}


def _num(v):
    return round(float(v), 1) if isinstance(v, (int, float)) and v > -120 else None


NEUTRAL = "#8a8a8a"         # the cap of a bus and the master (the kit's fg3): only tracks carry a colour


def strip(item: dict, name: str, meter: dict, routing: dict | None = None, vendor_of=None, hue: str = NEUTRAL) -> dict:
    """`routing` (tracks and buses, `routing()` below) adds where it plays to and its sends; `vendor_of(plugin
    record)` names the vendor so a plug-in's chip can drop it; `hue` is the track's arrangement colour (its cap)."""
    kind = item["type"]
    return {"id": item["id"], "name": name, "hue": hue, "volume": item.get("volume", 1), "pan": item.get("pan", 0),
            "mute": bool(item.get("mute")), "solo": bool(item.get("solo")), "effects": chain(item, vendor_of), "meter": meter,
            "reverb": item.get("reverb", 0) if kind == "track" else None, "canSolo": kind == "track", "canArm": kind == "track" and item.get("instrument") != "voice", "canMute": kind != MASTER, "canPan": kind != MASTER,
            **(routing or ROUTING_NONE)}


ROUTING_NONE = {"output": "", "outputId": "", "outputs": [], "sends": [], "sendTargets": [], "ducks": [], "duckTargets": []}


def _feeds(buses: dict, start: str, goal: str) -> bool:
    """True when bus `start` plays (through other buses) into bus `goal`."""
    at = buses.get(start, {}).get("output", MASTER)
    seen = set()
    while at in buses and at not in seen:
        if at == goal:
            return True
        seen.add(at)
        at = buses[at].get("output", MASTER)
    return False


def routing(item: dict, buses: list[dict], label) -> dict:
    """Where a track or bus plays to (in words, and the choices it can move to: never itself or a loop) and, for a
    track, its sends (one per bus) and the buses it doesn't send to yet."""
    by_id = {b["id"]: b for b in buses}
    now = item.get("output", MASTER)
    to = f"→ {label(by_id[now])}" if now in by_id else "→ Master"
    choices = [{"id": MASTER, "label": "Master"}] + [
        {"id": b["id"], "label": label(b) + " group"} for b in buses
        if b["id"] != item["id"] and not (item["type"] == "bus" and _feeds(by_id, b["id"], item["id"]))]
    sends = [{"id": s["id"], "name": label(by_id[s["bus"]]) if s["bus"] in by_id else s["bus"],
              "level": s.get("level", 1) if not isinstance(s.get("level"), list) else 1} for s in item.get("sends", [])]
    used = {s["bus"] for s in item.get("sends", [])}
    return {**ROUTING_NONE, "output": to, "outputId": now, "outputs": choices, "sends": sends,
            "sendTargets": [] if item["type"] != "track" else [{"id": b["id"], "name": label(b)} for b in buses
                                                               if b["id"] not in used]}

