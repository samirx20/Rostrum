"""An operation's parameters: type, range, help, and the facts screens are built from (group, importance,
valid_when). One description feeds argument checking, the MCP schema, the inspector and the command bar.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import colours
from .param_check import TIME_UNITS, CheckMixin  # noqa: F401  (TIME_UNITS: one import for apps)
from .param_schema import SchemaMixin

IMPORTANCE = ("primary", "secondary", "deep")
SHOWN = ("", "script", "changed")
TYPES = ("number", "toggle", "choice", "text", "color", "id", "points", "time", "list")
HEX = colours.HEX6                             # how a colour is stored (colours.read takes the forms people write)
_WORD_BREAK = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|[_\-]+")


def plain_words(value) -> str:
    """A choice value in plain words for screens: "warmPad" -> "Warm pad", "built_in" -> "Built in"."""
    words = [w for w in _WORD_BREAK.split(str(value)) if w]
    words = [w if w.isupper() and len(w) > 1 else w.lower() for w in words]   # keep "LFO", "HDR"
    text = " ".join(words)
    return text[:1].upper() + text[1:]


_UNSET = object()


@dataclass
class Param(CheckMixin, SchemaMixin):
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
