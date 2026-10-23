"""The song's music map edited from the screen (no Qt): tempo, key and sections as operation calls.

Everything here builds calls for the document's own operations (`doc.set`, `tempo.add`, `key.add` / `key.set`,
`section.add` / `section.set`, `*.remove`); the bridge applies them (a drag: one gesture = one undo step). Times keep
the form they were written in (beats stay beats, a section on a marker stays on it); a new thing is written in beats.
`state` is what the settings panel's song view needs: only what is valid right now (a delete only with that thing selected).
"""
from __future__ import annotations

from rostrum_core import RostrumError, codes
from rostrum_sound.doc import keys as K
from rostrum_sound.doc import meter, tempo

from . import timing

TYPES = ("tempo", "edge")        # drags handled here (a key change moves like any timed item: moves.py)
NO_KEY = "No key"               # the one wording for a song with no key, wherever it shows
TONICS = ["C", "C#", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
SECTION_BARS = 4


def _bad(where, what, why, allowed=()):
    return RostrumError(codes.BAD_ARGUMENT, where, what, why, list(allowed))


def _beat_at(root, t, free=False):
    b = tempo.beat_at(root, t)
    return round(b, 4) if free else round(b / timing.SNAP_BEATS) * timing.SNAP_BEATS


def _name(have, base="section"):
    n = 1
    while f"{base}_{n}" in have:
        n += 1
    return f"{base}_{n}"


# ---- what the popup shows ----------------------------------------------------------------------------------
def split_key(key: str) -> tuple[str, str]:
    p = K.parse(key) if key else None
    if p is None:
        return "", "major"          # no key: no tonic (every screen says NO_KEY; a first key is chosen, never assumed)
    pc, mode = p
    return next(n for n in TONICS if (K.TONICS[n[0]] + {"#": 1, "b": -1}.get(n[1:], 0)) % 12 == pc), mode


def state(root: dict, sel: dict | None, t: float) -> dict:
    """Facts for the song view at playhead `t` (seconds) with `sel` (the selected item, or None)."""
    from . import music_map
    keys = music_map.key_changes(root)
    here = next((k for k in reversed(keys) if k["t"] <= t + 1e-6), None)
    tonic, mode = split_key(here["key"] if here else "")
    kind = sel["type"] if sel else ""
    out = {"startBpm": tempo.start_bpm(root), "hasKey": here is not None, "tonic": tonic, "mode": mode,
           "keyAtPlayhead": here is not None and abs(here["t"] - t) < 0.01,
           "selected": kind if kind in ("tempo", "key", "section") else "", "selName": "", "selBpm": 0}
    if kind == "section":
        out["selName"] = sel.get("name", "")
    if kind == "tempo":
        out["selBpm"] = float(sel.get("bpm", 0))
    return out


# ---- calls -------------------------------------------------------------------------------------------------
def start_tempo_call(bpm: float) -> dict:
    return {"op": "doc.set", "target": ["root"], "args": {"tempo": float(bpm)}}


def add_tempo_call(root: dict, t: float, bpm: float | None = None) -> dict:
    """A tempo change at the playhead, on its beat (stays on it when earlier tempos change); starts at the tempo
    already playing there."""
    b = _beat_at(root, t)
    if b <= 1e-9:
        raise _bad("tempo.add", "the start of the song", "is the song's own tempo: change that one instead")
    return {"op": "tempo.add", "target": [],
            "args": {"at": {"beat": b}, "bpm": float(bpm or tempo.bpm_at(root, t))}}


def key_call(root: dict, t: float, tonic: str, mode: str, new_here: bool) -> dict:
    """Set the key: the key playing now when there is one, else a first key at the start; `new_here`: a key change
    at the playhead instead."""
    key = f"{tonic} {mode}"
    if K.parse(key) is None:
        raise _bad("key", f'"{key}"', "is not a key", K.FORMS)
    from . import music_map
    ks = music_map.key_changes(root)
    here = next((k for k in reversed(ks) if k["t"] <= t + 1e-6), None)
    if here is not None and not new_here:
        return {"op": "key.set", "target": [here["id"]], "args": {"key": key}}
    at = {"beat": _beat_at(root, t)} if new_here and ks else 0
    return {"op": "key.add", "target": [], "args": {"at": at, "key": key}}


def add_section_call(root: dict, t: float) -> dict:
    """A section from the playhead, four bars long, in beats."""
    b = _beat_at(root, t)
    bars = SECTION_BARS * meter.start_bar(root)
    name = _name({s.get("name") for s in root.get("sections", [])})
    return {"op": "section.add", "target": [], "args": {"name": name, "at": {"beat": b}, "end": {"beat": b + bars}}}


# ---- drags -------------------------------------------------------------------------------------------------
def edge_grab(doc, item_id: str, edge: str) -> dict:
    s = doc.item(item_id)
    if s["type"] != "section" or edge not in ("at", "end"):
        raise _bad("section edge", f'"{item_id}" {edge}', "is not an edge of a section", ["at", "end"])
    return {"id": item_id, "type": "edge", "edge": edge, "at": s[edge], "t": timing.sec(s[edge], doc.data, item_id)}


def drag_calls(doc, g: dict, dt: float, free: bool = False, grid=None) -> list[dict]:
    """`grid`: the window's Grid ▾ / Snap (timing.Grid); a section edge snaps to it, a tempo change to beats
    unless Snap is off."""
    root = doc.data
    free = free or (grid is not None and not grid.on)
    if g["type"] == "edge":
        s = doc.item(g["id"])
        other = timing.sec(s["end" if g["edge"] == "at" else "at"], root, g["id"])
        step = timing.spb(root, other) * timing.SNAP_BEATS
        t = timing.snap(g["t"] + dt, root, free, grid)
        t = max(0.0, min(t, other - step)) if g["edge"] == "at" else max(t, other + step)
        return [{"op": "section.set", "target": [g["id"]], "args": {g["edge"]: timing.write_time(g["at"], t, root)}}]
    # a tempo change: placed on the map without itself, so its own tempo doesn't move the ground under the drag
    rest = {**root, "tempos": [c for c in root.get("tempos", []) if c["id"] != g["id"]]}
    to = max(0.0, g["t"] + dt)
    at = round(tempo.beat_at(rest, to), 4) if free else _beat_at(rest, to)
    at = max(at, timing.SNAP_BEATS)
    new = {"beat": at} if isinstance(g["at"], dict) else round(tempo.seconds_at(rest, at), 4)
    return [{"op": "tempo.set", "target": [g["id"]], "args": {"at": new}}]
