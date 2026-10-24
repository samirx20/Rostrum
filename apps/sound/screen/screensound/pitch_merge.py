"""A clip's two pitch fields as one "Pitch" and a "Keep speed" switch on the screen (no Qt). The document keeps both
(`pitch`: tape-style, speed follows; `shift`: pitch only, the length stays), because agents and scripts write either;
a person sees one amount and one question. The switch is on while the pitch is held apart from the speed (`shift`),
and flipping it moves the amount to the other field, so the sound is the same pitch either way round the switch.
Called from inspect.py (the one place the inspector's values, rows and edits pass through)."""
from __future__ import annotations

AMOUNT = "Pitch"                 # the row that stays: it holds whichever field is in use (its id is its word, like the switch,
                                 # so a several-clips selection, which keeps the two plain rows, never reaches these edits)
TAPE = "pitch"
SWITCH = "Keep speed"            # its id is its words: the history says "Change Keep speed"
GONE = "shift"                   # the row folded into AMOUNT


def keeps_speed(item: dict) -> bool:
    return bool(item.get("shift")) or not item.get("pitch")


def amount(item: dict) -> float:
    return float(item.get("shift" if keeps_speed(item) else "pitch") or 0)


def merge_rows(item: dict, rows: list[dict]) -> list[dict]:
    """The clip's rows with Pitch (the amount in use) and the Keep speed switch where "Pitch only" was."""
    if item.get("type") != "clip":
        return rows
    gone = next((r for r in rows if r["id"] == GONE), None)
    out = []
    for r in rows:
        if r["id"] == GONE:
            out.append({**r, "id": SWITCH, "label": SWITCH, "type": "toggle", "value": keeps_speed(item), "unit": "", "min": None, "max": None,
                        "step": None, "display": "", "options": [], "default": None, "anim": "", "expr": "",
                        "help": "On: the pitch changes and the clip keeps its speed and length. Off: pitch and speed change together, like a tape."})
        elif r["id"] == TAPE and gone is not None:
            out.append({**r, "id": AMOUNT, "label": "Pitch", "value": amount(item), "default": 0,
                        "help": "How far the clip is moved up or down, in semitones (12 = an octave)."})
        else:
            out.append(r)
    return out


def edit_args(item: dict, param: str, value) -> dict | None:
    """The fields a Pitch / Keep speed edit writes ({} keys), or None when the param is not one of these."""
    if item.get("type") != "clip" or param not in (AMOUNT, SWITCH):
        return None
    if param == AMOUNT:
        return {"shift" if keeps_speed(item) else "pitch": value}
    now = amount(item)
    return {"shift": now, "pitch": 0} if value else {"pitch": now, "shift": 0}
