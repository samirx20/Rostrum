"""What a mixer strip shows, from the document and the last render's answer (no Qt).

A strip is a plain dict: id, name, volume, pan, mute, solo, the insert chain in order, and a meter that is
`{}` (absent) until a render has measured the track. The master is one more strip, the one with id "master".
The master's loudness rows come from `master.set`'s own params (Loudness group, primary), so the loudness
target appears only while normalize is on, by `valid_when`.
"""
from __future__ import annotations

import math

from rostrum_gui import rows

MASTER = "master"
LOUDNESS = "Loudness"
EFFECT_NAMES = {"eq": "EQ", "deess": "De-ess", "dehum": "De-hum"}


def effect_name(kind: str) -> str:
    return EFFECT_NAMES.get(kind) or kind[:1].upper() + kind[1:]


def db(linear: float) -> float | None:
    return round(20 * math.log10(linear), 1) if linear and linear > 0 else None


def chain(item: dict) -> list[dict]:
    """The inserts left to right in insert order; a bypassed one is dim (state), not a disabled control."""
    return [{"id": e["id"], "label": (e.get("plugin") or {}).get("name") or effect_name(e.get("effect", "")),
             "bypass": bool(e.get("bypass"))}
            for e in item.get("effects", [])]


def meter_of(render: dict, track_id: str) -> dict:
    """{peak (dBFS), lufs} of a track, or {} when no render has measured it."""
    for t in render.get("tracks") or []:
        if t.get("id") == track_id:
            return {"peak": db(t.get("peak")), "lufs": _num(t.get("lufs"))}
    return {}


def master_meter(render: dict) -> dict:
    if "lufs" not in render:
        return {}
    return {"peak": db(render.get("peak")), "lufs": _num(render.get("lufs")), "truePeak": _num(render.get("truePeak")),
            "lra": _num(render.get("lra"))}


def _num(v):
    return round(float(v), 1) if isinstance(v, (int, float)) and v > -120 else None


def strip(item: dict, name: str, meter: dict, routing: dict | None = None) -> dict:
    """`routing` (tracks and buses, `routing()` below) adds where it plays to and its sends."""
    return {"id": item["id"], "name": name, "volume": item.get("volume", 1), "pan": item.get("pan", 0),
            "mute": bool(item.get("mute")), "solo": bool(item.get("solo")), "effects": chain(item), "meter": meter,
            "canSolo": item["type"] == "track", **(routing or ROUTING_NONE)}


ROUTING_NONE = {"output": "", "outputId": "", "outputs": [], "sends": [], "sendTargets": []}


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
    to = f"to {label(by_id[now])} bus" if now in by_id else "to Master"
    choices = [{"id": MASTER, "label": "Master"}] + [
        {"id": b["id"], "label": label(b) + " bus"} for b in buses
        if b["id"] != item["id"] and not (item["type"] == "bus" and _feeds(by_id, b["id"], item["id"]))]
    sends = [{"id": s["id"], "name": label(by_id[s["bus"]]) if s["bus"] in by_id else s["bus"],
              "level": s.get("level", 1) if not isinstance(s.get("level"), list) else 1} for s in item.get("sends", [])]
    used = {s["bus"] for s in item.get("sends", [])}
    return {"output": to, "outputId": now, "outputs": choices, "sends": sends,
            "sendTargets": [] if item["type"] != "track" else [{"id": b["id"], "name": label(b)} for b in buses
                                                               if b["id"] not in used]}


def master_layout(op) -> list[dict]:
    """The master strip's extra rows: the Loudness group's primary params (normalize, loudness)."""
    return [r for r in rows.layout(op) if r["row"] == "param" and r["group"] == LOUDNESS and r["importance"] == "primary"]
