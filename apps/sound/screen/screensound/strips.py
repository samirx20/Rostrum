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
    return [{"id": e["id"], "label": effect_name(e.get("effect", "")), "bypass": bool(e.get("bypass"))}
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


def strip(item: dict, name: str, meter: dict) -> dict:
    return {"id": item["id"], "name": name, "volume": item.get("volume", 1), "pan": item.get("pan", 0),
            "mute": bool(item.get("mute")), "solo": bool(item.get("solo")), "effects": chain(item), "meter": meter}


def master_layout(op) -> list[dict]:
    """The master strip's extra rows: the Loudness group's primary params (normalize, loudness)."""
    return [r for r in rows.layout(op) if r["row"] == "param" and r["group"] == LOUDNESS and r["importance"] == "primary"]
