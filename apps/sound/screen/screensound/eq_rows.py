"""An EQ's bands as plain controls on the screen (no Qt). The document keeps one `bands` list ([{shape, freq, gain, q}]:
what agents write); a person sees "Bands" (how many) and, per band, Type, Frequency, Gain and Width. Gain is there only
for the shapes that boost or cut (peak, shelves): the band's own facts decide, like every other row. A band whose
value is an automation envelope shows no number for it (its lane moves it). Every edit rewrites the whole list
through `effect.set` (one history step). Called from inspect.py, like pitch_merge.py."""
from __future__ import annotations

from rostrum_core import Param
from rostrum_gui.rows import _param_row

from rostrum_sound import names
from rostrum_sound.doc import effects, values as V

MOST = 8
GAINS = ("peak", "lowshelf", "highshelf")            # the shapes that boost or cut
SHAPE_WORDS = {"lowshelf": "Low shelf", "highshelf": "High shelf", "peak": "Bell", "lowpass": "Cut highs", "highpass": "Cut lows",
               "notch": "Notch"}
FIELDS = {"shape": "Type", "freq": "Frequency", "gain": "Gain", "q": "Width"}
HELP = {"shape": "Bell lifts or dips around one frequency; shelves lift or dip everything above or below it; Cut highs / Cut lows "
                 "remove what is above / below it; Notch removes a narrow slice.",
        "freq": "Where the band works.", "gain": "How much it lifts (+) or dips (−) there.",
        "q": "How narrow the band is: higher is narrower."}
COUNT = "Bands"
UNSET = {"gain": 0, "q": 0.707}                     # what the engine plays for a field a band leaves out (contract/names.rs)
_PARAMS = {
    "shape": Param.choice("shape", names.EQ_SHAPES, labels=SHAPE_WORDS, label="Type", group="Effect", help=HELP["shape"]),
    "freq": V.N("freq", 20, 24000, "Effect", "Hz", label="Frequency", help=HELP["freq"]),
    "gain": V.N("gain", -36, 36, "Effect", "dB", label="Gain", help=HELP["gain"]),
    "q": V.N("q", 0.1, 30, "Effect", label="Width", help=HELP["q"]),
}


def is_eq(item: dict) -> bool:
    return item.get("type") == "effect" and item.get("effect") == "eq"


def _id(n: int, field: str) -> str:
    return f"Band {n} {FIELDS[field].lower()}"          # its id is its words: the history says "Change Band 2 frequency"


def _row(base: dict, p: Param, rid: str, value, ok: bool) -> dict:
    """A param row like the raw Bands row (same group, importance, folding), for one band's value."""
    return {**base, **_param_row(p), "id": rid, "value": value, "anim": "", "expr": "", "holds": ok, "valid": ok, "valid_when": {}}


def band_rows(item: dict, rows: list[dict]) -> list[dict]:
    """The effect's rows with the raw Bands list replaced by the count and each band's controls."""
    at = next((i for i, r in enumerate(rows) if r["id"] == "bands" and r["row"] == "param"), None)
    if not is_eq(item) or at is None:
        return rows
    base, bands, more = rows[at], item.get("bands") or [], []
    count = Param.number(COUNT, min=1, max=MOST, step=1, integer=True, label=COUNT, group="Effect",
                         help="How many bands this EQ has; a new band starts flat.")
    more.append(_row(base, count, COUNT, len(bands), base["valid"]))
    for n, b in enumerate(bands, 1):
        if len(bands) > 1:
            ids = [_id(n, f) for f in FIELDS]
            more.append({"row": "group", "id": f"group:Band {n}", "label": f"Band {n}", "members": ids, "value": None, "anim": "",
                         "expr": "", "holds": base["valid"], "valid": base["valid"]})
        for f in FIELDS:
            v = b.get(f, UNSET.get(f))                   # a band that leaves Width out plays 0.707: show that, never 0
            plain = not isinstance(v, list)                # an envelope: a lane moves it, no number here
            ok = base["valid"] and plain and (f != "gain" or b.get("shape") in GAINS)
            more.append(_row(base, _PARAMS[f], _id(n, f), v if plain else None, ok))
    return rows[:at] + more + rows[at + 1:]


def edit_args(item: dict, param: str, value) -> dict | None:
    """The new `bands` list an edit of one of these rows writes ({"bands": [...]}), or None for another row."""
    if not is_eq(item):
        return None
    bands = [dict(b) for b in item.get("bands") or []]
    if param == COUNT:
        n = max(1, min(MOST, int(round(value))))
        while len(bands) > n:
            bands.pop()
        while len(bands) < n:
            bands.append({"shape": "peak", "freq": _spread(len(bands)), "gain": 0, "q": 1})
        return {"bands": bands}
    for n, b in enumerate(bands, 1):
        for f in FIELDS:
            if param == _id(n, f):
                b[f] = value if f == "shape" else round(float(value), 4)
                return {"bands": bands}
    return None


def _spread(n: int) -> float:
    """Where the next new band sits: 1 kHz, then spread across the range so bands do not start stacked."""
    return [1000, 100, 8000, 400, 3000, 60, 12000, 200][n % MOST]
