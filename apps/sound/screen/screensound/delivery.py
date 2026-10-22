"""Delivery targets: where a mix is going and the loudness and true peak that place asks for (no Qt).

These are published specifications, not taste: each row names where its numbers come from. Choosing one sets the
master's own `loudness` and `truePeak` in one `master.set`; `verdict` then compares the last render to the master's
numbers, whatever they were set by.

Only the fields that apply now take part (`applying`: their valid_when on the master, from the field op): the true
peak ceiling always does (the limiter), the loudness target only while Normalize is on. So the chooser is there
whenever one of them applies, sets only those, and judges only those.
"""
from __future__ import annotations

from rostrum_core.conditions import holds

LUFS_TOLERANCE = 1.0          # a mix within ±1 LU of the target meets it (the engine normalizes to the target)

TARGETS = [
    {"key": "streaming", "label": "Streaming", "lufs": -14.0, "peak": -1.0,
     "source": "Spotify for Artists (loudness normalization: -14 LUFS, true peak -1 dBTP); YouTube plays near -14 LUFS."},
    {"key": "apple", "label": "Apple Music", "lufs": -16.0, "peak": -1.0,
     "source": "Apple Digital Masters / Sound Check reference level -16 LUFS; true peak -1 dBTP."},
    {"key": "ebu", "label": "EBU R128", "lufs": -23.0, "peak": -1.0,
     "source": "EBU R128 (programme loudness -23 LUFS, +-0.5 LU; max true peak -1 dBTP)."},
    {"key": "atsc", "label": "ATSC A/85", "lufs": -24.0, "peak": -2.0,
     "source": "ATSC A/85 (target -24 LKFS, +-2 dB; true peak -2 dBTP)."},
    {"key": "podcast", "label": "Podcast", "lufs": -16.0, "peak": -1.0,
     "source": "Apple Podcasts / AES TD1004 recommendation (-16 LUFS stereo; true peak -1 dBTP)."},
]
BY_KEY = {t["key"]: t for t in TARGETS}


FIELDS = {"loudness": ("lufs", "LUFS"), "truePeak": ("peak", "dBTP")}     # master field -> (row key, unit)
ALL = tuple(FIELDS)


def applying(field_op, master: dict, facts: dict) -> list[str]:
    """The master's delivery fields valid right now (by their valid_when), in FIELDS order."""
    when = {p.name: p.valid_when for p in field_op.params}
    return [f for f in FIELDS if f in when and holds(when[f], master, facts)]


def _detail(t: dict, fields) -> str:
    return " · ".join(f"{_n(t[FIELDS[f][0]])} {FIELDS[f][1]}" for f in fields)


def choices(fields=ALL) -> list[dict]:
    """[{id, label, detail}] for the chooser: each target's numbers for the fields that apply."""
    return [{"id": t["key"], "label": t["label"], "detail": _detail(t, fields)} for t in TARGETS]


def key_of(master: dict, fields=ALL) -> str:
    """The one row whose numbers (of the fields that apply) the master has now; "" for none or several."""
    keys = [t["key"] for t in TARGETS if all(t[FIELDS[f][0]] == master.get(f) for f in fields)]
    return keys[0] if len(keys) == 1 or (keys and tuple(fields) == ALL) else ""


def label_of(master: dict, fields=ALL) -> str:
    """The row's name, or the numbers themselves when no single row has them ("−1 dBTP" with only the ceiling on)."""
    if "loudness" not in fields:                       # Normalize off: no target chosen yet
        return "Choose…"
    t = BY_KEY.get(key_of(master, fields))
    return t["label"] if t else _detail({FIELDS[f][0]: master.get(f) for f in fields}, fields) or "Custom"


def call(key: str, master_id: str = "master") -> dict:
    """The one operation that delivers to a target (one undo step): Normalize on, so the mix is made that loud, and
    both its numbers. (Choosing "Streaming" with Normalize off used to set only the ceiling: it looked like nothing
    happened, P21 walk-through.)"""
    t = BY_KEY[key]
    return {"op": "master.set", "target": [master_id],
            "args": {"normalize": True, **{f: t[FIELDS[f][0]] for f in ALL}}}


def _n(v: float) -> str:
    return f"{v:g}".replace("-", "−")


def verdict(master: dict, render: dict, fields=ALL) -> dict:
    """Pass or miss of `render` (the engine's answer) against the master's target: loudness within ±1 LU (while it
    applies) and true peak under the ceiling. {} when there is no measurement yet."""
    lufs, peak = render.get("lufs"), render.get("truePeak")
    if not isinstance(lufs, (int, float)) or not isinstance(peak, (int, float)):
        return {}
    goal, ceiling = master.get("loudness", -16), master.get("truePeak", -1)
    off = lufs - goal
    problems = []
    if "loudness" in fields and abs(off) > LUFS_TOLERANCE:
        problems.append(f"{abs(off):.1f} LU too {'loud' if off > 0 else 'quiet'}")
    if peak > ceiling:
        problems.append(f"loudest peak {peak - ceiling:.1f} dB over the limit")
    measured = f"loudness {_n(round(lufs, 1))} LUFS, loudest peak {_n(round(peak, 1))} dBTP"
    if problems:
        return {"ok": False, "text": f"Miss: {' and '.join(problems)} ({measured})"}
    if "loudness" not in fields:                       # only the ceiling applies: no target to pass
        return {"ok": True, "text": f"Loudest peak is under the limit ({measured})"}
    return {"ok": True, "text": f"Pass: {measured}"}
