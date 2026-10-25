"""Keep notes in the key, and Only the key's rows (the In key ▾ chip, SPEC 3.6): the rules, as plain functions (no Qt).
Both are screen state per window; the key is the song's key at the note's own time (doc/keys.py). Every place a note
gets a pitch from the pointer or a key asks here: Draw and double-click (`snapped`), a vertical drag (`shifted`), the
↑ ↓ nudge (`step_call`). `fold` lays the roll's rows out again with the rows outside the key left out; a note already
outside the key keeps its row, so nothing in the song is hidden.
"""
from __future__ import annotations

from rostrum_sound.doc import keys as K

from . import action_calls as C
from . import timing


def has_key(root: dict) -> bool:
    return any(k.get("key") and K.parse(k["key"]) for k in root.get("keys", []))


def snapped(root: dict, t: float, midi: int) -> int:
    """The nearest note of the key playing at `t` (ties go down); `midi` itself while the song has no key."""
    key = K.key_for(root, t)
    return K.snap(midi, key) if key and K.parse(key) else midi


def shifted(root: dict, t: float, pitch, dsemi: int, lock: bool):
    """`pitch` moved `dsemi` half steps; with `lock`, the (lowest) note lands on the key's nearest note and a chord
    keeps its shape."""
    if lock and dsemi:
        low = min(K.midis(pitch))
        dsemi = snapped(root, t, max(0, min(127, low + dsemi))) - low
    return timing.shift_pitch(pitch, dsemi)


def step_call(root: dict, t: float, notes: list[str], semis: int, lock: bool) -> dict:
    """The ↑ ↓ nudge: a half step (Shift: an octave), or with `lock` one step of the key (an octave stays an octave)."""
    if lock and abs(semis) == 1 and has_key(root):
        return C.call("note.transpose", notes, steps=semis)
    return C.call("note.transpose", notes, semitones=semis)


def outside(root: dict, note: dict, t: float) -> bool:
    """Does any tone of the note sit outside the key playing at `t`?"""
    key = K.key_for(root, t)
    return bool(key and K.parse(key)) and any(not K.in_key(k, key) for k in K.midis(note["pitch"]))


def fold(roll: dict, root: dict) -> dict:
    """The roll with only the key's rows (every key the song has in the range) and the rows its notes sit on: `rows`
    (the keys shown, top first) and `rowNames` cut to match. The roll as it was when the song has no key."""
    if roll.get("kind") != "notes" or not has_key(root) or not roll.get("rowNames"):
        return roll
    top = roll["hi"]
    inside = [any(e["inKey"][i] for e in roll["rowNames"]) for i in range(top - roll["lo"] + 1)]
    held = {k for b in roll["blocks"] if b["type"] == "note" for k in b["keys"]}
    keep = [i for i, ok in enumerate(inside) if ok or top - i in held]
    names = [{**e, "names": [e["names"][i] for i in keep], "inKey": [e["inKey"][i] for i in keep]} for e in roll["rowNames"]]
    return {**roll, "rows": [top - i for i in keep], "rowNames": names}
