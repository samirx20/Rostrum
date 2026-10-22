"""Sound values the shared parameter types don't cover: times, lengths, pitches, drums, envelopes and lists.

Each is a `rostrum_core.Param` with its own `check` and schema, so operations, the script merge and the MCP
schema treat them like any other parameter. (A shared "time" / "list" type would make these smaller; asked
of Team Sam.) Out of range is an error, never a clamp.
"""
from __future__ import annotations

import math

import re
from dataclasses import dataclass
from typing import Callable

from rostrum_core import Param, RostrumError, codes

from . import markers, times

NOTE = re.compile(r"^[A-Ga-g](#|b)?-?\d$")
TIME_SCHEMA = {"anyOf": [{"type": "number", "minimum": 0},
                         {"type": "object", "properties": {"beat": {"type": "number", "minimum": 0}}},
                         {"type": "string", "pattern": markers.REF.pattern}]}
LENGTH_SCHEMA = {"anyOf": [{"type": "number", "minimum": 0},
                           {"type": "object", "properties": {"beats": {"type": "number", "minimum": 0}}}]}
TIED_SCHEMA = {"anyOf": [*LENGTH_SCHEMA["anyOf"], {"type": "object", "properties": {"to": TIME_SCHEMA}, "required": ["to"]},
                         {"const": "next"}]}
PITCH_ONE = {"anyOf": [{"type": "string", "pattern": NOTE.pattern}, {"type": "integer", "minimum": 0,
                                                                    "maximum": 127}]}


def _bad(p, value, where, problem, accepted=()):
    raise RostrumError(codes.BAD_ARGUMENT, where, f"{p.name}={value!r}", problem, accepted)


def _described(p, schema):
    schema = dict(schema)
    base = Param.json_schema(p)
    schema["description"] = base["description"]
    return schema


@dataclass
class Value(Param):
    """A Param with its own checker `rule(param, value, where) -> value` and JSON schema. `form` is "time" or
    "length" for a field that holds one (what the screen reads in seconds and writes back in the same form)."""
    rule: Callable | None = None
    schema: dict | None = None
    form: str = ""

    def check(self, value, where):
        return self.rule(self, value, where)

    def json_schema(self):
        return _described(self, self.schema)


def _time(p, v, where, length=False, tied=False):
    why = times.problem(v, length, tied)
    if why:
        _bad(p, v, where, why, times.forms(length, tied))
    return v


def _pitch_one(p, v, where):
    if isinstance(v, bool) or not (isinstance(v, int) and 0 <= v <= 127 or isinstance(v, str) and NOTE.match(v)):
        _bad(p, v, where, "is not a note", ['"D4"', '"F#3"', '"Bb2"', "a MIDI number 0 … 127"])
    return v


def _pitch(p, v, where):
    if isinstance(v, list):
        if not v:
            _bad(p, v, where, "is an empty chord")
        return [_pitch_one(p, x, where) for x in v]
    return _pitch_one(p, v, where)


def _drum(p, v, where):
    if isinstance(v, bool) or not (isinstance(v, str) and v or isinstance(v, int) and 0 <= v <= 127):
        _bad(p, v, where, "is not a drum", ["a drum name", "a GM key number"])
    return v


def _number(p, v, where):
    return Param.check(Param.number(p.name, min=p.min, max=p.max), v, where)


def _env(p, v, where):
    """A number, or an envelope [[time, value], …] in time order."""
    if not isinstance(v, list):
        return _number(p, v, where)
    for pt in v:
        if not (isinstance(pt, (list, tuple)) and len(pt) == 2):
            _bad(p, v, where, "is not an envelope", ["a number", "[[time, value], …]"])
        _time(p, pt[0], where)
        _number(p, pt[1], where)
    return [list(pt) for pt in v]


def time(name, **kw) -> Value:
    return Value(name, "number", rule=_time, schema=TIME_SCHEMA, unit="s", step=0.01, form="time", **kw)


def length(name, tied=False, **kw) -> Value:
    """A length; `tied` (a note's) may also end on a time (`{"to": "#land"}`) or hold to the next note (`"next"`)."""
    return Value(name, "number", rule=lambda p, v, w: _time(p, v, w, True, tied),
                 schema=TIED_SCHEMA if tied else LENGTH_SCHEMA, unit="s", step=0.01, form="length", **kw)


def pitch(name, **kw) -> Value:
    return Value(name, "text", rule=_pitch, schema={"anyOf": [PITCH_ONE, {"type": "array", "items": PITCH_ONE}]},
                 **kw)


def drum(name, **kw) -> Value:
    return Value(name, "text", rule=_drum, schema={"anyOf": [{"type": "string"}, {"type": "integer"}]}, **kw)


