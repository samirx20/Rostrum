"""How the inspector shows and edits Sound items (no Qt): times read in seconds whatever form they were written
in, a typed time written back in that same form (beats stay beats, "#drop+0.5" stays on its marker), and the
names items go by (a note by its pitch, a hit by its drum, a clip by its file).
"""
from __future__ import annotations

import re

from rostrum_gui.edits import field_call

from rostrum_sound.doc import fields as FD

from . import timeline, timing


def _time_kind(item: dict, param: str) -> str:
    """"time", "length" or "" for a field of an item: what its Param says it holds (values.py `form`)."""
    p = next((p for p in FD.FIELDS.get(item["type"], ()) if p.name == param), None)
    return getattr(p, "form", "")


def _start(item: dict, root: dict) -> float:
    """Where the item starts (a length in beats is counted from there)."""
    return timing.sec(item["at"], root, item["id"]) if item.get("at") is not None else 0.0


def shown(item: dict, root: dict) -> dict:
    out = dict(item)
    for k, v in item.items():
        kind = _time_kind(item, k)
        if kind and not isinstance(v, (int, float)):
            out[k] = round(timing.sec(v, root, item["id"]) if kind == "time" else
                           timing.length_sec(v, root, _start(item, root), item), 3)
    if item["type"] == "track" and not item.get("colour"):          # the colour it is drawn in (timeline.hue)
        i = next((n for n, t in enumerate(root.get("tracks", [])) if t["id"] == item["id"]), 0)
        out["colour"] = timeline.hue(item, i)
    if item["type"] == "clip" and item.get("length") is None:      # plays to the file's end: show how long that is
        out["length"] = round(timeline.clip_span(item, root)[1], 3)
    return out


def edit_call(doc, item_id, param, value) -> dict:
    item = doc.item(item_id)
    kind = _time_kind(item, param)
    if kind and isinstance(value, (int, float)) and not isinstance(value, bool) and item.get(param) is not None:
        old = item[param]
        value = timing.write_time(old, float(value), doc.data) if kind == "time" else             timing.write_length(old, float(value), doc.data, _start(item, doc.data))
    return field_call(doc, item_id, param, value)


KIND_WORDS = {"tempo": "Tempo change", "meter": "Time signature", "key": "Key change", "section": "Section",
              "marker": "Marker", "track": "Track", "bus": "Bus", "group": "Group", "line": "Line", "doc": "Song"}
COUNTED = ("track", "bus", "group")           # several of these share a word: "Track 2"
_MADE_ID = re.compile(r"^([a-z]+)_\d+$")         # the ids the document hands out ("tempo_1", "meter_2")


def name_of(item: dict) -> str:
    """What an item is called: its name; with none, its id only when a person chose it, else its kind in words
    (a made-up id never reaches a title, a list or Ctrl K)."""
    if item.get("name"):
        return str(item["name"])
    made = _MADE_ID.match(str(item["id"]))
    if not made and item["id"]:
        return str(item["id"])
    t = item.get("type") or (made.group(1) if made else "")
    word = KIND_WORDS.get(t) or t.replace("_", " ").capitalize() or "Item"
    n = item["id"].rsplit("_", 1)[-1] if made else ""
    return f"{word} {n}" if n and t in COUNTED else word


def label(item: dict) -> str:
    t = item.get("type")
    if t == "note":
        keys = timing.keys(item["pitch"])
        return " ".join(timing.name(k) for k in keys) + (" chord" if len(keys) > 1 else " note")
    if t == "hit":
        return f"{item['drum']} hit"
    if t == "clip":
        return str(item["media"]).replace("\\", "/").rsplit("/", 1)[-1]
    if t == "line":
        return f'“{item.get("text", "")}”'
    if t == "doc":
        return "Song"
    return name_of(item)
