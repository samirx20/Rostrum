"""Ctrl+↑ / Ctrl+↓: the selected notes up or down one step of the song's key (a scale step, not a half step).
One `note.transpose` per distance (steps are a half or a whole step apart), all in one change. A chord moves by its lowest note's step."""
from __future__ import annotations

from rostrum_sound.doc import keys


def song_key(root: dict, sec: float) -> str:
    """The key playing at `sec`, else the first key change's; "" while the song has no key."""
    return keys.key_at(root, sec) or next((k["key"] for k in root.get("keys", []) if k.get("key")), "")


def calls(doc, ids, key: str, sign: int) -> list[dict]:
    by: dict[int, list[str]] = {}
    for i in ids:
        lowest = min(keys.midis(doc.item(i)["pitch"]))
        by.setdefault(keys.step_in_key(lowest, key, sign) - lowest, []).append(i)
    return [{"op": "note.transpose", "target": t, "args": {"semitones": d}} for d, t in by.items() if d]
