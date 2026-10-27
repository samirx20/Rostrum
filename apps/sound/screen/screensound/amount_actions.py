"""Sound's actions with amounts (the kit's amounts popover, rostrum_gui/amounts.py): their calls from the amounts a
person set, and each one's say on its rows (`fit`: what applies now, ranges, pickers, starting values). The rows
themselves come from the operations' own parameters. No Qt.

    Quantise ▾   Grid (picker), Strength, Swing; More: Snap the ends too (notes)
    Humanise ▾   Timing, Velocity, Length (notes); Another take; More: Seed
    Transpose ▾ › By…    Semitones (−24 … +24), or with "Along the key" (only when the song has a key) Steps (−14 … +14)
    Repeat…      Times (2 … 64) and Until (Just N times · End of <section> · End of the range · Next marker <name>)
    Fill row…    Every (grid steps), Starting on (step), Velocity; More: Accent every (steps)  (a drum row's menu; hit.fill)
    Start a bar here…    Bar
"""
from __future__ import annotations

from rostrum_core import Param
from rostrum_sound.doc import keys, markers, musical
from rostrum_sound.doc import select_time as ST

from . import action_calls as C
from . import drum_steps as D
from .action_calls import TIMED

GRIDS = [(1.0, "1/4"), (0.5, "1/8"), (0.25, "1/16"), (0.125, "1/32"), (2.0, "1/2"), (1 / 3, "1/8 triplet"),
         (1 / 6, "1/16 triplet")]
ALONG = Param.toggle("along", label="Along the key", help="Move by steps of the song's key, so the notes stay in it.")
UNTIL = Param.choice("until", ["times"], label="Until", help="Copy until a point instead of a number of times.")
NOTE_HIT = ("note", "hit")


def _args(f, op, amounts) -> dict:
    """The amounts this operation takes (Length is notes only, Snap the ends too notes only)."""
    names = {p.name for p in f.doc.kind.registry.get(op).params}
    return {k: v for k, v in amounts.items() if k in names}


def on(kinds, op):
    """(valid, calls(f, amounts)) of an action on the selected items of `kinds`: one call per kind."""
    return (lambda f: bool(f.by_kind(kinds)),
            lambda f, a=None: [C.call(f"{k}.{op}", ids, **_args(f, f"{k}.{op}", a or {}))
                               for k, ids in f.by_kind(kinds).items()])         # no amounts: the defaults


def quantize_fit(f, a):
    return {"grid": {"type": "choice", "options": [{"value": v, "label": w} for v, w in GRIDS]}}


# ---- Transpose › By… -------------------------------------------------------------------------------------------
def has_key(f) -> bool:
    return bool(keys.key_for(f.doc.data, 0.0))


def transpose_calls(f, a):
    notes = f.by_kind(("note",)).get("note", [])
    if a.get("along") and has_key(f):
        return [C.call("note.transpose", notes, steps=int(a.get("steps", 2)))]
    return [C.call("note.transpose", notes, semitones=int(a.get("semitones", 7)))]


def transpose_fit(f, a):
    along = bool(a.get("along")) and has_key(f)
    return {"along": {"valid": has_key(f)},
            "semitones": {"valid": not along, "min": -24, "max": 24, "default": 7},
            "steps": {"valid": along, "default": 2}}


# ---- Repeat… -----------------------------------------------------------------------------------------------------
def repeat_valid(f) -> bool:
    """Notes, hits or clips selected, or one section (and no newer time range)."""
    return not f.on_range and bool(f.count) and (f.kinds <= set(TIMED) or f.one == "section")


def repeat_range_valid(f) -> bool:
    return f.on_range and bool(C.inside(f))


