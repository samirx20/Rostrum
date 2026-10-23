"""The brush: the next stroke's settings. Screen state, not a document change (a stroke records what it was drawn
with). Its controls are built from `rostrum_paint.fields.BRUSH` exactly like the inspector from a field operation:
rows with valid_when / importance. The settings panel shows it two ways (painting design §2.1): the quick rows while
painting (`QUICK`, under the brush's own row), or every setting on "Edit brush ›" (`editing`). A brush starts as one
of the shipped presets (brush_presets.py); picking one sets every setting but the colour. The erase mode is the
Eraser tool (paint_tool.py), so the panel's Paints list leaves it out (`fields.BAR_VALUE`). No Qt.
"""
from __future__ import annotations

from types import SimpleNamespace

from rostrum_gui import rows
from rostrum_paint.fields import BAR_VALUE, BRUSH

from . import brush_presets


QUICK = ("size", "opacity", "color", "size_pressure", "opacity_pressure")   # the quick rows, in this order
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
        self.preset, self.editing = "", False
        self.apply_preset(brush_presets.DEFAULT)

    def _evaluated(self) -> list[dict]:
        return rows.evaluate(self._static, self.values, {}, True)

    def rows(self) -> list[dict]:
        """The settings panel's brush rows: the quick ones (no headings: the panel's Brush row heads them), or, while
        editing the brush, every setting but the colour (a quick row) and the seed (set once per stroke). A setting
        whose one value is a tool (mode's "erase": Eraser) keeps its other values here."""
        out = [r for r in self._evaluated() if r["row"] != "more"]
        for r in out:
            if r["row"] == "param" and r["id"] in BAR_VALUE:
                bar_value = BAR_VALUE[r["id"]]
                r["options"] = [o for o in r["options"] if o["value"] != bar_value]
                r["valid"] = r["valid"] and r["value"] != bar_value
        if self.editing:
            return rows.omit(out, {"color", "seed"})
        quick = [r for r in out if r["row"] == "param" and r["id"] in QUICK]
        return sorted(quick, key=lambda r: QUICK.index(r["id"]))

    def shown(self) -> tuple[list[str], list[str]]:
        return rows.shown(self.rows())

    def set(self, name: str, value):
        """Checked by the setting's own rules (out of range raises; never a silent clamp)."""
        self.values[name] = self._by_name[name].check(value, f"brush {name}")

    def apply_preset(self, pid: str):
        """Every setting of preset `pid`, checked like a typed one; the colour stays the person's."""
        for k, v in brush_presets.settings(pid).items():
            if k in self._by_name:
                self.set(k, v)
        self.preset = pid

    def stroke_args(self) -> dict:
        """The settings the next stroke is made with: only those that apply (a tip angle only when the tip does not
        follow the stroke), as the stroke operation insists."""
        return {r["id"]: r["value"] for r in self._evaluated() if r["row"] == "param" and r["holds"]}

    def label(self) -> str:
        return brush_presets.name(self.preset)
