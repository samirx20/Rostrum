"""Delivery targets: where a mix is going and the loudness and true peak that place asks for (no Qt).

These are published specifications, not taste: each row names where its numbers come from. Choosing one sets the
master's own `loudness` and `truePeak` in one `master.set`; `verdict` then compares the last render to the master's
numbers, whatever they were set by.
"""
from __future__ import annotations

LUFS_TOLERANCE = 1.0          # a mix within ±1 LU of the target meets it (the engine normalizes to the target)

TARGETS = [
    {"key": "streaming", "label": "Streaming", "lufs": -14.0, "peak": -1.0,
     "source": "Spotify for Artists (loudness normalization: -14 LUFS, true peak -1 dBTP); YouTube plays near -14 LUFS."},
    {"key": "apple", "label": "Apple Music", "lufs": -16.0, "peak": -1.0,
     "source": "Apple Digital Masters / Sound Check reference level -16 LUFS; true peak -1 dBTP."},
    {"key": "ebu", "label": "EBU R128 broadcast", "lufs": -23.0, "peak": -1.0,
     "source": "EBU R128 (programme loudness -23 LUFS, +-0.5 LU; max true peak -1 dBTP)."},
    {"key": "atsc", "label": "ATSC A/85 broadcast", "lufs": -24.0, "peak": -2.0,
     "source": "ATSC A/85 (target -24 LKFS, +-2 dB; true peak -2 dBTP)."},
    {"key": "podcast", "label": "Podcast", "lufs": -16.0, "peak": -1.0,
     "source": "Apple Podcasts / AES TD1004 recommendation (-16 LUFS stereo; true peak -1 dBTP)."},
]
BY_KEY = {t["key"]: t for t in TARGETS}


def choices() -> list[dict]:
    """[{id, label, detail}] for the chooser."""
    return [{"id": t["key"], "label": t["label"], "detail": f"{_n(t['lufs'])} LUFS · {_n(t['peak'])} dBTP"} for t in TARGETS]


def key_of(master: dict) -> str:
    """The row whose numbers the master has now ("" when they match none: a custom target)."""
    return next((t["key"] for t in TARGETS if t["lufs"] == master.get("loudness") and t["peak"] == master.get("truePeak")), "")


def label_of(master: dict) -> str:
    t = BY_KEY.get(key_of(master))
    return t["label"] if t else "Custom"


def call(key: str, master_id: str = "master") -> dict:
    """The one operation that sets the target (both numbers at once, so one undo step)."""
    t = BY_KEY[key]
    return {"op": "master.set", "target": [master_id], "args": {"loudness": t["lufs"], "truePeak": t["peak"]}}


def _n(v: float) -> str:
    return f"{v:g}".replace("-", "−")


def verdict(master: dict, render: dict) -> dict:
    """Pass or miss of `render` (the engine's answer) against the master's target: loudness within ±1 LU and true peak
    under the ceiling. {} when there is no measurement yet."""
    lufs, peak = render.get("lufs"), render.get("truePeak")
    if not isinstance(lufs, (int, float)) or not isinstance(peak, (int, float)):
        return {}
    goal, ceiling = master.get("loudness", -16), master.get("truePeak", -1)
    off = lufs - goal
    problems = []
    if abs(off) > LUFS_TOLERANCE:
        problems.append(f"{abs(off):.1f} LU too {'loud' if off > 0 else 'quiet'}")
    if peak > ceiling:
        problems.append(f"true peak {peak - ceiling:.1f} dB over the ceiling")
    measured = f"{_n(round(lufs, 1))} LUFS, true peak {_n(round(peak, 1))} dBTP"
    if problems:
        return {"ok": False, "text": f"Miss: {' and '.join(problems)} ({measured})"}
    return {"ok": True, "text": f"Pass: {measured}"}
