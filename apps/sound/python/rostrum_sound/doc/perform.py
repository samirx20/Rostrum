"""The track's `perform` field: how a person would play the part (GAP.md § 2, engine contract § Perform).

Absent or true = the instrument family's defaults (a little timing feel, velocity variety, accents, legato on sustained
instruments, vibrato on held notes, strum); an object changes some of them over those defaults; false plays every note
exactly as written. The engine applies it where it turns notes and hits into voices (so render, playback and every app hear
the same, seeded by the track so a re-render is identical); the compiler passes the field only when the document holds
it. On the screen it is the one toggle "Played like a person" (on while the field is absent).
"""
from __future__ import annotations

from rostrum_core import Param

from . import values as V

ARTICULATIONS = ["legato", "staccato", "normal"]
FIELDS = [
    Param.number("seed", help="Any number: a different, still repeatable, performance."),
    Param.number("timing", min=0, max=100, unit="ms", help="Each note lands up to this many ms off the grid."),
    Param.number("lean", min=-200, max=200, unit="ms", help="The whole part laid back (+, behind the beat) or pushed (−)."),
    Param.number("swing", min=0, max=1, help="The off-beat 8ths (or 16ths, swingGrid 0.25) come late; 1 is a triplet feel."),
    Param.number("swingGrid", min=0.0625, max=1, help="The beat fraction that swings: 0.5 = 8ths (default), 0.25 = 16ths."),
    Param.number("velocity", min=0, max=1, help="Each note's velocity varies by up to this fraction of itself."),
    V.curve("dynamics", (0, None), (0, 4), help="Dynamics across the part: [[seconds, factor], …] multiplies velocity (a crescendo is [[0, 0.6], [4, 1.1]])."),
    Param.number("accent", min=0, max=0.3, help="Notes on a bar's downbeat this much louder, the other beats half of it."),
    Param.choice("articulation", ARTICULATIONS, help="Every note: legato holds each into the next (a bowed line slurs), staccato shortens; a note's own art wins."),
    V.record("vibrato", [Param.number("rateHz", min=0.1, max=20, required=True), Param.number("depthCents", min=0, max=200, required=True),
                         Param.number("delaySec", min=0, max=5)], "vibrato", help='Vibrato on held notes that have none: {"rateHz": 5.5, "depthCents": 25}.'),
    Param.number("strum", min=0, max=1, help="Strum spacing varies this much string to string, each string a little softer."),
]
BY = {p.name: p for p in FIELDS}
PERMITTED = {"anyOf": [{"type": "boolean"}, {"type": "object", "properties": {p.name: p.json_schema() for p in FIELDS}}]}


def _rule(p, v, where):
    if isinstance(v, bool):
        return v
    if not isinstance(v, dict):
        V._bad(p, v, where, "must be true, false or an object of changes", [f"{{{', '.join(BY)}}}"])
    out = {}
    for k, x in v.items():
        if k not in BY:
            V._bad(p, v, where, f'has no field "{k}"', list(BY))
        out[k] = False if (k == "vibrato" and x is False) else BY[k].check(x, f"{where} › perform.{k}")
    return out


def perform(**kw) -> V.Value:
    """The track's field: a toggle on screen (true while the field is absent), an object for scripts and agents."""
    return V.Value("perform", "toggle", rule=_rule, schema=PERMITTED, default=True, label="Played like a person",
                   help="On (also when the field is absent): the part is played like a person would, in the instrument family's way. "
                        "An object changes some values (timing, lean, swing, velocity, accent, strum, articulation, vibrato, seed, dynamics); "
                        "false plays every note exactly as written.", **kw)
