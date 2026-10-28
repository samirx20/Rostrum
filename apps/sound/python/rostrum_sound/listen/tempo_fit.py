"""tempo_fit: the song's tempo against the brief's (an `expect` entry {"kind": "tempo", "bpm": 132}).

Round 2's jazz agent sped 132 BPM up to 133 so a stop would fall on a bar line; the judges heard it rushed. The song's
start tempo and the tempo it holds for most of its length (a short glide or a pickup does not move it) are
compared with the asked one; either off by more than 0.5 % is a fault naming the ways to land a sync moment that keep the tempo."""
from __future__ import annotations

from .core import num

OFF_PCT = 0.5


def faults(asked: dict) -> list[dict]:
    """asked: {"bpm", "start_bpm", "held_bpm"} (moments_arg fills the song's two) -> the fault, if any."""
    bpm = float(asked["bpm"])
    off = {k: 100 * (float(asked[k]) - bpm) / bpm for k in ("start_bpm", "held_bpm")}
    if max(abs(v) for v in off.values()) <= OFF_PCT:
        return []
    return [{"kind": "off_tempo", "at_s": 0.0, "measured": {"asked_bpm": bpm, "start_bpm": num(asked["start_bpm"], 2),
             "held_bpm": num(asked["held_bpm"], 2), "off_pct": num(max(off.values(), key=abs), 2)}}]


def words(f) -> str:
    d = f["measured"]
    return (f"tempo far from the brief's: asked {d['asked_bpm']:g} BPM, the song starts at {d['start_bpm']:g} and holds "
            f"{d['held_bpm']:g} ({d['off_pct']:+g} %); listeners hear a bent tempo as rushed or dragging. Keep the asked "
            "tempo and land the sync moment another way: downbeat(bar(n), at=<seconds>) (a pickup before bar 1), "
            "land(bar(n), at=<seconds>, ramp_from=bar(m)) (a short glide that arrives on time), or place the moment in seconds")
