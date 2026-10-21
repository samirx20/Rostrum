"""How the inspector shows and edits Sound items (no Qt): times read in seconds whatever form they were written
in, a typed time written back in that same form (beats stay beats, "#drop+0.5" stays on its marker), and the
names items go by (a note by its pitch, a hit by its drum, a clip by its file).
"""
from __future__ import annotations

from rostrum_gui.edits import field_call
from rostrum_gui.bridge import name_of

from . import timeline, timing


def _time_kind(item: dict, param: str) -> str:
    """"time", "length" or "" for a field of an item."""
    if param == "at" or param == "length" and item["type"] == "doc":
        return "time"
    if param == "dur" or param == "length" and item["type"] == "clip":
        return "length"
    return ""


def shown(item: dict, root: dict) -> dict:
    out = dict(item)
    for k, v in item.items():
        kind = _time_kind(item, k)
        if kind and not isinstance(v, (int, float)):
            out[k] = round(timing.sec(v, root, item["id"]) if kind == "time" else timing.length_sec(v, root), 3)
    if item["type"] == "clip" and item.get("length") is None:      # plays to the file's end: show how long that is
        out["length"] = round(timeline.clip_span(item, root)[1], 3)
    return out


def edit_call(doc, item_id, param, value) -> dict:
    item = doc.item(item_id)
    kind = _time_kind(item, param)
    if kind and isinstance(value, (int, float)) and not isinstance(value, bool) and item.get(param) is not None:
        old = item[param]
        value = (timing.write_time if kind == "time" else timing.write_length)(old, float(value), doc.data)
    return field_call(doc, item_id, param, value)


def label(item: dict) -> str:
    t = item.get("type")
    if t == "note":
        keys = timing.keys(item["pitch"])
        return " ".join(timing.name(k) for k in keys) + (" chord" if len(keys) > 1 else " note")
    if t == "hit":
        return f"{item['drum']} hit"
    if t == "clip":
        return str(item["media"]).replace("\\", "/").rsplit("/", 1)[-1]
    if t == "doc":
        return "Song"
    return name_of(item)
