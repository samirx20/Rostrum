"""What an instrument card shows, from the track's field operation (rule of individuality as data; no Qt).

A card's controls are the operation's params in the "Instrument" group, and any group a later field adds there:
primary ones on the card, the rest (secondary and deep) behind the card's own More. Which of them are present
right now is each param's `valid_when` against the track's values, exactly as the inspector decides it
(`rostrum_gui.rows`). Nothing here names a single instrument's control; a new field in `doc/fields.py` shows up.
"""
from __future__ import annotations

import dataclasses
import re
from pathlib import Path
from types import SimpleNamespace

from rostrum_gui import rows

GROUP = "Instrument"
# Plain words for a procedural instrument (its `model` field); an unknown one is just its own name, spaced out.
FAMILY = {"guitar": "Plucked string", "nylonGuitar": "Plucked string", "violin": "Bowed string",
          "marimba": "Struck bar", "vibraphone": "Struck bar", "glockenspiel": "Struck bar", "tubularBell": "Struck bar"}


def spaced(name: str) -> str:
    """"grandPiano" -> "Grand piano"; "Violin_Section.sfz" -> "Violin Section"."""
    stem = Path(str(name).replace("\\", "/")).stem if str(name).lower().endswith(".sfz") else str(name)
    words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", stem).replace("_", " ").strip()
    return words[:1].upper() + words[1:]


def layout(op) -> list[dict]:
    """The card's static rows: the Instrument group's params (no group header), primary first, the rest
    behind a More row (the card's own: secondary counts as behind it here)."""
    params = [dataclasses.replace(p, importance="primary" if p.importance == "primary" else "deep")
              for p in op.params if p.group == GROUP and p.type != "id"]
    return [r for r in rows.layout(SimpleNamespace(params=params)) if r["row"] != "group"]


def has_instrument(track: dict) -> bool:
    return track.get("instrument", "none") != "none"


def what_it_is(track: dict) -> str:
    """The instrument in plain words: "Sampled · Violin Section", "Plucked string · guitar", "Synth · saw"."""
    kind = track.get("instrument", "none")
    if kind == "sfz":
        return "Sampled · " + spaced(track.get("sfz") or "no file")
    if kind == "builtIn":
        return "Built-in · " + spaced(track.get("builtIn") or "none")
    if kind == "kit":
        return "Drum kit · " + spaced(track.get("kit") or "synth")
    if kind == "kitSfz":
        return "Drum kit · " + spaced(track.get("kitSfz") or "no file")
    if kind == "model":
        m = track.get("model") or ""
        return f"{FAMILY.get(m, 'Instrument')} · {spaced(m).lower()}"
    if kind == "synth":
        return "Synth · " + str(track.get("synth") or "saw")
    if kind == "plugin":
        return "Plug-in · " + ((track.get("plugin") or {}).get("name") or "none chosen")
    if kind == "voice":
        return "Voice · " + spaced(track.get("voice") or "ryan")
    return spaced(kind)


def evaluate(doc, layout_rows: list[dict], track: dict, more_open: bool) -> list[dict]:
    return rows.evaluate(layout_rows, track, doc.kind.facts(track, doc), more_open)
