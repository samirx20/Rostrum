"""The brush: the next stroke's settings. Screen state, not a document change (a stroke records what it was drawn
with). Its controls are built from `rostrum_paint.fields.BRUSH` exactly like the inspector from a field operation:
rows with valid_when / importance, most important first, deep settings behind More. Each setting shows in ONE place,
by the kit's own table (`fields.BAR`, `BAR_VALUE`): the context bar's few (`bar()`), or the settings panel (`rows()`).
No Qt.
"""
from __future__ import annotations

from types import SimpleNamespace

from rostrum_gui import rows
from rostrum_paint.fields import BAR, BAR_VALUE, BRUSH, FIELDS


LIGHT_INK = "#f2f2f2"          # the starting colour on a dark background (a light one keeps the setting's own default)


def starting_colour(background: str, default: str) -> str:
    """The first stroke has to show on the drawing: the brush setting's default on a light background, a light ink on
    a dark one. (Only where the brush starts; later it is whatever the person picked.)"""
    h = background.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return default
    return LIGHT_INK if 0.2126 * r + 0.7152 * g + 0.0722 * b < 0.5 else default


class Brush:
    def __init__(self, background: str = ""):
        params = [p for p in getattr(BRUSH, "params", BRUSH) if p.type not in ("id", "points")]
        self._by_name = {p.name: p for p in params}
        self._static = rows.layout(SimpleNamespace(params=params))
        self.values = {p.name: p.default for p in params}
        if "color" in self.values and background:
            self.values["color"] = starting_colour(background, self.values["color"])
        self.more = False

    def _evaluated(self) -> list[dict]:
        return rows.evaluate(self._static, self.values, {}, self.more)

    def rows(self) -> list[dict]:
        """The settings panel's rows: everything the bar doesn't show. A setting the bar shows by one value (mode's
        "erase": Eraser) keeps its other values here, and applies only while that value is not on."""
        out = self._evaluated()
        for r in out:
            if r["row"] == "param" and r["id"] in BAR_VALUE:
                bar_value = BAR_VALUE[r["id"]]
                r["options"] = [o for o in r["options"] if o["value"] != bar_value]
                r["valid"] = r["valid"] and r["value"] != bar_value
        return rows.omit(out, set(BAR))

    def bar(self, mark: str = "stroke") -> list[dict]:
        """The context bar's controls, in the bar's order: [{id, label, type, options, min, max, step, unit, value}];
        for a fill (`mark` "fill"), only those a fill has (its colour and opacity come from the brush)."""
        by_id = {r["id"]: r for r in self._evaluated() if r["row"] == "param" and r["holds"]}
        has = {p.name for p in FIELDS[mark]}
        keep = ("id", "label", "type", "options", "min", "max", "step", "unit", "value")
        return [{k: by_id[n][k] for k in keep} for n in BAR if n in by_id and n in has]

    def shown(self) -> tuple[list[str], list[str]]:
        return rows.shown(self.rows())

    def set(self, name: str, value):
        """Checked by the setting's own rules (out of range raises; never a silent clamp)."""
        self.values[name] = self._by_name[name].check(value, f"brush {name}")

    def stroke_args(self) -> dict:
        """The settings the next stroke is made with: only those that apply (a tip angle only when the tip does not
        follow the stroke), as the stroke operation insists."""
        return {r["id"]: r["value"] for r in self._evaluated() if r["row"] == "param" and r["holds"]}

    def label(self) -> str:
        tip = self.values.get("brush")
        return f"{str(tip).capitalize()} brush" if tip else "Brush"
