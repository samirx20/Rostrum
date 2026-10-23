"""The song's music map: tempo changes, time signature changes, key changes and sections (named stretches: intro, verse, drop).
Fields, defaults and must-haves, merged into `fields.py`."""
from __future__ import annotations

from rostrum_core import Param

from . import keys
from . import markers
from . import values as V


def _tempo_time(p, v, where):
    """Seconds or {"beat": n}: a tempo change can't sit on a marker (`tempo.py`)."""
    if markers.ref(v) is not None:
        V._bad(p, v, where, "can't be a marker: a tempo change sits at seconds or a beat", ["2.5", '{"beat": 32}'])
    return V._time(p, v, where)


def _key(p, v, where):
    if keys.parse(v) is None:
        V._bad(p, v, where, "is not a key", keys.FORMS)
    return v


def _name(p, v, where):
    if not (isinstance(v, str) and V.NAME.match(v)):
        V._bad(p, v, where, "is not a name (1–64 letters, digits, _ . -)", ['"intro"', '"verse_2"', '"drop"'])
    return v


TEMPO_AT = V.Value("at", "number", rule=_tempo_time, schema={"anyOf": V.TIME_SCHEMA["anyOf"][:2]}, unit="s",
                   step=0.01, form="time", group="Tempo", help='Where the new tempo starts: {"beat": 32} (stays on its beat) or '
                   "seconds (stays at that moment).")
FIELDS = {
    "tempo": [V.N("bpm", 20, 400, "Tempo", "bpm", help="The tempo from here to the next change."), TEMPO_AT],
    "meter": [V.N("beatsPerBar", 1, 16, "Time signature", integer=True, label="Beats per bar",
                  help="Beats in each bar from here to the next change (3: 3/4, 6: 6/8 counted in eighths)."),
              V.Value("at", "number", rule=_tempo_time, schema={"anyOf": V.TIME_SCHEMA["anyOf"][:2]}, unit="s", step=0.01,
                      form="time", group="Time signature", help='Where it starts, a new bar: {"beat": 32} or seconds.')],
    "key": [V.Value("key", "text", rule=_key, schema={"type": "string"}, group="Key",
                    help='"D minor", "F# major", "Bb dorian": from here to the next key change.'),
            V.time("at", group="Key")],
    "section": [V.Value("name", "text", rule=_name, schema={"type": "string", "pattern": V.NAME.pattern},
                        group="Section", help='"intro", "verse", "drop" …'),
                V.time("at", group="Section", help="Where it starts."),
                V.time("end", group="Section", help="Where it ends (the next part starts here).")],
}
DEFAULTS = {"tempo": {}, "meter": {}, "key": {}, "section": {}}
REQUIRED = {"tempo": ["bpm", "at"], "meter": ["beatsPerBar", "at"], "key": ["key", "at"], "section": ["name", "at", "end"]}
