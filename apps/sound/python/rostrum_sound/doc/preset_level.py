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

TABLE = Path(__file__).resolve().parents[1] / "library_data" / "preset_levels.json"
FORMS = ("builtIn", "model", "synth", "kit")        # the instrument forms whose value names a preset


@cache
def presets() -> dict:
    return json.loads(TABLE.read_text(encoding="utf-8"))["presets"] if TABLE.exists() else {}


def gain(track: dict) -> float:
    form = track.get("instrument", "none")
    return presets().get(f"{form}:{track.get(form)}", {}).get("gain", 1.0) if form in FORMS else 1.0


def scaled(points, g: float, cap: float | None = None) -> list:
    return [[t, round(v * g if cap is None else min(cap, v * g), 6)] for t, v in points]
