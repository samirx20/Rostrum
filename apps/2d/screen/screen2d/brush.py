"""The brush: the next stroke's settings. Screen state, not a document change (a stroke records what it was drawn
with). The panel is built from `rostrum_paint.fields.BRUSH` exactly like the inspector from a field operation:
rows with valid_when / importance, most important first, deep settings behind More. No Qt.
"""
from __future__ import annotations

from types import SimpleNamespace

from rostrum_gui import rows
from rostrum_paint.fields import BRUSH


class Brush:
    def __init__(self):
        params = [p for p in getattr(BRUSH, "params", BRUSH) if p.type not in ("id", "points")]
        self._by_name = {p.name: p for p in params}
        self._static = rows.layout(SimpleNamespace(params=params))
        self.values = {p.name: p.default for p in params}
        self.more = False

    def rows(self) -> list[dict]:
        return rows.evaluate(self._static, self.values, {}, self.more)

    def shown(self) -> tuple[list[str], list[str]]:
        return rows.shown(self.rows())

    def set(self, name: str, value):
        """Checked by the setting's own rules (out of range raises; never a silent clamp)."""
        self.values[name] = self._by_name[name].check(value, f"brush {name}")

    def stroke_args(self) -> dict:
        """The settings the next stroke is made with: only those that apply (a tip angle only when the tip does not
        follow the stroke), as the stroke operation insists."""
        return {r["id"]: r["value"] for r in self.rows() if r["row"] == "param" and r["holds"]}

    def label(self) -> str:
        tip = self.values.get("brush")
        return f"{str(tip).capitalize()} brush" if tip else "Brush"