def range_words(f) -> str:
    """The time range in bars when it is whole bars ("bar 5–6", "bar 5"), else "time range 5.1–9.3"."""
    at = [musical.position(t, f.doc.data).split(".") for t in f.range]
    if all(p[1:2] == ["1"] and all(set(x) <= {"0"} for x in p[2:]) for p in at):
        a, b = int(at[0][0]), int(at[1][0]) - 1
        return f"bar {a}" if b <= a else f"bar {a}–{b}"
    return f"time range {'.'.join(at[0][:2])}–{'.'.join(at[1][:2])}"


def _end(f) -> float:
    if f.on_range:
        return f.range[1]
    return f.once("end", lambda f: max(ST.end_of(f.doc.data, it) for it in f.items))     # (asked twice a pick)


def _section_at(f, t):
    root = f.doc.data
    for s in root.get("sections", []):
        if ST.start_of(root, s) <= t - 1e-6 <= ST.start_of(root, {**s, "at": s["end"]}) - 1e-6:
            return s
    return None


def until_options(f, times) -> list[dict]:
    """Just N times · End of <section> (the section the selection ends in) · End of the range (items picked under a
    time range that goes on past them; repeating the range itself up to its own end would copy nothing) · Next marker
    <name>."""
    out = [{"value": "times", "label": f"Just {int(times)} times"}]
    if f.one == "section":                     # a section's copies make their own room: what follows moves, no end to fill to
        return out
    t = _end(f)
    sec = _section_at(f, t)
    if sec:
        out.append({"value": "section:" + sec["name"], "label": f"End of {sec['name']}"})
    if f.range and not f.on_range and f.range[1] > t + 1e-6:     # notes picked inside an older range: fill it up
        out.append({"value": "range", "label": "End of the range"})
    nxt = next((n for n, at in markers.all(f.doc.data) if at > t + 1e-6), None)
    if nxt:
        out.append({"value": "#" + nxt, "label": f"Next marker {nxt}"})
    return out


def _until(f, until):
    if until.startswith("section:"):
        return {"section": until[8:]}
    return round(f.range[1], 4) if until == "range" else until


def repeat_calls(f, a):
    until = a.get("until", "times")
    args = {"times": int(a.get("times", 4))} if until == "times" else {"until": _until(f, until)}
    return C.range_duplicate(f, **args) if f.on_range else C.duplicate(f, **args)


def repeat_fit(f, a):
    times, until = a.get("times", 4), a.get("until", "times")
    return {"times": {"importance": "primary", "min": 2, "default": 4, "unit": "times", "valid": until == "times"},
            "until": {"options": until_options(f, times), "said": until != "times"}}


# ---- Fill row… (a drum row's menu: hit.fill) ---------------------------------------------------------------------
def fill_calls(f, a):
    """The amounts count the window's grid steps (`x["step"]`: one step in beats, set when the row's menu asked); hit.fill
    itself takes beats. Starting on counts from step 1 (the first step of the range)."""
    x = f.fill
    step = x.get("step", 0.25)
    return [D.fill_call(f.doc, x["track"], x["drum"], x["from"], x["to"], every=a.get("every", 1) * step,
                        offset=(a.get("offset", 1) - 1) * step, vel=a.get("vel", 0.85),
                        accentEvery=(a.get("accentEvery") or 0) * step)]


def fill_fit(f, a):
    steps = {"min": 1, "max": 64, "step": 1}
    return {"every": {"importance": "primary", "label": "Every (grid steps)", "default": 1, **steps},
            "offset": {"importance": "primary", "label": "Starting on (step)", "default": 1, **steps},
            "vel": {"importance": "primary"},
            "accentEvery": {"importance": "secondary", "label": "Accent every (steps)", "min": 0, "max": 64, "step": 1}}


# ---- Start a bar here… -----------------------------------------------------------------------------------------
def fit_bar_calls(f, a):
    return C.fit_bar(f, a.get("bar"))


def fit_bar_fit(f, a):
    near = C.bar_near(f)
    return {"bar": {"default": near, "fresh": True, "said": f"bar {int(a.get('bar', near))}"}}
