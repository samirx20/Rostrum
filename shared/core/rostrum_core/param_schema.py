"""A Param written out for others: the MCP schema and the plain dict screens are built from (see params.py)."""
from __future__ import annotations

from . import colours


class SchemaMixin:
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