def step(lo, hi, unit="", integer=False) -> float:
    """The one rule for how finely a number moves on screen (a scrub step, a typed value's decimals): a hundredth of
    its range's order (0 … 1 -> 0.01, 0 … 20 -> 0.1, 40 … 20000 -> 1), whole numbers 1, seconds at least 0.01."""
    if integer:
        return 1
    span = (hi - lo) if lo is not None and hi is not None else 100
    s = min(1.0, 10 ** (math.floor(math.log10(span) + 0.31) - 2)) if span > 0 else 0.01
    return min(s, 0.01) if unit == "s" else s


def N(name, lo, hi, group, unit="", imp="primary", when=None, integer=False, default=None, label="", help="", display=""):
    """A number field (the Sound document's one way to make one): range, group, importance, validity, step."""
    return Param.number(name, min=lo, max=hi, step=step(lo, hi, unit, integer), group=group, unit=unit,
                        importance=imp, valid_when=when, integer=integer, default=default, label=label, help=help,
                        display=display)     # how screens show it: "db", "pan", "percent" (the kit's ValueKinds.js)


def env(name, lo, hi, **kw) -> Value:
    """A number from lo to hi, or an envelope of such numbers over time."""
    pt = {"type": "array", "items": [TIME_SCHEMA, {"type": "number"}], "minItems": 2, "maxItems": 2}
    return Value(name, "number", rule=_env, min=lo, max=hi, step=step(lo, hi, kw.get("unit", "")), schema={"anyOf": [
        {"type": "number", "minimum": lo, "maximum": hi}, {"type": "array", "items": pt}]}, **kw)


def listof(name, item_rule: Callable, item_schema: dict, **kw) -> Value:
    """A list whose every entry passes `item_rule(param, entry, where) -> entry`."""
    def rule(p, v, where):
        if not isinstance(v, list):
            _bad(p, v, where, "must be a list")
        return [item_rule(p, x, f"{where} › {p.name}[{n}]") for n, x in enumerate(v)]
    return Value(name, "text", rule=rule, schema={"type": "array", "items": item_schema}, **kw)


def fields_of(params: list[Param], what: str):
    """An item rule for listof(): a dict whose keys are these params, checked by them (required ones present)."""
    by = {p.name: p for p in params}

    def rule(p, v, where):
        if not isinstance(v, dict):
            _bad(p, v, where, f"is not a {what}", [f"{{{', '.join(by)}}}"])
        for k in v:
            if k not in by:
                _bad(p, v, where, f'has no field "{k}"', list(by))
        for q in params:
            if q.required and q.name not in v:
                _bad(p, v, where, f'needs "{q.name}"')
        return {k: by[k].check(x, where) for k, x in v.items()}
    return rule, {"type": "object", "properties": {q.name: q.json_schema() for q in params}}


def curve(name, x: tuple, y: tuple, **kw) -> Value:
    """Points [[x, y], …] in x order, x in x = (lo, hi), y in y = (lo, hi) (hi None = no top): a note's
    dynamics (fraction of its length -> level) or bend (seconds into it -> cents)."""
    def rule(p, v, where):
        if not isinstance(v, list) or not v:
            _bad(p, v, where, "is not a list of points", ["[[x, y], …]"])
        last = None
        for pt in v:
            if not (isinstance(pt, (list, tuple)) and len(pt) == 2) or any(
                    isinstance(c, bool) or not isinstance(c, (int, float)) for c in pt):
                _bad(p, v, where, "is not a list of points", ["[[x, y], …]"])
            for c, (lo, hi), axis in ((pt[0], x, "x"), (pt[1], y, "y")):
                if c < lo or hi is not None and c > hi:
                    _bad(p, v, where, f"has {axis} {c} outside {lo} … {hi if hi is not None else '∞'}")
            if last is not None and pt[0] < last:
                _bad(p, v, where, "is not in order", ["points sorted by their first number"])
            last = pt[0]
        return [list(pt) for pt in v]
    pt = {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2}
    return Value(name, "text", rule=rule, schema={"type": "array", "items": pt, "minItems": 1}, **kw)


def record(name, params: list[Param], what: str, **kw) -> Value:
    """A small object whose fields are `params` (a note's vibrato {rate, depth, delay})."""
    rule, schema = fields_of(params, what)
    return Value(name, "text", rule=rule, schema=schema, **kw)


NAME = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")


def mapping(name, what: str, **kw) -> Value:
    """{name: text, …}: an sfz track's articulations (articulation name -> its SFZ file)."""
    def rule(p, v, where):
        if not isinstance(v, dict):
            _bad(p, v, where, f"is not a list of {what}", ['{"spiccato": "C:\\…\\spic.sfz"}'])
        for k, x in v.items():
            if not (isinstance(k, str) and NAME.match(k)) or not (isinstance(x, str) and x):
                _bad(p, v, where, f"entry {k!r}: needs a name (letters, digits, _ . -) and a file path")
        return dict(v)
    return Value(name, "text", rule=rule, schema={"type": "object", "additionalProperties": {"type": "string"}},
                 **kw)
