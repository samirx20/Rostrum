"""How the inspector shows and edits Sound items (no Qt): every time and length reads in bars.beats ("5.3", ticks only
between counts; seconds on hover) whatever form it was written in, a typed time ("5.3", "5", "9.6 s", "0:09.6") is
written back in that same form (beats stay beats, "#drop+0.5" stays on its marker), pitches read as note names, and
the names items go by (a note by its pitch, a hit by its drum, a clip by its file). Formatting is doc/musical.py's.
"""
from __future__ import annotations

import functools
import re

from rostrum_core import RostrumError, codes
from rostrum_gui.edits import field_call

from rostrum_sound.doc import fields as FD
from rostrum_sound.doc import effects, musical, sounds

from . import drum_rows, effect_rows, eq_rows, feel_rows, note_feel, output_pick, pitch_merge, timeline, timing


def time_kind(item: dict, param: str) -> str:
    """"time", "length" or "" for a field of an item: what its Param says it holds (values.py `form`)."""
    forms = _FORMS.get(item["type"])
    if forms is None:               # each kind's table, read once (a scan of its fields per row cost ~10 % of a big pick)
        forms = _FORMS[item["type"]] = {p.name: getattr(p, "form", "") for p in reversed(FD.FIELDS.get(item["type"], ()))}
    return forms.get(param, "")


_FORMS: dict = {}


def _start(item: dict, root: dict) -> float:
    """Where the item starts (a length in beats is counted from there)."""
    return timing.sec(item["at"], root, item["id"]) if item.get("at") is not None else 0.0


def shown(item: dict, root: dict) -> dict:
    out = dict(item)
    for k, v in item.items():
        out[k] = shown_field(item, k, root)
    if item["type"] == "track" and not item.get("colour"):          # the colour it is drawn in (timeline.hue)
        i = next((n for n, t in enumerate(root.get("tracks", [])) if t["id"] == item["id"]), 0)
        out["colour"] = timeline.hue(item, i)
    if item["type"] == "track" and sounds.key_of(item) and sounds.choices(item):            # the one Sound picker reads the track's sound (never stored)
        out["sound"] = sounds.key_of(item)
    if output_pick.nowhere_else(root, item):                       # only the Master to play to: no Output row
        out.pop(output_pick.FIELD, None)
    if item["type"] == "clip" and item.get("length") is None:      # plays to the file's end: show how long that is
        out["length"] = round(timeline.clip_span(item, root)[1], 3)
    return out


def shown_field(item: dict, k: str, root: dict):
    """One field as `shown` has it, as written but for a time or length in a form other than seconds, made
    seconds (`shown` adds a few more for tracks and clips: their colour, sound, Output and a clip's length)."""
    v = item.get(k)
    kind = time_kind(item, k)
    if kind and v is not None and not isinstance(v, (int, float)):      # (None: left out, e.g. the song's length)
        return round(timing.sec(v, root, item["id"]) if kind == "time" else
                     timing.length_sec(v, root, _start(item, root), item), 3)
    return v


def musical_rows(item: dict, rows: list[dict], root: dict, sh: dict | None = None) -> list[dict]:
    """The evaluated rows with each time / length as a text field in bars.beats (its seconds in the hover help) and
    a note's pitch as a name. The one place; every panel's time fields come through here. (`sh`: shown(item, root),
    when the caller has it.)"""
    sh = shown(item, root) if sh is None else sh
    out = [musical_row(item, sh, r, root) for r in rows]
    return pitch_merge.merge_rows(item, eq_rows.band_rows(item, effect_rows.own_rows(item, out)))


def musical_row(item: dict, sh: dict, r: dict, root: dict) -> dict:
    """One evaluated row as musical_rows shows it (`sh`: shown(item, root))."""
    kind = time_kind(item, r["id"]) if r["row"] == "param" else ""
    if kind and isinstance(sh.get(r["id"]), (int, float)) and not isinstance(sh[r["id"]], bool):
        sec = float(sh[r["id"]])
        text = (musical.position(sec, root) if kind == "time" else
                f"{sec:.2f} s" if item["type"] == "clip" else musical.note_length(sec, root, _start(item, root)))   # a sound's length is in seconds
        help_ = f"{r['help']} " if r["help"] else ""
        return {**r, "type": "text", "value": text, "unit": "", "display": "", "control": "",
                "help": f"{help_}Now {sec:.2f} s. Type " + ("a note value (1/8), " if kind == "length" and item["type"] != "clip" else "") + "bars.beats (5.3), seconds (9.6 s) or a clock (0:09.6)."}
    if r["row"] == "param" and item["type"] == "note" and r["id"] == "pitch" and r["value"] is not None:
        return {**r, "value": musical.note_name(r["value"])}
    if r["row"] == "param" and item["type"] == "hit" and r["id"] == "drum":
        return {**r, "type": "choice", "control": "", "options": drum_options(root, item)}    # a pick of the kit's drums
    if r["row"] == "param" and item["type"] == "note" and r["id"] in note_feel.PARAMS:
        return {**r, "type": "text", "label": note_feel.LABELS[r["id"]], "help": note_feel.HELP[r["id"]],
                "value": note_feel.words(r["id"], r["value"], _seconds(item, root))}
    return r


