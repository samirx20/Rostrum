"""Checking a value against a Param: the rules per type, and the plain words when it is refused (see params.py)."""
from __future__ import annotations

import re

from . import colours
from .errors import RostrumError, codes, did_you_mean

TIME_UNITS = ("seconds", "beats", "marker")     # a time value is {"seconds": 1.5}, {"beats": 4} or {"marker": "drop"}
_LOOSE = re.compile(r"[\s_\-]+")


class CheckMixin:
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
