"""An operation's parameters: type, range, help, and the facts screens are built from (group, importance,
valid_when). One description feeds argument checking, the MCP schema, the inspector and the command bar.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import colours
from .errors import RostrumError, codes, did_you_mean

IMPORTANCE = ("primary", "secondary", "deep")
SHOWN = ("", "script", "changed")
TYPES = ("number", "toggle", "choice", "text", "color", "id", "points", "time", "list")
TIME_UNITS = ("seconds", "beats", "marker")     # a time value is {"seconds": 1.5}, {"beats": 4} or {"marker": "drop"}
HEX = colours.HEX6                             # how a colour is stored (colours.read takes the forms people write)
_LOOSE = re.compile(r"[\s_\-]+")
_WORD_BREAK = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|[_\-]+")


def plain_words(value) -> str:
    """A choice value in plain words for screens: "warmPad" -> "Warm pad", "built_in" -> "Built in"."""
    words = [w for w in _WORD_BREAK.split(str(value)) if w]
    words = [w if w.isupper() and len(w) > 1 else w.lower() for w in words]   # keep "LFO", "HDR"
    text = " ".join(words)
    return text[:1].upper() + text[1:]
_UNSET = object()


@dataclass
class Param:
    name: str
    type: str
    label: str = ""
    group: str = ""
    importance: str = "primary"
    valid_when: dict | None = None
    help: str = ""
    default: object = None
    required: bool = False
    min: float | None = None
    max: float | None = None
    step: float | None = None
    unit: str = ""
    display: str = ""                # for type "number": how screens show it, one way per kind (the kit's ValueKinds.js):
                                     # "percent" (1 = 100 %), "db" (a linear gain as dB), "pan" (−1..1 as L / C / R); "" = plain.
                                     # For type "color": "swatch" = the swatch alone, no hex code beside it
    integer: bool = False
    options: list = field(default_factory=list)
    labels: dict = field(default_factory=dict)   # for type "choice": value -> the words screens show (else plain_words)
    kept: list = field(default_factory=list)     # for type "choice": values old files may hold (they still open and read)
                                                 # but nothing offers or newly sets: not in `options`, pickers, schemas
    words: dict = field(default_factory=dict)    # a value that means something, in words (a number's; a pick's "")
                                                 # ({36000.0: "End of comp"}): screens show the words, not the number
    kind: str | None = None          # for type "id": the item kind it must point at
    item: str | None = None          # for type "list": the type of each element (min/max/integer/options/kind then apply per element)
    min_items: int = 0
    markers: bool = False            # for type "number" (a time): may also be a shared marker reference, "#drop+0.2"
                                     # (marker_times.py reads it; the app turns it into seconds where it plays)
    max_items: int | None = None
    nullable: bool = False           # null is a value too (it means "remove": e.g. key.path_handles' out / in)
    control: str = ""                # the screen control when the type alone doesn't say which: "curve" for a text of
                                     # "x,y x,y …" points from 0 to 1 (the kit's CurveField); "pick" for a text naming one
                                     # other item ("" = none; the screen offers the app's choices); "" = the type's own
                                     # (a curve's max = the top of its y range; above 1 it is a multiplier, 1 = unchanged);
                                     # "file" / "folder" for a text holding a path (the field gets a Browse button that
                                     # opens the system's file or folder dialog)
    filters: list = field(default_factory=list)   # for control "file": what the dialog lists, ["SFZ instruments (*.sfz)"]
    shown: str = ""                  # where screens show it: "" = its settings row while valid; "script" = never on a
                                     # screen (raw data agents and scripts write: a path's SVG text, font axis tags; people
                                     # edit it another way or not at all); "changed" = its row shows only while it is away
                                     # from its default (set by a canvas drag or an agent: a layer's uneven stretch)
    on: object = None                # the value a screen's "+ group" sets to turn this param's group on, when it is a number
                                     # whose `words` call its default "Off" (motion blur's 180°); a toggle's is True

    def __post_init__(self):
        if self.type not in TYPES:
            raise ValueError(f"param {self.name}: type {self.type!r} not one of {TYPES}")
        if self.importance not in IMPORTANCE:
            raise ValueError(f"param {self.name}: importance {self.importance!r} not one of {IMPORTANCE}")
        if self.shown not in SHOWN:
            raise ValueError(f"param {self.name}: shown {self.shown!r} not one of {SHOWN}")
        if self.type == "choice" and not self.options:
            raise ValueError(f"param {self.name}: a choice needs options")
        if self.type == "list" and (self.item not in TYPES or self.item in ("list", "points")):
            raise ValueError(f"param {self.name}: a list needs an item type, one of {[t for t in TYPES if t not in ('list', 'points')]}")
        if self.type == "time" and self.default is None:
            self.default = {"seconds": 0}
        self.label = self.label or self.name.replace("_", " ").capitalize()
        unknown = [v for v in self.labels if v not in self.options and v not in self.kept]
        if unknown:
            raise ValueError(f"param {self.name}: labels for {unknown} which are not options")

    def option_label(self, value) -> str:
        return self.labels.get(value) or plain_words(value)

    def choices(self) -> list[dict]:
        """[{value, label}] of a choice (or a list of choices), in order: what screens show."""
        return [{"value": o, "label": self.option_label(o)} for o in self.options]

    # constructors, one per type
    @classmethod
    def number(cls, name, **kw): return cls(name, "number", **kw)
    @classmethod
    def toggle(cls, name, **kw): return cls(name, "toggle", **kw)
    @classmethod
    def choice(cls, name, options, **kw): return cls(name, "choice", options=list(options), **kw)   # labels={value: words}
    @classmethod
    def text(cls, name, **kw): return cls(name, "text", **kw)
    @classmethod
    def color(cls, name, **kw): return cls(name, "color", **kw)
    @classmethod
    def id(cls, name, kind=None, **kw): return cls(name, "id", kind=kind, **kw)
    @classmethod
    def points(cls, name, **kw): return cls(name, "points", **kw)   # [[x, y, extra…], …]: min/max = values per point

    @classmethod
    def time(cls, name, **kw): return cls(name, "time", **kw)       # {"seconds": s} | {"beats": b} | {"marker": "name"}; min/max bound seconds/beats
    @classmethod
    def list(cls, name, item, **kw): return cls(name, "list", item=item, **kw)   # [value, …] of one item type, each checked

    def _element(self, n) -> "Param":
        """The param each list element is checked against."""
        return Param(f"{self.name}[{n}]", self.item, min=self.min, max=self.max, integer=self.integer,
                     options=self.options, kind=self.kind, unit=self.unit)

    def check(self, value, where: str):
        """The value, checked (and an integer number made an int). Out of range is an error, never a clamp. A `kept`
        choice is refused here too (nothing newly sets it); only a stored value may hold it (DocKind.bad_values)."""
        def bad(problem, accepted=(), hint=None):
            raise RostrumError(codes.BAD_ARGUMENT, where, f"{self.name}={value!r}", problem, accepted, hint)
        if value is None and self.nullable:
            return None
        t = self.type
        if t == "number":
            if self.markers and isinstance(value, str):
                from .marker_times import FORMS, REF
                if not REF.match(value):
                    bad("is not seconds or a marker reference", ["seconds (1.5)", *FORMS],
                        f'A marker is written with #: "#{value}"' if REF.match(f"#{value}") else None)
                return value
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                bad("is not a number", hint="Seconds only, written as a plain number (2.5)." if self.unit == "s" else None)
            if self.integer and value != int(value):
                bad("must be a whole number")
            if (self.min is not None and value < self.min) or (self.max is not None and value > self.max):
                pct = self.display == "percent"
                bad("is out of range", [f"{self.min:g} to {self.max:g}{self.unit}" + (" (1 = 100 %)" if pct else "")],
                    f"Write {value / 100:g} for {value:g} %" if pct and self.max is not None and value <= self.max * 100 else None)
            return int(value) if self.integer else value
        if t == "toggle":
            if not isinstance(value, bool):
                bad("must be true or false", ["true", "false"])
        elif t == "choice":
            if value not in self.options:
                same = self._same_choice(value)
                if same is None:
                    bad("is not one of the choices" + (" (no longer offered)" if value in self.kept else ""),
                        self.options, did_you_mean(value, self.options))
                value = same
            return self.options[self.options.index(value)]   # the option itself (a screen's 48000.0 is 48000)
        elif t == "color":
            if (c := colours.read(value)) is None:
                bad("is not a colour", colours.FORMS, colours.hint(value))
            return c
        elif t == "points":
            return self._check_points(value, bad)
        elif t == "time":
            return self._check_time(value, bad)
        elif t == "list":
            if not isinstance(value, (list, tuple)):
                bad("must be a list", ["[value, …]"])
            if len(value) < self.min_items or (self.max_items is not None and len(value) > self.max_items):
                bad(f"has {len(value)} values", [f"{self.min_items} to {self.max_items if self.max_items is not None else 'any number of'} values"])
            return [self._element(n).check(v, where) for n, v in enumerate(value)]
        elif t in ("text", "id"):
            if not isinstance(value, str) or (t == "id" and not value):
                bad("must be text" if t == "text" else "must be an id")
        return value

    def _same_choice(self, value):
        """The one option `value` names when written another common way ("ease-out" / "EaseOut" for easeOut, 3 for
        "3"), else None. Two options that read the same that way are ambiguous: None, so the caller refuses."""
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            same = [o for o in self.options if isinstance(o, str) and o == f"{value:g}"]
        elif isinstance(value, str):
            key = _LOOSE.sub("", value).lower()
            same = [o for o in self.options if isinstance(o, str) and _LOOSE.sub("", o).lower() == key]
        else:
            same = []
        return same[0] if len(same) == 1 else None

    def _check_time(self, value, bad):
        """A time: exactly one of seconds / beats (a number, within min and max) or marker (a marker name)."""
        accepted = ['{"seconds": 1.5}', '{"beats": 4}', '{"marker": "drop"}']
        if not isinstance(value, dict) or len(value) != 1 or next(iter(value)) not in TIME_UNITS:
            bad("is not a time", accepted, did_you_mean(next(iter(value), ""), TIME_UNITS) if isinstance(value, dict) else None)
        (unit, v), = value.items()
        if unit == "marker":
            if not isinstance(v, str) or not v:
                bad("marker must be a marker name", ['{"marker": "drop"}'])
            return {"marker": v}
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or v < 0:
            bad(f"{unit} must be a number, 0 or more", accepted)
        if unit == "seconds" and ((self.min is not None and v < self.min) or (self.max is not None and v > self.max)):
            bad("is out of range", [f"{self.min} to {self.max} seconds"])
        return {unit: v}

    def _check_points(self, value, bad):
        """A list of points, each [x, y, extra…] with between min and max numbers (default 2 to 4); kept as floats."""
        lo, hi = int(self.min if self.min is not None else 2), int(self.max if self.max is not None else 4)
        if not isinstance(value, (list, tuple)) or not value:
            bad("must be a list of points", ["[[x, y], …]"])
        out = []
        for n, q in enumerate(value):
            if (not isinstance(q, (list, tuple)) or not lo <= len(q) <= hi
                    or any(isinstance(v, bool) or not isinstance(v, (int, float)) or v != v for v in q)):
                bad(f"point {n} is not {lo} to {hi} numbers", ["[x, y]" if lo == 2 else f"{lo} numbers"])
            out.append([float(v) for v in q])
        return out

    def json_schema(self) -> dict:
        s = {"number": {"type": "integer" if self.integer else "number"}, "toggle": {"type": "boolean"},
             "choice": {"enum": list(self.options)}, "text": {"type": "string"},
             "color": {"type": "string", "pattern": colours.SCHEMA}, "id": {"type": "string"},
             "time": {"type": "object", "minProperties": 1, "maxProperties": 1, "properties": {
                 "seconds": {"type": "number", "minimum": 0}, "beats": {"type": "number", "minimum": 0},
                 "marker": {"type": "string", "minLength": 1}}, "additionalProperties": False},
             "list": {"type": "array", "minItems": self.min_items, **({"maxItems": self.max_items} if self.max_items is not None else {}),
                      "items": self._element(0).json_schema() if self.type == "list" else {}},
             "points": {"type": "array", "minItems": 1, "items": {"type": "array", "items": {"type": "number"},
                        "minItems": int(self.min or 2), "maxItems": int(self.max or 4)}}}[self.type]
        if self.type == "number" and self.min is not None:
            s["minimum"] = self.min
        if self.type == "number" and self.max is not None:
            s["maximum"] = self.max
        if self.type == "number" and self.markers:
            from .marker_times import REF
            s = {"anyOf": [s, {"type": "string", "pattern": REF.pattern}]}
        if self.nullable:
            s = {"anyOf": [s, {"type": "null"}]}
        desc = self.help or self.label
        if self.markers:
            desc += ' (seconds, or a shared marker: "#drop", "#drop+0.2", "#hush-0.5")'
        if self.words:
            desc += " (" + ", ".join(f"{v:g} = {w}" if isinstance(v, (int, float)) else f'"{v}" = {w}' for v, w in self.words.items()) + ")"
        if self.valid_when:
            from .conditions import describe
            desc += f" (only when {describe(self.valid_when)})"
        s["description"] = desc
        return s

    def to_dict(self) -> dict:
        d = {"name": self.name, "type": self.type, "label": self.label, "group": self.group,
             "importance": self.importance, "valid_when": self.valid_when, "help": self.help,
             "default": self.default, "required": self.required}
        if self.type == "list":
            d.update(item=self.item, min_items=self.min_items, max_items=self.max_items, min=self.min, max=self.max,
                     integer=self.integer, options=list(self.options), kind=self.kind)
        if self.type == "number":
            d.update(min=self.min, max=self.max, step=self.step, unit=self.unit, integer=self.integer, markers=self.markers)
            if self.words:
                d["words"] = {str(v): w for v, w in self.words.items()}
        if self.type == "time":
            d.update(min=self.min, max=self.max)
        if self.type == "choice":
            d["options"] = list(self.options)
            d["option_labels"] = [self.option_label(o) for o in self.options]
        if self.type == "id":
            d["kind"] = self.kind
        return d