def edit_call(doc, item_id, param, value) -> dict:
    item = doc.item(item_id)
    feel = feel_rows.call(item, param, value)                   # a Feel row: one track.feel (merges into perform)
    if feel is not None:
        return feel
    merged = pitch_merge.edit_args(item, param, value)          # Pitch / Keep speed: one or two fields of the clip
    if merged is not None:
        first, *rest = merged
        call = field_call(doc, item_id, first, merged[first])
        call["args"].update({k: merged[k] for k in rest})
        return call
    bands = eq_rows.edit_args(item, param, value)               # an EQ band's row: the whole bands list is written
    if bands is not None:
        return field_call(doc, item_id, "bands", bands["bands"])
    if item["type"] == "note" and isinstance(value, str) and param in note_feel.PARAMS:     # typed words: Swell, Vibrato, Bend
        try:
            value = note_feel.parse(param, value, _seconds(item, doc.data))
        except ValueError as e:
            raise RostrumError(codes.BAD_ARGUMENT, "set", note_feel.LABELS[param], str(e)) from None
    if item["type"] == "note" and param == "pitch" and isinstance(value, str):
        value = typed_pitch(value)
    kind = time_kind(item, param)
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


def by_length(item: dict, param: str) -> bool:
    """Whether a field reads differently on items of other lengths with the same value written (many_rows)."""
    return time_kind(item, param) == "length" or item["type"] == "note" and param in note_feel.BY_LENGTH


def _seconds(note: dict, root: dict) -> float:
    return timing.length_sec(note["dur"], root, _start(note, root), note)


def typed_pitch(text: str):
    """A typed pitch: a name ("C5", "F#3"), a MIDI number ("72"), or several for a chord ("60 64 67", "C4, E4")."""
    keys = [int(k) if k.lstrip("-").isdigit() else k for k in re.split(r"[\s,]+", text.strip()) if k]
    return keys[0] if len(keys) == 1 else keys if keys else text


def drum_options(root: dict, hit: dict) -> list[dict]:
    """The Drum picker: every drum the hit's track's kit plays, in its own order, by plain name (the one it is now
    first kept, if the kit does not have it: a GM key number, an old name)."""
    tid = str(hit["id"]).split(".", 1)[0]
    track = next((t for t in root.get("tracks", []) if t["id"] == tid and hit in t.get("hits", [])), None) or next(
        (t for t in root.get("tracks", []) if any(h["id"] == hit["id"] for h in t.get("hits", []))), {})
    drums = drum_rows.kit_drums(track)
    have = [hit["drum"]] if hit.get("drum") not in drums else []
    return [{"value": d, "label": drum_words(d) if isinstance(d, str) else f"Key {d}"} for d in [*have, *drums]]


KIND_WORDS = {"tempo": "Tempo change", "meter": "Time signature", "key": "Key change", "section": "Section",
              "marker": "Marker", "track": "Track", "bus": "Group", "group": "Group", "line": "Line", "doc": "Song",
              "effect": "Effect", "lane": "Automation", "send": "Send", "duck": "Dip", "note": "Note", "hit": "Hit",
              "clip": "Clip", "master": "Master"}
EFFECT_WORDS = effects.WORDS
ONLY_ONE = ("master", "doc")                   # one per song: never called by its id
COUNTED = ("track", "bus", "group", "section")           # several of these share a word: "Track 2"
# the ids the document hands out: "tempo_1", "meter_2", and the ones inside a track: "pad.delay_1", "pad.n1500", "marker.drop"
_MADE_ID = re.compile(r"^([a-z]+)_\d+$|^[^.\s]+\.[^\s]+$")


def name_of(item: dict) -> str:
    """What an item is called: its name; with none, its id only when a person chose it, else its kind in words
    (a made-up id never reaches a title, a list or Ctrl K; an effect is its effect type: "Delay")."""
    name = item.get("name")
    if name and not (item.get("type") == "section" and re.match(r"^[a-z]+_\d+$", str(name))):      # an old "section_1" is a made-up name too
        return str(name)
    made = _MADE_ID.match(str(item["id"]))
    if name:
        made = re.match(r"^([a-z]+)_\d+$", str(name))
        item = {**item, "id": str(name)}
    elif item.get("type") in ONLY_ONE:
        made = None
    elif not made and item["id"]:
        return str(item["id"])
    t = item.get("type") or (made.group(1) if made and made.group(1) else "")
    if t == "effect" and item.get("effect"):
        return EFFECT_WORDS.get(item["effect"]) or str(item["effect"]).replace("_", " ").capitalize()
    word = KIND_WORDS.get(t) or t.replace("_", " ").capitalize() or "Item"
    n = item["id"].rsplit("_", 1)[-1] if made and made.group(1) else ""
    n = n if n.isdigit() else ""
    return f"{word} {n}" if n and t in COUNTED else word


@functools.lru_cache(maxsize=512)
def drum_words(drum) -> str:
    """A drum's stored name ("openHat", "kick") in words, as the roll's rows say it: "Open hat", "Kick"."""
    s = re.sub(r"([a-z])([A-Z0-9])", r"\1 \2", str(drum).replace("_", " ")).lower()
    return s[:1].upper() + s[1:]


def label(item: dict) -> str:
    t = item.get("type")
    if t == "note":
        keys = timing.keys(item["pitch"])
        return " ".join(timing.name(k) for k in keys) + (" chord" if len(keys) > 1 else " note")
    if t == "hit":
        return f"{drum_words(item['drum'])} hit"
    if t == "clip":
        return str(item["media"]).replace("\\", "/").rsplit("/", 1)[-1]
    if t == "line":
        return f'“{item.get("text", "")}”'
    if t == "doc":
        return "Song"
    return name_of(item)


def in_words(text: str, doc) -> str:
    """A line meant for a person (a status, an error) with every item id in it said as its name: "track_1.c0: denoise"
    reads "Recording-take-1.wav: denoise". One place for every line built from engine output."""
    for i in sorted((i["id"] for i in doc.items() if i.get("id")), key=len, reverse=True):
        if i in text:
            text = re.sub(rf"(?<![\w.]){re.escape(i)}(?![\w])", lambda _m, i=i: label(doc.item(i)), text)
    return text
