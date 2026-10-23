"""How the inspector shows and edits Sound items (no Qt): every time and length reads in bars.beats ("5.3", ticks only
between counts; seconds on hover) whatever form it was written in, a typed time ("5.3", "5", "9.6 s", "0:09.6") is
written back in that same form (beats stay beats, "#drop+0.5" stays on its marker), pitches read as note names, and
the names items go by (a note by its pitch, a hit by its drum, a clip by its file). Formatting is doc/musical.py's.
"""
from __future__ import annotations

import re

from rostrum_core import RostrumError, codes
from rostrum_gui.edits import field_call

from rostrum_sound.doc import fields as FD
from rostrum_sound.doc import musical

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


def musical_rows(item: dict, rows: list[dict], root: dict) -> list[dict]:
    """The evaluated rows with each time / length as a text field in bars.beats (its seconds in the hover help) and
    a note's pitch as a name. The one place; every panel's time fields come through here."""
    sh, out = shown(item, root), []
    for r in rows:
        kind = _time_kind(item, r["id"]) if r["row"] == "param" else ""
        if kind and isinstance(sh.get(r["id"]), (int, float)) and not isinstance(sh[r["id"]], bool):
            sec = float(sh[r["id"]])
            text = musical.position(sec, root) if kind == "time" else musical.length(sec, root, _start(item, root))
            help_ = f"{r['help']} " if r["help"] else ""
            r = {**r, "type": "text", "value": text, "unit": "", "display": "", "control": "",
                 "help": f"{help_}Now {sec:.2f} s. Type bars.beats (5.3), seconds (9.6 s) or a clock (0:09.6)."}
        elif r["row"] == "param" and item["type"] == "note" and r["id"] == "pitch" and r["value"] is not None:
            r = {**r, "value": musical.note_name(r["value"])}
        out.append(r)
    return out


def edit_call(doc, item_id, param, value) -> dict:
    item = doc.item(item_id)
    kind = _time_kind(item, param)
    if kind and isinstance(value, str):             # typed words: bars.beats or seconds, as seconds
        start = _start(item, doc.data)
        try:
            value = musical.parse(value, doc.data, kind == "length", start)
        except ValueError as e:
            raise RostrumError(codes.BAD_ARGUMENT, "set", f"{param}={value!r}", str(e)) from None
    if kind and isinstance(value, (int, float)) and not isinstance(value, bool) and item.get(param) is not None:
        old = item[param]
        value = timing.write_time(old, float(value), doc.data) if kind == "time" else             timing.write_length(old, float(value), doc.data, _start(item, doc.data))
    return field_call(doc, item_id, param, value)


KIND_WORDS = {"tempo": "Tempo change", "meter": "Time signature", "key": "Key change", "section": "Section",
              "marker": "Marker", "track": "Track", "bus": "Bus", "group": "Group", "line": "Line", "doc": "Song",
              "effect": "Effect", "lane": "Automation", "send": "Send", "duck": "Duck", "note": "Note", "hit": "Hit",
              "clip": "Clip"}
EFFECT_WORDS = {"eq": "EQ", "compressor": "Compressor", "reverb": "Reverb", "delay": "Delay", "saturate": "Saturation",
                "tape": "Tape", "limiter": "Limiter", "width": "Stereo width", "gate": "Gate", "deess": "De-esser",
                "dehum": "De-hum", "plugin": "Plug-in"}
COUNTED = ("track", "bus", "group")           # several of these share a word: "Track 2"
# the ids the document hands out: "tempo_1", "meter_2", and the ones inside a track: "pad.delay_1", "pad.n1500", "marker.drop"
_MADE_ID = re.compile(r"^([a-z]+)_\d+$|^[^.\s]+\.[^\s]+$")


def name_of(item: dict) -> str:
    """What an item is called: its name; with none, its id only when a person chose it, else its kind in words
    (a made-up id never reaches a title, a list or Ctrl K; an effect is its effect type: "Delay")."""
    if item.get("name"):
        return str(item["name"])
    made = _MADE_ID.match(str(item["id"]))
    if not made and item["id"]:
        return str(item["id"])
    t = item.get("type") or (made.group(1) if made and made.group(1) else "")
    if t == "effect" and item.get("effect"):
        return EFFECT_WORDS.get(item["effect"]) or str(item["effect"]).replace("_", " ").capitalize()
    word = KIND_WORDS.get(t) or t.replace("_", " ").capitalize() or "Item"
    n = item["id"].rsplit("_", 1)[-1] if made and made.group(1) else ""
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
