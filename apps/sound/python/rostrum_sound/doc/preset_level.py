"""Level matching: every built-in instrument, played instrument, synth wave and kit has a measured gain, so equal
track volumes sound balanced (a piano used to come out 10 dB under the drums at the same fader).

    preset_level.gain(track)          # the gain the compiler puts under the track's own volume (1 for a sampled,
                                      #   plug-in or recorded track: their level is the file's)
    preset_level.scaled(points, g)    # an automation lane's [[time, value], …] with every value times g (at most `cap`)

The table is `library_data/preset_levels.json`, made by `devtools/level_match.py` (equal integrated loudness for one
reference phrase per preset). It is part of the file format: songs saved before it hold their volumes offset by it
(doc/migrations.py), so a changed number needs a new format step, never just a new table.
"""
from __future__ import annotations

import json
from functools import cache
from pathlib import Path

from .. import names

DATA = Path(__file__).resolve().parents[1] / "library_data"
TABLE = DATA / "preset_levels.json"
FORMAT2 = DATA / "preset_levels_format2.json"      # the table songs of file format 2 were offset by (frozen: doc/migrations.py)
FORMS = ("builtIn", "model", "synth", "kit")        # the instrument forms whose value names a preset


@cache
def presets(table: Path = TABLE) -> dict:
    return json.loads(table.read_text(encoding="utf-8"))["presets"] if table.exists() else {}


def gain(track: dict, table: Path = TABLE) -> float:
    form = track.get("instrument", "none")
    name = track.get(form)
    if form == "builtIn":
        name = names.BUILT_IN_ALIASES.get(name, name)        # a name that plays the same sound shares its gain
    return presets(table).get(f"{form}:{name}", {}).get("gain", 1.0) if form in FORMS else 1.0


def scaled(points, g: float, cap: float | None = None) -> list:
    return [[t, round(v * g if cap is None else min(cap, v * g), 6)] for t, v in points]
