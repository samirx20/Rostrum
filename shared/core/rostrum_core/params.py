"""An operation's parameters: type, range, help, and the facts screens are built from (group, importance,
valid_when). One description feeds argument checking, the MCP schema, the inspector and the command bar.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .errors import RostrumError, codes, did_you_mean

IMPORTANCE = ("primary", "secondary", "deep")
TYPES = ("number", "toggle", "choice", "text", "color", "id", "points")
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
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
    integer: bool = False
    options: list = field(default_factory=list)
    kind: str | None = None          # for type "id": the item kind it must point at

    def __post_init__(self):
        if self.type not in TYPES:
            raise ValueError(f"param {self.name}: type {self.type!r} not one of {TYPES}")
        if self.importance not in IMPORTANCE:
            raise ValueError(f"param {self.name}: importance {self.importance!r} not one of {IMPORTANCE}")
        if self.type == "choice" and not self.options:
            raise ValueError(f"param {self.name}: a choice needs options")
        self.label = self.label or self.name.replace("_", " ").capitalize()

    # constructors, one per type
    @classmethod
    def number(cls, name, **kw): return cls(name, "number", **kw)
    @classmethod
    def toggle(cls, name, **kw): return cls(name, "toggle", **kw)
    @classmethod
    def choice(cls, name, options, **kw): return cls(name, "choice", options=list(options), **kw)
    @classmethod
    def text(cls, name, **kw): return cls(name, "text", **kw)
    @classmethod
    def color(cls, name, **kw): return cls(name, "color", **kw)
    @classmethod
    def id(cls, name, kind=None, **kw): return cls(name, "id", kind=kind, **kw)
    @classmethod
    def points(cls, name, **kw): return cls(name, "points", **kw)   # [[x, y, extra…], …]: min/max = values per point

    def check(self, value, where: str):
        """The value, checked (and an integer number made an int). Out of range is an error, never a clamp."""
        def bad(problem, accepted=(), hint=None):
            raise RostrumError(codes.BAD_ARGUMENT, where, f"{self.name}={value!r}", problem, accepted, hint)
        t = self.type
        if t == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                bad("is not a number")
            if self.integer and value != int(value):
                bad("must be a whole number")
            if (self.min is not None and value < self.min) or (self.max is not None and value > self.max):
                bad("is out of range", [f"{self.min} to {self.max}{self.unit}"])
            return int(value) if self.integer else value
        if t == "toggle":
            if not isinstance(value, bool):
                bad("must be true or false", ["true", "false"])
        elif t == "choice":
            if value not in self.options:
                bad("is not one of the choices", self.options, did_you_mean(value, self.options))
        elif t == "color":
            if not isinstance(value, str) or not HEX.match(value):
                bad("is not a colour", ["#rrggbb"])
        elif t == "points":
            return self._check_points(value, bad)
        elif t in ("text", "id"):
            if not isinstance(value, str) or (t == "id" and not value):
                bad("must be text" if t == "text" else "must be an id")
        return value

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
             "color": {"type": "string", "pattern": HEX.pattern}, "id": {"type": "string"},
             "points": {"type": "array", "minItems": 1, "items": {"type": "array", "items": {"type": "number"},
                        "minItems": int(self.min or 2), "maxItems": int(self.max or 4)}}}[self.type]
        if self.type == "number" and self.min is not None:
            s["minimum"] = self.min
        if self.type == "number" and self.max is not None:
            s["maximum"] = self.max
        desc = self.help or self.label
        if self.valid_when:
            from .conditions import describe
            desc += f" (only when {describe(self.valid_when)})"
        s["description"] = desc
        return s

    def to_dict(self) -> dict:
        d = {"name": self.name, "type": self.type, "label": self.label, "group": self.group,
             "importance": self.importance, "valid_when": self.valid_when, "help": self.help,
             "default": self.default, "required": self.required}
        if self.type == "number":
            d.update(min=self.min, max=self.max, step=self.step, unit=self.unit, integer=self.integer)
        if self.type == "choice":
            d["options"] = list(self.options)
        if self.type == "id":
            d["kind"] = self.kind
        return d
